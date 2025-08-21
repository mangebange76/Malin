import streamlit as st
import json
import random
import pandas as pd
from datetime import date, time, datetime, timedelta

# ============================================================
#  Grundinställningar
# ============================================================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (Profiler + Sheets + scenarion)")

# ============================================================
#  Nycklar i session_state
# ============================================================
CFG_KEY        = "CFG"             # alla config/etiketter/parametrar
PROFILE_KEY    = "PROFILE"         # aktiv profil
ROWS_KEY       = "ROWS"            # list[dict] – lokalt cacheade rader
HIST_MM_KEY    = "HIST_MINMAX"     # historiska min/max per kolumn
SCENEINFO_KEY  = "CURRENT_SCENE"   # (nr, datum, veckodag)
SCENARIO_KEY   = "SCENARIO"        # valt scenario i rullisten

# ============================================================
#  Försök importera dina riktiga beräkningar
# ============================================================
try:
    from berakningar import calc_row_values as _calc_row_values_external
except Exception:
    _calc_row_values_external = None

# ============================================================
#  Google Sheets-koppling
# ============================================================
def _get_gspread_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")
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

def _sheet_exists(ss, title: str) -> bool:
    import gspread
    try:
        ss.worksheet(title)
        return True
    except gspread.WorksheetNotFound:
        return False

# ------------------------------------------------------------
# Profil-lista (från fliken "Profil", kolumn A)
# ------------------------------------------------------------
def _load_profiles_list(ss) -> list:
    try:
        ws = _ensure_ws(ss, "Profil")
        names = ws.col_values(1)
        return [n.strip() for n in names if str(n).strip()]
    except Exception as e:
        st.error(f"Kunde inte läsa profil-lista: {e}")
        return []

# ------------------------------------------------------------
# Läs/Skriv profilens inställningar (Key/Value i blad med profilens namn)
# ------------------------------------------------------------
def _load_profile_cfg(ss, profile: str) -> dict:
    """Returnerar dict av Key/Value från blad med namnet = profile (om det finns)."""
    out = {}
    try:
        ws = _ensure_ws(ss, profile)
        rows = ws.get_all_values()
        # Om första raden är header "Key","Value", hoppa den
        if rows and rows[0][:2] == ["Key", "Value"]:
            data_rows = rows[1:]
        else:
            data_rows = rows
        for row in data_rows:
            if not row:
                continue
            key = str(row[0]).strip() if len(row) > 0 else ""
            if not key:
                continue
            val = row[1] if len(row) > 1 else ""
            # försök typkonvertera
            if key in ("startdatum","fodelsedatum"):
                try:
                    y,m,d = [int(x) for x in str(val).split("-")]
                    out[key] = date(y,m,d)
                    continue
                except Exception:
                    pass
            try:
                if isinstance(val, str) and "." in val:
                    out[key] = float(val)
                else:
                    out[key] = int(val)
            except Exception:
                out[key] = val
    except Exception as e:
        st.warning(f"Kunde inte läsa profilens inställningar ({profile}): {e}")
    return out

