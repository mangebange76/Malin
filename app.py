# app.py
import streamlit as st
import json
import random
from datetime import date, time, datetime, timedelta
import pandas as pd

# ========= Grund =========
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets)")

# ========= Import av beräkningar =========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# ========= Keys =========
CFG_KEY        = "CFG"           # alla config
ROWS_KEY       = "ROWS"          # lokala rader (dicts)
HIST_MM_KEY    = "HIST_MINMAX"   # min/max för slump
SCENEINFO_KEY  = "CURRENT_SCENE" # (scen_nr, datum, veckodag)
SCENARIO_KEY   = "SCENARIO"      # valt scenario
PROFILE_KEY    = "CURRENT_PROFILE"

# ========= Sheets-hjälp =========
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

def _get_profiles(ss):
    """Hämta profilnamn från fliken 'Profil' (kol A)."""
    try:
        ws = _ensure_ws(ss, "Profil", rows=100, cols=5)
        names = [x.strip() for x in ws.col_values(1) if x.strip()]
        # filtrera ev rubriker/dupplikat
        out = []
        for n in names:
            if n.lower() != "profil" and n not in out:
                out.append(n)
        return out
    except Exception as e:
        st.warning(f"Kunde inte läsa profil-lista: {e}")
        return []

def _load_profile_cfg(ss, profile):
    """Läs profilens inställnings-blad (bladnamn = profilen). Key/Value i kol A/B."""
    ws = _ensure_ws(ss, profile)
    rows = ws.get_all_values()
    cfg = {}
    for i, row in enumerate(rows):
        if i == 0 and len(row) >= 2 and row[0].lower() in ("key", "nyckel"):
            continue
        if len(row) < 2:
            continue
        key = str(row[0]).strip()
        val = str(row[1]).strip()
        if not key:
            continue
        # försök typning
        if key in ("startdatum", "fodelsedatum"):
            try:
                y, m, d = [int(x) for x in val.split("-")]
                cfg[key] = date(y, m, d)
                continue
            except:
                pass
        # int/float
        try:
            if "." in val:
                cfg[key] = float(val)
            else:
                cfg[key] = int(val)
        except:
            cfg[key] = val
    return cfg

def _save_profile_cfg(ss, profile, cfg: dict):
    """Skriv hela CFG (nyckel/värde) till profilbladet."""
    ws = _ensure_ws(ss, profile)
    rows = []
    for k, v in cfg.items():
        if isinstance(v, (date, datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([str(k), str(v)])
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def _data_sheet_name(profile: str) -> str:
    return f"Data_{profile}"

def _load_profile_rows(ss, profile) -> pd.DataFrame:
    """Läs rader för profilen från Data_<profil>."""
    ws = _ensure_ws(ss, _data_sheet_name(profile))
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    return df

def _append_row_to_profile(ss, profile, row_dict: dict):
    """Append en rad till Data_<profil>. Skapar header vid behov."""
    import gspread
    ws = _ensure_ws(ss, _data_sheet_name(profile))
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

# ========= Init =========
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr - 1)
    veckodagar = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum":   date(1990, 1, 1),
            "starttid":     time(7, 0),
            "fodelsedatum": date(1970, 1, 1),
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,

            # Bonus
            "BONUS_PERCENT": 1.0,          # procent av prenumeranter som blir bonus (styrbart)
            "BONUS_AVAILABLE": 0,          # räknas om vid inläsning

            # Eskilstuna-intervall
            "ESK_MIN": 20, "ESK_MAX": 40,

            # Maxvärden för källor
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
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = ""

    # standardvärden för inputs
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander_on":1
    }
    for k in [
        "in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
        "in_tid_s","in_tid_d","in_vila","in_dt_tid","in_dt_vila",
        "in_alskar","in_sover",
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna",
        "in_bonus_deltagit","in_personal_deltagit",
        "in_nils","in_hander_on"
    ]:
        st.session_state.setdefault(k, defaults.get(k, 0))

    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# ========= Slump & historik =========
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

