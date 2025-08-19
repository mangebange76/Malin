import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
import random

# =====================================================
# Grundinställningar & app-konfiguration
# =====================================================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")

# Endast import – alla beräkningar bor i berakningar.py (inte i app.py)
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

# =====================================================
# Konstanter & session-nycklar
# =====================================================
CFG_KEY          = "CFG"                  # Inställningar i minnet
ROWS_KEY         = "LOCAL_ROWS"           # Lokalt sparade rader (lista av dict)
ROWCOUNT_KEY     = "ROWCOUNT_LOCAL"       # Räknare för scennummer (lokalt)
SCEN_INFO_KEY    = "CURRENT_SCENE_INFO"   # (scen_no, datum, veckodag)
HIST_MINMAX_KEY  = "HIST_MINMAX"          # Historik min/max för slump
HOME_OFFSET_KEY  = "home_day_offset"      # 0..6 => dag 1..7
HOME_NILS_MASK   = "HOME_NILS_MASK"       # set({0..4}) vilka dagar får NILS=1
SCENARIO_KEY     = "SCENARIO"             # valt scenario i rullistan

# Ordning: exakt som du specificerat
# Män, Svarta, Fitta, Rumpa, DP, DPP, DAP, TAP,
# Pappans vänner, Grannar, Nils vänner, Nils familj,
# Bekanta, Eskilstuna killar, Bonus deltagit, Personal deltagit,
# Älskar, Sover med, Tid S, Tid D, Vila, DT tid, DT vila
INPUT_ORDER = [
    ("in_män", "Män"),
    ("in_svarta", "Svarta"),
    ("in_fitta", "Fitta"),
    ("in_rumpa", "Rumpa"),
    ("in_dp", "DP"),
    ("in_dpp", "DPP"),
    ("in_dap", "DAP"),
    ("in_tap", "TAP"),
    ("in_pappan", "Pappans vänner"),
    ("in_grannar", "Grannar"),
    ("in_nils_vanner", "Nils vänner"),
    ("in_nils_familj", "Nils familj"),
    ("in_bekanta", "Bekanta"),
    ("in_eskilstuna", "Eskilstuna killar"),
    ("in_bonus_deltagit", "Bonus deltagit"),
    ("in_personal_deltagit", "Personal deltagit"),
    ("in_alskar", "Älskar"),
    ("in_sover", "Sover med"),
    ("in_tid_s", "Tid S (sek)"),
    ("in_tid_d", "Tid D (sek)"),
    ("in_vila", "Vila (sek)"),
    ("in_dt_tid", "DT tid (sek/kille)"),
    ("in_dt_vila", "DT vila (sek/kille)"),
]

