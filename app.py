# app.py
import streamlit as st
import json
import random
import pandas as pd
from datetime import date, time, datetime, timedelta

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (lokal + Sheets via SHEET_URL)")

# ======== State-nycklar ========
CFG_KEY        = "CFG"           # alla config + etiketter
ROWS_KEY       = "ROWS"          # sparade rader (lokalt minne)
HIST_MM_KEY    = "HIST_MINMAX"   # min/max per fält
SCENEINFO_KEY  = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"      # rullist-valet
PROFILE_KEY    = "PROFILE"       # vald profil
PROFILE_LIST   = "PROFILE_LIST"  # cache av profiler från blad 'Profil'
BONUS_LEFT_KEY = "BONUS_AVAILABLE"  # kvarvarande bonuskillar i CFG

# ======== Import av beräkning & statistik ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    from statistik import compute_stats
except Exception:
    compute_stats = None

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

# ---------- Key/Value-läsare (PATCH #1) ----------
def _read_kv_sheet(ws):
    """
    Läs key/value-ark (kol A=Key, kol B=Value) -> dict med auto-typning.
    Fungerar både med och utan rubrikrad ("Key","Value").
    Tolkar även startdatum, fodelsedatum (YYYY-MM-DD) och starttid (HH:MM).
    """
    out = {}
    vals = ws.get_all_values() or []
    if not vals:
        return out

    # detektera rubrikrad
    start_idx = 1 if vals and len(vals[0]) >= 2 and \
        vals[0][0].strip().lower() == "key" and vals[0][1].strip().lower() == "value" else 0

    for r in vals[start_idx:]:
        if not r or not r[0]:
            continue
        k = r[0].strip()
        v = (r[1].strip() if len(r) > 1 else "")

        kl = k.lower()
        if kl in ("startdatum", "fodelsedatum"):
            try:
                y, m, d = [int(x) for x in v.split("-")]
                out[k] = date(y, m, d)
                continue
            except:
                pass
        if kl == "starttid":
            try:
                hh, mm = [int(x) for x in v.split(":")]
                out[k] = time(hh, mm)
                continue
            except:
                pass

        # generisk typning
        try:
            if v.strip() == "":
                out[k] = v
            elif "." in v or "," in v:
                out[k] = float(v.replace(",", "."))
            else:
                out[k] = int(v)
            continue
        except:
            pass
        if v.lower() in ("true", "false"):
            out[k] = (v.lower() == "true")
        else:
            out[k] = v
    return out

# ---------- Profil-config-läsare (PATCH #2) ----------
def _load_profile_config(profile_name: str) -> dict:
    """
    Försök läsa config från 'Config - <profil>' och fall back till '<profil>'.
    Returnerar dict med nyckel->värde.
    """
    ss = _get_gspread_client()
    # försök 'Config - <profil>' först
    try:
        ws = _ensure_ws(ss, f"Config - {profile_name}")
        cfg = _read_kv_sheet(ws)
        if cfg:
            return cfg
    except Exception:
        pass
    # fallback: bladet heter exakt som profilen
    try:
        ws = _ensure_ws(ss, profile_name)
        cfg = _read_kv_sheet(ws)
        return cfg
    except Exception as e:
        raise RuntimeError(f"Kunde inte läsa config för profilen: {e}")

# ---------- Profilens data-inläsning ----------
def _load_profile_rows(profile_name: str) -> list[dict]:
    """
    Läser alla rader från fliken 'Data - <profil>' om den finns.
    Returnerar list[dict] (get_all_records()) eller tom lista.
    """
    try:
        ss = _get_gspread_client()
        try:
            ws = ss.worksheet(f"Data - {profile_name}")
        except Exception:
            return []
        return ws.get_all_records() or []
    except Exception:
        return []