def _save_profile_cfg(ss, profile: str, cfg: dict):
    """Skriv Key/Value till blad med profilens namn (rensar och skriver hela cfg)."""
    ws = _ensure_ws(ss, profile)
    rows = []
    for k, v in cfg.items():
        if isinstance(v, (date, datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([k, str(v)])
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

# ------------------------------------------------------------
# Välj rätt data-blad för profilen (dedikerat vs. gemensamt)
# ------------------------------------------------------------
def _resolve_data_target(ss, profile: str):
    """
    Returnerar (mode, worksheet):
      mode="dedicated" => Eget blad (Data_<profil> / Data <profil> / <profil>_Data / explicit DATA_SHEET)
      mode="shared"    => Gemensamt blad 'Data' med kolumn 'Profil'
    Prioritet:
      1) DATA_SHEET i profilens inställningar/CFG
      2) Data_<profil>
      3) Data <profil>
      4) <profil>_Data
      5) Data (shared)
      6) Skapa Data_<profil>
    """
    # 1) explicit
    explicit = st.session_state[CFG_KEY].get("DATA_SHEET")
    if not explicit:
        try:
            prof_cfg = _load_profile_cfg(ss, profile)
            if prof_cfg.get("DATA_SHEET"):
                explicit = str(prof_cfg["DATA_SHEET"])
                st.session_state[CFG_KEY]["DATA_SHEET"] = explicit
        except Exception:
            pass

    if explicit:
        try:
            ws = ss.worksheet(str(explicit))
            if str(explicit).strip().lower() == "data":
                return ("shared", ws)
            return ("dedicated", ws)
        except Exception:
            pass

    # 2–4) heuristik
    for candidate in (f"Data_{profile}", f"Data {profile}", f"{profile}_Data"):
        try:
            ws = ss.worksheet(candidate)
            return ("dedicated", ws)
        except Exception:
            continue

    # 5) shared
    try:
        ws = ss.worksheet("Data")
        return ("shared", ws)
    except Exception:
        pass

    # 6) skapa nytt dedikerat
    ws = _ensure_ws(ss, f"Data_{profile}")
    return ("dedicated", ws)

def _load_profile_rows(ss, profile: str) -> pd.DataFrame:
    """Läser rader för profilen ur dedikerat eller gemensamt blad."""
    mode, ws = _resolve_data_target(ss, profile)
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    if mode == "shared":
        if "Profil" in df.columns:
            return df[df["Profil"].astype(str) == str(profile)].copy()
        return pd.DataFrame(columns=df.columns)
    return df

def _append_row_to_profile(ss, profile: str, row_dict: dict):
    """Append rad till rätt blad; säkerställer header och 'Profil' vid shared."""
    mode, ws = _resolve_data_target(ss, profile)
    row_to_write = dict(row_dict)
    if mode == "shared":
        row_to_write["Profil"] = profile
    header = ws.row_values(1)
    if not header:
        header = list(row_to_write.keys())
        ws.update("A1", [header])
    values = [row_to_write.get(col, "") for col in header]
    ws.append_row(values)

# ------------------------------------------------------------
# Historik min/max & slump
# ------------------------------------------------------------
def _rebuild_hist_from_rows(cfg: dict):
    """Bygg om HIST_MINMAX från st.session_state[ROWS_KEY] och aktuella etiketter."""
    st.session_state[HIST_MM_KEY] = {}
    label_cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"],
        cfg["LBL_NILS_FAMILJ"], cfg["LBL_BEKANTA"], cfg["LBL_ESK"]
    ]
    for r in st.session_state.get(ROWS_KEY, []):
        for col in label_cols:
            try:
                v = int(r.get(col, 0))
            except Exception:
                v = 0
            mn, mx = st.session_state[HIST_MM_KEY].get(col, (v, v))
            st.session_state[HIST_MINMAX := HIST_MM_KEY][col] = (min(mn, v), max(mx, v))

def _rand_1_to_max(colname: str) -> int:
    """Slumpa 1..historiskt MAX (om max<=0 -> 0)."""
    mn, mx = st.session_state.get(HIST_MM_KEY, {}).get(colname, (0, 0))
    if mx <= 0:
        return 0
    return random.randint(1, mx)

# ============================================================
#  Exakt input-ordning
# ============================================================
INPUT_ORDER = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_nils","in_hander_aktiv"
]

# ============================================================
#  Initiera state
# ============================================================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # Bas
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),
            # Ekonomi/bonus
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,
            "BONUS_PERCENT": 1.0,     # % av prenumeranter som ger bonus-killar
            "BONUS_AVAILABLE": 0,     # antal kvar (räknas upp/ner)
            # Eskilstuna-intervall
            "ESK_MIN": 20, "ESK_MAX": 40,
            # Maxvärden (källor)
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
            # Etiketter
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",
            # Data-blad explicit (valfritt)
            "DATA_SHEET": ""
        }
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, 0)
    if st.session_state.get("in_hander_aktiv", None) is None:
        st.session_state["in_hander_aktiv"] = 1  # default på
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# ============================================================
#  Scenarioknappar (slump 1..MAX) + 'Vila'-nollning i liven/spar
# ============================================================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s   = st.session_state[SCENARIO_KEY]

    # Nolla allt (behåll tid-standarder)
    defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_aktiv":1}
    for k in INPUT_ORDER:
        st.session_state[k] = defaults.get(k, 0)

    if s == "Ny scen":
        return

    # Hjälpare: slumpa källor via etiketter
    def _slumpa_kallor():
        st.session_state["in_pappan"]       = _rand_1_to_max(CFG["LBL_PAPPAN"])
        st.session_state["in_grannar"]      = _rand_1_to_max(CFG["LBL_GRANNAR"])
        st.session_state["in_nils_vanner"]  = _rand_1_to_max(CFG["LBL_NILS_VANNER"])
        st.session_state["in_nils_familj"]  = _rand_1_to_max(CFG["LBL_NILS_FAMILJ"])
        st.session_state["in_bekanta"]      = _rand_1_to_max(CFG["LBL_BEKANTA"])
        st.session_state["in_eskilstuna"]   = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))

    def _slumpa_sexuella():
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_max(f)

    if s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_1_to_max("Män")
        _slumpa_sexuella()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_1_to_max("Svarta")
        _slumpa_sexuella()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        _slumpa_sexuella()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        # ekonomi nollas i liven/spar

    elif s == "Vila i hemmet (dag 1–7)":
        _slumpa_sexuella()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        # ekonomi nollas i liven/spar

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ============================================================
#  Sidopanel: Profilval, inläsning, inställningar
# ============================================================
CFG = st.session_state[CFG_KEY]

