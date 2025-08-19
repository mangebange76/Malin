# app.py — stabil bas (ingen Sheets), uppdaterad enligt dina punkter
import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
import random

from berakningar import berakna_radvarden as calc_row_values

# ================== Grund ==================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (stabil bas)")

CFG_KEY = "CFG"
DATA_KEY = "ROWS"
ROWNO_KEY = "ROW_NO"
HIST_KEY = "HIST_MINMAX"

def _init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7, 0),
            "fodelsedatum": date(1995, 1, 1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,    # all personal får lön (inte bara deltagit)
            "BONUS_AVAILABLE": 500,
            "ESK_MIN": 20,
            "ESK_MAX": 40,
        }
    if DATA_KEY not in st.session_state:
        st.session_state[DATA_KEY] = []  # sparas lokalt i sessionen
    if ROWNO_KEY not in st.session_state:
        st.session_state[ROWNO_KEY] = 0
    if HIST_KEY not in st.session_state:
        st.session_state[HIST_KEY] = {}
_init_state()
CFG = st.session_state[CFG_KEY]

def _next_scene_no() -> int:
    return st.session_state[ROWNO_KEY] + 1

def _scene_date_and_wd(scene_no: int):
    d = CFG["startdatum"] + timedelta(days=scene_no - 1)
    wd = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
    return d, wd

def _rebuild_hist_minmax():
    """Bygg min/max för slump från de lokalt sparade raderna."""
    cols = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]
    mm = {c:[None,None] for c in cols}
    for r in st.session_state[DATA_KEY]:
        for c in cols:
            try:
                v = int(r.get(c, 0) or 0)
            except Exception:
                v = 0
            if mm[c][0] is None or v < mm[c][0]: mm[c][0] = v
            if mm[c][1] is None or v > mm[c][1]: mm[c][1] = v
    st.session_state[HIST_KEY] = {c:(mm[c][0] or 0, mm[c][1] or 0) for c in cols}

# ================ Sidopanel (inställningar + scenario) ================
with st.sidebar:
    st.header("Inställningar")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift (USD)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))
    CFG["PROD_STAFF"]   = st.number_input("Totalt personal (får alltid lön)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    st.caption(f"Bonus killar tillgängliga: **{CFG['BONUS_AVAILABLE']}**")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=int(CFG["ESK_MIN"]), step=1, value=int(CFG["ESK_MAX"]))

    st.markdown("---")
    scenval = st.selectbox(
        "Scenario",
        ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet"],
        index=0
    )
    if st.button("⬇️ Hämta värden till formuläret"):
        st.session_state["SCEN_TO_APPLY"] = scenval
        st.rerun()

# ================ Input-fält (EXAKT ordning i EN kolumn) ================
st.markdown("### Inmatning (exakt ordning)")

def _ni(label, key, min_value=0, value=0, step=1, help=None, max_value=None):
    args = dict(label=label, min_value=min_value, step=step, key=key, help=help)
    if max_value is not None:
        args["max_value"] = max_value
    if key not in st.session_state:
        st.session_state[key] = value
    return st.number_input(**args, value=st.session_state[key])

# Ordningen du specificerade:
in_man     = _ni("Män", "in_män", value=0)
in_svarta  = _ni("Svarta", "in_svarta", value=0)
in_fitta   = _ni("Fitta", "in_fitta", value=0)
in_rumpa   = _ni("Rumpa", "in_rumpa", value=0)
in_dp      = _ni("DP", "in_dp", value=0)
in_dpp     = _ni("DPP", "in_dpp", value=0)
in_dap     = _ni("DAP", "in_dap", value=0)
in_tap     = _ni("TAP", "in_tap", value=0)

in_pappan  = _ni("Pappans vänner", "in_pappan", value=0)
in_grannar = _ni("Grannar", "in_grannar", value=0)
in_nv      = _ni("Nils vänner", "in_nils_vanner", value=0)
in_nf      = _ni("Nils familj", "in_nils_familj", value=0)
in_bek     = _ni("Bekanta", "in_bekanta", value=0)
in_esk     = _ni("Eskilstuna killar", "in_eskilstuna", value=0)

in_bonus_d = _ni(f"Bonus deltagit (tillgängligt: {CFG['BONUS_AVAILABLE']})", "in_bonus_deltagit", value=0,
                 max_value=int(CFG["BONUS_AVAILABLE"]))
in_pers_d  = _ni("Personal deltagit", "in_personal_deltagit", value=0)

in_alskar  = _ni("Älskar (antal)", "in_alskar", value=0)
in_sover   = _ni("Sover med (0/1)", "in_sover", value=0, max_value=1)

in_tid_s   = _ni("Tid S (sek)", "in_tid_s", value=60)
in_tid_d   = _ni("Tid D (sek)", "in_tid_d", value=60)
in_vila    = _ni("Vila (sek)", "in_vila", value=7)
in_dt_tid  = _ni("DT tid (sek/kille)", "in_dt_tid", value=60)
in_dt_vila = _ni("DT vila (sek/kille)", "in_dt_vila", value=3)

# ================ Scenariofyllning (rör BARA inputs) ================
def _hist_minmax(col):
    lo, hi = st.session_state[HIST_KEY].get(col, (0, 0))
    return int(lo), int(hi)

def _rand_hist(col):
    lo, hi = _hist_minmax(col)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

def _apply_scenario_to_inputs(name: str):
    def zero_many(keys):
        for k in keys: st.session_state[k] = 0

    if name == "Ny scen":
        # gör inget — låt dina manuella värden stå kvar
        return

    if name == "Slumpa scen vit":
        # Svarta ska ALLTID vara 0 här
        st.session_state["in_svarta"] = 0
        # Slumpa övriga
        st.session_state["in_män"]    = _rand_hist("Män")
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_pappan"] = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"]= _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"]     = _rand_hist("Bekanta")
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_personal_deltagit"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        # Bonus deltagit anger du själv (fältet står kvar)

    elif name == "Slumpa scen svart":
        # Svarta slumpas, alla källor 0, personal 0
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        zero_many(["in_män","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"])
        st.session_state["in_personal_deltagit"] = 0
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif name == "Vila på jobbet":
        # Slumpa: Pappans vänner, Grannar, Nils vänner, Nils familj, Bekanta, Eskilstuna killar
        for col, key in [
            ("Pappans vänner","in_pappan"),
            ("Grannar","in_grannar"),
            ("Nils vänner","in_nils_vanner"),
            ("Nils familj","in_nils_familj"),
            ("Bekanta","in_bekanta"),
        ]:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))

        # Sex-aktiviteter kan slumpas lätt från historik (eller nollas – din call).
        st.session_state["in_fitta"] = _rand_hist("Fitta")
        st.session_state["in_rumpa"] = _rand_hist("Rumpa")
        st.session_state["in_dp"]    = _rand_hist("DP")
        st.session_state["in_dpp"]   = _rand_hist("DPP")
        st.session_state["in_dap"]   = _rand_hist("DAP")
        st.session_state["in_tap"]   = _rand_hist("TAP")

        st.session_state["in_män"]    = 0   # enligt tidigare logik
        st.session_state["in_svarta"] = 0
        # Bonus/Personal anger du själv
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif name == "Vila i hemmet":
        # Slumpa: Pappans vänner, Grannar, Nils vänner, Nils familj, Bekanta, Eskilstuna killar
        for col, key in [
            ("Pappans vänner","in_pappan"),
            ("Grannar","in_grannar"),
            ("Nils vänner","in_nils_vanner"),
            ("Nils familj","in_nils_familj"),
            ("Bekanta","in_bekanta"),
        ]:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))

        # Sex-aktiviteter 0 hemma (enligt tidigare önskemål)
        zero_many(["in_män","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"])
        # Bonus/Personal anger du själv
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0  # sätt 1 själv när det är ‘sista dagen’