def _rebuild_hist_from_rows(cfg):
    st.session_state[HIST_MM_KEY] = {}
    cols = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"], cfg["LBL_NILS_FAMILJ"],
            cfg["LBL_BEKANTA"], cfg["LBL_ESK"]]
    for r in st.session_state.get(ROWS_KEY, []):
        for c in cols:
            _add_hist_value(c, r.get(c, 0))

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    # bygg från lokala rader om saknas
    vals = []
    for r in st.session_state.get(ROWS_KEY, []):
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

def _rand_1_to_hist_max(colname: str):
    """Slumpar 1..max (om max>=1), annars 0."""
    _, hi = _minmax_from_hist(colname)
    if hi >= 1:
        return random.randint(1, hi)
    return 0

# ========= Bonusberäkning från historik =========
def _recalc_bonus_available(cfg: dict, rows_df: pd.DataFrame) -> int:
    try:
        percent = float(cfg.get("BONUS_PERCENT", 1.0))
    except:
        percent = 1.0
    if rows_df is None or rows_df.empty:
        return 0
    # exkludera vila-rader
    if "Typ" in rows_df.columns:
        mask_eko = ~rows_df["Typ"].astype(str).str.contains("Vila", case=False, na=False)
        rows = rows_df[mask_eko].copy()
    else:
        rows = rows_df.copy()
    pren = pd.to_numeric(rows.get("Prenumeranter", 0), errors="coerce").fillna(0)
    gen  = (pren * (percent/100.0)).astype(float).apply(lambda x: int(x))
    cons = pd.to_numeric(rows.get("Bonus deltagit", 0), errors="coerce").fillna(0).astype(int)
    available = int(gen.sum() - cons.sum())
    return max(0, available)

