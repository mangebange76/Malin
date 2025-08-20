# app.py
import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import pandas as pd
import json

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets + händer)")

# ======== Import av beräkning ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# ======== Import av statistik (valfri, men vi försöker) ========
try:
    from statistik import compute_stats as _compute_stats
except Exception:
    _compute_stats = None

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

def _ensure_ws(ss, title, rows=4000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

# =========================
# State-nycklar
# =========================
CFG_KEY       = "CFG"           # config + etiketter + profilnamn
ROWS_KEY      = "ROWS"          # lokalt cache: rader för vald profil
HIST_MM_KEY   = "HIST_MINMAX"   # min/max per kolumn (för slump)
SCENEINFO_KEY = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY  = "SCENARIO"      # rullist-valet
PROFILE_KEY   = "PROFILE"       # valt profilnamn
HANDER_KEY    = "in_hander"     # 0/1 för händer aktiv på radnivå

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

def _init_cfg_defaults():
    return {
        # start/födelse enligt din begäran
        "startdatum":   date(1990,1,1),
        "starttid":     time(7,0),
        "fodelsedatum": date(1970,1,1),
        "avgift_usd":   30.0,
        "PROD_STAFF":   800,
        "BONUS_AVAILABLE": 500,
        "BONUS_RATE":   1.0,  # % (kan ändras vid behov)
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

        # Profilnamn (default)
        "PROFIL_NAMN": "Malin"
    }

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = _init_cfg_defaults()
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = st.session_state[CFG_KEY]["PROFIL_NAMN"]
    # default för tidsfält m.m.
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))
    # Händer aktiv default = 1
    st.session_state.setdefault(HANDER_KEY, 1)
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
    # bygg från ROWS om saknas
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

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

def _mmss(sec: float) -> str:
    try:
        sec = max(0, int(round(float(sec))))
        m, s = divmod(sec, 60)
        return f"{m}:{s:02d}"
    except:
        return "-"

# =========================
# Slump-scenarier
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]
    # nolla (behåll tidsstandarder)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)
    # nollställ händer aktiv? Nej – behåller senaste val
    # st.session_state[HANDER_KEY] = 1

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        # män + sexualfält mellan historiska min/max
        st.session_state["in_man"]   = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),
                      ("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        # källor (kan slumpas, men sällan höga)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),
                      ("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        # sexualfält + källor slumpas
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),
                      ("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                      ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                      ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag enligt din specifikation – slumpa sexualfält + källor
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),
                      ("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    # uppdatera sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Läs/Spara mot Sheets
# =========================
def read_profile_list():
    """Hämtar listan med profiler från fliken 'Profil' (kolumn A)."""
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, "Profil")
        names = ws.col_values(1)
        names = [n.strip() for n in names if n and n.strip() and n.strip().lower() != "profil"]
        return names or ["Malin"]
    except Exception as e:
        st.warning(f"Kunde inte läsa profil-lista: {e}")
        return [st.session_state[CFG_KEY]["PROFIL_NAMN"]]

def load_profile_and_rows(profile_name: str):
    """Läs in profilens inställningar (blad=profil_name, key/value) + rader ur Data (filtrerat på Profil)."""
    try:
        ss = _get_gspread_client()
    except Exception as e:
        st.error(f"Kunde inte koppla upp mot Sheets: {e}")
        return

    # 1) Inställningar
    try:
        wsP = _ensure_ws(ss, profile_name)
        rows = wsP.get_all_values()
        if rows:
            for row in rows:
                if len(row) >= 2 and row[0]:
                    key = row[0].strip()
                    val = row[1]
                    # konvertera
                    if key in ("startdatum","fodelsedatum"):
                        try:
                            y,m,d = [int(x) for x in val.split("-")]
                            st.session_state[CFG_KEY][key] = date(y,m,d)
                        except:
                            pass
                    else:
                        try:
                            if "." in str(val):
                                st.session_state[CFG_KEY][key] = float(val)
                            else:
                                st.session_state[CFG_KEY][key] = int(val)
                        except:
                            st.session_state[CFG_KEY][key] = val
        st.session_state[CFG_KEY]["PROFIL_NAMN"] = profile_name
    except Exception as e:
        st.warning(f"Kunde inte läsa profilblad '{profile_name}': {e}")

    # 2) Data
    try:
        wsD = _ensure_ws(ss, "Data")
        data = wsD.get_all_records()
        if data:
            df = pd.DataFrame(data)
            if "Profil" in df.columns:
                df = df[df["Profil"].astype(str) == str(profile_name)]
            # konvertera numeric där möjligt
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="ignore")
            st.session_state[ROWS_KEY] = df.to_dict(orient="records")
        else:
            st.session_state[ROWS_KEY] = []
    except Exception as e:
        st.warning(f"Kunde inte läsa Data: {e}")

    # bygga om historik min/max
    st.session_state[HIST_MM_KEY] = {}
    for r in st.session_state[ROWS_KEY]:
        for col in [
            "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            st.session_state[CFG_KEY]["LBL_PAPPAN"],
            st.session_state[CFG_KEY]["LBL_GRANNAR"],
            st.session_state[CFG_KEY]["LBL_NILS_VANNER"],
            st.session_state[CFG_KEY]["LBL_NILS_FAMILJ"],
            st.session_state[CFG_KEY]["LBL_BEKANTA"],
            st.session_state[CFG_KEY]["LBL_ESK"]
        ]:
            _add_hist_value(col, r.get(col, 0))
    st.session_state[SCENEINFO_KEY] = _current_scene_info()
    st.success(f"✅ Profil '{profile_name}' inläst.")

