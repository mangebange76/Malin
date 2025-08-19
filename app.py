# malin app – 0.9.8-stable (part 1/6)
import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
import random

APP_VERSION = "malin-app 0.9.8-stable"
APP_SIGNATURE = {
    "no_sheets_until_save": True,
    "inputs_order": [
        "in_män","in_svarta",
        "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna",
        "in_bonus_deltagit","in_personal_deltagit",
        "in_alskar","in_sover",
        "in_tid_s","in_tid_d","in_vila",
        "in_dt_tid","in_dt_vila"
    ],
    "scenarios": ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet"]
}

# -------------------------
# Grundinställningar
# -------------------------
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")
st.caption(f"Version: **{APP_VERSION}**")

# -------------------------
# Session keys
# -------------------------
CFG_KEY         = "CFG"
DATA_KEY        = "LOCAL_ROWS"         # lokal lista av sparade rader (om du inte sparar till Sheets)
ROWCOUNT_KEY    = "ROWCOUNT_LOCAL"     # scennummer lokalt
SCENEINFO_KEY   = "CURRENT_SCENE_INFO" # (scen, datum, veckodag)
HIST_MINMAX_KEY = "HIST_MINMAX"        # cache för lokala min/max
SCENARIO_KEY    = "SCENARIO_SELECT"    # rullistval
# in-form fält (måste stämma exakt med din ordning)
INPUT_KEYS = list(APP_SIGNATURE["inputs_order"])
# extra fält vi använder lokalt
EXTRA_INPUTS = ["in_nils", "in_avgift", "in_typ"]
ALL_FORM_KEYS = INPUT_KEYS + EXTRA_INPUTS

