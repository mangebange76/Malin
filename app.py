# app.py
import streamlit as st
import json, random, math, re
from datetime import date, time, datetime, timedelta
import pandas as pd

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + per-profil-data + Sheets)")

# ======== Import av beräkning ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    from statistik import compute_stats
except Exception:
    compute_stats = None

# ======== State-nycklar ========
CFG_KEY        = "CFG"
ROWS_KEY       = "ROWS"
HIST_MM_KEY    = "HIST_MINMAX"
SCENEINFO_KEY  = "CURRENT_SCENE"
SCENARIO_KEY   = "SCENARIO"
PROFILE_KEY    = "PROFILE_NAME"
LAST_SAVED_WS  = "LAST_SAVED_WS"

# =========================
# Helpers: Secrets & Sheets
# =========================
def _get_gspread_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS/SHEET_URL).")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def _ensure_ws(ss, title, rows=4000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _list_profiles(ss):
    try:
        ws = _ensure_ws(ss, "Profil")
        vals = ws.col_values(1)
        return [v.strip() for v in vals if v and v.strip()]
    except Exception:
        return []

def _read_profile_settings(ss, profile_name):
    ws = _ensure_ws(ss, profile_name)
    allv = ws.get_all_values()
    if not allv:
        return {}
    # Header-detektion för "Nyckel/Värde" (valfritt)
    start_row = 1
    if allv and allv[0]:
        hdr = [h.strip().lower() for h in allv[0]]
        if "nyckel" in hdr and "värde" in hdr:
            start_row = 2
    settings = {}
    for row in allv[start_row-1:]:
        if len(row) < 2:
            continue
        k = str(row[0]).strip()
        v = str(row[1]).strip()
        if not k:
            continue
        if k in ("startdatum","fodelsedatum"):
            try:
                y,m,d = [int(x) for x in v.split("-")]
                settings[k] = date(y,m,d)
            except:
                settings[k] = v
        else:
            try:
                if "." in v:
                    settings[k] = float(v)
                else:
                    settings[k] = int(v)
            except:
                vv = v.strip().lower()
                if vv in ("true","ja","1","on","yes"):
                    settings[k] = 1
                elif vv in ("false","nej","0","off","no"):
                    settings[k] = 0
                else:
                    settings[k] = v
    return settings

def _normalize_title(s: str) -> str:
    # ner till gemener + ta bort mellanrum, _ , bindestreck (inkl. en/em-dash) och punkter
    return re.sub(r"[ \t\-\u2013\u2014_\.]+", "", s.strip().lower())

def _find_profile_data_ws(ss, profile_name):
    """
    Hitta rätt data-blad:
    - Matcha valfritt blad där både 'data' och profilnamnet förekommer (oavsett tecken mellan)
      ex. 'Data - Malin Andren', 'Malin Andren – Data', 'DATA_MALIN ANDREN' osv.
    - I andra hand: Data_<profil>, <profil>_Data, Data <profil>
    - I sista hand: 'Data' (globalt) — men då filtrerar vi på kolumnen 'Profil'
    - Om inget hittas: skapa 'Data - <profil>'
    """
    wanted = "data" + _normalize_title(profile_name)
    sheets = ss.worksheets()

    # 1) Sök efter båda orden i titeln
    prof_norm = _normalize_title(profile_name)
    best = None
    for ws in sheets:
        t = ws.title
        t_norm = _normalize_title(t)
        if "data" in t_norm and prof_norm in t_norm:
            best = ws
            break
    if best:
        return best, best.title

    # 2) Klassiska kandidater
    candidates = [
        f"Data_{profile_name}",
        f"{profile_name}_Data",
        f"Data {profile_name}",
        f"Data - {profile_name}",
        "Data",
    ]
    for title in candidates:
        try:
            ws = ss.worksheet(title)
            return ws, title
        except Exception:
            continue

    # 3) Skapa
    new_title = f"Data - {profile_name}"
    ws = _ensure_ws(ss, new_title)
    return ws, new_title