def _profile_names_from_sheet() -> list[str]:
    """Hämta profiler från fliken 'Profil' (kolumn A)."""
    try:
        ss = _get_gspread_client()
        ws = _ensure_ws(ss, "Profil")
        names = [x.strip() for x in ws.col_values(1) if x.strip()]
        return names
    except Exception as e:
        st.error(f"Kunde inte läsa profil-lista: {e}")
        return []

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
    "in_hander_on",   # <-- NYTT: Händer aktiv (0/1)
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
            # start/födelse enligt din begäran
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),

            "avgift_usd":   30.0,
            "PROD_STAFF":   800,

            BONUS_LEFT_KEY: 500,
            "BONUS_PCT":    1.0,     # % av nya prenumeranter som skapar bonuskillar

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

            # BMI / längd (kan fyllas via profil)
            "HEIGHT_M": 1.64,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = "— ingen —"
    if PROFILE_LIST not in st.session_state:
        st.session_state[PROFILE_LIST] = []

    # default för tidsfält m.m.
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander_on":1
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
    mm = (min(vals), max(vals)) if vals else (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_upto_max(colname: str):
    """Slumpa 1..max (om max==0 -> 0)."""
    _, hi = _minmax_from_hist(colname)
    if hi <= 0:
        return 0
    return random.randint(1, hi)

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_on":1}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_upto_max("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_upto_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_upto_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_upto_max("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_upto_max(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_upto_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                      ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                      ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_upto_max(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0

    elif s == "Vila i hemmet (dag 1–7)":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_upto_max(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_upto_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'} • SHEET_URL: {'✅' if has_url else '❌'}")

    # Uppdatera rullista
    if st.button("🔄 Uppdatera profiler"):
        st.session_state[PROFILE_LIST] = _profile_names_from_sheet()
        st.success("Profiler uppdaterade.")

    profile = st.selectbox(
        "Välj profil (från flik 'Profil')",
        options=["— ingen —"] + st.session_state[PROFILE_LIST],
        index=(["— ingen —"] + st.session_state[PROFILE_LIST]).index(st.session_state[PROFILE_KEY])
        if st.session_state[PROFILE_KEY] in (["— ingen —"] + st.session_state[PROFILE_LIST]) else 0
    )
    st.session_state[PROFILE_KEY] = profile

    colp1, colp2 = st.columns(2)
    # ---------- PATCH #3: explicit knappar ----------
    with colp1:
        if st.button("📥 Läs in profilens inställningar"):
            if profile == "— ingen —":
                st.info("Välj en profil först.")
            else:
                try:
                    cfg_over = _load_profile_config(profile)
                    st.session_state[CFG_KEY].update(cfg_over)
                    st.success(f"Inställningar inlästa från '{profile}' ({len(cfg_over)} nycklar).")
                except Exception as e:
                    st.error(f"Kunde inte läsa inställningar: {e}")

    with colp2:
        if st.button("📥 Läs in profilens data"):
            if profile == "— ingen —":
                st.info("Välj en profil först.")
            else:
                rows = _load_profile_rows(profile)
                st.session_state[ROWS_KEY] = rows
                # bygga min/max
                st.session_state[HIST_MM_KEY] = {}
                lbls = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                        CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]
                for r in rows:
                    for col in lbls:
                        _add_hist_value(col, r.get(col, 0))
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"Data inläst: {len(rows)} rader från 'Data - {profile}'.")

    st.markdown("---")
    st.subheader("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG[BONUS_LEFT_KEY])}")
    CFG["BONUS_PCT"] = st.number_input("Bonus-% från prenumeranter", min_value=0.0, max_value=100.0, value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)

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
    st.subheader("Etiketter (slår igenom i input/live)")
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
    st.subheader("Spara inställningar till Sheets")
    if st.button("💾 Spara inställningar"):
        try:
            ss = _get_gspread_client()
            wsI = _ensure_ws(ss, "Inställningar")
            rows = []
            for k,v in st.session_state[CFG_KEY].items():
                if isinstance(v, (date, datetime)):
                    v = v.strftime("%Y-%m-%d")
                elif isinstance(v, time):
                    v = v.strftime("%H:%M")
                rows.append([k, str(v)])
            wsI.clear()
            wsI.update("A1", [["Key","Value"]])
            if rows:
                wsI.update(f"A2:B{len(rows)+1}", rows)
            st.success("✅ Inställningar sparade.")
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
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG[BONUS_LEFT_KEY])})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_hander_on":"Händer aktiv (0/1)",
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
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_hander_on"], min_value=0, max_value=1, step=1, key="in_hander_on")
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

        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv": st.session_state["in_hander_on"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"])
    }
    # Känner (summa käll-etiketter)
    base["Känner"] = (
        int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) +
        int(base[LBL_NV]) + int(base[LBL_NF])
    )
    # meta till beräkning
    base["_rad_datum"]    = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    # lägg med MAX-fält (för beräkningar som kan behöva dem)
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