# ========= Scenario-fill =========
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]
    # behåll tidsstandard
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_on":st.session_state.get("in_hander_on",1)}
    for k in [
        "in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
        "in_tid_s","in_tid_d","in_vila","in_dt_tid","in_dt_vila",
        "in_alskar","in_sover",
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna",
        "in_bonus_deltagit","in_personal_deltagit",
        "in_nils","in_hander_on"
    ]:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        return

    if s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_1_to_hist_max("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        return

    if s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_1_to_hist_max("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        return

    if s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_BEKANTA"],"in_bekanta"),
                      (CFG["LBL_GRANNAR"],"in_grannar"),(CFG["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (CFG["LBL_NILS_FAMILJ"],"in_nils_familj")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        return

    if s == "Vila i hemmet (dag 1–7)":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_1_to_hist_max(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        return

# ========= Profil & inläsning =========
def _ensure_profile_loaded(profile: str):
    """Skapa tomma blad om saknas."""
    ss = _get_gspread_client()
    _ensure_ws(ss, "Profil")
    _ensure_ws(ss, profile)
    _ensure_ws(ss, _data_sheet_name(profile))
    return ss

def _load_everything_for_profile(profile: str):
    """Läs både inställningar och data för profilen. Recalc BONUS."""
    ss = _ensure_profile_loaded(profile)
    # cfg
    prof_cfg = _load_profile_cfg(ss, profile)
    # base defaults
    base = st.session_state[CFG_KEY].copy()
    # uppdatera med prof_cfg (skriv över defaults)
    base.update(prof_cfg)
    st.session_state[CFG_KEY] = base

    # data
    df = _load_profile_rows(ss, profile)
    st.session_state[ROWS_KEY] = df.to_dict("records")
    # rebuild hist
    _rebuild_hist_from_rows(st.session_state[CFG_KEY])

    # recalc bonus
    bonus_left = _recalc_bonus_available(st.session_state[CFG_KEY], df)
    st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = int(bonus_left)

    # bump sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ========= Input UI =========
def _labels(cfg):
    return {
        "LBL_PAPPAN": cfg["LBL_PAPPAN"],
        "LBL_GRANNAR": cfg["LBL_GRANNAR"],
        "LBL_NILS_VANNER": cfg["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ": cfg["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": cfg["LBL_BEKANTA"],
        "LBL_ESK": cfg["LBL_ESK"],
    }

def _build_base(cfg):
    scen_nr, d, veckodag = st.session_state[SCENEINFO_KEY]
    L = _labels(cfg)
    base = {
        "Profil": st.session_state.get(PROFILE_KEY, ""),
        "Datum": d.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen_nr,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"],
        "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"],
        "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"],
        "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"],
        "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"],
        "Tid D": st.session_state["in_tid_d"],
        "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"],
        "DT vila (sek/kille)": st.session_state["in_dt_vila"],

        "Älskar": st.session_state["in_alskar"],
        "Sover med": st.session_state["in_sover"],

        L["LBL_PAPPAN"]: st.session_state["in_pappan"],
        L["LBL_GRANNAR"]: st.session_state["in_grannar"],
        L["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        L["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        L["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        L["LBL_ESK"]: st.session_state["in_eskilstuna"],

        "Bonus deltagit": st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils": st.session_state["in_nils"],
        "Händer aktiv": int(st.session_state.get("in_hander_on", 1)),

        "Avgift": float(cfg.get("avgift_usd", 30.0)),
        "PROD_STAFF": int(cfg.get("PROD_STAFF", 800)),
        # ge beräkningen tillgång till maxvärden & labels
        "MAX_PAPPAN": int(cfg.get("MAX_PAPPAN", 0)),
        "MAX_GRANNAR": int(cfg.get("MAX_GRANNAR", 0)),
        "MAX_NILS_VANNER": int(cfg.get("MAX_NILS_VANNER", 0)),
        "MAX_NILS_FAMILJ": int(cfg.get("MAX_NILS_FAMILJ", 0)),
        "MAX_BEKANTA": int(cfg.get("MAX_BEKANTA", 0)),
        "LBL_PAPPAN": L["LBL_PAPPAN"],
        "LBL_GRANNAR": L["LBL_GRANNAR"],
        "LBL_NILS_VANNER": L["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ": L["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": L["LBL_BEKANTA"],
        "LBL_ESK": L["LBL_ESK"],
    }
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = cfg["fodelsedatum"]
    base["_starttid"]     = cfg["starttid"]
    return base

# ========= Sidopanel =========
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.subheader("Profil")
    try:
        ss = _get_gspread_client()
        profiles = _get_profiles(ss)
    except Exception as e:
        profiles = []
        st.warning(f"Kunde inte läsa profiler: {e}")

    if profiles:
        sel = st.selectbox("Välj profil", options=["— Välj —"]+profiles,
                           index=(["— Välj —"]+profiles).index(st.session_state.get(PROFILE_KEY,"— Välj —")) if st.session_state.get(PROFILE_KEY) in profiles else 0)
        if sel != "— Välj —" and sel != st.session_state.get(PROFILE_KEY, ""):
            st.session_state[PROFILE_KEY] = sel

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📥 Läs in PROFILENS inställningar"):
                try:
                    ss = _ensure_profile_loaded(st.session_state[PROFILE_KEY])
                    prof_cfg = _load_profile_cfg(ss, st.session_state[PROFILE_KEY])
                    # skriv över i CFG
                    tmp = CFG.copy()
                    tmp.update(prof_cfg)
                    st.session_state[CFG_KEY] = tmp
                    CFG = tmp
                    st.success("Inställningar inlästa.")
                except Exception as e:
                    st.error(f"Kunde inte läsa inställningar: {e}")
        with c2:
            if st.button("📥 Läs in PROFILENS data"):
                try:
                    ss = _ensure_profile_loaded(st.session_state[PROFILE_KEY])
                    df = _load_profile_rows(ss, st.session_state[PROFILE_KEY])
                    st.session_state[ROWS_KEY] = df.to_dict("records")
                    _rebuild_hist_from_rows(st.session_state[CFG_KEY])
                    CFG["BONUS_AVAILABLE"] = _recalc_bonus_available(CFG, df)
                    st.session_state[SCENEINFO_KEY] = _current_scene_info()
                    st.success("Data inläst.")
                except Exception as e:
                    st.error(f"Kunde inte läsa data: {e}")

    st.markdown("---")
    st.header("Inställningar (lokalt/profil)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_PERCENT"]= st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0, value=float(CFG.get("BONUS_PERCENT",1.0)), step=0.1)

    st.caption(f"**Bonus killar kvar:** {int(CFG.get('BONUS_AVAILABLE',0))}")

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
        "Välj scenario",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Google Sheets – status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

# ========= Input (exakt ordning) =========
st.subheader("Input (exakt ordning)")
cols_left, cols_right = st.columns(2)
L = _labels(CFG)

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{L['LBL_PAPPAN']} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{L['LBL_GRANNAR']} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{L['LBL_NILS_VANNER']} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{L['LBL_NILS_FAMILJ']} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{L['LBL_BEKANTA']} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{L['LBL_ESK']} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG.get('BONUS_AVAILABLE',0))})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_nils":"Nils (0/1/2)",
    "in_hander_on":"Händer aktiv (Ja=1 / Nej=0)"
}

with cols_left:
    for key in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap","in_tid_s","in_tid_d","in_vila"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
with cols_right:
    for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna","in_bonus_deltagit","in_personal_deltagit","in_nils"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_hander_on"], min_value=0, max_value=1, step=1, key="in_hander_on")

