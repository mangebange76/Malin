import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import pandas as pd

# ======== App-inställningar ========
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (lokal + Sheets via SHEET_URL)")

# ======== State-nycklar ========
CFG_KEY       = "CFG"
ROWS_KEY      = "ROWS"          # sparade rader (lokalt minne)
HIST_MM_KEY   = "HIST_MINMAX"   # min/max per fält (bygger vi när du sparar rader)
SCENEINFO_KEY = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY  = "SCENARIO"      # rullist-valet

# Alla inputfält (EXAKT ordning du begärt)
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

# ======== Init ========
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # enligt din senaste önskan
            "startdatum": date(1990,1,1),
            "starttid": time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,         # hela personalstyrkan som ska få lön
            "BONUS_AVAILABLE": 500,    # tillgängliga bonuskillar (info)
            "ESK_MIN": 20, "ESK_MAX": 40,
            # Maxvärden för källor
            "MAX_PAPPAN": 100,
            "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100,
            "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []  # lista av dictar
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {} # t.ex. {"Fitta": (min,max), ...}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    # säkra alla inputs med default (tidsfält med dina standardvärden)
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))
    # sceninfo
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# ======== Import av beräkning ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# ======== Hjälpare för slump/minmax (MÅSTE ligga före sidopanelen) ========
def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        v = r.get(colname, 0)
        try: vals.append(int(v))
        except: pass
    if vals:
        mn, mx = min(vals), max(vals)
    else:
        mn = mx = 0
    st.session_state[HIST_MM_KEY][colname] = (mn, mx)
    return mn, mx

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

def apply_scenario_fill():
    """Fyller endast input-fälten i session_state – inga externa anrop."""
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    if s == "Ny scen":
        return

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        # övrigt 0, personal 0 redan

    elif s == "Vila på jobbet":
        for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                      ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                      ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        day = st.session_state.get("VIH_DAY", 1)
        day = st.number_input("Dag (1–7)", min_value=1, max_value=7, value=day, step=1, key="VIH_DAY")
        if day <= 5:
            for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                          ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[key] = _rand_hist(f)
            for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                          ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                          ("Nils familj","in_nils_familj")]:
                st.session_state[key] = _rand_hist(f)
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 0
            r = random.random()
            st.session_state["in_nils"] = 0 if r < 0.50 else (1 if r < 0.95 else 2)
        else:
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 1 if day == 7 else 0

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ======== Sidopanel ========
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    st.caption(f"Bonus killar tillgängliga (info): {int(CFG['BONUS_AVAILABLE'])}")

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
    st.subheader("Secrets-status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

# ======== Inmatning (EXAKT ordning, två kolumner snygg layout) ========
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":"Pappans vänner","in_grannar":"Grannar","in_nils_vanner":"Nils vänner","in_nils_familj":"Nils familj",
    "in_bekanta":"Bekanta","in_eskilstuna":"Eskilstuna killar",
    "in_bonus_deltagit":"Bonus deltagit","in_personal_deltagit":"Personal deltagit",
    "in_nils":"Nils"
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

# ======== Live-förhandsvisning ========
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen, "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),
        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],
        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],
        "Pappans vänner": st.session_state["in_pappan"], "Grannar": st.session_state["in_grannar"],
        "Nils vänner": st.session_state["in_nils_vanner"], "Nils familj": st.session_state["in_nils_familj"],
        "Bekanta": st.session_state["in_bekanta"], "Eskilstuna killar": st.session_state["in_eskilstuna"],
        "Bonus deltagit": st.session_state["in_bonus_deltagit"], "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Nils": st.session_state["in_nils"],
        "Avgift": float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"])
    }
    base["Känner"] = int(base["Pappans vänner"]) + int(base["Grannar"]) + int(base["Nils vänner"]) + int(base["Nils familj"])
    # meta för beräkning
    base["_rad_datum"] = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    # bonusrate: 1%
    base["BONUS_RATE"]    = 0.01
    return base

st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# ➕ Säkerställ att “Totalt Män” inkluderar Bekanta + Bonus deltagit + Personal deltagit
try:
    preview["Totalt Män"] = int(preview.get("Totalt Män", 0)) \
        + int(base.get("Bekanta", 0)) \
        + int(base.get("Bonus deltagit", 0)) \
        + int(base.get("Personal deltagit", 0))
except Exception:
    pass

# Överkant: datum/veckodag + ålder
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
alder = _d.year - fd.year - (( _d.month, _d.day) < (fd.month, fd.day))
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
    st.metric("Totalt män", int(preview.get("Totalt Män",0)))

# Hångel/Sug + Ekonomi
c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

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

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men lägger på klockan.")

# ======== Spara lokalt ========
st.markdown("---")
cL, cR = st.columns([1,1])
with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(preview)
        # uppdatera min/max
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]:
            v = int(preview.get(col,0))
            mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
            st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
        st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(0, int(st.session_state[CFG_KEY]["BONUS_AVAILABLE"]) - int(preview.get("Bonus deltagit",0)))
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad i minnet (ingen Sheets).")

# ======== Spara till Google Sheets (RADER, via SHEET_URL) ========
def save_row_to_sheets(row_dict: dict):
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")
    # cred kan vara JSON-sträng eller dict/AttrDict
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    import json
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
    try:
        ws = ss.worksheet("Data")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="Data", rows=2000, cols=80)

    # Header
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update(f"A1:{gspread.utils.rowcol_to_a1(1, len(header))}", [header])

    # rad-data enligt header-ordning
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            save_row_to_sheets(preview)
            st.success("✅ Raden sparad till Google Sheets (flik: Data).")
            # bumpa scen & min/max även lokalt
            st.session_state[ROWS_KEY].append(preview)
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]:
                v = int(preview.get(col,0))
                mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
                st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
            st.session_state[CFG_KEY]["BONUS_AVAILABLE"] = max(0, int(st.session_state[CFG_KEY]["BONUS_AVAILABLE"]) - int(preview.get("Bonus deltagit",0)))
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# ======== Spara INSTÄLLNINGAR till Google Sheets (ny) ========
st.markdown("---")
st.subheader("⚙️ Spara Inställningar till Google Sheets")

def save_settings_to_sheets(cfg: dict):
    """Sparar alla viktiga inställningar till fliken 'Inställningar' som Nyckel/Värde."""
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")

    import json
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
    try:
        ws = ss.worksheet("Inställningar")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="Inställningar", rows=200, cols=2)

    # Plocka ut settings vi vill spara
    keys = [
        "startdatum","starttid","fodelsedatum","avgift_usd","PROD_STAFF","BONUS_AVAILABLE",
        "ESK_MIN","ESK_MAX",
        "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA"
    ]
    rows = []
    for k in keys:
        v = cfg.get(k)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif isinstance(v, time):
            v = v.strftime("%H:%M")
        rows.append([k, v if v is not None else ""])

    # skriv header + rader
    ws.clear()
    ws.update("A1:B1", [["Nyckel","Värde"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

if st.button("💽 Spara inställningar till Google Sheets"):
    try:
        save_settings_to_sheets(st.session_state[CFG_KEY])
        st.success("✅ Inställningar sparade till fliken 'Inställningar'.")
    except Exception as e:
        st.error(f"Misslyckades att spara inställningar: {e}")

# ======== Visa lokala rader ========
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=300)
else:
    st.info("Inga lokala rader ännu.")
