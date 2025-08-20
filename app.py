# app.py
import streamlit as st
import pandas as pd
import random
import json
from datetime import date, time, datetime, timedelta

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets)")

# ======== Import av beräkning (din modul) ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# ======== Import statistik (om finns) ========
try:
    from statistik import compute_stats
    HAS_STATS = True
except Exception:
    HAS_STATS = False

# ======== State-nycklar ========
CFG_KEY        = "CFG"           # alla config + etiketter + profil
ROWS_KEY       = "ROWS"          # sparade rader (lokalt minne) för vald profil
HIST_MM_KEY    = "HIST_MINMAX"   # min/max per fält
SCENEINFO_KEY  = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"      # rullist-valet
PROFILE_KEY    = "PROFILE"       # vald profil
PROFILE_LOADED = "PROFILE_LOADED" # senaste inlästa profilnamn

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

def _ensure_ws(ss, title, rows=4000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _get_profiles(ss):
    # Läs fliken "Profil" kolumn A (namnlist)
    try:
        ws = _ensure_ws(ss, "Profil", rows=100, cols=3)
        rows = ws.col_values(1)
        rows = [r.strip() for r in rows if r.strip()]
        # ta bort ev. header
        if rows and rows[0].lower() in ("profil","namn","name"):
            rows = rows[1:]
        return rows
    except Exception:
        return []

# =========================
# Init state
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d  = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # start/födelse
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),

            # ekonomi/produktion
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,

            # bonus
            "BONUS_AVAILABLE": 500,
            "BONUS_RATE_PCT": 1.0,   # justerbar %

            # Eskilstuna-intervall
            "ESK_MIN": 20,
            "ESK_MAX": 40,

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

            # BMI (profilhöjd + kumulativa samples)
            "BMI_HOJD_M": 1.64,
            "BMI_SAMPLES_SUM": 0.0,
            "BMI_SAMPLES_COUNT": 0,

            # Aktiv profil
            "SUBJECT_NAME": "Malin",
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""
    if PROFILE_LOADED not in st.session_state:
        st.session_state[PROFILE_LOADED] = ""

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

