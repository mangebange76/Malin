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

# ======== Nycklar i state ========
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
    "in_hander_aktiv",   # NYTT: Händer aktiv
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

            # Bonus-styrning (kan du ändra senare)
            "BONUS_PCT": 1.0,  # procent av prenumeranter som ger “bonus killar”
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
        "in_sover":0, "in_alskar":0, "in_nils":0,
        "in_hander_aktiv": 1,
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))

    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# =========================
# Hjälpare: min/max + slump (1..max)
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
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_up_to_max(colname: str):
    _, hi = _minmax_from_hist(colname)
    return random.randint(1, hi) if hi > 0 else 0

# =========================
# Läs/Spara – Profil & Data_<Profil>
# =========================
def list_profiles():
    """Läs profiler från fliken 'Profil' kol A."""
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, "Profil")
        names = [x.strip() for x in ws.col_values(1) if x and x.strip()]
        # ta bort potentiell header
        if names and names[0].lower() in ("profil","namn","name"):
            names = names[1:]
        return names
    except Exception as e:
        st.warning(f"Kunde inte läsa profil-lista: {e}")
        return []

def load_profile_settings(profile_name: str):
    """Läser inställningar från bladet <Profil> (Key/Value eller tabell)."""
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, profile_name)
        vals = ws.get_all_values()
        if not vals:
            st.info(f"Inga inställningar i bladet '{profile_name}'.")
            return
        # Om första raden är ["Key","Value"]
        header = [h.strip() for h in vals[0]] if vals else []
        rows = vals[1:] if header else vals

        new_cfg = {}
        if header and len(header) >= 2 and header[0].lower()=="key" and header[1].lower()=="value":
            for row in rows:
                if len(row) < 2: continue
                k = row[0].strip()
                v = row[1].strip()
                if not k: continue
                new_cfg[k] = v
        else:
            # anta 2 kolumner: Nyckel, Värde
            for row in vals:
                if len(row) < 2: continue
                k = row[0].strip()
                v = row[1].strip()
                if not k: continue
                new_cfg[k] = v

        # Skriv in i st.session_state[CFG_KEY] med typning
        for k,v in new_cfg.items():
            if k in ("startdatum","fodelsedatum"):
                try:
                    y,m,d = [int(x) for x in v.split("-")]
                    st.session_state[CFG_KEY][k] = date(y,m,d)
                except:
                    pass
            elif k in st.session_state[CFG_KEY]:
                try:
                    if v.lower() in ("true","false"):
                        st.session_state[CFG_KEY][k] = (v.lower()=="true")
                    elif "." in v:
                        st.session_state[CFG_KEY][k] = float(v)
                    else:
                        st.session_state[CFG_KEY][k] = int(v)
                except:
                    st.session_state[CFG_KEY][k] = v
            else:
                st.session_state[CFG_KEY][k] = v

        st.success(f"✅ Inställningar inlästa för profil '{profile_name}'.")
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar för profil '{profile_name}': {e}")

def load_profile_data(profile_name: str):
    """Läser data från fliken 'Data_<Profil>' – fallback: global 'Data' filtrerad på kolumn 'Profil'."""
    try:
        ss = _get_gspread_client()
        try:
            ws = _ensure_ws(ss, f"Data_{profile_name}")
            recs = ws.get_all_records()
        except Exception:
            # fallback – global Data, filtrera
            ws = _ensure_ws(ss, "Data")
            recs_all = ws.get_all_records()
            # filtrera på 'Profil'
            if recs_all and "Profil" in recs_all[0]:
                recs = [r for r in recs_all if str(r.get("Profil","")).strip()==profile_name]
            else:
                recs = recs_all

        st.session_state[ROWS_KEY] = recs or []
        # bygg min/max
        st.session_state[HIST_MM_KEY] = {}
        cfg = st.session_state[CFG_KEY]
        for r in st.session_state[ROWS_KEY]:
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"],
                        cfg["LBL_NILS_FAMILJ"], cfg["LBL_BEKANTA"], cfg["LBL_ESK"]]:
                _add_hist_value(col, r.get(col, 0))
        # bump sceninfo
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success(f"✅ Data inläst för profil '{profile_name}'.")
    except Exception as e:
        st.error(f"Kunde inte läsa data för profil '{profile_name}': {e}")

