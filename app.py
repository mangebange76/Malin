# app.py
import streamlit as st
import pandas as pd
import json
import random
from datetime import date, time, datetime, timedelta

# ---- Google Sheets ----
import gspread
from google.oauth2.service_account import Credentials

# ---- Dina moduler ----
from berakningar import calc_row_values         # redan byggd med alla beräkningar
from statistik import compute_stats             # ska finnas i samma mapp

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")

# =========================
# Nycklar i session
# =========================
CFG_KEY        = "CFG"             # alla config + etiketter + BM-ackumulatorer
ROWS_KEY       = "ROWS"            # lokalt cache: profilens rader
HIST_MM_KEY    = "HIST_MINMAX"     # min/max per kolumn (för slump)
PROFILE_KEY    = "PROFILE"         # valt prof-namn
SCENEINFO_KEY  = "CURRENT_SCENE"   # (nr, datum, veckodag)
SCENARIO_KEY   = "SCENARIO"        # rullist-scenario

# =========================
# Hjälpare: Google Sheets
# =========================
def _get_client_and_ss():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return client, ss

def _ensure_ws(ss, title, rows=5000, cols=120):
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _read_sheet_records(ws):
    # get_all_records() → list[dict]; tomt → []
    try:
        return ws.get_all_records()
    except Exception:
        return []

def _write_keyvals(ws, dct: dict):
    # Rensar och skriver key/value-tabell
    ws.clear()
    rows = [["Key","Value"]]
    for k, v in dct.items():
        if isinstance(v, (date, datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([k, str(v)])
    ws.update(f"A1:B{len(rows)}", rows)

def _read_keyvals(ws) -> dict:
    vals = ws.get_all_values()
    out = {}
    if not vals:
        return out
    # hoppa header om den finns
    start = 1 if vals and vals[0] and vals[0][0].strip().lower() in ("key","nyckel") else 0
    for row in vals[start:]:
        if len(row) >= 2 and row[0]:
            out[row[0].strip()] = row[1]
    return out

# =========================
# Init state
# =========================
def _init_defaults():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # datum/tid (krav)
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),

            # ekonomi/parametrar
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,
            "BONUS_AVAILABLE": 500,
            "BONUS_RATE": 1,           # % för hur många pren skapar bonuskillar

            # Eskilstuna slumpintervall
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

            # Profilnamn (för lönetikett)
            "NAME_LABEL": "Malin",

            # BM / Målvikt (kumulativt per profil)
            "HOJD_M": 1.64,     # läses från profilinställningar
            "BM_SUM": 0,        # summerad BM för alla pren hittills
            "BM_COUNT": 0,      # antal pren som fått BM-värde
            "BM_MAL": 0.0,      # medel-BM
            "MAL_VIKT": 0.0,    # BM_MAL * (HOJD_M**2)
        }

    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []  # aktuell profil lokala rader

    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}

    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""

    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"

    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

_init_defaults()

# =========================
# Hjälp: min/max + slump
# =========================
def _add_hist(col, v):
    try: v = int(v)
    except: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax(col):
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(r.get(col, 0)))
        except: pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0,0)
    st.session_state[HIST_MM_KEY][col] = mm
    return mm

def _rand_hist(col):
    lo, hi = _minmax(col)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

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

def _ensure_input_defaults():
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7,
        "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))

_ensure_input_defaults()

# =========================
# Profiler
# =========================
def _load_profiles_list():
    try:
        _, ss = _get_client_and_ss()
        wsP = _ensure_ws(ss, "Profil")
        names = wsP.col_values(1)
        names = [x for x in names if x and x.strip()]
        if names and names[0].strip().lower() in ("profil","name","namn"):
            names = names[1:]
        return names
    except Exception as e:
        st.error(f"Kunde inte läsa profil-lista: {e}")
        return []

