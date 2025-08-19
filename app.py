import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import pandas as pd

# ======== App-inställningar ========
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (lokal, utan Sheets)")

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
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_alskar","in_sover",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila"
]

# ======== Init ========
def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7,0),
            "fodelsedatum": date(1995,1,1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,         # hela personalstyrkan som ska få lön
            "BONUS_AVAILABLE": 500,    # tillgängliga bonuskillar (info)
            "ESK_MIN": 20, "ESK_MAX": 40,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []  # lista av dictar
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {} # t.ex. {"Fitta": (min,max), ...}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    # säkra alla inputs med default = 0
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, 0)
    # sceninfo
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

init_state()

# ======== Import av beräkning ========
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

CFG = st.session_state[CFG_KEY]

# ======== Sidopanel ========
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
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

# ======== Hjälpare för slump/minmax ========
def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    # bygg från sparade rader om finns:
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

# ======== Scenario-fyllning (INGA externa anrop) ========
def apply_scenario_fill():
    scen, d, _ = st.session_state[SCENEINFO_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla alla inputs först
    for k in INPUT_ORDER: st.session_state[k] = 0

    if s == "Ny scen":
        # allt 0 – du matar in själv
        pass

    elif s == "Slumpa scen vit":
        # Svarta = 0 (alltid)
        st.session_state["in_svarta"] = 0
        # Slumpa övriga via historik
        st.session_state["in_man"]    = _rand_hist("Män")
        st.session_state["in_fitta"]  = _rand_hist("Fitta")
        st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
        st.session_state["in_dp"]     = _rand_hist("DP")
        st.session_state["in_dpp"]    = _rand_hist("DPP")
        st.session_state["in_dap"]    = _rand_hist("DAP")
        st.session_state["in_tap"]    = _rand_hist("TAP")
        st.session_state["in_pappan"]      = _rand_hist("Pappans vänner")
        st.session_state["in_grannar"]     = _rand_hist("Grannar")
        st.session_state["in_nils_vanner"] = _rand_hist("Nils vänner")
        st.session_state["in_nils_familj"] = _rand_hist("Nils familj")
        st.session_state["in_bekanta"]     = _rand_hist("Bekanta")
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        # bonus/personaldeltagit anger du manuellt

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        # övriga källor = 0, personal deltagit = 0
        # (redan nollat ovan)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        # Slumpa också källor du bad om:
        for f, key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                       ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                       ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # Sexuella fält slumpas också enligt din begäran:
        for f, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                       ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        # bonus/personaldeltagit anger du själv

    elif s == "Vila i hemmet (dag 1–7)":
        # Visa en dag i taget. Dag (1..7) väljs här:
        day = st.session_state.get("VIH_DAY", 1)
        day = st.number_input("Dag (1–7)", min_value=1, max_value=7, value=day, step=1, key="VIH_DAY")
        if day <= 5:
            # Slumpa ALLA fält du listade (utom bonus/personaldeltagit som du matar själv)
            st.session_state["in_fitta"]  = _rand_hist("Fitta")
            st.session_state["in_rumpa"]  = _rand_hist("Rumpa")
            st.session_state["in_dp"]     = _rand_hist("DP")
            st.session_state["in_dpp"]    = _rand_hist("DPP")
            st.session_state["in_dap"]    = _rand_hist("DAP")
            st.session_state["in_tap"]    = _rand_hist("TAP")
            for f, key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                           ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                           ("Nils familj","in_nils_familj")]:
                st.session_state[key] = _rand_hist(f)
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 0
            # Nils slump enligt 50/45/5 → 0/1/2 ettor över dag 1–6.
            # Enkelt: 0 eller 1 eller 2 på just denna dag (väldigt enkelt när bara en dag visas)
            r = random.random()
            st.session_state["in_nils"] = 0 if r < 0.50 else (1 if r < 0.95 else 2)
        else:
            # Dag 6–7: allt 0 utom älskar=6
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 1 if day == 7 else 0
            # övriga ligger kvar som 0 (nollade i början)

    # Uppdatera sceninfo (så datum/veckodag i liven stämmer)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ======== UI – Inmatningsraden (EXAKT ordning) ========
st.subheader("Input (fritext – inget sparas förrän du trycker Spara)")
c1,c2,c3,c4 = st.columns(4)