with st.sidebar:
    st.subheader("📁 Profil")
    profiles = []
    try:
        ss = _get_gspread_client()
        profiles = _load_profiles_list(ss)
    except Exception as e:
        st.warning(f"Kan inte läsa profiler ännu: {e}")
    if profiles:
        current = st.session_state.get(PROFILE_KEY, "")
        idx = profiles.index(current) if current in profiles else 0
        selected = st.selectbox("Välj profil", options=profiles, index=idx)
        st.session_state[PROFILE_KEY] = selected
    else:
        st.info("Lägg upp profiler i fliken 'Profil' (kolumn A).")

    colA, colB = st.columns(2)
    with colA:
        if st.button("📥 Läs in PROFILENS inställningar", use_container_width=True, disabled=not profiles):
            try:
                ss = _get_gspread_client()
                prof_cfg = _load_profile_cfg(ss, st.session_state[PROFILE_KEY])
                if prof_cfg:
                    st.session_state[CFG_KEY].update(prof_cfg)
                    st.success("Inställningar inlästa från profilbladet.")
                else:
                    st.info("Profilbladet var tomt (Key/Value).")
            except Exception as e:
                st.error(f"Kunde inte läsa profil-inställningar: {e}")
    with colB:
        if st.button("📥 Läs in PROFILENS data", use_container_width=True, disabled=not profiles):
            try:
                ss = _get_gspread_client()
                df = _load_profile_rows(ss, st.session_state[PROFILE_KEY])
                st.session_state[ROWS_KEY] = df.to_dict("records")
                # BONUS_AVAILABLE – om saknas i profilens inställningar, räkna från data
                if "BONUS_AVAILABLE" not in st.session_state[CFG_KEY]:
                    try:
                        pct = float(st.session_state[CFG_KEY].get("BONUS_PERCENT", 1.0))
                        tot_pren = pd.to_numeric(df.get("Prenumeranter", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
                        gen = int((tot_pren * pct) // 100)
                        delt = pd.to_numeric(df.get("Bonus deltagit", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
                        st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(0, int(gen - delt))
                    except Exception:
                        st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = 0
                _rebuild_hist_from_rows(st.session_state[CFG_KEY])
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"Läste {len(st.session_state[ROWS_KEY])} rader för profilen.")
            except Exception as e:
                st.error(f"Kunde inte läsa profilens data: {e}")

    if st.button("💾 Spara PROFILENS inställningar", use_container_width=True, disabled=not profiles):
        try:
            ss = _get_gspread_client()
            _save_profile_cfg(ss, st.session_state[PROFILE_KEY], st.session_state[CFG_KEY])
            st.success("Profilens inställningar sparade.")
        except Exception as e:
            st.error(f"Kunde inte spara profil-inställningar: {e}")

    st.markdown("---")
    st.subheader("🔐 Google Sheets")
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if 'GOOGLE_CREDENTIALS' in st.secrets else '❌'}")
    st.write(f"SHEET_URL: {'✅' if 'SHEET_URL' in st.secrets else '❌'}")

    st.markdown("---")
    st.subheader("🛠️ Inställningar (lokalt, kan sparas till profil)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    CFG["BONUS_PERCENT"]   = st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0, step=0.1, value=float(CFG.get("BONUS_PERCENT",1.0)))
    st.caption("Andel av nya prenumeranter som genererar 'Bonus killar'.")
    st.markdown(f"**Bonus killar kvar:** {int(CFG.get('BONUS_AVAILABLE',0))}")

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
    st.subheader("Egna etiketter (slår igenom)")
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

# ============================================================
#  Inmatning (exakt ordning, etiketter från inställningar)
# ============================================================
st.subheader("Input (exakt ordning)")
c1, c2 = st.columns(2)

LBL_PAPPAN = CFG["LBL_PAPPAN"]
LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]
LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"]
LBL_ESK = CFG["LBL_ESK"]

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{LBL_PAPPAN} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{LBL_GRANNAR} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{LBL_NV} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{LBL_NF} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{LBL_BEK} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{LBL_ESK} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG.get('BONUS_AVAILABLE',0))})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_nils":"Nils (0/1/2)",
    "in_hander_aktiv":"Händer aktiv (0/1)"
}

