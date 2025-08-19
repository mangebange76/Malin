# app.py
import streamlit as st
from datetime import date, time, timedelta, datetime
import random

# Alla beräkningar ligger i berakningar.py
from berakningar import berakna_radvarden as calc_row_values

st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")

# ---------------- Session keys & defaults ----------------
CFG_KEY      = "CFG"
DATA_KEY     = "LOCAL_ROWS"
ROWCOUNT_KEY = "ROWCOUNT_LOCAL"

def _init_defaults():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid":   time(7, 0),
            "fodelsedatum": date(1995,1,1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,
            "ESK_MIN": 20,
            "ESK_MAX": 40,
            "BONUS_AVAILABLE": 500,
        }
    if DATA_KEY not in st.session_state:
        st.session_state[DATA_KEY] = []  # lokal “databas”
    if ROWCOUNT_KEY not in st.session_state:
        st.session_state[ROWCOUNT_KEY] = 0

    # init inputs (ASCII-nycklar!)
    defaults = {
        "in_man":0, "in_svarta":0,
        "in_fitta":0, "in_rumpa":0, "in_dp":0, "in_dpp":0, "in_dap":0, "in_tap":0,
        "in_pappan":0, "in_grannar":0, "in_nils_vanner":0, "in_nils_familj":0,
        "in_bekanta":0, "in_eskilstuna":0,
        "in_bonus_deltagit":0, "in_personal_deltagit":0,
        "in_alskar":0, "in_sover":0,
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_typ":"Ny scen",
    }
    for k,v in defaults.items():
        st.session_state.setdefault(k, v)

_init_defaults()
CFG = st.session_state[CFG_KEY]

def _next_scene_number():
    return st.session_state[ROWCOUNT_KEY] + 1

def _scene_date_and_weekday(scene_no: int):
    d = CFG["startdatum"] + timedelta(days=scene_no - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

# ---------------- Sidopanel ----------------
with st.sidebar:
    st.header("Inställningar")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"], key="cfg_startdatum")
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"], key="cfg_starttid")
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"], key="cfg_fodelsedatum")
    CFG["avgift_usd"]   = st.number_input("Avgift (USD)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="cfg_avgift")
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (för lön)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]), key="cfg_prod_staff")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]), key="cfg_esk_min")
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], step=1, value=int(CFG["ESK_MAX"]), key="cfg_esk_max")

    st.markdown("---")
    st.subheader("Bonus killar (tillgängligt)")
    st.write(f"**{CFG['BONUS_AVAILABLE']}** st tillgängliga")

# ---------------- Scenario “Hämta värden” ----------------
st.subheader("⚙️ Hämta/slumpa scenvärden (fyller endast in fält)")
scenario = st.selectbox(
    "Välj åtgärd",
    ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet"],
    index=0,
    key="scenario_select"
)

def _hist_minmax(colname: str):
    rows = st.session_state[DATA_KEY]
    if not rows: return (0,0)
    vals = []
    for r in rows:
        try:
            vals.append(int(r.get(colname, 0) or 0))
        except Exception:
            pass
    return (min(vals), max(vals)) if vals else (0,0)

def _rand_hist(col):
    lo, hi = _hist_minmax(col)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

if st.button("📥 Hämta/Slumpa till input", use_container_width=True, key="btn_fetch"):
    # bestäm scenens datum
    scen_no = _next_scene_number()
    d, _ = _scene_date_and_weekday(scen_no)

    if scenario == "Ny scen":
        # nollställ (du fyller bonus/personaldeltagit manuellt)
        keep = ["in_tid_s","in_tid_d","in_vila","in_dt_tid","in_dt_vila"]
        for k in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
                  "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna",
                  "in_alskar","in_sover","in_bonus_deltagit","in_personal_deltagit"]:
            st.session_state[k] = st.session_state.get(k, 0)
        st.session_state["in_typ"] = "Ny scen"

    elif scenario == "Slumpa scen vit":
        # Svarta = 0 (alltid)
        st.session_state["in_svarta"] = 0
        # slumpa övriga från historik
        st.session_state["in_man"]    = _rand_hist("Män")
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_pappan"] = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"] = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"] = _rand_hist("Bekanta")
        # Eskilstuna från intervall
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # default
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Ny scen"

    elif scenario == "Slumpa scen svart":
        # slumpa akter + svarta; övriga källor 0, personal 0
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for k in ["in_man","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
            st.session_state[k] = 0
        st.session_state["in_personal_deltagit"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Ny scen (svart)"

    elif scenario == "Vila på jobbet":
        # slumpa även källfälten + akterna
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_pappan"] = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"] = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"] = _rand_hist("Bekanta")
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # du anger själv bonus/personaldeltagit
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Vila på jobbet"

    elif scenario == "Vila i hemmet":
        # slumpa samma källfält; akter = 0 enligt vila
        for k in ["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap","in_man","in_svarta"]:
            st.session_state[k] = 0
        st.session_state["in_pappan"] = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"] = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"] = _rand_hist("Bekanta")
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # bonus/personaldeltagit anger du
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_typ"] = "Vila i hemmet"

    st.rerun()