def save_settings_to_profile_sheet():
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, st.session_state[CFG_KEY]["PROFIL_NAMN"])
        # skriv om allt: key/value
        rows = []
        for k,v in st.session_state[CFG_KEY].items():
            if isinstance(v, (date, datetime)):
                v = v.strftime("%Y-%m-%d")
            rows.append([k, str(v)])
        ws.clear()
        ws.update("A1", [["Key","Value"]])
        if rows:
            ws.update(f"A2:B{len(rows)+1}", rows)
        st.success("✅ Inställningar sparade till profilbladet.")
    except Exception as e:
        st.error(f"Misslyckades att spara inställningar: {e}")

def save_row_to_data(row_dict: dict):
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, "Data")
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

# =========================
# Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    profile_options = read_profile_list()
    current_profile = st.selectbox("Välj profil", options=profile_options, index=profile_options.index(st.session_state[PROFILE_KEY]) if st.session_state[PROFILE_KEY] in profile_options else 0)
    if st.button("📥 Läs in vald profil + Data"):
        st.session_state[PROFILE_KEY] = current_profile
        load_profile_and_rows(current_profile)

    st.markdown("---")
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG.get("startdatum", date(1990,1,1)))
    CFG["starttid"]     = st.time_input("Starttid", value=CFG.get("starttid", time(7,0)))
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG.get("fodelsedatum", date(1970,1,1)))
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG.get("avgift_usd",30.0)), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG.get("PROD_STAFF",800)), step=1)
    CFG["BONUS_RATE"]   = st.number_input("Bonus-killar % av prenumeranter", min_value=0.0, value=float(CFG.get("BONUS_RATE",1.0)), step=0.1)
    st.markdown(f"**Bonus killar kvar:** {int(CFG.get('BONUS_AVAILABLE',0))}")

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG.get("ESK_MIN",20)), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG.get("ESK_MAX",40)), step=1)

    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG.get("MAX_PAPPAN",100)), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG.get("MAX_GRANNAR",100)), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG.get("MAX_NILS_VANNER",100)), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG.get("MAX_NILS_FAMILJ",100)), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG.get("MAX_BEKANTA",100)), step=1)

    st.subheader("Egna etiketter (slår igenom i input/live)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG.get("LBL_PAPPAN","Pappans vänner"))
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG.get("LBL_GRANNAR","Grannar"))
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG.get("LBL_NILS_VANNER","Nils vänner"))
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG.get("LBL_NILS_FAMILJ","Nils familj"))
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG.get("LBL_BEKANTA","Bekanta"))
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG.get("LBL_ESK","Eskilstuna killar"))

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
    st.subheader("Google Sheets (status)")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    st.markdown("---")
    if st.button("💾 Spara inställningar till profilblad"):
        save_settings_to_profile_sheet()

# =========================
# Inmatning (etiketter av inställningar), exakt ordning
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