with c1:
    for key in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap","in_tid_s","in_tid_d","in_vila"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

with c2:
    for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna","in_bonus_deltagit","in_personal_deltagit","in_nils","in_hander_aktiv"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# ============================================================
#  Bygg basrad
# ============================================================
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
        # källor – etiketter som kolumnnamn
        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],
        # övrigt
        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Nils":    st.session_state["in_nils"],
        "Händer aktiv": st.session_state["in_hander_aktiv"],
        # meta för beräkning
        "_rad_datum": st.session_state[SCENEINFO_KEY][1],
        "_fodelsedatum": st.session_state[CFG_KEY]["fodelsedatum"],
        "_starttid":     st.session_state[CFG_KEY]["starttid"],
        # för fallback-beräkning (labels + max)
        "LBL_PAPPAN": CFG["LBL_PAPPAN"], "LBL_GRANNAR": CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER": CFG["LBL_NILS_VANNER"], "LBL_NILS_FAMILJ": CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": CFG["LBL_BEKANTA"], "LBL_ESK": CFG["LBL_ESK"],
        "MAX_PAPPAN": int(CFG.get("MAX_PAPPAN",0)), "MAX_GRANNAR": int(CFG.get("MAX_GRANNAR",0)),
        "MAX_NILS_VANNER": int(CFG.get("MAX_NILS_VANNER",0)), "MAX_NILS_FAMILJ": int(CFG.get("MAX_NILS_FAMILJ",0)),
        # ekonomi-parametrar
        "Avgift":     float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
        "BONUS_PERCENT": float(CFG.get("BONUS_PERCENT",1.0))
    }
    # Känner
    base["Känner"] = int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) + int(base[LBL_NV]) + int(base[LBL_NF])
    return base

# ============================================================
#  Live + beräkning
# ============================================================
st.markdown("---")
st.subheader("🔎 Live")