# -------------------------
# Initiera session_state
# -------------------------
def _init_defaults():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7, 0),
            "fodelsedatum": date(1995, 1, 1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,     # hela personalstyrkan för lön
            "BONUS_AVAILABLE": 500,
            "ESK_MIN": 20, "ESK_MAX": 40
        }
    if DATA_KEY not in st.session_state:
        st.session_state[DATA_KEY] = []   # lista med sparade rader (om du väljer att inte skriva till Sheets)
    if ROWCOUNT_KEY not in st.session_state:
        st.session_state[ROWCOUNT_KEY] = 0
    if HIST_MINMAX_KEY not in st.session_state:
        st.session_state[HIST_MINMAX_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if SCENEINFO_KEY not in st.session_state:
        # sätts strax nedan utifrån startdatum
        pass
    # säkerställ alla formfält finns (0 som default)
    for k in ALL_FORM_KEYS:
        st.session_state.setdefault(k, 0)

_init_defaults()
CFG = st.session_state[CFG_KEY]

# -------------------------
# Hjälpmetoder (ingen Sheets)
# -------------------------
def _next_scene_number() -> int:
    return int(st.session_state.get(ROWCOUNT_KEY, 0)) + 1

def _scene_date_and_weekday(scene_no: int):
    d = CFG["startdatum"] + timedelta(days=scene_no - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

def _ensure_sceneinfo():
    scen = _next_scene_number()
    d, veckodag = _scene_date_and_weekday(scen)
    st.session_state[SCENEINFO_KEY] = (scen, d, veckodag)

_ensure_sceneinfo()

def _self_test_ui():
    with st.sidebar.expander("⚙️ Självtest / Debug", expanded=False):
        st.write(f"Version: **{APP_VERSION}**")
        # kontrollera inputordning
        ok_order = (INPUT_KEYS == APP_SIGNATURE["inputs_order"])
        st.write("Input-ordning:", "✅ OK" if ok_order else "❌ FEL")
        # kontroll att vi inte har några Sheets-objekt i minnet
        sheets_loaded = any(k in st.session_state for k in ["GOOGLE_SHEET_ID","sheet","gspread_client"])
        st.write("No Sheets förrän Spara:", "✅ OK" if not sheets_loaded else "⚠️ KAN FINNAS")

_self_test_ui()

def _update_hist_minmax_with_row(row: dict):
    """Uppdatera lokala min/max baserat på sparade rader."""
    mm = st.session_state[HIST_MINMAX_KEY]
    for k, v in row.items():
        if not isinstance(v, (int, float)): 
            continue
        cur = mm.get(k)
        if cur is None:
            mm[k] = (v, v)
        else:
            lo, hi = cur
            mm[k] = (min(lo, v), max(hi, v))

def _rand_from_hist(col: str, default_lo=0, default_hi=0):
    lo, hi = st.session_state.get(HIST_MINMAX_KEY, {}).get(col, (default_lo, default_hi))
    if hi < lo: hi = lo
    return int(random.randint(lo, hi)) if hi > lo else int(lo)

def _age_on(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

# malin app – 0.9.8-stable (part 2/6)

# -------------------------
# Sidopanel – Inställningar
# -------------------------
with st.sidebar:
    st.header("Inställningar")
    CFG["startdatum"] = st.date_input("Startdatum (för scen-datum)", value=CFG["startdatum"], key="cfg_startdatum")
    CFG["starttid"]   = st.time_input("Starttid", value=CFG["starttid"], key="cfg_starttid")
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"], key="cfg_fodelsedatum")
    CFG["avgift_usd"] = st.number_input("Avgift (USD per prenumerant)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0, key="cfg_avgift")
    CFG["PROD_STAFF"] = st.number_input("Totalt antal personal (för lön)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1, key="cfg_prodstaff")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (slump)")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1, key="cfg_esk_min")
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1, key="cfg_esk_max")

    st.markdown("---")
    st.write(f"**Bonus killar tillgängliga:** {int(CFG['BONUS_AVAILABLE'])}")
    st.write(f"**Personal (fast, lönebas):** {int(CFG['PROD_STAFF'])}")

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        APP_SIGNATURE["scenarios"],
        index=APP_SIGNATURE["scenarios"].index(st.session_state[SCENARIO_KEY])
    )

    if st.button("⬇️ Hämta / Slumpa värden till formuläret", use_container_width=True, key="btn_fetch"):
        st.session_state["__DO_SCENARIO_FILL__"] = True
        st.rerun()

# -------------------------
# Formulär – Input i exakt ordning
# -------------------------
st.markdown("### Inmatning (exakt ordning)")
scen, rad_datum, veckodag = st.session_state[SCENEINFO_KEY]
st.caption(f"Scen #{scen} – {rad_datum} ({veckodag})")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.session_state["in_män"]     = st.number_input("Män", min_value=0, step=1, value=int(st.session_state.get("in_män", 0)), key="in_män")
    st.session_state["in_svarta"]  = st.number_input("Svarta", min_value=0, step=1, value=int(st.session_state.get("in_svarta", 0)), key="in_svarta")
    st.session_state["in_fitta"]   = st.number_input("Fitta", min_value=0, step=1, value=int(st.session_state.get("in_fitta", 0)), key="in_fitta")
    st.session_state["in_rumpa"]   = st.number_input("Rumpa", min_value=0, step=1, value=int(st.session_state.get("in_rumpa", 0)), key="in_rumpa")
    st.session_state["in_dp"]      = st.number_input("DP", min_value=0, step=1, value=int(st.session_state.get("in_dp", 0)), key="in_dp")
    st.session_state["in_dpp"]     = st.number_input("DPP", min_value=0, step=1, value=int(st.session_state.get("in_dpp", 0)), key="in_dpp")

with c2:
    st.session_state["in_dap"]     = st.number_input("DAP", min_value=0, step=1, value=int(st.session_state.get("in_dap", 0)), key="in_dap")
    st.session_state["in_tap"]     = st.number_input("TAP", min_value=0, step=1, value=int(st.session_state.get("in_tap", 0)), key="in_tap")
    st.session_state["in_pappan"]  = st.number_input("Pappans vänner", min_value=0, step=1, value=int(st.session_state.get("in_pappan", 0)), key="in_pappan")
    st.session_state["in_grannar"] = st.number_input("Grannar", min_value=0, step=1, value=int(st.session_state.get("in_grannar", 0)), key="in_grannar")
    st.session_state["in_nils_vanner"]  = st.number_input("Nils vänner", min_value=0, step=1, value=int(st.session_state.get("in_nils_vanner", 0)), key="in_nils_vanner")
    st.session_state["in_nils_familj"]  = st.number_input("Nils familj", min_value=0, step=1, value=int(st.session_state.get("in_nils_familj", 0)), key="in_nils_familj")

with c3:
    st.session_state["in_bekanta"] = st.number_input("Bekanta", min_value=0, step=1, value=int(st.session_state.get("in_bekanta", 0)), key="in_bekanta")
    st.session_state["in_eskilstuna"] = st.number_input("Eskilstuna killar", min_value=0, step=1, value=int(st.session_state.get("in_eskilstuna", 0)), key="in_eskilstuna")
    st.session_state["in_bonus_deltagit"]    = st.number_input(f"Bonus deltagit (tillgängligt: {int(CFG['BONUS_AVAILABLE'])})", min_value=0, step=1, value=int(st.session_state.get("in_bonus_deltagit", 0)), key="in_bonus_deltagit")
    st.session_state["in_personal_deltagit"] = st.number_input("Personal deltagit (du anger)", min_value=0, step=1, value=int(st.session_state.get("in_personal_deltagit", 0)), key="in_personal_deltagit")
    st.session_state["in_alskar"]   = st.number_input("Älskar (antal)", min_value=0, step=1, value=int(st.session_state.get("in_alskar", 0)), key="in_alskar")
    st.session_state["in_sover"]    = st.number_input("Sover med (0/1)", min_value=0, max_value=1, step=1, value=int(st.session_state.get("in_sover", 0)), key="in_sover")

with c4:
    st.session_state["in_tid_s"]   = st.number_input("Tid S (sek)", min_value=0, step=1, value=int(st.session_state.get("in_tid_s", 60)), key="in_tid_s")
    st.session_state["in_tid_d"]   = st.number_input("Tid D (sek)", min_value=0, step=1, value=int(st.session_state.get("in_tid_d", 60)), key="in_tid_d")
    st.session_state["in_vila"]    = st.number_input("Vila (sek)", min_value=0, step=1, value=int(st.session_state.get("in_vila", 7)), key="in_vila")
    st.session_state["in_dt_tid"]  = st.number_input("DT tid (sek/kille)", min_value=0, step=1, value=int(st.session_state.get("in_dt_tid", 60)), key="in_dt_tid")
    st.session_state["in_dt_vila"] = st.number_input("DT vila (sek/kille)", min_value=0, step=1, value=int(st.session_state.get("in_dt_vila", 3)), key="in_dt_vila")

# extra (behöver ej påverka ordningen)
st.session_state["in_nils"]   = st.number_input("Nils", min_value=0, step=1, value=int(st.session_state.get("in_nils", 0)), key="in_nils")
st.session_state["in_avgift"] = st.number_input("Avgift (USD)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]), key="in_avgift")
st.session_state["in_typ"]    = st.text_input("Typ (auto från scenario)", value=str(st.session_state.get("in_typ", "")), key="in_typ")

# malin app – 0.9.8-stable (part 3/6)

# -------------------------
# Scenario-fyllnad (rör bara input-fälten)
# -------------------------
def _fill_new_scene_defaults():
    # Nollställ “svarta” i vit scen, personal & bonus anger du själv
    for k in ["in_män","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
              "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta",
              "in_eskilstuna"]:
        st.session_state[k] = st.session_state.get(k, 0)
    st.session_state["in_svarta"] = 0
    st.session_state["in_bonus_deltagit"] = st.session_state.get("in_bonus_deltagit", 0)
    st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)
    st.session_state["in_alskar"] = st.session_state.get("in_alskar", 0)
    st.session_state["in_sover"]  = st.session_state.get("in_sover", 0)
    st.session_state["in_typ"]    = "Ny scen"

def _apply_scenario_fill_once():
    """Kallas efter click på 'Hämta/Slumpa' – Fyller bara formuläret."""
    scenario = st.session_state[SCENARIO_KEY]

    # Ny scen = nollställ (svarta = 0)
    if scenario == "Ny scen":
        _fill_new_scene_defaults()
        return

    # Slumpa scen vit – Svarta **alltid 0**
    if scenario == "Slumpa scen vit":
        st.session_state["in_män"]    = _rand_from_hist("Män", 0, 0)
        st.session_state["in_svarta"] = 0
        st.session_state["in_fitta"]  = _rand_from_hist("Fitta", 0, 0)
        st.session_state["in_rumpa"]  = _rand_from_hist("Rumpa", 0, 0)
        st.session_state["in_dp"]     = _rand_from_hist("DP", 0, 0)
        st.session_state["in_dpp"]    = _rand_from_hist("DPP", 0, 0)
        st.session_state["in_dap"]    = _rand_from_hist("DAP", 0, 0)
        st.session_state["in_tap"]    = _rand_from_hist("TAP", 0, 0)

        st.session_state["in_pappan"]      = _rand_from_hist("Pappans vänner", 0, 0)
        st.session_state["in_grannar"]     = _rand_from_hist("Grannar", 0, 0)
        st.session_state["in_nils_vanner"] = _rand_from_hist("Nils vänner", 0, 0)
        st.session_state["in_nils_familj"] = _rand_from_hist("Nils familj", 0, 0)
        st.session_state["in_bekanta"]     = _rand_from_hist("Bekanta", 0, 0)

        # Eskilstuna via sidopanelintervall
        esk_lo, esk_hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
        if esk_hi < esk_lo: esk_hi = esk_lo
        st.session_state["in_eskilstuna"] = random.randint(esk_lo, esk_hi)

        # Bonus/Personal anger du själv
        st.session_state["in_bonus_deltagit"]    = st.session_state.get("in_bonus_deltagit", 0)
        st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)

        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"]    = "Ny scen (vit)"
        return

    # Slumpa scen svart – källor 0, personal 0
    if scenario == "Slumpa scen svart":
        st.session_state["in_män"] = 0
        st.session_state["in_svarta"] = _rand_from_hist("Svarta", 0, 0)
        st.session_state["in_fitta"]  = _rand_from_hist("Fitta", 0, 0)
        st.session_state["in_rumpa"]  = _rand_from_hist("Rumpa", 0, 0)
        st.session_state["in_dp"]     = _rand_from_hist("DP", 0, 0)
        st.session_state["in_dpp"]    = _rand_from_hist("DPP", 0, 0)
        st.session_state["in_dap"]    = _rand_from_hist("DAP", 0, 0)
        st.session_state["in_tap"]    = _rand_from_hist("TAP", 0, 0)

        for k in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
            st.session_state[k] = 0

        st.session_state["in_bonus_deltagit"]    = st.session_state.get("in_bonus_deltagit", 0)
        st.session_state["in_personal_deltagit"] = 0  # enligt krav

        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"]    = "Ny scen (svart)"
        return

    # Vila på jobbet – slumpa även källfälten
    if scenario == "Vila på jobbet":
        # Sexuella delar slumpas från historiska intervall
        st.session_state["in_fitta"]  = _rand_from_hist("Fitta", 0, 0)
        st.session_state["in_rumpa"]  = _rand_from_hist("Rumpa", 0, 0)
        st.session_state["in_dp"]     = _rand_from_hist("DP", 0, 0)
        st.session_state["in_dpp"]    = _rand_from_hist("DPP", 0, 0)
        st.session_state["in_dap"]    = _rand_from_hist("DAP", 0, 0)
        st.session_state["in_tap"]    = _rand_from_hist("TAP", 0, 0)

        # Källor slumpas också
        st.session_state["in_pappan"]      = _rand_from_hist("Pappans vänner", 0, 0)
        st.session_state["in_grannar"]     = _rand_from_hist("Grannar", 0, 0)
        st.session_state["in_nils_vanner"] = _rand_from_hist("Nils vänner", 0, 0)
        st.session_state["in_nils_familj"] = _rand_from_hist("Nils familj", 0, 0)
        st.session_state["in_bekanta"]     = _rand_from_hist("Bekanta", 0, 0)

        esk_lo, esk_hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
        if esk_hi < esk_lo: esk_hi = esk_lo
        st.session_state["in_eskilstuna"] = random.randint(esk_lo, esk_hi)

        # Resterande sätter du själv
        st.session_state["in_män"] = 0
        st.session_state["in_svarta"] = 0
        st.session_state["in_bonus_deltagit"]    = st.session_state.get("in_bonus_deltagit", 0)
        st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)

        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"]    = "Vila på jobbet"
        return

    # Vila i hemmet – slumpa källfälten
    if scenario == "Vila i hemmet":
        # inga sexuella aktiva delar
        for k in ["in_män","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
            st.session_state[k] = 0

        # Källor slumpas
        st.session_state["in_pappan"]      = _rand_from_hist("Pappans vänner", 0, 0)
        st.session_state["in_grannar"]     = _rand_from_hist("Grannar", 0, 0)
        st.session_state["in_nils_vanner"] = _rand_from_hist("Nils vänner", 0, 0)
        st.session_state["in_nils_familj"] = _rand_from_hist("Nils familj", 0, 0)
        st.session_state["in_bekanta"]     = _rand_from_hist("Bekanta", 0, 0)

        esk_lo, esk_hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
        if esk_hi < esk_lo: esk_hi = esk_lo
        st.session_state["in_eskilstuna"] = random.randint(esk_lo, esk_hi)

        # Bonus/Personal anger du själv
        st.session_state["in_bonus_deltagit"]    = st.session_state.get("in_bonus_deltagit", 0)
        st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)

        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_typ"]    = "Vila i hemmet"
        return