CFG = st.session_state[CFG_KEY]

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
        st.session_state[HIST_MM_KEY][col] = (min(mn, v), max(mx, v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm:
        return mm
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
        mm = (0, 0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo:
        hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# =========================
# Profil-inläsning/sparning
# =========================
def load_profile_data_and_settings(profile_name: str):
    """Läs in Inställningar + Data för vald profil, bygg min/max."""
    try:
        ss = _get_gspread_client()
    except Exception as e:
        st.error(f"Kunde inte koppla mot Sheets: {e}")
        return

    # Försök hitta inställningar i <Profil>_Inst -> <Profil> -> Inställningar
    inst_ws = None
    for title in (f"{profile_name}_Inst", f"{profile_name}", "Inställningar"):
        try:
            inst_ws = _ensure_ws(ss, title)
            break
        except Exception:
            inst_ws = None

    if inst_ws is not None:
        try:
            data = inst_ws.get_all_records()
            # Tillåt både tabell med Key/Value och ren key-value (första två kolumner)
            if data and "Key" in data[0] and "Value" in data[0]:
                kv_pairs = [(row["Key"], row["Value"]) for row in data if row.get("Key")]
            else:
                # som fri tabell → använd get_all_values()
                raw = inst_ws.get_all_values()
                kv_pairs = []
                for row in raw:
                    if len(row) >= 2 and row[0]:
                        kv_pairs.append((row[0].strip(), row[1]))
            # skriv in i CFG med typning
            for key, val in kv_pairs:
                if key in ("startdatum", "fodelsedatum"):
                    try:
                        y, m, d = [int(x) for x in str(val).split("-")]
                        CFG[key] = date(y, m, d)
                    except:
                        pass
                elif key in CFG:
                    # autodetect int/float/bool
                    s = str(val)
                    if s.lower() in ("true","false"):
                        CFG[key] = (s.lower() == "true")
                    else:
                        try:
                            if "." in s:
                                CFG[key] = float(s)
                            else:
                                CFG[key] = int(s)
                        except:
                            CFG[key] = s
                else:
                    # ok att lägga nycklar framåt
                    CFG[key] = val
        except Exception as e:
            st.warning(f"Kunde inte läsa inställningar för {profile_name}: {e}")

    # Data från <Profil>_Data -> Data
    rows_ws = None
    for title in (f"{profile_name}_Data", "Data"):
        try:
            rows_ws = _ensure_ws(ss, title)
            break
        except Exception:
            rows_ws = None

    st.session_state[ROWS_KEY] = []
    st.session_state[HIST_MM_KEY] = {}

    if rows_ws is not None:
        try:
            recs = rows_ws.get_all_records()
            st.session_state[ROWS_KEY] = recs or []
        except Exception as e:
            st.warning(f"Kunde inte läsa Data för {profile_name}: {e}")

    # Bygg min/max med gällande etiketter
    LBL_PAPPAN = CFG["LBL_PAPPAN"]
    LBL_GRANNAR = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]
    LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_BEK = CFG["LBL_BEKANTA"]
    LBL_ESK = CFG["LBL_ESK"]

    for r in st.session_state[ROWS_KEY]:
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
            _add_hist_value(col, r.get(col, 0))

    st.session_state[SCENEINFO_KEY] = _current_scene_info()
    st.session_state[PROFILE_LOADED] = profile_name
    st.success(f"✅ Profil '{profile_name}' inläst.")

def save_settings_for_profile(profile_name: str):
    """Spara alla CFG till <Profil>_Inst (nyckel, värde)."""
    ss = _get_gspread_client()
    wsI = _ensure_ws(ss, f"{profile_name}_Inst")
    rows = []
    for k, v in CFG.items():
        if isinstance(v, (date, datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([k, str(v)])
    wsI.clear()
    wsI.update("A1", [["Key","Value"]])
    if rows:
        wsI.update(f"A2:B{len(rows)+1}", rows)
    st.success("✅ Inställningar sparade.")

def save_row_to_profile_sheet(profile_name: str, row_dict: dict):
    """Spara rad till <Profil>_Data. Skapar header om saknas."""
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, f"{profile_name}_Data")
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)
    st.success("✅ Sparad till Google Sheets.")

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder)
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
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        # övriga källor/personaldeltagit 0

    elif s == "Vila på jobbet":
        # enligt önskemål: Vila ska ge 0 prenumeranter/kostnader/lön (hanteras i kalk),
        # men vi kan ändå slumpa lite fält om så önskas – här sätter vi dem 0
        for key in ["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
                    "in_pappan","in_bekanta","in_grannar","in_nils_vanner","in_nils_familj",
                    "in_eskilstuna"]:
            st.session_state[key] = 0
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag – slumpa källor och sexuella fält enligt tidigare krav
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        # bonus/personaldeltagit anger du själv

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel
# =========================
with st.sidebar:
    st.header("Google Sheets")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    profiles = []
    try:
        ss = _get_gspread_client()
        profiles = _get_profiles(ss)
    except Exception:
        profiles = []

    st.markdown("---")
    st.subheader("Profil")
    if profiles:
        current = st.session_state.get(PROFILE_KEY, profiles[0])
        st.session_state[PROFILE_KEY] = st.selectbox("Välj profil", profiles, index=profiles.index(current) if current in profiles else 0)
        # ladda aut. om bytt
        if st.session_state[PROFILE_KEY] != st.session_state.get(PROFILE_LOADED, ""):
            load_profile_data_and_settings(st.session_state[PROFILE_KEY])
    else:
        st.info("Ingen flik 'Profil' hittad eller tom. Skapa den i Google Sheets.")

    st.markdown("---")
    st.subheader("Inställningar (lokalt)")
    CFG["SUBJECT_NAME"] = st.text_input("Namn (etikett som sprids)", value=CFG["SUBJECT_NAME"])
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")
    CFG["BONUS_RATE_PCT"] = st.number_input("Bonus-killar % av prenumeranter", min_value=0.0, max_value=100.0, step=0.1, value=float(CFG["BONUS_RATE_PCT"]))

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
    st.subheader("BMI-inställningar")
    CFG["BMI_HOJD_M"]       = st.number_input("Längd (meter)", min_value=0.5, max_value=2.5, step=0.01, value=float(CFG["BMI_HOJD_M"]))
    st.caption("BM mål beräknas som snitt av slump [12–18] över alla prenumeranter (kumulativt).")
    st.caption(f"Kumulativt: sum={CFG['BMI_SAMPLES_SUM']:.1f}, count={int(CFG['BMI_SAMPLES_COUNT'])}")

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.experimental_rerun()

    st.markdown("---")
    if st.button("💾 Spara inställningar för vald profil"):
        try:
            save_settings_for_profile(st.session_state.get(PROFILE_KEY, ""))
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

# =========================
# Inmatning (etiketter från inställningar), exakt ordning
# =========================
st.subheader(f"Input (exakt ordning) – {CFG['SUBJECT_NAME']}")
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
# Bygg basrad från inputs
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
        "PROD_STAFF": int(CFG["PROD_STAFF"])
    }
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
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