def _load_profile(profil: str):
    """Läs in inställningar + Data_<profil>. Uppdatera CFG/ROWS/HIST."""
    try:
        _, ss = _get_client_and_ss()
        wsI = _ensure_ws(ss, profil)                 # inställningar
        wsD = _ensure_ws(ss, f"Data_{profil}")       # data

        keyvals = _read_keyvals(wsI)
        CFG = st.session_state[CFG_KEY]

        # applicera keyvals (typförsök)
        for k, v in keyvals.items():
            if k in ("startdatum","fodelsedatum"):
                try:
                    y,m,d = [int(x) for x in v.split("-")]
                    CFG[k] = date(y,m,d)
                except:
                    pass
            elif k in CFG:
                # autodetect int/float/bool
                try:
                    if v.lower() in ("true","false"):
                        CFG[k] = (v.lower() == "true")
                    elif "." in v:
                        CFG[k] = float(v)
                    else:
                        CFG[k] = int(v)
                except:
                    CFG[k] = v
            else:
                CFG[k] = v

        # läs data
        data = _read_sheet_records(wsD)
        st.session_state[ROWS_KEY] = data or []

        # bygg minmax
        st.session_state[HIST_MM_KEY] = {}
        labels = _labels()
        for r in st.session_state[ROWS_KEY]:
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        labels["LBL_PAPPAN"], labels["LBL_GRANNAR"], labels["LBL_NILS_VANNER"],
                        labels["LBL_NILS_FAMILJ"], labels["LBL_BEKANTA"], labels["LBL_ESK"]]:
                _add_hist(col, r.get(col, 0))

        # bumpa sceninfo
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

        # fallback BM-derivat
        _recompute_bm_targets()

        st.success(f"✅ Profil '{profil}' inläst.")
    except Exception as e:
        st.error(f"Kunde inte läsa profil '{profil}': {e}")

def _save_profile_settings(profil: str):
    """Spara alla CFG-nycklar till profilens inställningsflik."""
    try:
        _, ss = _get_client_and_ss()
        wsI = _ensure_ws(ss, profil)
        _write_keyvals(wsI, st.session_state[CFG_KEY])
        st.success("✅ Inställningar sparade till profilfliken.")
    except Exception as e:
        st.error(f"Misslyckades att spara inställningar: {e}")

def _append_row_to_data(profil: str, row_dict: dict):
    """Append i 'Data_<profil>'."""
    try:
        _, ss = _get_client_and_ss()
        wsD = _ensure_ws(ss, f"Data_{profil}")
        header = wsD.row_values(1)
        if not header:
            header = list(row_dict.keys())
            wsD.update("A1", [header])
        values = [row_dict.get(col, "") for col in header]
        wsD.append_row(values)
        return True
    except Exception as e:
        st.error(f"Misslyckades att spara rad: {e}")
        return False