# Kör scenariofyllnad om flaggan sattes av knappen
if st.session_state.get("__DO_SCENARIO_FILL__"):
    try:
        _apply_scenario_fill_once()
    finally:
        st.session_state["__DO_SCENARIO_FILL__"] = False
        st.experimental_rerun()

# -------------------------
# Bygg basrad för beräkning (från inputs)
# -------------------------
def _build_base_row_from_inputs():
    scen, rad_datum, veckodag = st.session_state[SCENEINFO_KEY]
    avgift = float(st.session_state.get("in_avgift", CFG["avgift_usd"]))
    typ = st.session_state.get("in_typ", "Ny scen")

    base = {
        "_rad_datum": rad_datum,
        "Datum": rad_datum.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen,
        "Typ": typ,

        "Män": st.session_state.get("in_män", 0),
        "Svarta": st.session_state.get("in_svarta", 0),
        "Fitta": st.session_state.get("in_fitta", 0),
        "Rumpa": st.session_state.get("in_rumpa", 0),
        "DP": st.session_state.get("in_dp", 0),
        "DPP": st.session_state.get("in_dpp", 0),
        "DAP": st.session_state.get("in_dap", 0),
        "TAP": st.session_state.get("in_tap", 0),

        "Pappans vänner": st.session_state.get("in_pappan", 0),
        "Grannar": st.session_state.get("in_grannar", 0),
        "Nils vänner": st.session_state.get("in_nils_vanner", 0),
        "Nils familj": st.session_state.get("in_nils_familj", 0),
        "Bekanta": st.session_state.get("in_bekanta", 0),
        "Eskilstuna killar": st.session_state.get("in_eskilstuna", 0),

        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
        # “Bonus killar” kolumnen kan representera *tillgängliga* innan – används mest i statistik
        "Bonus killar": int(CFG["BONUS_AVAILABLE"]),

        "Personal deltagit": st.session_state.get("in_personal_deltagit", 0),

        "Älskar": st.session_state.get("in_alskar", 0),
        "Sover med": st.session_state.get("in_sover", 0),

        "Tid S": st.session_state.get("in_tid_s", 60),
        "Tid D": st.session_state.get("in_tid_d", 60),
        "Vila":  st.session_state.get("in_vila", 7),
        "DT tid (sek/kille)":  st.session_state.get("in_dt_tid", 60),
        "DT vila (sek/kille)": st.session_state.get("in_dt_vila", 3),

        "Nils": st.session_state.get("in_nils", 0),
        "Avgift": avgift,

        # Lönen ska alltid baseras på hela personalstyrkan
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }

    # Här sätter vi Känner = summa av fyra fälten
    base["Känner"] = (
        int(base["Pappans vänner"]) +
        int(base["Grannar"]) +
        int(base["Nils vänner"]) +
        int(base["Nils familj"])
    )
    return base