# ========= Live =========
st.markdown("---")
st.subheader("🔎 Live")

def _merge_base_preview(base: dict, prev: dict) -> dict:
    m = base.copy()
    m.update(prev)
    return m

def render_live_and_preview(cfg):
    base = _build_base(cfg)
    try:
        prev = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
    except TypeError:
        prev = calc_row_values(base, base["_rad_datum"], cfg["fodelsedatum"], cfg["starttid"])

    # “Vila” scener -> nolla ekonomi + hårdhet + pren + kostn + lön + bonusgenerering
    typ = str(base.get("Typ","")).lower()
    is_vila = ("vila" in typ)
    if is_vila:
        # Tvinga 0 på ekonomi
        prev["Hårdhet"] = 0
        prev["Prenumeranter"] = 0
        prev["Intäkter"] = 0.0
        prev["Intäkt Känner"] = 0.0
        prev["Utgift män"] = 0.0
        prev["Lön Malin"] = 0.0
        prev["Vinst"] = 0.0

    merged = _merge_base_preview(base, prev)

    # Visa live-nycklar
    # Ålder
    rad_datum = merged.get("Datum", base["Datum"])
    veckodag = merged.get("Veckodag", "-")
    if isinstance(rad_datum, str):
        try:
            _d = datetime.fromisoformat(rad_datum).date()
        except Exception:
            _d = datetime.today().date()
    else:
        _d = datetime.today().date()
    fd = cfg["fodelsedatum"]
    alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
    st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} • **Ålder:** {alder} år")

    # Tid/kille i liven = Suger/kille + Händer/kille
    suger_pk = float(merged.get("Suger per kille (sek)", 0.0))
    hander_pk = float(merged.get("Händer per kille (sek)", 0.0))
    tidkille_total = suger_pk + hander_pk

    # Paneler
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", merged.get("Summa tid","-"))
        st.metric("Summa tid (sek)", int(merged.get("Summa tid (sek)",0)))
    with c2:
        # visa mm:ss för totala tid/kille (suger+hander)
        def _mmss(x):
            try:
                s = max(0, int(round(x)))
                m, s = divmod(s, 60)
                return f"{m}:{s:02d}"
            except:
                return "-"
        st.metric("Tid/kille", _mmss(tidkille_total))
        st.metric("Tid/kille (sek)", int(tidkille_total))
    with c3:
        st.metric("Klockan", merged.get("Klockan","-"))
        st.metric("Totalt män (beräkningar)", int(merged.get("Totalt Män",0)))

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Hångel (m:s/kille)", merged.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(merged.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger/kille (sek)", int(merged.get("Suger per kille (sek)", 0)))
        st.metric("Händer/kille (sek)", int(merged.get("Händer per kille (sek)", 0)))

    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", int(merged.get("Prenumeranter",0)))
        st.metric("Hårdhet", int(merged.get("Hårdhet",0)))
    with e2:
        st.metric("Intäkter", f"${float(merged.get('Intäkter',0)):,.2f}")
        st.metric("Intäkt Känner", f"${float(merged.get('Intäkt Känner',0)):,.2f}")
    with e3:
        st.metric("Kostnad män", f"${float(merged.get('Utgift män',0)):,.2f}")
        st.metric("Lön Malin", f"${float(merged.get('Lön Malin',0)):,.2f}")
    with e4:
        st.metric("Vinst", f"${float(merged.get('Vinst',0)):,.2f}")
        st.metric("Älskar (sek)", int(merged.get("Tid Älskar (sek)", 0)))

    # Käll-breakout
    st.markdown("**👥 Källor (live)**")
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: st.metric(CFG["LBL_PAPPAN"], int(base.get(CFG["LBL_PAPPAN"],0)))
    with k2: st.metric(CFG["LBL_GRANNAR"], int(base.get(CFG["LBL_GRANNAR"],0)))
    with k3: st.metric(CFG["LBL_NILS_VANNER"], int(base.get(CFG["LBL_NILS_VANNER"],0)))
    with k4: st.metric(CFG["LBL_NILS_FAMILJ"], int(base.get(CFG["LBL_NILS_FAMILJ"],0)))
    with k5: st.metric(CFG["LBL_BEKANTA"], int(base.get(CFG["LBL_BEKANTA"],0)))
    with k6: st.metric(CFG["LBL_ESK"], int(base.get(CFG["LBL_ESK"],0)))

    # extra kontroll
    tot_men_including = (
        int(base.get("Män",0)) + int(base.get("Svarta",0)) +
        int(base.get(CFG["LBL_PAPPAN"],0)) + int(base.get(CFG["LBL_GRANNAR"],0)) +
        int(base.get(CFG["LBL_NILS_VANNER"],0)) + int(base.get(CFG["LBL_NILS_FAMILJ"],0)) +
        int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0)) +
        int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
    )
    st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

    st.caption("Obs: Vila-scener ger 0 på hårdhet, prenumeranter, intäkter, kostnad, lön och bonus.")

    return base, merged, is_vila

