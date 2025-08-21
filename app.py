# app.py
import streamlit as st
import json
import random
import pandas as pd
import datetime as dt

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets)")

# ======== Import av beräkningar/statistik (valfritt för statistik) ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    from statistik import compute_stats as compute_stats_main
except Exception:
    compute_stats_main = None

try:
    from statistik_affar import compute_stats as compute_stats_affar
except Exception:
    compute_stats_affar = None

try:
    from statistik_relation import compute_stats as compute_stats_relation
except Exception:
    compute_stats_relation = None

# =========================
# Hjälpare: Sheets
# =========================
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

def _ensure_ws(ss, title, rows=5000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _list_profiles(ss):
    try:
        ws = _ensure_ws(ss, "Profil")
        names = ws.col_values(1)
        names = [n.strip() for n in names if n and n.strip()]
        return names
    except Exception:
        return []

def _load_profile_cfg(ss, profile_name):
    """Läs Key/Value från profilens blad. Returnerar dict."""
    try:
        ws = _ensure_ws(ss, profile_name)
        rows = ws.get_all_records()
        cfg = {}
        for r in rows:
            k = str(r.get("Key") or r.get("Nyckel") or "").strip()
            v = str(r.get("Value") or r.get("Värde") or "").strip()
            if not k:
                continue
            # typning
            lowk = k.lower()
            if lowk in ("startdatum","fodelsedatum"):
                try:
                    y, m, d = [int(x) for x in v.split("-")]
                    cfg[k] = dt.date(y, m, d)
                except:
                    continue
            else:
                # försök int/float/bool
                vv = v.replace(",", ".")
                if vv.lower() in ("true","false"):
                    cfg[k] = (vv.lower() == "true")
                else:
                    try:
                        if "." in vv:
                            cfg[k] = float(vv)
                        else:
                            cfg[k] = int(vv)
                    except:
                        cfg[k] = v
        return cfg
    except Exception as e:
        st.warning(f"Kunde inte läsa profil '{profile_name}': {e}")
        return {}

def _save_profile_cfg(ss, profile_name, cfg: dict):
    """Spara hela CFG som Key/Value till profilens blad."""
    ws = _ensure_ws(ss, profile_name)
    rows = []
    for k, v in cfg.items():
        vv = v
        if isinstance(v, (dt.date, dt.datetime)):
            vv = v.strftime("%Y-%m-%d")
        rows.append([k, str(vv)])
    ws.clear()
    ws.update("A1", [["Key","Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def _load_profile_rows(ss, profile_name):
    """Läs rader från Data_<Profil> som DataFrame."""
    ws = _ensure_ws(ss, f"Data_{profile_name}")
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    return df

def _append_row_to_profile(ss, profile_name, row_dict):
    ws = _ensure_ws(ss, f"Data_{profile_name}")
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

# =========================
# State-nycklar
# =========================
CFG_KEY       = "CFG"           # alla config + etiketter
ROWS_KEY      = "ROWS"          # rader (Data_<profil>) i minnet
HIST_MM_KEY   = "HIST_MINMAX"   # min/max per kolumn från ROWS
SCENEINFO_KEY = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY  = "SCENARIO"      # nuvarande scenario-val
PROFILE_KEY   = "PROFILE"       # vald profil

# =========================
# Input-ordning
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
    "in_nils",
    "in_hander_aktiv"
]

# =========================
# Init
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + dt.timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def _init_cfg_defaults():
    return {
        # fasta datum enl. krav
        "startdatum":   dt.date(1990,1,1),
        "starttid":     dt.time(7,0),
        "fodelsedatum": dt.date(1970,1,1),

        # ekonomi
        "avgift_usd":   30.0,
        "PROD_STAFF":   800,

        # bonus
        "BONUS_AVAILABLE": 500,     # kvar
        "BONUS_PERCENT":   1.0,     # % av prenumeranter

        # Eskilstuna intervall
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

        # Profil-attribut
        "HEIGHT_M": 1.64,   # längd i meter
    }

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = _init_cfg_defaults()

    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = None

    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []

    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}

    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"

    for k in INPUT_ORDER:
        st.session_state.setdefault(k, 0)

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
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn, v), max(mx, v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try:
            vals.append(int(r.get(colname, 0)))
        except:
            pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_up_to_max(colname: str, fallback_max: int = 0):
    """Slumpa från 1..(max i historik eller fallback_max). Om max=0 → 0."""
    _, hi = _minmax_from_hist(colname)
    mx = hi if hi > 0 else fallback_max
    if mx and mx > 0:
        return random.randint(1, int(mx))
    return 0

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # behåll standard för tidsfält + händer aktiv default = 1
    keep_defaults = {
        "in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,
        "in_hander_aktiv":1
    }
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    LBL_P = CFG["LBL_PAPPAN"]; LBL_G = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_up_to_max("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        for f,key in [(LBL_P,"in_pappan"),(LBL_G,"in_grannar"),
                      (LBL_NV,"in_nils_vanner"),(LBL_NF,"in_nils_familj"),
                      (LBL_BEK,"in_bekanta")]:
            # använd konfig max som fallback om historik saknas
            fb = CFG.get({
                LBL_P:"MAX_PAPPAN", LBL_G:"MAX_GRANNAR",
                LBL_NV:"MAX_NILS_VANNER", LBL_NF:"MAX_NILS_FAMILJ",
                LBL_BEK:"MAX_BEKANTA"
            }[f], 0)
            st.session_state[key] = _rand_up_to_max(f, fallback_max=fb)
        st.session_state["in_eskilstuna"]  = random.randint(1, int(max(1, CFG["ESK_MAX"])))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_up_to_max("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        for f,key in [(LBL_P,"in_pappan"),(LBL_BEK,"in_bekanta"),
                      (LBL_G,"in_grannar"),(LBL_NV,"in_nils_vanner"),
                      (LBL_NF,"in_nils_familj")]:
            fb = CFG.get({
                LBL_P:"MAX_PAPPAN", LBL_G:"MAX_GRANNAR",
                LBL_NV:"MAX_NILS_VANNER", LBL_NF:"MAX_NILS_FAMILJ",
                LBL_BEK:"MAX_BEKANTA"
            }[f], 0)
            st.session_state[key] = _rand_up_to_max(f, fallback_max=fb)
        st.session_state["in_eskilstuna"]  = random.randint(1, int(max(1, CFG["ESK_MAX"])))
        # Ekonomin ska vara 0; vi markerar detta via en flagg i session (används efter beräkning)
        st.session_state["SCEN_NO_ECON"] = True

    elif s == "Vila i hemmet (dag 1–7)":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        for f,key in [(LBL_P,"in_pappan"),(LBL_G,"in_grannar"),
                      (LBL_NV,"in_nils_vanner"),(LBL_NF,"in_nils_familj"),
                      (LBL_BEK,"in_bekanta")]:
            fb = CFG.get({
                LBL_P:"MAX_PAPPAN", LBL_G:"MAX_GRANNAR",
                LBL_NV:"MAX_NILS_VANNER", LBL_NF:"MAX_NILS_FAMILJ",
                LBL_BEK:"MAX_BEKANTA"
            }[f], 0)
            st.session_state[key] = _rand_up_to_max(f, fallback_max=fb)
        st.session_state["in_eskilstuna"] = random.randint(1, int(max(1, CFG["ESK_MAX"])))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        st.session_state["SCEN_NO_ECON"] = True

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sido-panel (Profiler + Inställningar)
# =========================
CFG = st.session_state[CFG_KEY]

with st.sidebar:
    st.subheader("Profil")
    try:
        ss = _get_gspread_client()
        profiles = _list_profiles(ss)
    except Exception as e:
        profiles = []
        st.error(f"Kunde inte läsa profil-lista: {e}")

    prof = st.selectbox("Välj profil", options=(profiles or ["(ingen)"]), index=0)
    if prof and prof != "(ingen)" and prof != st.session_state.get(PROFILE_KEY):
        # Ladda profilens CFG + rader
        st.session_state[PROFILE_KEY] = prof
        # overlay profilens cfg på defaults
        prof_cfg = _load_profile_cfg(ss, prof)
        base_cfg = _init_cfg_defaults()
        base_cfg.update(prof_cfg)
        st.session_state[CFG_KEY] = base_cfg
        CFG = st.session_state[CFG_KEY]

        # Läs rader
        try:
            df_prof = _load_profile_rows(ss, prof)
            st.session_state[ROWS_KEY] = df_prof.to_dict("records")
        except Exception as e:
            st.warning(f"Inga rader för profilen (ännu) eller fel: {e}")
            st.session_state[ROWS_KEY] = []

        # Bygg om historik min/max
        st.session_state[HIST_MM_KEY] = {}
        for r in st.session_state[ROWS_KEY]:
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                        CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                _add_hist_value(col, r.get(col, 0))

        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success(f"✅ Profil '{prof}' inläst.")

    st.markdown("---")
    st.header("Inställningar")

    CFG["startdatum"] = st.date_input("Startdatum", value=CFG.get("startdatum", dt.date(1990,1,1)))
    CFG["starttid"]   = st.time_input("Starttid",   value=CFG.get("starttid", dt.time(7,0)))
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG.get("fodelsedatum", dt.date(1970,1,1)))

    # Avgift robust float
    try:
        _fee = str(CFG.get("avgift_usd", 30.0)).strip().replace(",", ".")
        fee_default = float(_fee)
    except:
        fee_default = 30.0
    CFG["avgift_usd"] = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(fee_default), step=1.0)

    CFG["PROD_STAFF"] = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG.get("PROD_STAFF",800)), step=1)

    # BONUS %
    try:
        _bp = str(CFG.get("BONUS_PERCENT", 1.0)).strip().replace(",", ".")
        bonus_percent_default = float(_bp)
    except:
        bonus_percent_default = 1.0
    CFG["BONUS_PERCENT"] = st.number_input("Bonus-killar (% av prenumeranter)", min_value=0.0, max_value=100.0, value=bonus_percent_default, step=0.5)

    st.caption(f"Bonus killar kvar: **{int(CFG.get('BONUS_AVAILABLE',0))}**")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG.get("ESK_MIN",20)), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG.get("ESK_MAX",40)), step=1)

    st.markdown("---")
    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG.get("MAX_PAPPAN",100)), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG.get("MAX_GRANNAR",100)), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG.get("MAX_NILS_VANNER",100)), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG.get("MAX_NILS_FAMILJ",100)), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG.get("MAX_BEKANTA",100)), step=1)

    st.markdown("---")
    st.subheader("Egna etiketter")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett – Pappans vänner", value=str(CFG.get("LBL_PAPPAN","Pappans vänner")))
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett – Grannar",        value=str(CFG.get("LBL_GRANNAR","Grannar")))
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett – Nils vänner",    value=str(CFG.get("LBL_NILS_VANNER","Nils vänner")))
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett – Nils familj",    value=str(CFG.get("LBL_NILS_FAMILJ","Nils familj")))
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett – Bekanta",        value=str(CFG.get("LBL_BEKANTA","Bekanta")))
    CFG["LBL_ESK"]         = st.text_input("Etikett – Eskilstuna killar", value=str(CFG.get("LBL_ESK","Eskilstuna killar")))

    st.markdown("---")
    st.subheader("Längd + BM (beräknas i liven)")

    # Robust inläsning av längd
    try:
        _h = str(CFG.get("HEIGHT_M", 1.64)).strip().replace(",", ".")
        height_default = float(_h)
    except:
        height_default = 1.64
    height_default = max(1.40, min(2.20, height_default))

    CFG["HEIGHT_M"] = st.number_input("Längd (m)", min_value=1.40, max_value=2.20, value=height_default, step=0.01, format="%.2f")

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        # nollställ NO_ECON-flagga innan ny fyllning
        st.session_state["SCEN_NO_ECON"] = False
        apply_scenario_fill()
        st.rerun()

    st.markdown("---")
    st.subheader("Google Sheets – status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Spara endast den valda profilens inställningar
    if st.button("💾 Spara PROFIL-inställningar till Sheets"):
        if st.session_state.get(PROFILE_KEY):
            try:
                _save_profile_cfg(_get_gspread_client(), st.session_state[PROFILE_KEY], st.session_state[CFG_KEY])
                st.success("✅ Profil-inställningar sparade.")
            except Exception as e:
                st.error(f"Misslyckades att spara profil-inställningar: {e}")
        else:
            st.warning("Välj först en profil.")

# =========================
# Inmatning (exakt ordning)
# =========================
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
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG['BONUS_AVAILABLE'])})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_nils":"Nils (0/1/2)",
    "in_hander_aktiv":"Händer aktiv (0/1)"
}