def save_row_to_profile_data(profile_name: str, row_dict: dict):
    """Sparar en rad till 'Data_<Profil>' och säkerställer ‘Profil’-kolumnen."""
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, f"Data_{profile_name}")
    # Header
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        if "Profil" not in header:
            header = ["Profil"] + header
        ws.update("A1", [header])

    # Se till att 'Profil' finns i header och värden
    if "Profil" not in header:
        header = ["Profil"] + header
        ws.update("A1", [header])

    # Mappa row_dict -> header
    values_map = dict(row_dict)
    values_map["Profil"] = profile_name
    values = [values_map.get(col, "") for col in header]
    ws.append_row(values)

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder & händer aktiv)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_aktiv": st.session_state.get("in_hander_aktiv",1)}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        return

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_up_to_max("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_up_to_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
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
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_BEKANTA"],"in_bekanta"),
                      (CFG["LBL_GRANNAR"],"in_grannar"),(CFG["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (CFG["LBL_NILS_FAMILJ"],"in_nils_familj")]:
            st.session_state[key] = _rand_up_to_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag, slumpa allt enligt din lista
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_up_to_max(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_up_to_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    # uppdatera sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    profillista = list_profiles()
    sel = st.selectbox("Välj profil", options=profillista or ["(saknas)"], index=0)
    if sel != "(saknas)":
        st.session_state[PROFILE_KEY] = sel

    cA, cB = st.columns(2)
    with cA:
        if st.button("📥 Läs in inställningar (profil)"):
            if st.session_state[PROFILE_KEY]:
                load_profile_settings(st.session_state[PROFILE_KEY])
    with cB:
        if st.button("📥 Läs in data (profil)"):
            if st.session_state[PROFILE_KEY]:
                load_profile_data(st.session_state[PROFILE_KEY])

    st.markdown("---")
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_PCT"]    = st.number_input("Bonus-killar % av prenumeranter", min_value=0.0, max_value=100.0, value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)

    st.caption(f"Bonus killar kvar (info): {int(CFG['BONUS_AVAILABLE'])}")

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
        "Välj scen",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

    st.markdown("---")
    st.subheader("Google Sheets status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Spara inställningar (key/value) till profil-bladet
    if st.button("💾 Spara inställningar (profil-blad)"):
        try:
            if not st.session_state[PROFILE_KEY]:
                st.warning("Välj en profil först.")
            else:
                ss = _get_gspread_client()
                wsI = _ensure_ws(ss, st.session_state[PROFILE_KEY])
                rows = []
                for k,v in st.session_state[CFG_KEY].items():
                    if isinstance(v, (date, datetime)):
                        v = v.strftime("%Y-%m-%d")
                    rows.append([k, str(v)])
                wsI.clear()
                wsI.update("A1", [["Key","Value"]])
                if rows:
                    wsI.update(f"A2:B{len(rows)+1}", rows)
                st.success("✅ Inställningar sparade i profil-bladet.")
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
        "Avgift":  float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"]),

        # etikett-nycklar för berakningar-acceptans
        "LBL_PAPPAN": LBL_PAPPAN,
        "LBL_GRANNAR": LBL_GRANNAR,
        "LBL_NILS_VANNER": LBL_NV,
        "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK,
        "LBL_ESK": LBL_ESK,

        # händer på radnivå
        "Händer aktiv": st.session_state.get("in_hander_aktiv",1),
    }
    # Känner = summa av käll-etiketter (visas också i live)
    base["Känner"] = (
        int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) +
        int(base[LBL_NV]) + int(base[LBL_NF])
    )
    # meta till beräkning
    base["_rad_datum"]    = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    # max för statistik (om du vill nyttja i beräkn.)
    base["MAX_PAPPAN"]      = int(CFG["MAX_PAPPAN"])
    base["MAX_GRANNAR"]     = int(CFG["MAX_GRANNAR"])
    base["MAX_NILS_VANNER"] = int(CFG["MAX_NILS_VANNER"])
    base["MAX_NILS_FAMILJ"] = int(CFG["MAX_NILS_FAMILJ"])
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

# Tot män (rå kontroll)
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

# Hångel / Suger / Händer
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
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

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

st.caption("Obs: Älskar/Sover-med-tider ingår inte i scenens 'Summa tid', men lägger på klockan.")

# =========================
# Spara lokalt & till profilens Data-blad
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _after_save_housekeeping(preview_row):
    # uppdatera min/max baserat på det som sparats
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview_row.get(col,0))
        _add_hist_value(col, v)
    # minska bonus kvar med "Bonus deltagit"
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - int(preview_row.get("Bonus deltagit",0)))
    # nästa scen
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _after_save_housekeeping(preview)
        st.success("✅ Sparad i minnet.")

def _make_row_for_sheet(preview_row: dict):
    """Säkerställ att våra etiketter och nycklar följer samma form som i live/Data."""
    out = dict(preview_row)
    # include etikettkolumner om saknas
    for k,v in {
        "LBL_PAPPAN": LBL_PAPPAN, "LBL_GRANNAR": LBL_GRANNAR,
        "LBL_NILS_VANNER": LBL_NV, "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK, "LBL_ESK": LBL_ESK
    }.items():
        out.setdefault(k, v)
    return out

with cR:
    if st.button("📤 Spara raden till Google Sheets (profilens Data)"):
        try:
            if not st.session_state[PROFILE_KEY]:
                st.warning("Välj en profil först.")
            else:
                row_out = _make_row_for_sheet(preview)
                save_row_to_profile_data(st.session_state[PROFILE_KEY], row_out)
                st.success(f"✅ Sparad till fliken Data_{st.session_state[PROFILE_KEY]}.")
                # spegla även lokalt
                st.session_state[ROWS_KEY].append(preview)
                _after_save_housekeeping(preview)
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
# Statistik (valfritt – om modul finns)
# =========================
try:
    from statistik import compute_stats
    st.markdown("---")
    st.subheader("📊 Statistik")
    rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
    if not rows_df.empty:
        stats = compute_stats(rows_df, st.session_state[CFG_KEY])
        for k,v in stats.items():
            st.write(f"**{k}:** {v}")
    else:
        st.info("Ingen data att visa statistik för.")
except Exception as e:
    st.caption(f"(Statistik-modul ej aktiv: {e})")