def _read_profile_data(ss, profile_name):
    ws, title = _find_profile_data_ws(ss, profile_name)
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(), title

    KNOWN = set([
        "Datum","Veckodag","Scen","Typ","Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","DT tid (sek/kille)","DT vila (sek/kille)","Vila",
        "Älskar","Sover med","Bonus deltagit","Personal deltagit","Händer aktiv",
        "Känner","Totalt Män","Prenumeranter","Hårdhet","Intäkter","Intäkt Känner",
        "Kostnad män","Intäkt företag","Lön Malin","Vinst","Profil"
    ])

    # hitta header-rad (första rad med >=3 kända rubriker)
    header_idx, header = None, None
    for i, row in enumerate(values):
        row_stripped = [c.strip() for c in row]
        hits = sum(1 for c in row_stripped if c in KNOWN)
        if hits >= 3:
            header_idx = i
            header = row_stripped
            break
    if header_idx is None:
        header_idx, header = 0, [c.strip() for c in values[0]]

    # bygg records från alla efterföljande rader
    data_rows = values[header_idx+1:]
    records = []
    for r in data_rows:
        if not any(str(c).strip() for c in r):
            continue
        row = list(r) + [""] * (len(header) - len(r))
        row = [str(c).strip() for c in row[:len(header)]]
        records.append({header[j]: row[j] for j in range(len(header))})
    df = pd.DataFrame(records)

    # Om det blev gemensamma "Data": filtrera på Profil-kolumnen (om den finns)
    if not df.empty and title.lower() == "data" and "Profil" in df.columns:
        df["Profil_norm"] = df["Profil"].astype(str).str.strip().str.lower()
        prof_norm = str(profile_name).strip().lower()
        df = df[df["Profil_norm"] == prof_norm].drop(columns=["Profil_norm"])

    # ta bort helt tomma kolumner
    if not df.empty:
        empty_cols = [c for c in df.columns if df[c].astype(str).str.strip().eq("").all()]
        df = df.drop(columns=empty_cols)

    return df.reset_index(drop=True), title

def _save_settings_to_profile(ss, profile_name, cfg: dict):
    ws = _ensure_ws(ss, profile_name)
    rows = []
    for k,v in cfg.items():
        vv = v.strftime("%Y-%m-%d") if isinstance(v, (date, datetime)) else v
        rows.append([k, str(vv)])
    ws.clear()
    ws.update("A1", [["Nyckel","Värde"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def _append_row_to_profile_data(ss, profile_name, row_dict: dict):
    ws, title = _find_profile_data_ws(ss, profile_name)
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)
    return title

# =========================
# Input-ordning (EXAKT)
# =========================
INPUT_ORDER = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_hander","in_nils"
]

# =========================
# Init state
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,
            "BONUS_AVAILABLE": 500,
            "BONUS_PCT": 1.0,  # %
            "ESK_MIN": 20, "ESK_MAX": 40,
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",
        }
    if ROWS_KEY not in st.session_state:       st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:    st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:   st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:    st.session_state[PROFILE_KEY] = ""
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander":1
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# =========================
# Hjälpare: min/max + slump
# =========================
def _add_hist_value(col, v):
    try: v = int(v)
    except: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm: st.session_state[HIST_MM_KEY][col] = (min(mm[0],v), max(mm[1],v))
    else:  st.session_state[HIST_MM_KEY][col] = (v, v)

def _max_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return max(mm[0], mm[1])
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(r.get(colname, 0)))
        except: pass
    return max(vals) if vals else 0