with c1:
    for key in [
        "in_man","in_svarta",
        "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
        "in_tid_s","in_tid_d","in_vila"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

with c2:
    for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in [
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna",
        "in_bonus_deltagit","in_personal_deltagit","in_nils",
        "in_hander_aktiv"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# =========================
# Bygg bas-rad från inputs
# =========================
def build_base_from_inputs():
    scen_nr, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen_nr,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # händer aktiv (0/1)
        "Händer aktiv": int(st.session_state["in_hander_aktiv"]),
        # max för känner-delar, för statistik/beräkning
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]), "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]), "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"])
    }
    # Känner = summa av käll-etiketter
    base["Känner"] = (
        int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) +
        int(base[LBL_NV]) + int(base[LBL_NF])
    )
    # meta till beräkning
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# =========================
# Live + förhandsberäkning
# =========================
st.markdown("---"); st.subheader("🔎 Live")
base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# Om scenario är "Vila..." ska ekonomi = 0 & hårdhet 0
if st.session_state.get("SCEN_NO_ECON", False) or st.session_state.get(SCENARIO_KEY,"").startswith("Vila"):
    preview["Prenumeranter"] = 0
    preview["Intäkter"] = 0.0
    preview["Kostnad män"] = 0.0
    preview["Intäkt Känner"] = 0.0
    preview["Intäkt företag"] = 0.0
    preview["Lön Malin"] = 0.0
    preview["Vinst"] = 0.0
    preview["Hårdhet"] = 0