_base, _preview, _is_vila = render_live_and_preview(CFG)

# ========= Spara =========
st.markdown("---")
cL, cR = st.columns(2)

def _after_save_housekeeping(merged_row: dict):
    """Uppdatera lokalt minne, historik och BONUS_AVAILABLE; bump sceninfo."""
    # lägg till lokalt
    st.session_state[ROWS_KEY].append(merged_row)

    # uppdatera historik
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"], CFG["LBL_NILS_FAMILJ"],
                CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
        v = int(merged_row.get(col, 0))
        _add_hist_value(col, v)

    # BONUS_AVAILABLE: + ny_generering − consumed (endast ej-vila)
    percent = float(CFG.get("BONUS_PERCENT", 1.0))
    new_from_pren = 0 if _is_vila else int(float(merged_row.get("Prenumeranter",0)) * (percent/100.0))
    consumed = int(merged_row.get("Bonus deltagit", 0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE",0)) + new_from_pren - consumed)

    # uppdatera profilbladet med ny BONUS_AVAILABLE
    try:
        if st.session_state.get(PROFILE_KEY):
            ss = _get_gspread_client()
            _save_profile_cfg(ss, st.session_state[PROFILE_KEY], CFG)
    except Exception as e:
        st.warning(f"Kunde inte spara BONUS_AVAILABLE till profilblad: {e}")

    # nästa scen
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        _after_save_housekeeping(_preview.copy())
        st.success("✅ Sparad i minnet (profil-lokal).")

def _save_to_profile_sheet(row_dict: dict):
    ss = _get_gspread_client()
    profile = st.session_state.get(PROFILE_KEY, "")
    if not profile:
        raise RuntimeError("Ingen profil vald.")
    _append_row_to_profile(ss, profile, row_dict)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            _save_to_profile_sheet(_preview)
            _after_save_housekeeping(_preview.copy())
            st.success(f"✅ Sparad till Google Sheets (flik: { _data_sheet_name(st.session_state.get(PROFILE_KEY,'')) }).")
        except Exception as e:
            st.error(f"Misslyckades att spara: {e}")

# ========= Visa lokala rader =========
st.markdown("---")
st.subheader("📋 Lokala rader (profilens buffert)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu – läs in profilens data eller spara en rad.")