with c1:
    st.number_input("Män",    min_value=0, step=1, key="in_man")
    st.number_input("Fitta",  min_value=0, step=1, key="in_fitta")
    st.number_input("DP",     min_value=0, step=1, key="in_dp")
    st.number_input("DAP",    min_value=0, step=1, key="in_dap")
    st.number_input("Pappans vänner", min_value=0, step=1, key="in_pappan")
    st.number_input("Nils vänner",    min_value=0, step=1, key="in_nils_vanner")
    st.number_input("Bekanta",        min_value=0, step=1, key="in_bekanta")
    st.number_input("Bonus deltagit", min_value=0, step=1, key="in_bonus_deltagit")
    st.number_input("Älskar",         min_value=0, step=1, key="in_alskar")
    st.number_input("Tid S (sek)",    min_value=0, step=1, key="in_tid_s")
    st.number_input("Vila (sek)",     min_value=0, step=1, key="in_vila")
    st.number_input("DT tid (sek/kille)",  min_value=0, step=1, key="in_dt_tid")

with c2:
    st.number_input("Svarta", min_value=0, step=1, key="in_svarta")
    st.number_input("Rumpa",  min_value=0, step=1, key="in_rumpa")
    st.number_input("DPP",    min_value=0, step=1, key="in_dpp")
    st.number_input("TAP",    min_value=0, step=1, key="in_tap")
    st.number_input("Grannar",        min_value=0, step=1, key="in_grannar")
    st.number_input("Nils familj",    min_value=0, step=1, key="in_nils_familj")
    st.number_input("Eskilstuna killar", min_value=0, step=1, key="in_eskilstuna")
    st.number_input("Personal deltagit", min_value=0, step=1, key="in_personal_deltagit")
    st.number_input("Sover med (0/1)",   min_value=0, max_value=1, step=1, key="in_sover")
    st.number_input("Tid D (sek)",    min_value=0, step=1, key="in_tid_d")
    st.number_input("Nils",           min_value=0, step=1, key="in_nils")
    st.number_input("DT vila (sek/kille)", min_value=0, step=1, key="in_dt_vila")

# ======== Live-förhandsvisning ========
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen, "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),
        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],
        "Pappans vänner": st.session_state["in_pappan"], "Grannar": st.session_state["in_grannar"],
        "Nils vänner": st.session_state["in_nils_vanner"], "Nils familj": st.session_state["in_nils_familj"],
        "Bekanta": st.session_state["in_bekanta"], "Eskilstuna killar": st.session_state["in_eskilstuna"],
        "Bonus deltagit": st.session_state["in_bonus_deltagit"], "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],
        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Nils": st.session_state["in_nils"], "Avgift": float(CFG["avgift_usd"]),
        # Lönebas: hela personalstyrkan
        "PROD_STAFF": int(CFG["PROD_STAFF"])
    }
    # härled Känner av fyra fält
    base["Känner"] = int(base["Pappans vänner"]) + int(base["Grannar"]) + int(base["Nils vänner"]) + int(base["Nils familj"])
    # meta för beräkning
    base["_rad_datum"] = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"] = CFG["starttid"]
    return base

st.markdown("---")
st.subheader("🔎 Live")
base = build_base_from_inputs()
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    # äldre signatur
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

c1,c2,c3,c4 = st.columns(4)
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
    st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))

e1,e2,e3 = st.columns(3)
with e1:
    st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
with e2:
    st.metric("Utgift män", f"${float(preview.get('Utgift män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e3:
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)",0)))

st.caption("Hångel räknas separat och påverkar inget annat.")

# ======== Spara lokalt (till minnet) ========
st.markdown("---")
if st.button("💾 Spara raden (lokalt)"):
    st.session_state[ROWS_KEY].append(preview)
    # uppdatera min/max för slump framöver
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP","Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]:
        v = int(preview.get(col,0))
        mn,mx = st.session_state[HIST_MM_KEY].get(col,(v,v))
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
    # bonus-available: minska med inmatat bonus deltagit (du styr själv)
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - int(preview.get("Bonus deltagit",0)))
    # nästa scen
    st.session_state[SCENEINFO_KEY] = _current_scene_info()
    st.success("✅ Sparad i minnet (ingen Sheets).")

# ======== Visa lokala rader ========
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=300)
else:
    st.info("Inga lokala rader ännu.")