base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# Egen totalsiffra
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
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år &nbsp;•&nbsp; **Aktiv profil:** {st.session_state[PROFILE_KEY]}")

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
    st.metric("Suger (sek/kille)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
with c6:
    st.metric("Händer (sek/kille)", int(preview.get("Händer per kille (sek)", 0)))
    st.metric("Händer aktiv", int(preview.get("Händer aktiv", 0)))

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
    st.metric("Kostnad män", f"${float(preview.get('Utgift män',0)):,.2f}")
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
with e4:
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men lägger på klockan.")

# =========================
# Spara lokalt
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _after_save_housekeeping(preview: dict):
    """Uppdatera historik & bonus kvar – men rör inte widget-keys efter render."""
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview.get(col,0))
        _add_hist_value(col, v)

    # bonus kvar: vila-rader → bara minus "Bonus deltagit".
    # övriga rader → +BONUS_PCT% av nya prenumeranter − "Bonus deltagit".
    scenario = preview.get("Typ","")
    delta = - int(preview.get("Bonus deltagit",0))
    if not scenario.lower().startswith("vila"):
        bonus_pct = float(CFG.get("BONUS_PCT", 1.0))
        delta += int(round(float(preview.get("Prenumeranter",0)) * (bonus_pct/100.0)))

    CFG[BONUS_LEFT_KEY] = max(0, int(CFG[BONUS_LEFT_KEY]) + delta)

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        _after_save_housekeeping(preview)
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad i minnet (ingen Sheets).")

# =========================
# Spara till Google Sheets (profil-specifik flik)
# =========================
def save_to_profile_sheet(row_dict: dict, profile_name: str):
    if profile_name == "— ingen —":
        raise RuntimeError("Ingen profil vald. Välj en profil i sidopanelen.")
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, f"Data - {profile_name}")
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
            save_to_profile_sheet(preview, st.session_state[PROFILE_KEY])
            st.success(f"✅ Sparad till Google Sheets (flik: Data - {st.session_state[PROFILE_KEY]}).")
            # spegla lokalt + housekeeping
            st.session_state[ROWS_KEY].append(preview)
            _after_save_housekeeping(preview)
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
    # visa några intressanta kolumner först om de finns
    prefer = [ "Datum","Veckodag","Scen","Typ","Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
               LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
               "Känner","Totalt Män","Prenumeranter","Intäkter","Intäkt företag","Vinst" ]
    cols = [c for c in prefer if c in df.columns] + [c for c in df.columns if c not in prefer]
    df = df[cols]
    st.dataframe(df, use_container_width=True, height=360)
else:
    st.info("Inga lokala rader ännu.")

# =========================
# Statistik (om modul finns)
# =========================
st.markdown("---")
st.subheader("📊 Statistik")
if compute_stats:
    try:
        rows_df = pd.DataFrame(st.session_state[ROWS_KEY]) if st.session_state[ROWS_KEY] else pd.DataFrame()
        stats = compute_stats(rows_df, CFG) if "cfg" in compute_stats.__code__.co_varnames else compute_stats(rows_df)
        if isinstance(stats, dict):
            for k,v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.write(stats)
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
else:
    st.info("Modulen statistik.py saknas eller kunde inte importeras.")