def _rand_up_to_max(colname: str):
    hi = _max_from_hist(colname)
    return random.randint(1, hi) if hi > 0 else 0

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]
    keep = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander":st.session_state.get("in_hander",1)}
    for k in INPUT_ORDER: st.session_state[k] = keep.get(k, 0)

    if s == "Ny scen": return

    LBL_P = CFG["LBL_PAPPAN"]; LBL_G = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_B = CFG["LBL_BEKANTA"]

    def _slumpa_kallor():
        st.session_state["in_pappan"]      = _rand_up_to_max(LBL_P)
        st.session_state["in_grannar"]     = _rand_up_to_max(LBL_G)
        st.session_state["in_nils_vanner"] = _rand_up_to_max(LBL_NV)
        st.session_state["in_nils_familj"] = _rand_up_to_max(LBL_NF)
        st.session_state["in_bekanta"]     = _rand_up_to_max(LBL_B)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))

    def _slumpa_sex():
        for k in ["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
            col = k.split("_",1)[1].upper()
            st.session_state[k] = _rand_up_to_max(col)

    if s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_up_to_max("MÄN")
        _slumpa_sex(); _slumpa_kallor()
        st.session_state["in_alskar"] = 8; st.session_state["in_sover"] = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_up_to_max("SVARTA")
        _slumpa_sex(); _slumpa_kallor()
        st.session_state["in_alskar"] = 8; st.session_state["in_sover"] = 1

    elif s == "Vila på jobbet":
        _slumpa_sex(); _slumpa_kallor()
        st.session_state["in_alskar"] = 12; st.session_state["in_sover"] = 1

    elif s == "Vila i hemmet (dag 1–7)":
        _slumpa_sex(); _slumpa_kallor()
        st.session_state["in_alskar"] = 6; st.session_state["in_sover"] = 0; st.session_state["in_nils"] = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel (Profiler + Inställningar)
# =========================
CFG = st.session_state[CFG_KEY]

with st.sidebar:
    st.header("Profil")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets and "SHEET_URL" in st.secrets
    if has_creds:
        try:
            ss = _get_gspread_client()
            profiles = _list_profiles(ss)
        except Exception as e:
            profiles, ss = [], None
            st.error(f"Kunde inte läsa profil-lista: {e}")
    else:
        profiles, ss = [], None
        st.warning("Lägg in GOOGLE_CREDENTIALS och SHEET_URL i Secrets.")

    if profiles:
        current = st.session_state.get(PROFILE_KEY, profiles[0])
        sel = st.selectbox("Välj profil", options=profiles,
                           index=profiles.index(current) if current in profiles else 0, key=PROFILE_KEY)
    else:
        sel = st.text_input("Profil (manuell)", value=st.session_state.get(PROFILE_KEY,""))
        st.session_state[PROFILE_KEY] = sel

    st.markdown("---")
    colA, colB = st.columns(2)
    with colA:
        if st.button("📥 Läs in profilens inställningar"):
            if not has_creds or not ss or not sel:
                st.error("Saknar Sheets/secrets eller profil.")
            else:
                settings = _read_profile_settings(ss, sel)
                for k,v in settings.items(): st.session_state[CFG_KEY][k] = v
                st.success("✅ Inställningar (profil) inlästa.")
                CFG = st.session_state[CFG_KEY]
    with colB:
        if st.button("📥 Läs in profilens data"):
            if not has_creds or not ss or not sel:
                st.error("Saknar Sheets/secrets eller profil.")
            else:
                df, used_title = _read_profile_data(ss, sel)
                st.session_state[ROWS_KEY] = df.to_dict("records") if not df.empty else []
                st.session_state[HIST_MM_KEY] = {}
                for r in st.session_state[ROWS_KEY]:
                    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                                CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                        _add_hist_value(col, r.get(col, 0))
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"✅ Läste {len(st.session_state[ROWS_KEY])} rader från blad: **{used_title}**.")

    st.caption("Tips: Bladet kan heta t.ex. **Data - <Profil>** eller **<Profil> - Data** — båda hittas.")

    st.markdown("---")
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG.get('BONUS_AVAILABLE',0))}")
    CFG["BONUS_PCT"] = st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0,
                                       value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1)

    st.markdown("---")
    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG["MAX_PAPPAN"]), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG["MAX_GRANNAR"]), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG["MAX_NILS_VANNER"]), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG["MAX_NILS_FAMILJ"]), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG["MAX_BEKANTA"]), step=1)

    st.markdown("---")
    st.subheader("Egna etiketter (slår igenom i input/live)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG["LBL_ESK"])

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

    st.markdown("---")
    st.subheader("Spara inställningar")
    if st.button("💾 Spara inställningar till profilblad"):
        try:
            if not has_creds or not ss or not sel:
                st.error("Saknar Sheets/secrets eller profil.")
            else:
                _save_settings_to_profile(ss, sel, CFG)
                st.success("✅ Inställningar sparade till profilens blad.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

# =========================
# Inmatning (etiketter)
# =========================
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)
LBL_P = CFG["LBL_PAPPAN"]; LBL_G = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_B = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{LBL_P} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{LBL_G} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{LBL_NV} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{LBL_NF} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{LBL_B} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{LBL_ESK} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG.get('BONUS_AVAILABLE',0))})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_hander":"Händer aktiv (0/1)",
    "in_nils":"Nils (0/1/2)"
}

with c1:
    for key in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap","in_tid_s","in_tid_d","in_vila"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
with c2:
    st.number_input(labels["in_dt_tid"], min_value=0, step=1, key="in_dt_tid")
    st.number_input(labels["in_dt_vila"], min_value=0, step=1, key="in_dt_vila")
    st.number_input(labels["in_alskar"], min_value=0, step=1, key="in_alskar")
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_bonus_deltagit"], min_value=0, step=1, key="in_bonus_deltagit")
    st.number_input(labels["in_personal_deltagit"], min_value=0, step=1, key="in_personal_deltagit")
    st.number_input(labels["in_hander"], min_value=0, max_value=1, step=1, key="in_hander")
    st.number_input(labels["in_nils"], min_value=0, step=1, key="in_nils")

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        CFG["LBL_PAPPAN"]: st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]: st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        CFG["LBL_ESK"]: st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv": st.session_state["in_hander"],
        "Nils":    st.session_state["in_nils"],

        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
        # etiketter skickas med så beräkning kan läsa rätt nycklar vid behov
        "LBL_PAPPAN": CFG["LBL_PAPPAN"],
        "LBL_GRANNAR": CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER": CFG["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ": CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": CFG["LBL_BEKANTA"],
        "LBL_ESK": CFG["LBL_ESK"],
    }
    base["Känner"] = int(base[CFG["LBL_PAPPAN"]]) + int(base[CFG["LBL_GRANNAR"]]) + int(base[CFG["LBL_NILS_VANNER"]]) + int(base[CFG["LBL_NILS_FAMILJ"]])
    base["_rad_datum"]    = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# =========================
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