def _calc_row(base):
    # Använd extern modul om den finns, annars fallback
    if _calc_row_values_external is not None:
        try:
            out = _calc_row_values_external(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
        except TypeError:
            out = _calc_row_values_external(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])
        # Säkerställ att "Tid per kille" inkluderar händer om extern modul inte gjort det:
        if "Händer per kille (sek)" in out and "Tid per kille (sek)" in out:
            tpk = float(out.get("Tid per kille (sek)", 0))
            tpk += float(out.get("Händer per kille (sek)", 0))
            # skriv även om visningsfält
            out["Tid per kille (sek)"] = tpk
        return out
    else:
        # ---- Minimal fallback-beräkning (inkl. Suger/Händer) ----
        def _safe_int(x): 
            try: return int(x)
            except: return 0
        def _safe_float(x):
            try: return float(x)
            except: return 0.0
        def _mmss(s):
            try:
                s = max(0,int(round(s)))
                m,s = divmod(s,60)
                return f"{m}:{s:02d}"
            except: return "-"
        def _hhmm(s):
            try:
                s = max(0,int(round(s)))
                h,s = divmod(s,3600)
                m,_ = divmod(s,60)
                return f"{h:02d}:{m:02d}"
            except: return "-"

        man = _safe_int(base.get("Män",0)); svarta=_safe_int(base.get("Svarta",0))
        fitta=_safe_int(base.get("Fitta",0)); rumpa=_safe_int(base.get("Rumpa",0))
        dp=_safe_int(base.get("DP",0)); dpp=_safe_int(base.get("DPP",0)); dap=_safe_int(base.get("DAP",0)); tap=_safe_int(base.get("TAP",0))
        # källor med etiketter
        pappan=_safe_int(base.get(LBL_PAPPAN,0)); grannar=_safe_int(base.get(LBL_GRANNAR,0))
        nv=_safe_int(base.get(LBL_NV,0)); nf=_safe_int(base.get(LBL_NF,0)); bek=_safe_int(base.get(LBL_BEK,0)); esk=_safe_int(base.get(LBL_ESK,0))
        bonus_d=_safe_int(base.get("Bonus deltagit",0)); pers_d=_safe_int(base.get("Personal deltagit",0))
        tid_s=_safe_int(base.get("Tid S",0)); tid_d=_safe_int(base.get("Tid D",0)); dt_tid=_safe_int(base.get("DT tid (sek/kille)",0))
        hander_on=_safe_int(base.get("Händer aktiv",1))
        # känner
        kanner = pappan+grannar+nv+nf
        totalt = man + kanner + svarta + bek + esk + bonus_d + pers_d
        summa_s = tid_s*(fitta+rumpa) + dt_tid*totalt
        summa_d = tid_d*(dp+dpp+dap)
        summa_tp= tid_d*tap
        summa = max(0, summa_s+summa_d+summa_tp)
        # per-kille tider
        tot_for_hang = man+svarta+bek+esk+bonus_d+pers_d
        hang_pk = 0 if tot_for_hang<=0 else 10800.0/tot_for_hang
        if totalt>0:
            tpk_base = (summa_s + 2*summa_d + 3*summa_tp)/totalt
            suger_pk = 0.8*(summa_s/totalt) + 0.8*(summa_d/totalt) + 0.8*(summa_tp/totalt)
        else:
            tpk_base=0.0; suger_pk=0.0
        hander_pk = 2.0*suger_pk if hander_on else 0.0
        # Tid per kille inkluderar händer
        tpk_total = tpk_base + hander_pk
        # klockan
        try:
            base_dt = datetime.combine(base["_rad_datum"], base["_starttid"])
            klock = (base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa)).strftime("%H:%M")
            klock2= (base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa + 20*60*( _safe_int(base.get("Älskar",0))+_safe_int(base.get("Sover med",0)) )) ).strftime("%H:%M")
        except Exception:
            klock="-"; klock2="-"
        out = {
            "Datum": base.get("Datum",""), "Veckodag": base.get("Veckodag",""),
            "Totalt Män": totalt, "Känner": kanner,
            "Känner sammanlagt": _safe_int(base.get("MAX_PAPPAN",0))+_safe_int(base.get("MAX_GRANNAR",0))+_safe_int(base.get("MAX_NILS_VANNER",0))+_safe_int(base.get("MAX_NILS_FAMILJ",0)),
            "Summa S (sek)": int(summa_s), "Summa D (sek)": int(summa_d), "Summa TP (sek)": int(summa_tp),
            "Summa tid (sek)": int(summa), "Summa tid": _hhmm(summa),
            "Tid per kille (sek)": float(tpk_total), "Tid per kille": _mmss(tpk_total),
            "Hångel (sek/kille)": float(hang_pk), "Hångel (m:s/kille)": _mmss(hang_pk),
            "Suger per kille (sek)": float(suger_pk), "Händer per kille (sek)": float(hander_pk), "Händer aktiv": int(1 if hander_on else 0),
            "Suger": int(summa),
            "Tid Älskar (sek)": int(20*60*( _safe_int(base.get("Älskar",0))+_safe_int(base.get("Sover med",0)) )),
            "Klockan": klock, "Klockan inkl älskar/sover": klock2,
            # ekonomi nollas för 'Vila' senare
            "Prenumeranter": 0, "Hårdhet": 0, "Intäkter": 0.0, "Intäkt Känner": 0.0,
            "Kostnad män": 0.0, "Lön Malin": 0.0, "Vinst": 0.0, "Intäkt företag": 0.0
        }
        return out

