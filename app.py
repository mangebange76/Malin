import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import pandas as pd
import json

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (Profiler + Sheets + BMI mål)")

# ======== State-nycklar ========
CFG_KEY        = "CFG"            # alla config + etiketter + profilvärden
ROWS_KEY       = "ROWS"           # sparade rader (lokalt minne speglas från/vid Sheets)
HIST_MM_KEY    = "HIST_MINMAX"    # min/max per fält
SCENEINFO_KEY  = "CURRENT_SCENE"  # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"       # rullist-valet
PROFILE_KEY    = "PROFILE_NAME"   # valt profilnamn
PROFILE_LIST   = "PROFILE_LIST"   # lista av profiler (från fliken "Profil")

# ======== Import av beräkning & ev. statistik ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    from statistik import compute_stats   # valfri
    HAS_STATS = True
except Exception:
    HAS_STATS = False

# =========================
# Hjälpare: Secrets & Sheets
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

def _ensure_ws(ss, title, rows=4000, cols=80):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

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
    "in_nils"
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
            # Start/födelse enligt dina ramar
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),

            # Ekonomi & personal
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,

            # Bonus killar – initialt från Profil/Inställningar, uppdateras löpande
            "BONUS_AVAILABLE": 500,

            # Eskilstuna-intervall
            "ESK_MIN": 20, "ESK_MAX": 40,

            # Maxvärden (källor)
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,

            # Etiketter (kan döpas om)
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",

            # Profilfält
            "HEIGHT_M": 1.64,  # hämtas normalt från profilfliken
            "BM_MAL": 0.0,
            "MAL_VIKT": 0.0,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""  # väljs från Profil-fliken
    if PROFILE_LIST not in st.session_state:
        st.session_state[PROFILE_LIST] = []

    # default för tidsfält m.m.
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0
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
    try:
        v = int(v)
    except:
        v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
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
    mm = (min(vals), max(vals)) if vals else (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(st.session_state[CFG_KEY]["LBL_PAPPAN"],"in_pappan"),
                      (st.session_state[CFG_KEY]["LBL_GRANNAR"],"in_grannar"),
                      (st.session_state[CFG_KEY]["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (st.session_state[CFG_KEY]["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (st.session_state[CFG_KEY]["LBL_BEKANTA"],"in_bekanta")]:
            # slumpa via historiska rubriker
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(st.session_state[CFG_KEY]["LBL_PAPPAN"],"in_pappan"),
                      (st.session_state[CFG_KEY]["LBL_BEKANTA"],"in_bekanta"),
                      (st.session_state[CFG_KEY]["LBL_GRANNAR"],"in_grannar"),
                      (st.session_state[CFG_KEY]["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (st.session_state[CFG_KEY]["LBL_NILS_FAMILJ"],"in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad till en dag enligt dina senaste önskemål
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(st.session_state[CFG_KEY]["LBL_PAPPAN"],"in_pappan"),
                      (st.session_state[CFG_KEY]["LBL_GRANNAR"],"in_grannar"),
                      (st.session_state[CFG_KEY]["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (st.session_state[CFG_KEY]["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (st.session_state[CFG_KEY]["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Profil-hantering (läs Profil-lista + ladda profilblad)
# =========================
def _load_profile_names():
    try:
        ss = _get_gspread_client()
        wsP = _ensure_ws(ss, "Profil")
        vals = wsP.col_values(1)  # kolumn A
        names = [v.strip() for v in vals if v and v.strip().lower() != "profil"]
        st.session_state[PROFILE_LIST] = names
    except Exception as e:
        st.session_state[PROFILE_LIST] = []
        st.warning(f"Kunde inte läsa profilnamn: {e}")

def _load_profile_sheet(name: str):
    """Läser profilflik (Key/Value) + inställningar och dataflik med samma namn.
       Samt ‘Inställningar’ & ‘Data’ som bas (överlagras av profilen)."""
    try:
        ss = _get_gspread_client()
        # 1) Inställningar (global bas – läses först)
        wsI = _ensure_ws(ss, "Inställningar")
        inst = wsI.get_all_values()
        if inst:
            for row in inst:
                if len(row) >= 2 and row[0]:
                    key = row[0].strip()
                    val = row[1]
                    _assign_cfg_key(key, val)

        # 2) Profilblad: namn = name (Key/Value)
        wsProf = _ensure_ws(ss, name)
        prof = wsProf.get_all_values()
        for row in prof:
            if len(row) >= 2 and row[0]:
                key = row[0].strip()
                val = row[1]
                _assign_cfg_key(key, val)

        # 3) Data – profilens Dataflik? (om du vill separera per profil)
        #    Standard: vi använder universell "Data". Vill du ha per profil,
        #    döp fliken till exakt profilnamnet och läs därifrån:
        try:
            wsD = ss.worksheet(name)  # om du vill ha data i samma profilflik
            data_vals = wsD.get_all_records()
        except Exception:
            wsD = _ensure_ws(ss, "Data")
            data_vals = wsD.get_all_records()

        st.session_state[ROWS_KEY] = data_vals or []
        st.session_state[HIST_MM_KEY] = {}
        # bygg min/max för historik – använd gällande etiketter:
        LBL_PAPPAN = st.session_state[CFG_KEY]["LBL_PAPPAN"]
        LBL_GRANNAR = st.session_state[CFG_KEY]["LBL_GRANNAR"]
        LBL_NV = st.session_state[CFG_KEY]["LBL_NILS_VANNER"]
        LBL_NF = st.session_state[CFG_KEY]["LBL_NILS_FAMILJ"]
        LBL_BEK = st.session_state[CFG_KEY]["LBL_BEKANTA"]
        LBL_ESK = st.session_state[CFG_KEY]["LBL_ESK"]
        for r in st.session_state[ROWS_KEY]:
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
                _add_hist_value(col, r.get(col, 0))

        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success(f"✅ Profil '{name}' inläst.")
    except Exception as e:
        st.error(f"Kunde inte läsa profil '{name}': {e}")

def _assign_cfg_key(key, val):
    # Typning: datum, float/int/bool, annars str
    try:
        if key in ("startdatum","fodelsedatum"):
            y,m,d = [int(x) for x in str(val).replace("/", "-").split("-")]
            st.session_state[CFG_KEY][key] = date(y,m,d)
            return
        if str(val).strip().lower() in ("true","false"):
            st.session_state[CFG_KEY][key] = (str(val).strip().lower() == "true")
            return
        v2 = str(val).replace(",", ".")
        if "." in v2:
            st.session_state[CFG_KEY][key] = float(v2)
        else:
            st.session_state[CFG_KEY][key] = int(v2)
    except:
        st.session_state[CFG_KEY][key] = val

# =========================
# Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profiler")
    if st.button("↻ Läs in profiler"):
        _load_profile_names()
    # rullista (om inga profiler ännu – visa tomt)
    profile_names = st.session_state[PROFILE_LIST] or []
    st.session_state[PROFILE_KEY] = st.selectbox("Välj profil", options=[""] + profile_names, index=0)

    if st.session_state[PROFILE_KEY]:
        if st.button("📥 Ladda vald profil"):
            _load_profile_sheet(st.session_state[PROFILE_KEY])

    st.markdown("---")
    st.header("Inställningar")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")

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
    st.subheader("Egna etiketter")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett Eskilstuna killar", value=CFG["LBL_ESK"])

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
    st.subheader("Google Sheets – status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Spara inställningar till flik Inställningar (key/value)
    if st.button("💾 Spara inställningar till Sheets"):
        try:
            ss = _get_gspread_client()
            wsI = _ensure_ws(ss, "Inställningar")
            rows = []
            for k,v in st.session_state[CFG_KEY].items():
                if isinstance(v, (date, datetime)):
                    v = v.strftime("%Y-%m-%d")
                rows.append([k, str(v)])
            wsI.clear()
            wsI.update("A1", [["Key","Value"]])
            if rows:
                wsI.update(f"A2:B{len(rows)+1}", rows)
            st.success("✅ Inställningar sparade.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

# =========================
# Inmatning (etiketter via inställningar), exakt ordning
# =========================
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)

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
    "in_nils":"Nils (0/1/2)"
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
        "in_bonus_deltagit","in_personal_deltagit",
        "in_nils"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# =========================
# Basrad från inputs
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

        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"]),

        # MAX för statistik i beräkningar (om/när de används)
        "MAX_PAPPAN":      int(st.session_state[CFG_KEY]["MAX_PAPPAN"]),
        "MAX_GRANNAR":     int(st.session_state[CFG_KEY]["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(st.session_state[CFG_KEY]["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(st.session_state[CFG_KEY]["MAX_NILS_FAMILJ"]),
        "MAX_BEKANTA":     int(st.session_state[CFG_KEY]["MAX_BEKANTA"]),
    }
    # Känner = summa av käll-etiketter
    base["Känner"] = (
        int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) +
        int(base[LBL_NV]) + int(base[LBL_NF])
    )
    # meta till beräkning
    base["_rad_datum"]    = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
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
    preview = calc_row_values(base, base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# Datum/ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try:
        _d = datetime.fromisoformat(rad_datum).date()
    except Exception:
        _d = datetime.today().date()
else:
    _d = datetime.today().date()

fd = st.session_state[CFG_KEY]["fodelsedatum"]
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

# Hångel/Sug
c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

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
    st.metric("Utgift män", f"${float(preview.get('Utgift män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

# Käll-breakout (med etiketter)
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(base.get(LBL_ESK,0)))

st.caption("Obs: Älskar/Sover-med-tider ingår inte i scenens 'Summa tid', men läggs på klockan i din separata logik.")

# ======== BM mål och Mål vikt (ackumulerat över alla prenumeranter) ========
st.markdown("---")
st.subheader("📏 BM mål & Mål vikt (ackumulerat)")
try:
    prev_total = sum(int(r.get("Prenumeranter", 0)) for r in st.session_state[ROWS_KEY])
    curr = int(preview.get("Prenumeranter", 0))
    n_subs = prev_total + curr
except Exception:
    n_subs = 0

bm_mal = 0.0
mal_vikt = 0.0
if n_subs > 0:
    total = 0
    for _ in range(n_subs):
        total += random.randint(12, 18)
    bm_mal = total / float(n_subs)
    h = float(st.session_state[CFG_KEY].get("HEIGHT_M", 1.64))
    mal_vikt = bm_mal * h * h

st.session_state[CFG_KEY]["BM_MAL"] = float(bm_mal)
st.session_state[CFG_KEY]["MAL_VIKT"] = float(mal_vikt)

b1, b2 = st.columns(2)
with b1:
    st.metric("BM mål (snitt)", f"{bm_mal:.2f}")
with b2:
    st.metric("Mål vikt", f"{mal_vikt:.1f} kg")

# =========================
# Spara lokalt
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _after_save_common(preview_row: dict):
    """Gemensam uppdatering efter spar (lokalt/Sheets)."""
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview_row.get(col,0))
        _add_hist_value(col, v)
    # Bonus killar kvar = kvar + 1% av nya prenumeranter – ‘Bonus deltagit’ (på raden)
    try:
        add_from_subs = int(round(preview_row.get("Prenumeranter",0) * 0.01))
    except Exception:
        add_from_subs = 0
    try:
        used = int(preview_row.get("Bonus deltagit",0))
    except Exception:
        used = 0
    st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(0, int(st.session_state[CFG_KEY]["BONUS_AVAILABLE"]) + add_from_subs - used)

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _after_save_common(preview)
        st.success("✅ Sparad i minnet (ingen Sheets).")

# =========================
# Spara till Google Sheets (flik Data)
# =========================
def save_to_sheets(row_dict: dict):
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, "Data")
    # Header
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    # Mappa till headerordning
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            save_to_sheets(preview)
            st.success("✅ Sparad till Google Sheets (flik: Data).")
            # Spegla lokalt + bonus kvar
            st.session_state[ROWS_KEY].append(preview)
            _after_save_common(preview)
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader & Statistik (om finns)
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

if HAS_STATS:
    st.markdown("---")
    st.subheader("📈 Statistik (från statistik.py)")
    try:
        stats = compute_stats(st.session_state[ROWS_KEY], st.session_state[CFG_KEY])
        if isinstance(stats, dict):
            for k,v in stats.items():
                st.write(f"**{k}:** {v}")
        elif isinstance(stats, pd.DataFrame):
            st.dataframe(stats, use_container_width=True)
        else:
            st.write(stats)
    except Exception as e:
        st.error(f"Fel i compute_stats: {e}")