# -------------------------
# Live-förhandsberäkning (lazy-import av beräkning)
# -------------------------
def _calc_preview_row(base_row: dict) -> dict:
    try:
        from berakningar import berakna_radvarden as calc_row_values
    except Exception:
        # Om filen saknas: returnera tomt (men appen fortsätter)
        return {}

    # Anpassa namngivningen till din funktion (stöd för två varianter)
    try:
        res = calc_row_values(
            grund=base_row,
            rad_datum=base_row["_rad_datum"],
            fodelsedatum=CFG["fodelsedatum"],
            starttid=CFG["starttid"]
        )
    except TypeError:
        # Äldre signatur
        res = calc_row_values(base_row, base_row["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])
    return res or {}

# -------------------------
# Live-panel
# -------------------------
def _preview_live_panel(pre):
    if not pre:
        st.info("Ingen förhandsdata – berakningar.py saknas eller inga indata.")
        return

    # Ålder
    try:
        d = datetime.fromisoformat(pre.get("Datum", "")).date()
    except Exception:
        d = st.session_state[SCENEINFO_KEY][1]
    född = CFG["fodelsedatum"]
    ålder = _age_on(d, född)

    st.markdown(f"**Datum/Veckodag:** {pre.get('Datum','-')} / {pre.get('Veckodag','-')} • **Ålder:** {ålder} år")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", pre.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(pre.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid per kille", pre.get("Tid per kille", "-"))
        st.metric("Tid per kille (sek)", int(pre.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Klockan", pre.get("Klockan", "-"))
        st.metric("Totalt män", int(pre.get("Totalt Män", 0)))

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Hångel (m:s/kille)", pre.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(pre.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger (sek, totalt)", int(pre.get("Suger", 0)))
        st.metric("Suger per kille (sek)", int(pre.get("Suger per kille (sek)", 0)))

    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", int(pre.get("Prenumeranter", 0)))
        st.metric("Hårdhet", int(pre.get("Hårdhet", 0)))
    with e2:
        st.metric("Intäkter", f"${float(pre.get('Intäkter', 0)):,.2f}")
        st.metric("Intäkt Känner", f"${float(pre.get('Intäkt Känner', 0)):,.2f}")
    with e3:
        st.metric("Utgift män", f"${float(pre.get('Utgift män', 0)):,.2f}")
        st.metric("Lön Malin", f"${float(pre.get('Lön Malin', 0)):,.2f}")
    with e4:
        st.metric("Vinst", f"${float(pre.get('Vinst', 0)):,.2f}")
        st.metric("Älskar (sek)", int(pre.get("Tid Älskar (sek)", 0)))

# malin app – 0.9.8-stable (part 4/6)

# -------------------------
# Lokal historik (min/max) för slump
# -------------------------
HIST_KEY = "HIST_MINMAX"

def _ensure_hist():
    if HIST_KEY not in st.session_state:
        st.session_state[HIST_KEY] = {}

def _update_hist_minmax_from_row(row: dict):
    """
    Uppdatera lokala min/max för kända numeriska kolumner.
    Används efter lyckad sparning för att förbättra framtida slump.
    """
    _ensure_hist()
    num_cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
        "Bonus deltagit","Personal deltagit"
    ]
    for c in num_cols:
        try:
            v = int(row.get(c, 0) or 0)
        except Exception:
            continue
        lo, hi = st.session_state[HIST_KEY].get(c, (v, v))
        lo = min(lo, v)
        hi = max(hi, v)
        st.session_state[HIST_KEY][c] = (lo, hi)

def _append_local_row(row: dict):
    """Lägg också in raden i lokalt RAM-datalager för visning och slump-min/max."""
    st.session_state.setdefault(DATA_KEY, [])
    st.session_state[DATA_KEY].append(row)

# -------------------------
# UI: live-preview + spara
# -------------------------
st.markdown("---")
st.subheader("🔎 Live – förhandsberäkning + spar")

# 1) Bygg basrad av inputs och kör beräkning
_base_for_preview = _build_base_row_from_inputs()
_preview = _calc_preview_row(_base_for_preview)
_preview_live_panel(_preview)

# 2) Spara-knapp (enda stället som får skriva till Sheets)
def _save_current_row():
    """
    Sparar nuvarande inputs:
    - Kör beräkning igen (säkerhet)
    - Appenda till Google Sheet om 'sheet' finns, annars bara lokalt
    - Uppdatera BONUS_AVAILABLE: minus 'Bonus deltagit' du angivit
    - Uppdatera lokal historik (min/max)
    - Öka lokala scennumret
    """
    # Säkerställ sceninfo finns
    if SCENEINFO_KEY not in st.session_state:
        # Initiera sceninfo om saknas (fallback)
        scen_no = st.session_state.get(ROWCOUNT_KEY, 0) + 1
        d = CFG["startdatum"] + timedelta(days=scen_no - 1)
        veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
        st.session_state[SCENEINFO_KEY] = (scen_no, d, veckodagar[d.weekday()])

    base = _build_base_row_from_inputs()
    pre  = _calc_preview_row(base)
    if not pre:
        st.error("Beräkningen misslyckades – kontrollera berakningar.py och indata.")
        return

    # Om kolumnordningen finns (från del 1/6), använd den vid Sheets-append
    row_for_sheet = None
    if "COLUMNS" in st.session_state and isinstance(st.session_state["COLUMNS"], list):
        row_for_sheet = [pre.get(col, "") for col in st.session_state["COLUMNS"]]

    # --- Försök skriva till Sheets om 'sheet' finns och är giltig ---
    wrote_to_sheet = False
    try:
        if "sheet" in globals() and sheet is not None and callable(_retry_call) and row_for_sheet is not None:
            _retry_call(sheet.append_row, row_for_sheet)
            wrote_to_sheet = True
    except Exception as e:
        # Misslyckas Sheets → varna, men fortsätt lokalt
        st.warning(f"Kunde inte skriva till Google Sheets: {e}\nRaden sparas lokalt istället.")

    # --- Spara lokalt alltid (RAM) ---
    _append_local_row(pre)
    _update_hist_minmax_from_row(pre)

    # --- Uppdatera bonus-tillgängligt (bara minus det du angivit) ---
    try:
        used = int(base.get("Bonus deltagit", 0) or 0)
    except Exception:
        used = 0
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE", 0)) - used)

    # --- Öka lokala scennumret ---
    st.session_state[ROWCOUNT_KEY] = st.session_state.get(ROWCOUNT_KEY, 0) + 1

    # Feedback
    where = "Google Sheets + lokalt" if wrote_to_sheet else "lokalt"
    st.success(f"✅ Raden sparad ({where}). Bonus kvar: {CFG['BONUS_AVAILABLE']}.")

# Spara-knappen
save_col1, save_col2 = st.columns([1, 3])
with save_col1:
    if st.button("💾 Spara raden", use_container_width=True, key="btn_save_row"):
        _save_current_row()
        st.experimental_rerun()

# Visa lokalt sparade rader (snabb koll)
with save_col2:
    st.caption("Senaste lokalt sparade raderna (RAM):")
    if st.session_state.get(DATA_KEY):
        import pandas as pd
        df_local = pd.DataFrame(st.session_state[DATA_KEY])
        st.dataframe(df_local.tail(10), use_container_width=True, height=260)
    else:
        st.info("Inga lokalt sparade rader ännu.")

# malin app – 0.9.8-stable (part 5/6)

# -------------------------
# Säkerställ aktuell sceninfo
# -------------------------
def ensure_current_scene_info():
    """Initiera aktuell scen (nr, datum, veckodag) om saknas."""
    if SCENEINFO_KEY not in st.session_state:
        scen_no = _next_scene_number()
        d, wd = _scene_date_and_weekday(scen_no)
        st.session_state[SCENEINFO_KEY] = (scen_no, d, wd)

ensure_current_scene_info()

# -------------------------
# Hantera “Hämta/Slumpa till input”
# -------------------------
if st.session_state.get("DO_FILL_FROM_SCENARIO"):
    try:
        apply_scenario_fill()  # fyller *endast* session_state in_*-fälten
    finally:
        st.session_state.pop("DO_FILL_FROM_SCENARIO", None)
    st.rerun()

# -------------------------
# Snabb överblick av sceninfo + tillgängliga bonus
# -------------------------
scen, rad_datum, veckodag = st.session_state[SCENEINFO_KEY]
st.markdown(
    f"**Scen:** {scen}  &nbsp;•&nbsp; **Datum/Veckodag:** {rad_datum} / {veckodag} "
    f"&nbsp;•&nbsp; **Bonus kvar:** {int(CFG.get('BONUS_AVAILABLE', 0))}"
)

# -------------------------
# Statistik (lokal, RAM)
# -------------------------
st.markdown("---")
st.subheader("📊 Lokal statistik (RAM)")

def _safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

rows_local = st.session_state.get(DATA_KEY, [])
if rows_local:
    antal_rader = len(rows_local)
    tot_men_sum = sum(_safe_int(r.get("Totalt Män", 0)) for r in rows_local)
    bonus_sum   = sum(_safe_int(r.get("Bonus deltagit", 0)) for r in rows_local)
    pers_sum    = sum(_safe_int(r.get("Personal deltagit", 0)) for r in rows_local)
    pren_sum    = sum(_safe_int(r.get("Prenumeranter", 0)) for r in rows_local)
    int_sum     = sum(float(r.get("Intäkter", 0) or 0) for r in rows_local)
    vinst_sum   = sum(float(r.get("Vinst", 0) or 0) for r in rows_local)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("Rader (lokalt)", antal_rader)
    with c2: st.metric("Totalt män (sum)", int(tot_men_sum))
    with c3: st.metric("Bonus deltagit (sum)", int(bonus_sum))
    with c4: st.metric("Personal deltagit (sum)", int(pers_sum))
    with c5: st.metric("Prenumeranter (sum)", int(pren_sum))
    with c6: st.metric("Vinst (sum)", f"${vinst_sum:,.2f}")
else:
    st.info("Inga lokalt sparade rader ännu.")

# -------------------------
# Verktyg: Nollställ RAM / min–max
# -------------------------
st.markdown("---")
st.subheader("🧰 Verktyg")

tool_c1, tool_c2, tool_c3 = st.columns(3)

with tool_c1:
    if st.button("🗑️ Töm lokalt datalager (RAM)", use_container_width=True, key="btn_clear_local"):
        st.session_state[DATA_KEY] = []
        st.success("Lokalt datalager tömt.")

with tool_c2:
    if st.button("♻️ Nollställ min/max-historik", use_container_width=True, key="btn_clear_hist"):
        st.session_state[HIST_KEY] = {}
        st.success("Min/max-historiken nollställd.")

with tool_c3:
    if st.button("🔄 Återinitiera sceninfo", use_container_width=True, key="btn_reseed_scene"):
        # Sätt ROWCOUNT till längden på lokalt datalager (så nästa scen blir konsekvent)
        st.session_state[ROWCOUNT_KEY] = len(st.session_state.get(DATA_KEY, []))
        ensure_current_scene_info()
        st.success("Sceninfo återinitierad från lokalt antal rader.")
        st.rerun()

# Visa senaste 20 raderna lokalt (om du vill ha en snabb tabell här också)
with st.expander("Visa senaste 20 lokala rader"):
    if rows_local:
        import pandas as pd
        df_prev = pd.DataFrame(rows_local)
        st.dataframe(df_prev.tail(20), use_container_width=True, height=360)
    else:
        st.caption("— tomt —")

# malin app – 0.9.8-stable (part 6/6)

# -------------------------
# Etiketter (lokala overrides i sidopanel)
# -------------------------
with st.sidebar.expander("📝 Etiketter (valfritt)", expanded=False):
    CFG.setdefault("LABELS", {})
    L = CFG["LABELS"]

    def _lbl(key, default):
        L[key] = st.text_input(f"Etikett för “{default}”", value=L.get(key, default))

    # Du kan välja att ändra visningsnamn (lagras endast i RAM)
    _lbl("Män", "Män")
    _lbl("Svarta", "Svarta")
    _lbl("Fitta", "Fitta")
    _lbl("Rumpa", "Rumpa")
    _lbl("DP", "DP")
    _lbl("DPP", "DPP")
    _lbl("DAP", "DAP")
    _lbl("TAP", "TAP")
    _lbl("Pappans vänner", "Pappans vänner")
    _lbl("Grannar", "Grannar")
    _lbl("Nils vänner", "Nils vänner")
    _lbl("Nils familj", "Nils familj")
    _lbl("Bekanta", "Bekanta")
    _lbl("Eskilstuna killar", "Eskilstuna killar")
    _lbl("Bonus deltagit", "Bonus deltagit")
    _lbl("Personal deltagit", "Personal deltagit")
    _lbl("Älskar", "Älskar")
    _lbl("Sover med", "Sover med")
    _lbl("Tid S", "Tid S (sek)")
    _lbl("Tid D", "Tid D (sek)")
    _lbl("Vila", "Vila (sek)")
    _lbl("DT tid (sek/kille)", "DT tid (sek/kille)")
    _lbl("DT vila (sek/kille)", "DT vila (sek/kille)")

def _L(name: str) -> str:
    return CFG.get("LABELS", {}).get(name, name)


# -------------------------
# Inputformulär (EXAKT ordning)
# -------------------------
st.markdown("---")
st.subheader("🧾 Inmatning (enbart RAM, sparas först när du trycker “Spara raden i RAM”)")

# Visa “tillgängligt” intill bonus & personal
bonus_tillg = int(CFG.get("BONUS_AVAILABLE", 0))
personal_tot = int(CFG.get("PROD_STAFF", 0))

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.number_input(_L("Män"), min_value=0, step=1, key="in_man")
    st.number_input(_L("Svarta"), min_value=0, step=1, key="in_svarta")
    st.number_input(_L("Fitta"), min_value=0, step=1, key="in_fitta")
    st.number_input(_L("Rumpa"), min_value=0, step=1, key="in_rumpa")
    st.number_input(_L("DP"), min_value=0, step=1, key="in_dp")
    st.number_input(_L("DPP"), min_value=0, step=1, key="in_dpp")

with c2:
    st.number_input(_L("DAP"), min_value=0, step=1, key="in_dap")
    st.number_input(_L("TAP"), min_value=0, step=1, key="in_tap")
    st.number_input(_L("Pappans vänner"), min_value=0, step=1, key="in_pappan")
    st.number_input(_L("Grannar"), min_value=0, step=1, key="in_grannar")
    st.number_input(_L("Nils vänner"), min_value=0, step=1, key="in_nils_vanner")
    st.number_input(_L("Nils familj"), min_value=0, step=1, key="in_nils_familj")

with c3:
    st.number_input(_L("Bekanta"), min_value=0, step=1, key="in_bekanta")
    st.number_input(_L("Eskilstuna killar"), min_value=0, step=1, key="in_eskilstuna")
    st.number_input(f"{_L('Bonus deltagit')} (tillgängligt: {bonus_tillg})", min_value=0, step=1, key="in_bonus_deltagit")
    st.number_input(f"{_L('Personal deltagit')} (totalt: {personal_tot})", min_value=0, step=1, key="in_personal_deltagit")
    st.number_input(_L("Älskar"), min_value=0, step=1, key="in_alskar")
    st.number_input(_L("Sover med"), min_value=0, max_value=1, step=1, key="in_sover")

with c4:
    st.number_input(_L("Tid S"), min_value=0, step=1, key="in_tid_s")
    st.number_input(_L("Tid D"), min_value=0, step=1, key="in_tid_d")
    st.number_input(_L("Vila"), min_value=0, step=1, key="in_vila")
    st.number_input(_L("DT tid (sek/kille)"), min_value=0, step=1, key="in_dt_tid")
    st.number_input(_L("DT vila (sek/kille)"), min_value=0, step=1, key="in_dt_vila")

st.caption("Obs: Inga Google Sheets-anrop sker här. Allt ligger i RAM tills du explicit sparar till databasen (om/när du vill aktivera det senare).")


# -------------------------
# Live-förhandsvisning från nuvarande inputs
# -------------------------
st.markdown("### 🔎 Live-förhandsvisning")
base_row_for_preview = _build_base_row_from_inputs()            # definierad i del 3
preview_values = _calc_preview_row(base_row_for_preview)        # definierad i del 3
_preview_live_panel(preview_values)                              # definierad i del 3


# -------------------------
# Spara i RAM (enda permanens just nu)
# -------------------------
st.markdown("---")
if st.button("💾 Spara raden i RAM (lokalt)", use_container_width=True, key="btn_save_ram"):
    # 1) bygg & beräkna
    base = _build_base_row_from_inputs()
    prev = _calc_preview_row(base)
    if not prev:
        st.error("Beräkningen misslyckades – kunde inte spara i RAM.")
    else:
        # 2) lägg till i lokalt datalager (RAM)
        rows = st.session_state.get(DATA_KEY, [])
        rows.append(prev)
        st.session_state[DATA_KEY] = rows

        # 3) öka scennummer och initiera ny sceninfo
        st.session_state[ROWCOUNT_KEY] = st.session_state.get(ROWCOUNT_KEY, 0) + 1
        scen_no = _next_scene_number()
        d_new, wd_new = _scene_date_and_weekday(scen_no)
        st.session_state[SCENEINFO_KEY] = (scen_no, d_new, wd_new)

        # 4) uppdatera historik (min/max) för slump
        st.session_state.setdefault(HIST_KEY, {})
        H = st.session_state[HIST_KEY]
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]:
            try:
                v = int(prev.get(col, 0) or 0)
            except Exception:
                v = 0
            lo, hi = H.get(col, (v, v))
            H[col] = (min(lo, v), max(hi, v))

        # 5) uppdatera bonus-lager: dra bort det som deltog denna rad, lägg till ev. nya.
        #    (Här antar vi att “nya bonus” inte genereras automatiskt – du skriver dem i nästa scen.)
        used = int(base.get("Bonus deltagit", 0) or 0)
        CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE", 0)) - used)

        st.success("✅ Raden sparad i RAM. (Ingen extern skrivning.)")
        st.rerun()


# -------------------------
# Visa RAM-tabell
# -------------------------
st.markdown("### 📄 Rader i RAM (senaste 100)")
ram_rows = st.session_state.get(DATA_KEY, [])
if ram_rows:
    import pandas as pd
    st.dataframe(pd.DataFrame(ram_rows).tail(100), use_container_width=True, height=420)
else:
    st.info("Inga rader sparade i RAM ännu.")
