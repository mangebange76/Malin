# app.py
import streamlit as st
import json, random
import pandas as pd
from datetime import date, time, datetime, timedelta

# ====== App ======
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets)")

# ====== Import beräkningar/statistik ======
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    from statistik import compute_stats
except Exception:
    compute_stats = None  # valfri

# ====== Keys ======
CFG_KEY        = "CFG"
ROWS_KEY       = "ROWS"
HIST_MM_KEY    = "HIST_MINMAX"
SCENEINFO_KEY  = "CURRENT_SCENE"
SCENARIO_KEY   = "SCENARIO"
PROFILE_KEY    = "ACTIVE_PROFILE"

# ====== Sheets helpers ======
def _get_gspread_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS/SHEET_URL).")
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

def _read_kv_sheet(ws):
    """Läs key/value-ark (kol A=Key, kol B=Value) -> dict med auto-typning."""
    out = {}
    vals = ws.get_all_values()
    for r in vals[1:] if vals else []:  # hoppa header
        if not r or not r[0]:
            continue
        k = r[0].strip()
        v = r[1].strip() if len(r) > 1 else ""
        # typning
        if k in ("startdatum", "fodelsedatum"):
            try:
                y, m, d = [int(x) for x in v.split("-")]
                out[k] = date(y, m, d)
            except:
                out[k] = v
        else:
            try:
                if "." in v:
                    out[k] = float(v)
                else:
                    out[k] = int(v)
            except:
                # bool?
                if v.lower() in ("true","false"):
                    out[k] = (v.lower() == "true")
                else:
                    out[k] = v
    return out

def _read_table_sheet(ws):
    """Läs alla rader robust via get_all_values() och bygg records utifrån första header-raden."""
    vals = ws.get_all_values()
    if not vals:
        return []
    header = vals[0]
    records = []
    for row in vals[1:]:
        if not any(c != "" for c in row):
            continue
        rec = {}
        for i, h in enumerate(header):
            if not h:
                continue
            rec[h] = row[i] if i < len(row) else ""
        records.append(rec)
    return records

# ====== Init ======
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d  = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    dagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, dagar[d.weekday()])

def _init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date(1990,1,1),
            "starttid": time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,
            "BONUS_AVAILABLE": 0,
            "BONUS_PCT": 1.0,          # % av prenumeranter som blir bonuskillar
            "ESK_MIN": 20, "ESK_MAX": 40,
            # max
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
            # labels
            "LBL_PAPPAN":"Pappans vänner","LBL_GRANNAR":"Grannar",
            "LBL_NILS_VANNER":"Nils vänner","LBL_NILS_FAMILJ":"Nils familj",
            "LBL_BEKANTA":"Bekanta","LBL_ESK":"Eskilstuna killar",
            # BM (valfritt, visas om satta)
            "BM-mål": None, "Mål vikt": None, "HEIGHT_M": 1.64,
        }
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = None
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
    # defaults till inputs
    for k, v in {
        "in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,
        "in_sover":0,"in_alskar":0,"in_nils":0,"in_hander_on":True,
        "in_bonus_deltagit":0,"in_personal_deltagit":0,
    }.items():
        st.session_state.setdefault(k, v)

_init_state()

# ====== Hist/min-max + slump ======
def _add_hist_value(col, v):
    try: v = int(v)
    except: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn, v), max(mx, v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(col):
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(r.get(col, 0)))
        except: pass
    if vals: mm = (min(vals), max(vals))
    else: mm = (0,0)
    st.session_state[HIST_MM_KEY][col] = mm
    return mm

def _rand_up_to_max(col):
    """Slumpa 1..max (om max=0 -> 0)."""
    _, hi = _minmax_from_hist(col)
    if hi <= 0:
        return 0
    return random.randint(1, hi)

# ====== Scenario-fill ======
def _fill_fields_random(names):
    for f, key in names:
        st.session_state[key] = _rand_up_to_max(f)