def _apply_vila_zero(preview: dict, scenario_name: str):
    """Nollställer ekonomi/bonus/hårdhet i liven för 'Vila'-scenarier."""
    if scenario_name in ("Vila på jobbet", "Vila i hemmet (dag 1–7)"):
        preview["Prenumeranter"] = 0
        preview["Hårdhet"] = 0
        preview["Intäkter"] = 0.0
        preview["Intäkt Känner"] = 0.0
        preview["Kostnad män"] = 0.0
        preview["Lön Malin"] = 0.0
        preview["Vinst"] = 0.0
        preview["Intäkt företag"] = 0.0
    return preview

base = build_base_from_inputs()
preview = _calc_row(base)
preview = _apply_vila_zero(preview, st.session_state[SCENARIO_KEY])

# Egen kontrollsiffra
tot_men_including = (
    int(base.get("Män",0)) + int(base.get("Svarta",0)) +
    int(base.get(LBL_PAPPAN,0)) + int(base.get(LBL_GRANNAR,0)) +
    int(base.get(LBL_NV,0)) + int(base.get(LBL_NF,0)) +
    int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) +
    int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
)

# Överkant
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
try:
    _d = datetime.fromisoformat(rad_datum).date() if isinstance(rad_datum,str) else datetime.today().date()
except Exception:
    _d = datetime.today().date()
fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

# Tid/Klocka/Män
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

# Hångel/Sug/Händer
c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))

# Ekonomi
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
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

# Källor
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(base.get(LBL_ESK,0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

st.caption("Obs: 'Vila'-scenarier nollar ekonomi/hårdhet/bonus i liven och vid sparande.")

# ============================================================
#  Spara lokalt & till Sheets
# ============================================================
def _bonus_generated_from_preview(preview: dict, scenario_name: str) -> int:
    if scenario_name in ("Vila på jobbet", "Vila i hemmet (dag 1–7)"):
        return 0
    try:
        p = int(preview.get("Prenumeranter",0))
        pct = float(CFG.get("BONUS_PERCENT",1.0))
        return int((p * pct) // 100)
    except Exception:
        return 0

def _post_save_housekeeping(preview: dict):
    """Uppdatera min/max, bonus kvar, sceninfo."""
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP", LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        try:
            v = int(preview.get(col,0))
        except Exception:
            v = 0
        mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))

    # Bonus kvar = +genererade - deltagit
    gen = _bonus_generated_from_preview(preview, st.session_state[SCENARIO_KEY])
    delt = int(preview.get("Bonus deltagit",0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE",0)) + gen - delt)

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

st.markdown("---")
cL, cR = st.columns([1,1])
with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _post_save_housekeeping(preview)
        st.success("✅ Sparad i minnet.")

def _save_to_profile_sheet(row_dict: dict):
    ss = _get_gspread_client()
    prof = st.session_state.get(PROFILE_KEY,"").strip()
    if not prof:
        raise RuntimeError("Ingen profil vald.")
    _append_row_to_profile(ss, prof, row_dict)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            _save_to_profile_sheet(preview)
            st.success("✅ Sparad till profilens data-blad.")
            st.session_state[ROWS_KEY].append(preview)
            _post_save_housekeeping(preview)
        except Exception as e:
            st.error(f"Misslyckades att spara: {e}")

# ============================================================
#  Visa lokala rader
# ============================================================
st.markdown("---")
st.subheader("📋 Lokala rader (cache)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=340)
else:
    st.info("Inga lokala rader ännu.")

# ============================================================
#  (Valfritt) enkel statistik på slutet – om statistik.py saknas
# ============================================================
try:
    from statistik import compute_stats
except Exception:
    def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
        stats = {}
        if rows_df is None or rows_df.empty:
            return stats
        for col in ["Intäkter","Intäkt Känner","Kostnad män","Lön Malin","Vinst","Intäkt företag"]:
            stats[f"Totalt {col}"] = float(pd.to_numeric(rows_df.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        stats["Totalt antal prenumeranter"] = int(pd.to_numeric(rows_df.get("Prenumeranter", pd.Series(dtype=int)), errors="coerce").fillna(0).sum())
        stats["Antal scener"] = len(rows_df)
        return stats

st.markdown("---")
st.subheader("📊 Statistik (enkel)")
try:
    stats = compute_stats(pd.DataFrame(st.session_state[ROWS_KEY]), CFG)
    if stats:
        for k,v in stats.items():
            st.write(f"**{k}**: {v}")
    else:
        st.info("Ingen data att visa.")
except Exception as e:
    st.error(f"Kunde inte beräkna statistik: {e}")