# =====================================================
# Initiera session state (ingen Sheets-läsning)
# =====================================================
def _init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7, 0),
            "fodelsedatum": date(1995, 1, 1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,        # hela personalen för lön
            "BONUS_AVAILABLE": 500,   # tillgängliga bonuskillar (räknas ned först vid spara)
            "ESK_MIN": 20,
            "ESK_MAX": 40,
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []  # lokala rader
    if ROWCOUNT_KEY not in st.session_state:
        st.session_state[ROWCOUNT_KEY] = 0
    if HIST_MINMAX_KEY not in st.session_state:
        st.session_state[HIST_MINMAX_KEY] = {}
    if HOME_OFFSET_KEY not in st.session_state:
        st.session_state[HOME_OFFSET_KEY] = 0
    if HOME_NILS_MASK not in st.session_state:
        # 50% -> 0 ettor, 45% -> 1 etta, 5% -> 2 ettor (dag 1–5)
        r = random.random()
        if r < 0.50:
            ones = 0
        elif r < 0.95:
            ones = 1
        else:
            ones = 2
        st.session_state[HOME_NILS_MASK] = set(random.sample(range(5), ones)) if ones > 0 else set()
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if SCEN_INFO_KEY not in st.session_state:
        st.session_state[SCEN_INFO_KEY] = _current_scene_info()

    # se till att alla in_*-fält finns (0 default) + några extra
    for k, _label in INPUT_ORDER:
        st.session_state.setdefault(k, 0)
    st.session_state.setdefault("in_nils", 0)
    st.session_state.setdefault("in_avgift", float(st.session_state[CFG_KEY]["avgift_usd"]))
    st.session_state.setdefault("in_typ", "Ny scen")

def _current_scene_info():
    # Scen = lokal räknare + 1
    scen_no = st.session_state.get(ROWCOUNT_KEY, 0) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=scen_no - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (scen_no, d, veckodagar[d.weekday()])

_init_state()
CFG = st.session_state[CFG_KEY]

# =====================================================
# Hjälpfunktioner
# =====================================================
def _age_on(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

def _update_hist_minmax_with_row(row: dict):
    """Uppdaterar HIST_MINMAX när vi sparar en rad."""
    mm = st.session_state[HIST_MINMAX_KEY]
    for key in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta",
                "Eskilstuna killar"]:
        try:
            v = int(row.get(key, 0) or 0)
        except Exception:
            continue
        lo, hi = mm.get(key, (v, v))
        lo = min(lo, v)
        hi = max(hi, v)
        mm[key] = (lo, hi)
    st.session_state[HIST_MINMAX_KEY] = mm

def _hist_rand(col, default_lo=0, default_hi=0):
    lo, hi = st.session_state.get(HIST_MINMAX_KEY, {}).get(col, (default_lo, default_hi))
    if hi < lo: hi = lo
    return int(random.randint(lo, hi)) if hi > lo else int(lo)

def _esk_rand():
    esk_lo = int(CFG.get("ESK_MIN", 20))
    esk_hi = int(CFG.get("ESK_MAX", 40))
    if esk_hi < esk_lo: esk_hi = esk_lo
    return random.randint(esk_lo, esk_hi)

# =====================================================
# Sidopanel – Inställningar & scenarioval
# =====================================================
with st.sidebar:
    st.header("Inställningar")
    CFG["startdatum"]   = st.date_input("Startdatum (för scen-datum)", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift (USD per prenumerant)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (för lön)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (slump)")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1, key="esk_min")
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1, key="esk_max")

    st.markdown("---")
    st.subheader("Bonus")
    st.write(f"Bonus killar tillgängliga: **{int(CFG['BONUS_AVAILABLE'])}**")

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet (dag 1–7)"],
        index=["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )

# =====================================================
# Vilovecka: dagbläddrare (dag 1–7)
# =====================================================
st.markdown("#### Vilovecka hemma – dagbläddrare")
c_prev, c_label, c_next, c_reset = st.columns([1, 2, 1, 2])

with c_prev:
    if st.button("⬅️ Föregående dag", key="home_prev"):
        st.session_state[HOME_OFFSET_KEY] = max(0, st.session_state[HOME_OFFSET_KEY] - 1)
        st.rerun()

with c_label:
    dag = st.session_state[HOME_OFFSET_KEY] + 1
    st.markdown(f"<div style='text-align:center;font-weight:600'>Dag {dag} av 7</div>", unsafe_allow_html=True)

with c_next:
    if st.button("Nästa dag ➡️", key="home_next"):
        st.session_state[HOME_OFFSET_KEY] = min(6, st.session_state[HOME_OFFSET_KEY] + 1)
        st.rerun()

with c_reset:
    if st.button("🎲 Slumpa om Nils-dagar (1–5)", key="home_reset_mask"):
        r = random.random()
        if r < 0.50:
            ones = 0
        elif r < 0.95:
            ones = 1
        else:
            ones = 2
        st.session_state[HOME_NILS_MASK] = set(random.sample(range(5), ones)) if ones > 0 else set()
        st.session_state[HOME_OFFSET_KEY] = 0
        st.rerun()

# =====================================================
# Scenario -> fyll endast inputfälten (ingen sparning)
# =====================================================
def apply_scenario_to_inputs():
    scen_no, scen_date, veckodag = st.session_state[SCEN_INFO_KEY]
    scenario = st.session_state[SCENARIO_KEY]

    # Nollbas
    def zero_all():
        for k, _lbl in INPUT_ORDER:
            st.session_state[k] = 0
        st.session_state["in_nils"] = 0

    if scenario == "Ny scen":
        zero_all()
        st.session_state["in_typ"] = "Ny scen"

    elif scenario == "Slumpa scen vit":
        zero_all()
        # slumpa allt utom "Svarta" (som alltid ska bli 0)
        st.session_state["in_män"]    = _hist_rand("Män")
        st.session_state["in_fitta"]  = _hist_rand("Fitta")
        st.session_state["in_rumpa"]  = _hist_rand("Rumpa")
        st.session_state["in_dp"]     = _hist_rand("DP")
        st.session_state["in_dpp"]    = _hist_rand("DPP")
        st.session_state["in_dap"]    = _hist_rand("DAP")
        st.session_state["in_tap"]    = _hist_rand("TAP")
        st.session_state["in_pappan"]      = _hist_rand("Pappans vänner")
        st.session_state["in_grannar"]     = _hist_rand("Grannar")
        st.session_state["in_nils_vanner"] = _hist_rand("Nils vänner")
        st.session_state["in_nils_familj"] = _hist_rand("Nils familj")
        st.session_state["in_bekanta"]     = _hist_rand("Bekanta")
        st.session_state["in_eskilstuna"]  = _esk_rand()
        st.session_state["in_svarta"] = 0  # viktigt
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Ny scen"

    elif scenario == "Slumpa scen svart":
        zero_all()
        st.session_state["in_fitta"]  = _hist_rand("Fitta")
        st.session_state["in_rumpa"]  = _hist_rand("Rumpa")
        st.session_state["in_dp"]     = _hist_rand("DP")
        st.session_state["in_dpp"]    = _hist_rand("DPP")
        st.session_state["in_dap"]    = _hist_rand("DAP")
        st.session_state["in_tap"]    = _hist_rand("TAP")
        st.session_state["in_svarta"] = _hist_rand("Svarta")
        # källor 0, personal 0 – bonus/personaldeltagit anger du manuellt
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Ny scen (svart)"

    elif scenario == "Vila på jobbet":
        zero_all()
        # slumpa ALLA listade fälten: sexfält + källor + Eskilstuna
        st.session_state["in_fitta"]  = _hist_rand("Fitta")
        st.session_state["in_rumpa"]  = _hist_rand("Rumpa")
        st.session_state["in_dp"]     = _hist_rand("DP")
        st.session_state["in_dpp"]    = _hist_rand("DPP")
        st.session_state["in_dap"]    = _hist_rand("DAP")
        st.session_state["in_tap"]    = _hist_rand("TAP")
        st.session_state["in_pappan"]      = _hist_rand("Pappans vänner")
        st.session_state["in_grannar"]     = _hist_rand("Grannar")
        st.session_state["in_nils_vanner"] = _hist_rand("Nils vänner")
        st.session_state["in_nils_familj"] = _hist_rand("Nils familj")
        st.session_state["in_bekanta"]     = _hist_rand("Bekanta")
        st.session_state["in_eskilstuna"]  = _esk_rand()
        # bonus/personaldeltagit anges av dig i input
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        st.session_state["in_typ"] = "Vila på jobbet"

    elif scenario == "Vila i hemmet (dag 1–7)":
        zero_all()
        offset = st.session_state[HOME_OFFSET_KEY]  # 0..6
        nils_mask = st.session_state[HOME_NILS_MASK]

        if offset <= 4:  # dag 1–5
            # slumpa sex-fälten + källor + Eskilstuna (bonus/personaldeltagit = manuellt)
            st.session_state["in_fitta"]  = _hist_rand("Fitta")
            st.session_state["in_rumpa"]  = _hist_rand("Rumpa")
            st.session_state["in_dp"]     = _hist_rand("DP")
            st.session_state["in_dpp"]    = _hist_rand("DPP")
            st.session_state["in_dap"]    = _hist_rand("DAP")
            st.session_state["in_tap"]    = _hist_rand("TAP")
            st.session_state["in_pappan"]      = _hist_rand("Pappans vänner")
            st.session_state["in_grannar"]     = _hist_rand("Grannar")
            st.session_state["in_nils_vanner"] = _hist_rand("Nils vänner")
            st.session_state["in_nils_familj"] = _hist_rand("Nils familj")
            st.session_state["in_bekanta"]     = _hist_rand("Bekanta")
            st.session_state["in_eskilstuna"]  = _esk_rand()
            st.session_state["in_män"]    = 0
            st.session_state["in_svarta"] = 0
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 0
            st.session_state["in_nils"]   = 1 if offset in nils_mask else 0
            st.session_state["in_typ"]    = f"Vila i hemmet (dag {offset+1})"
        else:            # dag 6–7
            # allt 0 utom älskar=6
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 0
            st.session_state["in_typ"]    = f"Vila i hemmet (dag {offset+1})"

# Hämta/Slumpa-knapp (fyller bara inputs)
if st.button("📥 Hämta/Slumpa till input", use_container_width=True, key="btn_fetch_fill"):
    # uppdatera aktuell sceninfo före fyllning
    st.session_state[SCEN_INFO_KEY] = _current_scene_info()
    apply_scenario_to_inputs()
    st.rerun()

# =====================================================
# Inmatning – exakt ordning
# =====================================================
st.markdown("### Inmatning")

# Input visas i kolumner men ordningen (uppifrån-ner, vänster->höger) följer listan
cols = st.columns(4)
for i, (key, label) in enumerate(INPUT_ORDER):
    c = cols[i % 4]
    with c:
        default_val = int(st.session_state.get(key, 0))
        st.session_state[key] = st.number_input(label, min_value=0, step=1, value=default_val, key=key)

# Extra fält (inte i ordningslistan men behövs)
cA, cB, cC = st.columns(3)
with cA:
    st.session_state["in_nils"] = st.number_input("Nils", min_value=0, step=1, value=int(st.session_state.get("in_nils", 0)), key="in_nils")
with cB:
    st.session_state["in_avgift"] = st.number_input("Avgift (USD, rad)", min_value=0.0, step=1.0, value=float(st.session_state.get("in_avgift", CFG["avgift_usd"])), key="in_avgift")
with cC:
    scen_no, scen_date, veckodag = st.session_state[SCEN_INFO_KEY]
    ålder = _age_on(scen_date, CFG["fodelsedatum"])
    st.markdown(f"**Datum/Veckodag:** {scen_date} / {veckodag} • **Ålder:** {ålder} år")

# =====================================================
# Bygg basrad från inputs och kör beräkning
# =====================================================
def _build_base_row():
    scen_no, scen_date, veckodag = st.session_state[SCEN_INFO_KEY]
    avgift = float(st.session_state.get("in_avgift", CFG["avgift_usd"]))

    base = {
        # metadata
        "_rad_datum": scen_date,
        "Datum": scen_date.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen_no,
        "Typ": st.session_state.get("in_typ", "Ny scen"),

        # indata (alla)
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

        "Bonus killar": int(CFG["BONUS_AVAILABLE"]),     # visning – tillgängliga nu
        "Bonus deltagit": st.session_state.get("in_bonus_deltagit", 0),
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

        # Tvinga full personal i lönebas
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }
    # Känner = sum av fyra fält
    base["Känner"] = (
        int(base["Pappans vänner"]) +
        int(base["Grannar"]) +
        int(base["Nils vänner"]) +
        int(base["Nils familj"])
    )
    return base

def _calc_preview(base_row: dict) -> dict:
    if not callable(calc_row_values):
        return {}
    try:
        return calc_row_values(
            grund=base_row,
            rad_datum=base_row["_rad_datum"],
            fodelsedatum=CFG["fodelsedatum"],
            starttid=CFG["starttid"]
        ) or {}
    except TypeError:
        # fallback om din lokala modul har äldre signatur
        return calc_row_values(base_row, base_row["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"]) or {}

base_row = _build_base_row()
preview = _calc_preview(base_row)

# =====================================================
# Live-panel
# =====================================================
def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "-"

st.markdown("### Live – förhandsberäkning")
if not preview:
    st.info("Ingen förhandsdata – kontrollera att berakningar.py finns och att fälten är ifyllda.")
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", preview.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid/kille", preview.get("Tid per kille", "-"))
        st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Klockan", preview.get("Klockan", "-"))
        st.metric("Totalt män", int(preview.get("Totalt Män", 0)))

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger (totalt sek)", int(preview.get("Suger", 0)))
        st.metric("Suger per kille (sek)", int(preview.get("Suger per kille (sek)", 0)))

    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", int(preview.get("Prenumeranter", 0)))
        st.metric("Hårdhet", int(preview.get("Hårdhet", 0)))
    with e2:
        st.metric("Intäkter", _usd(preview.get("Intäkter", 0)))
        st.metric("Intäkt Känner", _usd(preview.get("Intäkt Känner", 0)))
    with e3:
        st.metric("Utgift män", _usd(preview.get("Utgift män", 0)))
        st.metric("Lön Malin", _usd(preview.get("Lön Malin", 0)))
    with e4:
        st.metric("Vinst", _usd(preview.get("Vinst", 0)))
        st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))
    st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men läggs på klockan.")