def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s   = st.session_state[SCENARIO_KEY]

    # reset inputs (tider kvar)
    keep = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_on":True}
    for k in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
              "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna",
              "in_alskar","in_sover","in_bonus_deltagit","in_personal_deltagit","in_nils"]:
        st.session_state[k] = keep.get(k, 0)

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"] = _rand_up_to_max("Män")
        _fill_fields_random([
            ("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
            ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")
        ])
        _fill_fields_random([
            ("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
            ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
            ("Bekanta","in_bekanta")
        ])
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_up_to_max("Svarta")
        _fill_fields_random([
            ("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
            ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")
        ])
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        _fill_fields_random([
            ("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
            ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")
        ])
        _fill_fields_random([
            ("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
            ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
            ("Bekanta","in_bekanta")
        ])
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        _fill_fields_random([
            ("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
            ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")
        ])
        _fill_fields_random([
            ("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
            ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
            ("Bekanta","in_bekanta")
        ])
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ====== Sidebar (Profiler + inställningar) ======
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}  •  SHEET_URL: {'✅' if has_url else '❌'}")

    profillista = []
    if has_creds and has_url:
        try:
            ss = _get_gspread_client()
            wsP = _ensure_ws(ss, "Profil")
            profillista = [r[0].strip() for r in wsP.get_all_values() if r and r[0].strip()]
        except Exception as e:
            st.warning(f"Kunde inte läsa profil-lista: {e}")

    st.session_state[PROFILE_KEY] = st.selectbox(
        "Välj profil (från flik 'Profil')",
        options=["— ingen —"] + profillista,
        index=(["— ingen —"] + profillista).index(st.session_state.get(PROFILE_KEY) or "— ingen —")
    )

    colp1, colp2 = st.columns(2)
    with colp1:
        if st.button("📥 Läs in profilens inställningar"):
            if st.session_state[PROFILE_KEY] and st.session_state[PROFILE_KEY] != "— ingen —":
                try:
                    wsC = _ensure_ws(ss, f"Config - {st.session_state[PROFILE_KEY]}")
                    cfg_over = _read_kv_sheet(wsC)
                    st.session_state[CFG_KEY].update(cfg_over)
                    st.success("Inställningar inlästa.")
                except Exception as e:
                    st.error(f"Kunde inte läsa inställningar: {e}")
            else:
                st.info("Välj en profil först.")
    with colp2:
        if st.button("📥 Läs in profilens data"):
            if st.session_state[PROFILE_KEY] and st.session_state[PROFILE_KEY] != "— ingen —":
                try:
                    wsD = _ensure_ws(ss, f"Data - {st.session_state[PROFILE_KEY]}")
                    data = _read_table_sheet(wsD)
                    st.session_state[ROWS_KEY] = data or []
                    # bygg hist
                    st.session_state[HIST_MM_KEY] = {}
                    labs = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            CFG["LBL_PAPPAN"],CFG["LBL_GRANNAR"],CFG["LBL_NILS_VANNER"],
                            CFG["LBL_NILS_FAMILJ"],CFG["LBL_BEKANTA"],CFG["LBL_ESK"]]
                    for r in st.session_state[ROWS_KEY]:
                        for c in labs:
                            _add_hist_value(c, r.get(c, 0))
                    st.session_state[SCENEINFO_KEY] = _current_scene_info()
                    st.success(f"Läste in {len(st.session_state[ROWS_KEY])} rader.")
                except Exception as e:
                    st.error(f"Kunde inte läsa data: {e}")
            else:
                st.info("Välj en profil först.")

    st.markdown("---")
    st.subheader("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_PCT"]    = st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0, value=float(CFG["BONUS_PCT"]), step=0.1)

    st.caption(f"Bonus killar kvar: **{int(CFG['BONUS_AVAILABLE'])}**")

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1)

    st.subheader("Maxvärden")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG["MAX_PAPPAN"]), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG["MAX_GRANNAR"]), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG["MAX_NILS_VANNER"]), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG["MAX_NILS_FAMILJ"]), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG["MAX_BEKANTA"]), step=1)

    st.subheader("Etiketter")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett Eskilstuna killar", value=CFG["LBL_ESK"])

    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden (scenario)"):
        apply_scenario_fill()
        st.rerun()

# ====== Inputs ======
st.subheader("Input (exakt ordning)")

LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"];    LBL_ESK = CFG["LBL_ESK"]

c1, c2 = st.columns(2)
with c1:
    st.number_input("Män",    min_value=0, step=1, key="in_man")
    st.number_input("Svarta", min_value=0, step=1, key="in_svarta")
    st.number_input("Fitta",  min_value=0, step=1, key="in_fitta")
    st.number_input("Rumpa",  min_value=0, step=1, key="in_rumpa")
    st.number_input("DP",     min_value=0, step=1, key="in_dp")
    st.number_input("DPP",    min_value=0, step=1, key="in_dpp")
    st.number_input("DAP",    min_value=0, step=1, key="in_dap")
    st.number_input("TAP",    min_value=0, step=1, key="in_tap")
    st.number_input("Tid S (sek)", min_value=0, step=1, key="in_tid_s")
    st.number_input("Tid D (sek)", min_value=0, step=1, key="in_tid_d")
    st.number_input("Vila (sek)",  min_value=0, step=1, key="in_vila")

with c2:
    st.number_input("DT tid (sek/kille)",  min_value=0, step=1, key="in_dt_tid")
    st.number_input("DT vila (sek/kille)", min_value=0, step=1, key="in_dt_vila")
    st.number_input("Älskar", min_value=0, step=1, key="in_alskar")
    st.number_input("Sover med (0/1)", min_value=0, max_value=1, step=1, key="in_sover")
    st.checkbox("Händer aktiv", value=st.session_state.get("in_hander_on", True), key="in_hander_on")
    st.number_input(f"{LBL_PAPPAN} (MAX {int(CFG['MAX_PAPPAN'])})", min_value=0, step=1, key="in_pappan")
    st.number_input(f"{LBL_GRANNAR} (MAX {int(CFG['MAX_GRANNAR'])})", min_value=0, step=1, key="in_grannar")
    st.number_input(f"{LBL_NV} (MAX {int(CFG['MAX_NILS_VANNER'])})", min_value=0, step=1, key="in_nils_vanner")
    st.number_input(f"{LBL_NF} (MAX {int(CFG['MAX_NILS_FAMILJ'])})", min_value=0, step=1, key="in_nils_familj")
    st.number_input(f"{LBL_BEK} (MAX {int(CFG['MAX_BEKANTA'])})", min_value=0, step=1, key="in_bekanta")
    st.number_input(f"{LBL_ESK} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})", min_value=0, step=1, key="in_eskilstuna")
    st.number_input("Bonus deltagit", min_value=0, step=1, key="in_bonus_deltagit")
    st.number_input("Personal deltagit", min_value=0, step=1, key="in_personal_deltagit")
    st.number_input("Nils (0/1/2)", min_value=0, step=1, key="in_nils")

# ====== Build base + live preview ======
def _build_base():
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
        "Händer aktiv": 1 if st.session_state.get("in_hander_on", True) else 0,
        CFG["LBL_PAPPAN"]: st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]: st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        CFG["LBL_ESK"]:      st.session_state["in_eskilstuna"],
        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Nils": st.session_state["in_nils"],
        "Avgift": float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
        # max för “Känner sammanlagt” (om beräkningen använder dem)
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]), "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]), "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
    }
    base["Känner"] = int(base[CFG["LBL_PAPPAN"]]) + int(base[CFG["LBL_GRANNAR"]]) + int(base[CFG["LBL_NILS_VANNER"]]) + int(base[CFG["LBL_NILS_FAMILJ"]])
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

st.markdown("---")
st.subheader("🔎 Live")

base = _build_base()
preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])

# När scenario är vila – nolla ekonomi/hårdhet
is_rest = st.session_state[SCENARIO_KEY] in ("Vila på jobbet","Vila i hemmet (dag 1–7)")
if is_rest:
    for k in ["Hårdhet","Prenumeranter","Intäkter","Utgift män","Lön Malin","Vinst","Intäkt Känner"]:
        preview[k] = 0

# Datum/ålder
try:
    d = datetime.fromisoformat(preview.get("Datum", base["Datum"])).date()
