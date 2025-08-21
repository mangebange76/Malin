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
st.title("Malin – produktionsapp (profiler + lokalt + Sheets via SHEET_URL)")

# ======== State-nycklar ========
CFG_KEY        = "CFG"            # alla config + etiketter
ROWS_KEY       = "ROWS"           # sparade rader (lokalt minne, aktuell profil)
HIST_MM_KEY    = "HIST_MINMAX"    # min/max per fält (för slump)
SCENEINFO_KEY  = "CURRENT_SCENE"  # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"       # rullist-valet
PROFILE_KEY    = "PROFILE"        # valt profilt namn

# ======== Import av beräkning ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# (valfri) statistik
try:
    from statistik import compute_stats as compute_stats_df  # för DataFrame
except Exception:
    compute_stats_df = None

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

def _find_ws_case_insensitive(ss, wanted_title: str):
    """Returnera worksheet som matchar wanted_title (case-insensitive, trim)."""
    wt = wanted_title.strip().lower()
    for ws in ss.worksheets():
        if ws.title.strip().lower() == wt:
            return ws
    return None

def _ensure_ws(ss, title, rows=6000, cols=150):
    import gspread
    ws = _find_ws_case_insensitive(ss, title)
    if ws:
        return ws
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _get_profiles():
    """Läs profilnamn från fliken 'Profil' (kolumn A)."""
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, "Profil", rows=100, cols=5)
        vals = ws.col_values(1)
        return [v.strip() for v in vals if v and v.strip().lower() != "profil"]
    except Exception as e:
        st.warning(f"Kunde inte läsa profil-lista: {e}")
        return []

def _profile_settings_sheet_name(profile: str) -> str:
    # Vi använder ett blad med samma namn som profilen (Key/Value)
    return profile

def _profile_data_sheet_name(profile: str) -> str:
    # Profilens datablad – separat per profil
    return f"Data_{profile}"

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
    "in_nils",
    "in_hander_aktiv",
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
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""  # väljs i sidopanel
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # start/födelse – dina default
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,
            "BONUS_AVAILABLE": 500,
            "BONUS_PCT":    1.0,  # % av prenumeranter som läggs som bonus killar
            "ESK_MIN": 20, "ESK_MAX": 40,

            # Maxvärden (källor)
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,

            # Etiketter (kan döpas om i sidopanel)
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"

    # default för tidsfält m.m.
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander_aktiv":1
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
    # bygg från lokala ROWS om saknas
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

def _rand_hist_1_to_max(colname: str):
    """Slumpa mellan 1..max (om max>0), annars 0."""
    _, hi = _minmax_from_hist(colname)
    return random.randint(1, hi) if hi > 0 else 0

# =========================
# Scenario-fill (Hämta värden)
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_aktiv":st.session_state.get("in_hander_aktiv",1)}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist_1_to_max("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist_1_to_max("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                      ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                      ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # Ekonomi/hårdhet/bonus hanteras vid spar (sätts till 0 där)

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag enligt din beskrivning
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist_1_to_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        # Ekonomi/hårdhet/bonus hanteras vid spar

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel – Profil & Inställningar
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    profiles = _get_profiles()
    selected = st.selectbox("Välj profil", options=["—"] + profiles, index=0)
    if selected != "—":
        st.session_state[PROFILE_KEY] = selected

    st.markdown("---")
    st.subheader("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_PCT"]    = st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0, value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)

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
    st.subheader("Google Sheets")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Läs in INSTÄLLNINGAR för vald profil
    def _load_profile_settings(profile: str):
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, _profile_settings_sheet_name(profile))
        vals = ws.get_all_values()
        if not vals:
            return
        # anta Key/Value på två första kolumnerna
        for row in vals[1:] if vals and vals[0] and "key" in vals[0][0].lower() else vals:
            if len(row) >= 2 and row[0]:
                key = row[0].strip()
                val = row[1]
                if key in ("startdatum","fodelsedatum"):
                    try:
                        y,m,d = [int(x) for x in val.split("-")]
                        st.session_state[CFG_KEY][key] = date(y,m,d)
                    except:
                        pass
                elif key in st.session_state[CFG_KEY]:
                    try:
                        if "." in val:
                            st.session_state[CFG_KEY][key] = float(val)
                        else:
                            st.session_state[CFG_KEY][key] = int(val)
                    except:
                        st.session_state[CFG_KEY][key] = val
                else:
                    st.session_state[CFG_KEY][key] = val

    # Läs in DATA för vald profil (Data_<Profil>)
    def _load_profile_data(profile: str):
        ss = _get_gspread_client()
        # primärt: Data_<profil>
        ws = _find_ws_case_insensitive(ss, _profile_data_sheet_name(profile))
        rows = []
        if ws:
            rows = ws.get_all_records()
        else:
            # fallback: global Data med kolumn Profil
            wsG = _find_ws_case_insensitive(ss, "Data")
            if wsG:
                all_rows = wsG.get_all_records()
                rows = [r for r in all_rows if str(r.get("Profil","")).strip().lower()==profile.strip().lower()]
        st.session_state[ROWS_KEY] = rows or []
        # bygg historik-min/max
        st.session_state[HIST_MM_KEY] = {}
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

    # Knappar
    colA, colB = st.columns(2)
    with colA:
        if st.button("📥 Läs in profilens inställningar"):
            if st.session_state[PROFILE_KEY]:
                try:
                    _load_profile_settings(st.session_state[PROFILE_KEY])
                    st.success("✅ Profilens inställningar inlästa.")
                except Exception as e:
                    st.error(f"Kunde inte läsa inställningar: {e}")
            else:
                st.warning("Välj en profil först.")
    with colB:
        if st.button("📥 Läs in profilens data"):
            if st.session_state[PROFILE_KEY]:
                try:
                    _load_profile_data(st.session_state[PROFILE_KEY])
                    st.success("✅ Profilens data inläst.")
                except Exception as e:
                    st.error(f"Kunde inte läsa data: {e}")
            else:
                st.warning("Välj en profil först.")

    # Spara inställningar till profilens blad (Key/Value)
    if st.button("💾 Spara inställningar till profilblad"):
        try:
            profile = st.session_state[PROFILE_KEY]
            if not profile:
                st.warning("Välj en profil först.")
            else:
                ss = _get_gspread_client()
                wsI = _ensure_ws(ss, _profile_settings_sheet_name(profile))
                rows = []
                for k,v in st.session_state[CFG_KEY].items():
                    if isinstance(v, (date, datetime)):
                        v = v.strftime("%Y-%m-%d")
                    rows.append([k, str(v)])
                wsI.clear()
                wsI.update("A1", [["Key","Value"]])
                if rows:
                    wsI.update(f"A2:B{len(rows)+1}", rows)
                st.success("✅ Inställningar sparade till profilblad.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

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
        "in_bonus_deltagit","in_personal_deltagit",
        "in_nils","in_hander_aktiv"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

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

        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils":    st.session_state["in_nils"],
        "Händer aktiv": st.session_state["in_hander_aktiv"],

        "Avgift":  float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"])
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

# Egen “Totalt Män (inkl källor/bonus/personal/Eskilstuna)” – rå summering för din kontroll
tot_men_including = (
    int(base.get("Män",0)) + int(base.get("Svarta",0)) +
    int(base.get(LBL_PAPPAN,0)) + int(base.get(LBL_GRANNAR,0)) +
    int(base.get(LBL_NV,0)) + int(base.get(LBL_NF,0)) +
    int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) +
    int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
)

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