# =========================
# Etiketter (inkl namn)
# =========================
def _labels():
    CFG = st.session_state[CFG_KEY]
    return {
        "LBL_PAPPAN": CFG.get("LBL_PAPPAN","Pappans vänner"),
        "LBL_GRANNAR": CFG.get("LBL_GRANNAR","Grannar"),
        "LBL_NILS_VANNER": CFG.get("LBL_NILS_VANNER","Nils vänner"),
        "LBL_NILS_FAMILJ": CFG.get("LBL_NILS_FAMILJ","Nils familj"),
        "LBL_BEKANTA": CFG.get("LBL_BEKANTA","Bekanta"),
        "LBL_ESK": CFG.get("LBL_ESK","Eskilstuna killar"),
        "NAME": CFG.get("NAME_LABEL","Malin"),
    }

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill(s):
    CFG = st.session_state[CFG_KEY]
    keep = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for k in INPUT_ORDER:
        st.session_state[k] = keep.get(k, 0)

    if s == "Ny scen":
        return

    if s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        labs = _labels()
        for f,key in [(labs["LBL_PAPPAN"],"in_pappan"),(labs["LBL_GRANNAR"],"in_grannar"),
                      (labs["LBL_NILS_VANNER"],"in_nils_vanner"),(labs["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (labs["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
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
        labs = _labels()
        for f,key in [(labs["LBL_PAPPAN"],"in_pappan"),(labs["LBL_BEKANTA"],"in_bekanta"),
                      (labs["LBL_GRANNAR"],"in_grannar"),(labs["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (labs["LBL_NILS_FAMILJ"],"in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: en dags-värden enligt specifikationen
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        labs = _labels()
        for f,key in [(labs["LBL_PAPPAN"],"in_pappan"),(labs["LBL_GRANNAR"],"in_grannar"),
                      (labs["LBL_NILS_VANNER"],"in_nils_vanner"),(labs["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (labs["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Bygg basrad från inputs
# =========================
def _build_base_for_calc():
    CFG  = st.session_state[CFG_KEY]
    labs = _labels()
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

        labs["LBL_PAPPAN"]: st.session_state["in_pappan"],
        labs["LBL_GRANNAR"]: st.session_state["in_grannar"],
        labs["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        labs["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        labs["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        labs["LBL_ESK"]:      st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # MAX för statistik/beräkningar (känner sammanlagt m.m.)
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
        "MAX_BEKANTA": int(CFG["MAX_BEKANTA"]),
    }
    # Känner (rad)
    base["Känner"] = (
        int(base[labs["LBL_PAPPAN"]]) + int(base[labs["LBL_GRANNAR"]]) +
        int(base[labs["LBL_NILS_VANNER"]]) + int(base[labs["LBL_NILS_FAMILJ"]])
    )
    # meta
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    # profilnamn för etiketter (t.ex. Lön <NAME>)
    base["_NAME"]         = labs["NAME"]
    return base

# =========================
# BM-hjälpare
# =========================
def _recompute_bm_targets():
    CFG = st.session_state[CFG_KEY]
    # Räknar om BM_MAL & MAL_VIKT från SUM/COUNT/HOJD_M
    count = int(CFG.get("BM_COUNT", 0))
    total = float(CFG.get("BM_SUM", 0))
    if count > 0:
        bm = total / count
    else:
        bm = 0.0
    CFG["BM_MAL"] = bm
    h = float(CFG.get("HOJD_M", 1.64))
    CFG["MAL_VIKT"] = bm * (h * h)

def _update_bm_for_new_subs(new_subs: int):
    """Lägg till BM-slump 12..18 för NYA prenumeranter på raden, uppdatera SUM/COUNT & derivat."""
    if new_subs <= 0:
        return
    # Summan av new_subs slump mellan 12–18
    s = 0
    for _ in range(new_subs):
        s += random.randint(12, 18)
    CFG = st.session_state[CFG_KEY]
    CFG["BM_SUM"]   = float(CFG.get("BM_SUM", 0)) + float(s)
    CFG["BM_COUNT"] = int(CFG.get("BM_COUNT", 0)) + int(new_subs)
    _recompute_bm_targets()

# =========================
# UI: Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
profiles = _load_profiles_list()
with st.sidebar:
    st.header("Profil")
    sel = st.selectbox("Välj profil", [""] + profiles, index=([""]+profiles).index(st.session_state[PROFILE_KEY]) if st.session_state[PROFILE_KEY] in profiles else 0)
    if sel and sel != st.session_state[PROFILE_KEY]:
        st.session_state[PROFILE_KEY] = sel
        _load_profile(sel)

    st.markdown("---")
    st.header("Inställningar")
    CFG["NAME_LABEL"] = st.text_input("Namn (etikett för lön)", CFG.get("NAME_LABEL","Malin"))
    CFG["startdatum"] = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]   = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"] = st.number_input("Avgift (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"] = st.number_input("Totalt personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_RATE"] = st.number_input("Bonus % av prenumeranter", min_value=0.0, value=float(CFG.get("BONUS_RATE",1.0)), step=0.5)
    st.write(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Esk minst", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Esk max", min_value=int(CFG["ESK_MIN"]), value=int(CFG["ESK_MAX"]), step=1)

    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]      = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG["MAX_PAPPAN"]), step=1)
    CFG["MAX_GRANNAR"]     = st.number_input("MAX Grannar", min_value=0, value=int(CFG["MAX_GRANNAR"]), step=1)
    CFG["MAX_NILS_VANNER"] = st.number_input("MAX Nils vänner", min_value=0, value=int(CFG["MAX_NILS_VANNER"]), step=1)
    CFG["MAX_NILS_FAMILJ"] = st.number_input("MAX Nils familj", min_value=0, value=int(CFG["MAX_NILS_FAMILJ"]), step=1)
    CFG["MAX_BEKANTA"]     = st.number_input("MAX Bekanta", min_value=0, value=int(CFG["MAX_BEKANTA"]), step=1)

    st.subheader("Etiketter (källor)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett Eskilstuna killar", value=CFG["LBL_ESK"])

    st.subheader("BM / Målvikt")
    CFG["HOJD_M"]   = st.number_input("Längd i meter", min_value=0.5, value=float(CFG.get("HOJD_M",1.64)), step=0.01, format="%.2f")
    st.caption(f"BM-mål (nu): **{CFG.get('BM_MAL',0):.2f}** • Målvikt: **{CFG.get('MAL_VIKT',0):.1f} kg**")

    st.markdown("---")
    if st.button("💾 Spara inställningar till profil"):
        if not st.session_state[PROFILE_KEY]:
            st.error("Välj en profil först.")
        else:
            _recompute_bm_targets()
            _save_profile_settings(st.session_state[PROFILE_KEY])

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill(st.session_state[SCENARIO_KEY])

# =========================
# Input (exakt ordning)
# =========================
st.markdown("---")
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)

labs = _labels()
labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{labs['LBL_PAPPAN']} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{labs['LBL_GRANNAR']} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{labs['LBL_NILS_VANNER']} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{labs['LBL_NILS_FAMILJ']} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{labs['LBL_BEKANTA']} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{labs['LBL_ESK']} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
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
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

base = _build_base_for_calc()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# Om scen är "Vila ..." → nollställ pren/intäkter/kostnad/lön enligt din regel
if st.session_state[SCENARIO_KEY].startswith("Vila"):
    preview["Prenumeranter"] = 0
    preview["Intäkter"] = 0.0
    preview["Utgift män"] = 0.0
    # byt lön-nyckeln (dynamisk etikett):
    lon_key = f"Lön {labs['NAME']}"
    preview[lon_key] = 0.0
    preview["Vinst"] = preview.get("Intäkt företag", 0.0) - preview.get(lon_key, 0.0)

# Datum/ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try: _d = datetime.fromisoformat(rad_datum).date()
    except: _d = datetime.today().date()
else:
    _d = datetime.today().date()
fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} • **Ålder:** {alder} år • **BM-mål:** {CFG.get('BM_MAL',0):.2f} • **Målvikt:** {CFG.get('MAL_VIKT',0):.1f} kg")

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
lon_key = f"Lön {labs['NAME']}"
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
with e2:
    st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
with e3:
    st.metric("Utgift män", f"${float(preview.get('Utgift män',0)):,.2f}")
    st.metric(lon_key, f"${float(preview.get(lon_key,0)):,.2f}")
with e4:
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
st.caption("Obs: Älskar/Sover-med ingår inte i scenens ’Summa tid’, men påverkar klockan inkl älskar/sover (om du visar den).")

# Källor
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(labs["LBL_PAPPAN"], int(base.get(labs["LBL_PAPPAN"],0)))
with k2: st.metric(labs["LBL_GRANNAR"], int(base.get(labs["LBL_GRANNAR"],0)))
with k3: st.metric(labs["LBL_NILS_VANNER"], int(base.get(labs["LBL_NILS_VANNER"],0)))
with k4: st.metric(labs["LBL_NILS_FAMILJ"], int(base.get(labs["LBL_NILS_FAMILJ"],0)))
with k5: st.metric(labs["LBL_BEKANTA"], int(base.get(labs["LBL_BEKANTA"],0)))
with k6: st.metric(labs["LBL_ESK"], int(base.get(labs["LBL_ESK"],0)))

# =========================
# Spara (lokalt / Google)
# =========================
st.markdown("---")
cL, cR = st.columns(2)

def _after_save_side_effects(saved_row: dict):
    # uppdatera minmax
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                labs["LBL_PAPPAN"], labs["LBL_GRANNAR"], labs["LBL_NILS_VANNER"],
                labs["LBL_NILS_FAMILJ"], labs["LBL_BEKANTA"], labs["LBL_ESK"]]:
        _add_hist(col, saved_row.get(col,0))

    # Bonus kvar: + nya bonus (från prenumeranter * BONUS_RATE) – Bonus deltagit (inmatat på raden)
    bonus_rate = float(CFG.get("BONUS_RATE", 1.0))
    new_bonus = int(round(int(saved_row.get("Prenumeranter",0)) * (bonus_rate/100.0)))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + new_bonus - int(saved_row.get("Bonus deltagit",0)))

    # BM uppdatering baserat på **nya prenumeranter på raden**
    _update_bm_for_new_subs(int(saved_row.get("Prenumeranter",0)))

    # bumpa scen och spara inställningar (för att persistiera BONUS_AVAILABLE, BM_SUM/COUNT)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()
    if st.session_state[PROFILE_KEY]:
        _save_profile_settings(st.session_state[PROFILE_KEY])

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        # spara det vi ser i preview (inkl lönetiketten dynamiskt)
        st.session_state[ROWS_KEY].append(preview)
        _after_save_side_effects(preview)
        st.success("✅ Sparad i minnet.")

def _ensure_header_and_append(ws, row_dict: dict):
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    ws.append_row([row_dict.get(col, "") for col in header])

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        profil = st.session_state[PROFILE_KEY]
        if not profil:
            st.error("Välj en profil först.")
        else:
            if _append_row_to_data(profil, preview):
                # spegla lokalt + sidoeffekter
                st.session_state[ROWS_KEY].append(preview)
                _after_save_side_effects(preview)
                st.success(f"✅ Rad sparad till 'Data_{profil}'.")

# =========================
# Visa lokala rader & Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

st.markdown("---")
st.subheader("📈 Statistik")
try:
    df_stats_input = pd.DataFrame(st.session_state[ROWS_KEY])
    stats = compute_stats(df_stats_input, st.session_state[CFG_KEY])
    st.write(stats)
except Exception as e:
    st.error(f"Kunde inte beräkna statistik: {e}")