except Exception:
    d = datetime.today().date()
fd = CFG["fodelsedatum"]
alder = d.year - fd.year - ((d.month, d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {preview.get('Datum','-')} / {preview.get('Veckodag','-')} • **Ålder:** {alder} år")

c1,c2,c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille","-"))
    st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
with c3:
    st.metric("Klockan", preview.get("Klockan","-"))
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

c4,c5,c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
with c6:
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))

st.markdown("**💵 Ekonomi (live)**")
e1,e2,e3,e4 = st.columns(4)
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

# Visa BM-mål / Mål vikt om satta
bm_row = []
if CFG.get("BM-mål") is not None:
    bm_row.append(f"BM-mål: **{CFG['BM-mål']}**")
if CFG.get("Mål vikt") is not None:
    bm_row.append(f"Mål vikt: **{CFG['Mål vikt']} kg**")
if bm_row:
    st.caption(" • ".join(bm_row))

st.caption("Obs: Älskar/Sover ingår inte i 'Summa tid', men påverkar 'Klockan inkl älskar/sover'.")

# ====== Spara ======
def _after_save_housekeeping(preview_dict):
    """Justera bonus-kvar och sceninfo utan att skriva till widget-värden."""
    cfg = st.session_state[CFG_KEY]
    bonus_left = int(cfg.get("BONUS_AVAILABLE", 0))
    dec = int(preview_dict.get("Bonus deltagit", 0))

    # Ökning från prenumeranter (om ej vila)
    if st.session_state[SCENARIO_KEY] in ("Vila på jobbet","Vila i hemmet (dag 1–7)"):
        inc = 0
    else:
        pct = float(cfg.get("BONUS_PCT", 1.0)) / 100.0
        inc = int(round(float(preview_dict.get("Prenumeranter", 0)) * pct))

    cfg["BONUS_AVAILABLE"] = max(0, bonus_left + inc - dec)
    st.session_state[CFG_KEY] = cfg
    # bumpa scen
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

def _save_row_to_profile_sheet(profile: str, row: dict):
    ss = _get_gspread_client()
    ws = _ensure_ws(ss, f"Data - {profile}")
    # header
    vals = ws.get_all_values()
    header = vals[0] if vals else []
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])
    # align
    out = [row.get(h, "") for h in header]
    ws.append_row(out)

st.markdown("---")
cL, cR = st.columns(2)
with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        # uppdatera hist
        for c in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                  CFG["LBL_PAPPAN"],CFG["LBL_GRANNAR"],CFG["LBL_NILS_VANNER"],
                  CFG["LBL_NILS_FAMILJ"],CFG["LBL_BEKANTA"],CFG["LBL_ESK"]]:
            _add_hist_value(c, preview.get(c, 0))
        _after_save_housekeeping(preview)
        st.success("Sparad i minnet.")

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        prof = st.session_state.get(PROFILE_KEY)
        if not prof or prof == "— ingen —":
            st.warning("Välj profil först.")
        else:
            try:
                _save_row_to_profile_sheet(prof, preview)
                st.success(f"Sparad till flik 'Data - {prof}'.")
                # spegla lokalt
                st.session_state[ROWS_KEY].append(preview)
                for c in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                          CFG["LBL_PAPPAN"],CFG["LBL_GRANNAR"],CFG["LBL_NILS_VANNER"],
                          CFG["LBL_NILS_FAMILJ"],CFG["LBL_BEKANTA"],CFG["LBL_ESK"]]:
                    _add_hist_value(c, preview.get(c, 0))
                _after_save_housekeeping(preview)
            except Exception as e:
                st.error(f"Misslyckades att spara till Sheets: {e}")

# ====== Tabell lokalt ======
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

# ====== Statistik ======
st.markdown("---")
st.subheader("📊 Statistik")
if compute_stats:
    try:
        df = pd.DataFrame(st.session_state[ROWS_KEY])
        stats = compute_stats(df, st.session_state[CFG_KEY])
        for k, v in stats.items():
            st.write(f"**{k}**: {v}")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
else:
    st.caption("Ingen statistik-modul hittad (statistik.py).")