# Ålder
try:
    dstr = preview.get("Datum", base["Datum"])
    _d = dt.date.fromisoformat(dstr) if isinstance(dstr, str) else base["_rad_datum"]
except:
    _d = base["_rad_datum"]
fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
veckodag = preview.get("Veckodag","-")
st.markdown(f"**Datum/Veckodag:** {preview.get('Datum','-')} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år  •  Längd: {CFG['HEIGHT_M']:.2f} m")

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

# Hångel / Suger / Händer
c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer aktiv", int(preview.get("Händer aktiv", 1)))
with c6:
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))

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
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
with e4:
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

# Källor
st.markdown("**👥 Källor (live)**")
kk1,kk2,kk3,kk4,kk5,kk6 = st.columns(6)
with kk1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN,0)))
with kk2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR,0)))
with kk3: st.metric(LBL_NV, int(base.get(LBL_NV,0)))
with kk4: st.metric(LBL_NF, int(base.get(LBL_NF,0)))
with kk5: st.metric(LBL_BEK, int(base.get(LBL_BEK,0)))
with kk6: st.metric(LBL_ESK, int(base.get(LBL_ESK,0)))

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men påverkar separat klockan (i beräkning).")

# =========================
# Spara lokalt / Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _post_save_common(preview_row: dict):
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        _add_hist_value(col, preview_row.get(col, 0))

    # uppdatera BONUS_AVAILABLE = +nytt - deltagit
    # (om scenario är vila → inget nytt)
    bonus_new = 0
    if not (st.session_state.get("SCEN_NO_ECON", False) or st.session_state.get(SCENARIO_KEY,"").startswith("Vila")):
        try:
            pn = int(preview_row.get("Prenumeranter",0))
            pct = float(CFG.get("BONUS_PERCENT", 1.0))
            bonus_new = int(round(pn * (pct/100.0)))
        except:
            bonus_new = 0
    bonus_used = int(preview_row.get("Bonus deltagit", 0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE",0)) + bonus_new - bonus_used)

    # bumpa sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _post_save_common(preview)
        st.success("✅ Sparad i minnet.")

def _save_row_to_profile_sheets(preview_row: dict):
    prof = st.session_state.get(PROFILE_KEY)
    if not prof:
        raise RuntimeError("Ingen profil vald.")
    ss = _get_gspread_client()
    # lägg även till profilnamn i raden
    row = dict(preview_row)
    row["Profil"] = prof
    _append_row_to_profile(ss, prof, row)
    # spara uppdaterat CFG (för t.ex. BONUS_AVAILABLE) tillbaka till profilens blad
    _save_profile_cfg(ss, prof, CFG)

with cR:
    if st.button("📤 Spara raden till Google Sheets (profilens Data)"):
        try:
            _save_row_to_profile_sheets(preview)
            st.session_state[ROWS_KEY].append(preview)
            _post_save_common(preview)
            st.success("✅ Sparad till Google Sheets i fliken 'Data_%s'." % st.session_state.get(PROFILE_KEY,"?"))
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader + Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=340)
else:
    st.info("Inga lokala rader ännu.")

st.markdown("---")
st.subheader("📊 Statistik")
rows_df = pd.DataFrame(st.session_state[ROWS_KEY]) if st.session_state[ROWS_KEY] else pd.DataFrame()

cols = st.columns(3)
with cols[0]:
    if compute_stats_main:
        try:
            stats_main = compute_stats_main(rows_df, CFG)
            st.markdown("**Översikt**")
            for k, v in stats_main.items():
                st.write(f"- **{k}**: {v}")
        except Exception as e:
            st.error(f"Kunde inte beräkna statistik: {e}")
    else:
        st.info("`statistik.py` saknas (valfritt).")

with cols[1]:
    if compute_stats_affar:
        try:
            stats_a = compute_stats_affar(rows_df, CFG)
            st.markdown("**Affär**")
            for k, v in stats_a.items():
                st.write(f"- **{k}**: {v}")
        except Exception as e:
            st.error(f"Affärsstatistik fel: {e}")
    else:
        st.info("`statistik_affar.py` saknas (valfritt).")

with cols[2]:
    if compute_stats_relation:
        try:
            stats_r = compute_stats_relation(rows_df, CFG)
            st.markdown("**Relation**")
            for k, v in stats_r.items():
                st.write(f"- **{k}**: {v}")
        except Exception as e:
            st.error(f"Relationsstatistik fel: {e}")
    else:
        st.info("`statistik_relation.py` saknas (valfritt).")