# =====================================================
# Spara (lokalt; inga Sheets)
# =====================================================
st.markdown("---")
if st.button("💾 Spara rad", use_container_width=True):
    if not preview:
        st.error("Beräkning saknas – kan inte spara.")
    else:
        # 1) Lägg till i lokala rader
        st.session_state[ROWS_KEY].append(preview)

        # 2) Uppdatera historik för slump
        _update_hist_minmax_with_row(preview)

        # 3) Räkna ner bonus-tillgängliga (endast det du angav i input)
        used_bonus = int(base_row.get("Bonus deltagit", 0) or 0)
        CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - used_bonus)

        # 4) Öka scenräknare & sceninfo framåt
        st.session_state[ROWCOUNT_KEY] = int(st.session_state[ROWCOUNT_KEY]) + 1
        st.session_state[SCEN_INFO_KEY] = _current_scene_info()

        st.success("✅ Raden sparad lokalt.")
        st.rerun()

# =====================================================
# Visa lokala rader (”databas” tills Sheets kopplas på)
# =====================================================
st.markdown("### Sparade rader (lokalt)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True)
else:
    st.caption("Inga lokala rader sparade ännu.")

# (Valfritt: knapp för att nollställa lokalt – ingen Sheetspåverkan)
with st.expander("Nollställ (lokalt)"):
    if st.button("🧹 Töm alla lokala rader & historik"):
        st.session_state[ROWS_KEY] = []
        st.session_state[HIST_MINMAX_KEY] = {}
        st.session_state[ROWCOUNT_KEY] = 0
        st.session_state[SCEN_INFO_KEY] = _current_scene_info()
        st.success("Nollställt lokalt.")
        st.rerun()