st.checkbox("Händer aktiv (påverkar Tid/kille)", key=HANDER_KEY, value=bool(st.session_state.get(HANDER_KEY,1)))

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Profil": st.session_state[CFG_KEY]["PROFIL_NAMN"],
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

        # Etiketter skickas med ifall beräkningsmodulen vill använda dem
        "LBL_PAPPAN": LBL_PAPPAN, "LBL_GRANNAR": LBL_GRANNAR,
        "LBL_NILS_VANNER": LBL_NV, "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK, "LBL_ESK": LBL_ESK,

        # Händer-flagga
        "Händer aktiv": int(bool(st.session_state[HANDER_KEY])),
    }
    # Känner (hjälp till andra delar ev.)
    base["Känner"] = int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) + int(base[LBL_NV]) + int(base[LBL_NF])
    # meta
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    # max för “känner sammanlagt”
    base["MAX_PAPPAN"] = int(CFG["MAX_PAPPAN"])
    base["MAX_GRANNAR"] = int(CFG["MAX_GRANNAR"])
    base["MAX_NILS_VANNER"] = int(CFG["MAX_NILS_VANNER"])
    base["MAX_NILS_FAMILJ"] = int(CFG["MAX_NILS_FAMILJ"])
    return base

# =========================
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

_base = build_base_from_inputs()
try:
    preview = calc_row_values(_base, _base["_rad_datum"], _base["_fodelsedatum"], _base["_starttid"])
except TypeError:
    preview = calc_row_values(_base, _base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# “Tid/kille” i liven = bas + händer
tid_kille_total_sek = float(preview.get("Tid per kille (sek)", 0)) + float(preview.get("Händer per kille (sek)", 0))
tid_kille_total_str = _mmss(tid_kille_total_sek)

# Egen raw totalsiffra (kontroll)
tot_men_including = (
    int(_base.get("Män",0)) + int(_base.get("Svarta",0)) +
    int(_base.get(LBL_PAPPAN,0)) + int(_base.get(LBL_GRANNAR,0)) +
    int(_base.get(LBL_NV,0)) + int(_base.get(LBL_NF,0)) +
    int(_base.get(LBL_BEK,0)) + int(_base.get(LBL_ESK,0)) +
    int(_base.get("Bonus deltagit",0)) + int(_base.get("Personal deltagit",0))
)

# Datum/ålder
rad_datum = preview.get("Datum", _base["Datum"])
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
    st.metric("Tid/kille", tid_kille_total_str)
    st.metric("Tid/kille (sek)", int(tid_kille_total_sek))
with c3:
    st.metric("Klockan", preview.get("Klockan","-"))
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

# Hångel/Sug/Händer
c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer (sek/kille)", int(preview.get("Händer per kille (sek)", 0)))
with c6:
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

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
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(_base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(_base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(_base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(_base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(_base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(_base.get(LBL_ESK,0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

st.caption("Obs: Tid/kille i liven inkluderar händer. Älskar/Sover ingår inte i scenens 'Summa tid', men lägger på klockan.")

# =========================
# Spara lokalt / Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _post_save_bookkeeping(preview_row: dict):
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview_row.get(col,0))
        _add_hist_value(col, v)
    # bonus kvar minskas med inmatat “Bonus deltagit”
    try:
        used = int(preview_row.get("Bonus deltagit",0))
    except:
        used = 0
    st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(0, int(st.session_state[CFG_KEY]["BONUS_AVAILABLE"]) - used)
    # bumpa sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        # lägg med Profil + Händer aktiv i raden
        preview["Profil"] = st.session_state[CFG_KEY]["PROFIL_NAMN"]
        preview["Händer aktiv"] = int(bool(st.session_state[HANDER_KEY]))
        st.session_state[ROWS_KEY].append(preview)
        _post_save_bookkeeping(preview)
        st.success("✅ Sparad i minnet.")

def save_to_sheets(row_dict: dict):
    row_to_save = dict(row_dict)
    row_to_save["Profil"] = st.session_state[CFG_KEY]["PROFIL_NAMN"]
    row_to_save["Händer aktiv"] = int(bool(st.session_state[HANDER_KEY]))
    save_row_to_data(row_to_save)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            save_to_sheets(preview)
            st.success("✅ Sparad till Google Sheets (flik: Data).")
            st.session_state[ROWS_KEY].append(preview)
            _post_save_bookkeeping(preview)
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

# =========================
# Statistik (om modul finns)
# =========================
st.markdown("---")
st.subheader("📊 Statistik")
rows_df = pd.DataFrame(st.session_state[ROWS_KEY]) if st.session_state[ROWS_KEY] else pd.DataFrame()
if _compute_stats is None:
    st.info("statistik.py hittades inte – lägg filen i samma mapp med funktionen compute_stats(rows_df, cfg).")
else:
    try:
        stats = _compute_stats(rows_df, st.session_state[CFG_KEY])
        if not stats:
            st.info("Ingen statistik att visa ännu.")
        else:
            for k,v in stats.items():
                st.write(f"**{k}**: {v}")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