if "SCEN_TO_APPLY" in st.session_state:
    _apply_scenario_to_inputs(st.session_state.pop("SCEN_TO_APPLY"))

# ================ Live-förhandsvisning ================
def _build_base_for_calc():
    scen_no = _next_scene_no()
    d, wd = _scene_date_and_wd(scen_no)
    base = {
        "Datum": d.isoformat(),
        "Veckodag": wd,
        "Scen": scen_no,
        "Typ": "Händelse",

        # inputs
        "Män": st.session_state["in_män"],
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
    # Känner (radnivå) = fyra fält
    base["Känner"] = int(base["Pappans vänner"]) + int(base["Grannar"]) + int(base["Nils vänner"]) + int(base["Nils familj"])
    return base, d

base, rad_datum = _build_base_for_calc()
preview = calc_row_values(base, rad_datum, CFG["fodelsedatum"], CFG["starttid"])

st.markdown("### Live-förhandsvisning")
if not preview:
    st.info("Fyll i fält eller hämta scenvärden för att se förhandsvisning.")
else:
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid","-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid/kille", preview.get("Tid per kille","-"))
        st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Totalt män", int(preview.get("Totalt Män", 0)))
        st.metric("Klockan", preview.get("Klockan","-"))
    with c4:
        st.metric("Hårdhet", int(preview.get("Hårdhet", 0)))
        st.metric("Prenumeranter", int(preview.get("Prenumeranter", 0)))

    st.markdown("#### Ekonomi")
    e1,e2,e3,e4 = st.columns(4)
    with e1:
        st.metric("Intäkter", f"${float(preview.get('Intäkter', 0)):,.2f}")
    with e2:
        st.metric("Utgift män", f"${float(preview.get('Utgift män', 0)):,.2f}")
    with e3:
        st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner', 0)):,.2f}")
    with e4:
        st.metric("Lön Malin", f"${float(preview.get('Lön Malin', 0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst', 0)):,.2f}")

# ================ Spara lokalt (ingen Sheets här) ================
st.markdown("---")
if st.button("💾 Spara raden (lokalt i sessionen)"):
    if not preview:
        st.error("Inget att spara – fyll i fält eller hämta scenvärden först.")
    else:
        st.session_state[DATA_KEY].append(preview)
        st.session_state[ROWNO_KEY] += 1
        # minska tillgängliga bonuskillar med det du angett som deltagit
        used = int(base.get("Bonus deltagit", 0))
        CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - used)
        _rebuild_hist_minmax()
        st.success("✅ Rad sparad (lokalt).")

# Visa sparade rader
if st.session_state[DATA_KEY]:
    st.markdown("### Sparade rader (lokalt)")
    df = pd.DataFrame(st.session_state[DATA_KEY])
    st.dataframe(df, use_container_width=True)