tot_men_incl = (
    int(base.get("Män",0)) + int(base.get("Svarta",0)) +
    int(base.get(CFG["LBL_PAPPAN"],0)) + int(base.get(CFG["LBL_GRANNAR"],0)) +
    int(base.get(CFG["LBL_NILS_VANNER"],0)) + int(base.get(CFG["LBL_NILS_FAMILJ"],0)) +
    int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0)) +
    int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
)

rad_datum = preview.get("Datum", base["Datum"])
veckodag  = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try: _d = datetime.fromisoformat(rad_datum).date()
    except: _d = datetime.today().date()
else:
    _d = datetime.today().date()

fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille","-"))
    st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
with c3:
    st.metric("Klockan", preview.get("Klockan","-"))
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
with c6:
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))

st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
with e2:
    st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
with e3:
    st.metric("Kostnad män", f"${float(preview.get('Kostnad män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(CFG["LBL_PAPPAN"], int(base.get(CFG["LBL_PAPPAN"],0)))
with k2: st.metric(CFG["LBL_GRANNAR"], int(base.get(CFG["LBL_GRANNAR"],0)))
with k3: st.metric(CFG["LBL_NILS_VANNER"], int(base.get(CFG["LBL_NILS_VANNER"],0)))
with k4: st.metric(CFG["LBL_NILS_FAMILJ"], int(base.get(CFG["LBL_NILS_FAMILJ"],0)))
with k5: st.metric(CFG["LBL_BEKANTA"], int(base.get(CFG["LBL_BEKANTA"],0)))
with k6: st.metric(CFG["LBL_ESK"], int(base.get(CFG["LBL_ESK"],0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_incl)

st.caption("Obs: Vila-scenarion ger 0 pren/0 intäkt/0 kostnad/0 lön/0 vinst. Bonus: +% av pren för icke-vila, minus 'Bonus deltagit' alltid.")

# =========================
# Spara lokalt + Sheets
# =========================
st.markdown("---")

def _after_save_housekeeping(preview_row: dict, profile: str):
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
        _add_hist_value(col, preview_row.get(col, 0))

    bonus_pct = float(CFG.get("BONUS_PCT", 1.0)) / 100.0
    scen_typ = str(preview_row.get("Typ","")).lower()
    add_from_pren = 0 if scen_typ.startswith("vila") else int(math.floor(int(preview_row.get("Prenumeranter",0)) * bonus_pct))
    used = int(preview_row.get("Bonus deltagit",0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE",0)) + add_from_pren - used)

    st.session_state["in_bonus_deltagit"] = 0
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

cL, cR = st.columns([1,1])
with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _after_save_housekeeping(preview, st.session_state.get(PROFILE_KEY,""))
        st.success("✅ Sparad i minnet (aktuella profilen).")

def _save_row_to_sheets(preview_row: dict, profile: str):
    if not profile:
        raise RuntimeError("Ingen profil vald.")
    ss = _get_gspread_client()
    row_to_save = dict(preview_row)
    row_to_save["Profil"] = profile
    title = _append_row_to_profile_data(ss, profile, row_to_save)
    st.session_state[LAST_SAVED_WS] = title

with cR:
    if st.button("📤 Spara raden till Google Sheets (profilens data)"):
        try:
            prof = st.session_state.get(PROFILE_KEY,"")
            if not prof:
                st.error("Välj/skriv en profil först.")
            else:
                _save_row_to_sheets(preview, prof)
                st.session_state[ROWS_KEY].append(preview)
                _after_save_housekeeping(preview, prof)
                st.success(f"✅ Sparad till {st.session_state.get(LAST_SAVED_WS,'(okänd)')} (endast denna profil).")
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade för vald profil)")
if st.session_state[ROWS_KEY]:
    st.dataframe(pd.DataFrame(st.session_state[ROWS_KEY]), use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu för denna profil.")

# =========================
# Statistik
# =========================
st.markdown("---")
st.subheader("📈 Statistik (hela den laddade profildatan)")
if compute_stats and st.button("Beräkna statistik"):
    try:
        rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
        stats = compute_stats(rows_df, CFG) if "cfg" in compute_stats.__code__.co_varnames else compute_stats(rows_df)
        if isinstance(stats, dict) and stats:
            for k,v in stats.items(): st.write(f"**{k}:** {v}")
        else:
            st.info("Inga statistikvärden returnerades.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
else:
    st.caption("Lägg valfri statistik i statistik.py (compute_stats).")