# app.py (forts)

st.markdown("---")
st.subheader("📝 Inmatning (ordning enligt din lista)")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.number_input("Män",    min_value=0, step=1, key="in_man")
    st.number_input("Svarta", min_value=0, step=1, key="in_svarta")
    st.number_input("Fitta",  min_value=0, step=1, key="in_fitta")
    st.number_input("Rumpa",  min_value=0, step=1, key="in_rumpa")
    st.number_input("DP",     min_value=0, step=1, key="in_dp")
    st.number_input("DPP",    min_value=0, step=1, key="in_dpp")

with c2:
    st.number_input("DAP",    min_value=0, step=1, key="in_dap")
    st.number_input("TAP",    min_value=0, step=1, key="in_tap")
    st.number_input("Pappans vänner", min_value=0, step=1, key="in_pappan")
    st.number_input("Grannar",         min_value=0, step=1, key="in_grannar")
    st.number_input("Nils vänner",     min_value=0, step=1, key="in_nils_vanner")
    st.number_input("Nils familj",     min_value=0, step=1, key="in_nils_familj")

with c3:
    st.number_input("Bekanta",           min_value=0, step=1, key="in_bekanta")
    st.number_input("Eskilstuna killar", min_value=0, step=1, key="in_eskilstuna")
    st.number_input("Bonus deltagit",    min_value=0, step=1, key="in_bonus_deltagit",
                    help=f"Tillgängligt: {CFG['BONUS_AVAILABLE']}")
    st.number_input("Personal deltagit", min_value=0, step=1, key="in_personal_deltagit",
                    help=f"Total personal (får lön): {CFG['PROD_STAFF']}")

    st.number_input("Älskar",            min_value=0, step=1, key="in_alskar")
    st.number_input("Sover med (0/1)",   min_value=0, max_value=1, step=1, key="in_sover")

with c4:
    st.number_input("Tid S (sek)",           min_value=0, step=1, key="in_tid_s")
    st.number_input("Tid D (sek)",           min_value=0, step=1, key="in_tid_d")
    st.number_input("Vila (sek)",            min_value=0, step=1, key="in_vila")
    st.number_input("DT tid (sek/kille)",    min_value=0, step=1, key="in_dt_tid")
    st.number_input("DT vila (sek/kille)",   min_value=0, step=1, key="in_dt_vila")

# Bygg basrad och beräkna preview
def _build_base_row():
    scen_no = _next_scene_number()
    rad_datum, veckodag = _scene_date_and_weekday(scen_no)
    base = {
        "Typ": st.session_state.get("in_typ","Ny scen"),
        "Män": st.session_state["in_man"],
        "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"],
        "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"],
        "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"],
        "TAP": st.session_state["in_tap"],
        "Pappans vänner": st.session_state["in_pappan"],
        "Grannar": st.session_state["in_grannar"],
        "Nils vänner": st.session_state["in_nils_vanner"],
        "Nils familj": st.session_state["in_nils_familj"],
        "Bekanta": st.session_state["in_bekanta"],
        "Eskilstuna killar": st.session_state["in_eskilstuna"],
        "Bonus deltagit": st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Älskar": st.session_state["in_alskar"],
        "Sover med": st.session_state["in_sover"],
        "Tid S": st.session_state["in_tid_s"],
        "Tid D": st.session_state["in_tid_d"],
        "Vila":  st.session_state["in_vila"],
        "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
        "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Avgift": float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }
    return base, rad_datum

base, rad_dt = _build_base_row()
preview = calc_row_values(base, rad_dt, CFG["fodelsedatum"], CFG["starttid"])

# Livepanel
st.markdown("---")
st.subheader("🔎 Live – förhandsvisning")
if not preview:
    st.info("Fyll i fält eller hämta ett scenario.")
else:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid","-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
    with c2:
        st.metric("Tid/kille", preview.get("Tid per kille","-"))
        st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
    with c3:
        st.metric("Klockan", preview.get("Klockan","-"))
        st.metric("Totalt män", int(preview.get("Totalt Män",0)))
    with c4:
        st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
        st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))

    st.caption("Älskar/Sover ingår inte i Summa tid, men läggs på klockan.")

# app.py (forts – spara lokalt + visa tabell)

st.markdown("---")
if st.button("💾 Spara raden (lokalt)", use_container_width=True, key="btn_save"):
    row = dict(preview)  # spara allt beräknat
    st.session_state[DATA_KEY].append(row)
    st.session_state[ROWCOUNT_KEY] += 1

    # uppdatera bonus-available: dra bort det du angav som “deltagit”
    used = int(st.session_state.get("in_bonus_deltagit",0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - used)

    st.success("Rad sparad lokalt ✅")

# Visa lokala rader
st.subheader("📋 Lokala rader")
rows = st.session_state[DATA_KEY]
if rows:
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.caption("Inga sparade rader ännu.")