# Hångel/Sug/Händer
c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
with c6:
    st.metric("Händer aktiv", int(preview.get("Händer aktiv", 0)))
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
    st.metric("Utgift män", f"${float(preview.get('Utgift män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

# Käll-brakeout med dina etiketter + extra totalsiffra
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(base.get(LBL_ESK,0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men lägger på klockan.")

# =========================
# Spara lokalt
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _update_hist_and_scene(preview_row: dict):
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview_row.get(col,0))
        _add_hist_value(col, v)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

def _after_save_housekeeping(preview_row: dict, is_vila: bool):
    # Bonus kvar: olika logik beroende på scenario
    bonus_left = int(st.session_state[CFG_KEY].get("BONUS_AVAILABLE", 0))
    bonus_pct  = float(st.session_state[CFG_KEY].get("BONUS_PCT", 1.0))
    new_subs   = int(preview_row.get("Prenumeranter", 0))
    bonus_used = int(preview_row.get("Bonus deltagit", 0))

    if is_vila:
        # Endast minus deltagit
        bonus_left = max(0, bonus_left - bonus_used)
    else:
        # Lägg till % av prenumeranter, minus deltagit
        bonus_left = max(0, bonus_left + round(new_subs * (bonus_pct/100.0)) - bonus_used)

    st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = bonus_left

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _update_hist_and_scene(preview)
        # vila = om scenario är vila på jobbet / i hemmet → justera bara minus
        scenario_now = st.session_state.get(SCENARIO_KEY,"")
        is_vila = scenario_now in ("Vila på jobbet","Vila i hemmet (dag 1–7)")
        _after_save_housekeeping(preview, is_vila)
        st.success("✅ Sparad i minnet.")

# =========================
# Spara till Google Sheets (profilblad)
# =========================
def save_row_to_profile_sheet(profile: str, row_dict: dict):
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, _profile_data_sheet_name(profile))

    # säkerställ header + union av nya fält
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys()) + ["Profil"]
        ws.update("A1", [header])
    else:
        # utöka header om nya fält tillkommit
        need_extend = False
        for k in list(row_dict.keys()) + ["Profil"]:
            if k not in header:
                header.append(k); need_extend = True
        if need_extend:
            ws.update("A1", [header])

    # mappa i headerordning
    row_out = [row_dict.get(col, "") for col in header]
    ws.append_row(row_out)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            profile = st.session_state.get(PROFILE_KEY,"").strip()
            if not profile:
                st.warning("Välj en profil först.")
            else:
                # Skriv även Profil-namn in i raden (behövs om man nånsin vill aggregera globalt)
                preview_with_profile = dict(preview)
                preview_with_profile["Profil"] = profile

                save_row_to_profile_sheet(profile, preview_with_profile)

                st.success(f"✅ Sparad till Google Sheets (flik: { _profile_data_sheet_name(profile) }).")
                # spegla lokalt + hist + bonus
                st.session_state[ROWS_KEY].append(preview)
                _update_hist_and_scene(preview)
                scenario_now = st.session_state.get(SCENARIO_KEY,"")
                is_vila = scenario_now in ("Vila på jobbet","Vila i hemmet (dag 1–7)")
                _after_save_housekeeping(preview, is_vila)
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader + (valfri) Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

if compute_stats_df is not None and st.session_state[ROWS_KEY]:
    try:
        stats = compute_stats_df(pd.DataFrame(st.session_state[ROWS_KEY]), st.session_state[CFG_KEY])
        st.markdown("---")
        st.subheader("📊 Statistik (enkel)")
        for k,v in stats.items():
            st.write(f"**{k}:** {v}")
    except Exception as e:
        st.warning(f"Kunde inte beräkna statistik: {e}")