_base = build_base_from_inputs()
try:
    preview = calc_row_values(_base, _base["_rad_datum"], _base["_fodelsedatum"], _base["_starttid"])
except TypeError:
    preview = calc_row_values(_base, _base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# Tvinga “Vila”-rader att ge 0 pren/intäkter/kostnader/lön (enligt dina krav)
typ_txt = _base.get("Typ","")
if "Vila" in typ_txt:
    for k in ("Prenumeranter","Intäkter","Utgift män","Lön Malin","Vinst"):
        preview[k] = 0 if "Intäkter" not in k else 0.0

# BMI-mål/Målvikt (live, beror på ackumulerad samples + ev. nya när vi sparar)
bmi_avg = (CFG["BMI_SAMPLES_SUM"] / CFG["BMI_SAMPLES_COUNT"]) if CFG["BMI_SAMPLES_COUNT"] > 0 else 0.0
mal_vikt = bmi_avg * (CFG["BMI_HOJD_M"] ** 2)

# Överkant: datum/veckodag + ålder
rad_datum = preview.get("Datum", _base["Datum"])
veckodag = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try:
        _d = datetime.fromisoformat(rad_datum).date()
    except Exception:
        _d = datetime.today().date()
else:
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

st.markdown(f"**🎯 BM mål:** {bmi_avg:.2f} • **Mål vikt:** {mal_vikt:.2f} kg")

# Käll-breakout med etiketter
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(_base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(_base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(_base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(_base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(_base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(_base.get(LBL_ESK,0)))

st.caption("Obs: Älskar/Sover-med-tider ingår inte i scenens 'Summa tid', men läggs på klockan via beräkningen i berakningar.py.")

# =========================
# Spara lokalt / Spara till profilens Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _update_hist_from_row(row):
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(row.get(col, 0))
        _add_hist_value(col, v)

def _update_bonus_and_bmi_after_save(preview_row, is_vila: bool):
    """Uppdatera BONUS_AVAILABLE + BMI-ack baserat på nya prenumeranter."""
    try:
        new_subs = int(preview_row.get("Prenumeranter", 0))
    except:
        new_subs = 0

    # Vila-rader ska inte bidra
    if is_vila:
        new_subs = 0

    # Bonus-killar
    rate = float(CFG.get("BONUS_RATE_PCT", 1.0))
    new_bonus = int((new_subs * rate) // 100)  # heltal
    used_bonus = int(preview_row.get("Bonus deltagit", 0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + new_bonus - used_bonus)

    # BMI-ack (slump 12–18 för varje ny prenumerant)
    if new_subs > 0:
        # Summan av N likformiga 12..18 ≈ N * medel (15), men vi drar exakt:
        # för performance drar vi i klumpar:
        s = 0.0
        for _ in range(new_subs):
            s += random.uniform(12.0, 18.0)
        CFG["BMI_SAMPLES_SUM"]   = float(CFG.get("BMI_SAMPLES_SUM", 0.0)) + s
        CFG["BMI_SAMPLES_COUNT"] = int(CFG.get("BMI_SAMPLES_COUNT", 0)) + new_subs

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _update_hist_from_row(preview)
        _is_vila = "Vila" in _base.get("Typ","")
        _update_bonus_and_bmi_after_save(preview, _is_vila)
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad i minnet.")

def save_to_sheets_current_profile(preview_row: dict):
    prof = st.session_state.get(PROFILE_KEY, "").strip()
    if not prof:
        raise RuntimeError("Ingen profil vald.")
    save_row_to_profile_sheet(prof, preview_row)

with cR:
    if st.button("📤 Spara raden till Google Sheets (profil)"):
        try:
            save_to_sheets_current_profile(preview)
            # spegla lokalt uppdateringar
            st.session_state[ROWS_KEY].append(preview)
            _update_hist_from_row(preview)
            _is_vila = "Vila" in _base.get("Typ","")
            _update_bonus_and_bmi_after_save(preview, _is_vila)
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
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
if HAS_STATS:
    try:
        rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
        stats = compute_stats(rows_df, CFG)
        with st.expander("Visa statistik"):
            if isinstance(stats, dict):
                for k, v in stats.items():
                    st.write(f"**{k}:** {v}")
            else:
                st.write(stats)
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
else:
    st.info("Hittade inte modulen statistik.py (compute_stats). Lägg den i samma mapp om du vill visa statistik.")
