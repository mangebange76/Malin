import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
import random

# --------------------------------------------------
# App-inställningar
# --------------------------------------------------
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp")

# --------------------------------------------------
# Session keys
# --------------------------------------------------
CFG_KEY         = "CFG"                  # inställningar i minnet (ingen Sheets-läsning live)
DATA_KEY        = "LOCAL_ROWS"           # lokalt sparade rader (fallback om Sheets saknas)
ROWCOUNT_KEY    = "ROWCOUNT_LOCAL"       # räknare för scennummer
SCENARIO_KEY    = "SCENARIO"             # valt scenario i rullistan
FORM_READY_KEY  = "FORM_READY"           # när vi fyllt formuläret från scenario (Hämta värden)
MULTI_PREVIEW   = "MULTI_PREVIEW"        # för ’Vila i hemmet’ (7 rader buffert)
MULTI_INDEX_KEY = "MULTI_INDEX"          # vilken av 7 som visas

# Alla formfält (ordning exakt enligt din lista)
FORM_FIELDS = [
    "in_man", "in_svarta",
    "in_fitta", "in_rumpa", "in_dp", "in_dpp", "in_dap", "in_tap",
    "in_pappan", "in_grannar", "in_nils_vanner", "in_nils_familj",
    "in_bekanta", "in_eskilstuna",
    "in_bonus_deltagit", "in_personal_deltagit",
    "in_alskar", "in_sover",
    "in_tid_s", "in_tid_d", "in_vila",
    "in_dt_tid", "in_dt_vila"
]

# --------------------------------------------------
# Initiera state
# --------------------------------------------------
def _init_defaults():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7, 0),
            "fodelsedatum": date(1995, 1, 1),
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,              # total personal (för lön)
            "BONUS_AVAILABLE": 500,         # tillgängliga bonuskillar att använda
            "ESK_MIN": 20,                  # Eskilstuna slumpinterval
            "ESK_MAX": 40,
        }
    if DATA_KEY not in st.session_state:
        st.session_state[DATA_KEY] = []    # lista av sparade rader (om Sheets ej används)
    if ROWCOUNT_KEY not in st.session_state:
        st.session_state[ROWCOUNT_KEY] = 0
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if FORM_READY_KEY not in st.session_state:
        st.session_state[FORM_READY_KEY] = False
    if MULTI_PREVIEW not in st.session_state:
        st.session_state[MULTI_PREVIEW] = []   # 7 raderna för ’Vila i hemmet’
    if MULTI_INDEX_KEY not in st.session_state:
        st.session_state[MULTI_INDEX_KEY] = 0

    # se till att alla formfält finns i state (och sätt 0 som default)
    for k in FORM_FIELDS:
        st.session_state.setdefault(k, 0)

_init_defaults()
CFG = st.session_state[CFG_KEY]

# --------------------------------------------------
# Hjälpfunktioner (utan Sheets)
# --------------------------------------------------
def _age_on(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

def _next_scene_number() -> int:
    # Helt lokal räknare (ingen sheets-läsning!)
    return st.session_state[ROWCOUNT_KEY] + 1

def _scene_date_and_weekday(scene_no: int):
    d = CFG["startdatum"] + timedelta(days=scene_no - 1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return d, veckodagar[d.weekday()]

def ensure_default(key: str, value):
    """Sätt default i session state endast om det saknas (för att undvika Streamlit-nyckelkrockar)."""
    if key not in st.session_state:
        st.session_state[key] = value

def fill_form_from_dict(d: dict):
    """Fyll samtliga in_*-fält från en dict med samma nycklar; nudda inte övrigt state."""
    for k in FORM_FIELDS:
        if k in d:
            st.session_state[k] = d[k]
    st.session_state[FORM_READY_KEY] = True

# --------------------------------------------------
# Sidopanel – Inställningar + scenario/knappar
# --------------------------------------------------
with st.sidebar:
    st.header("Inställningar (lokalt)")
    CFG["startdatum"] = st.date_input("Startdatum (för scen-datum)", value=CFG["startdatum"])
    CFG["starttid"]   = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"] = st.number_input("Avgift (USD per prenumerant)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"] = st.number_input("Totalt antal personal (för lön)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    # Bonus-tillgängliga visas och uppdateras enbart vid spar
    st.write(f"Bonus killar tillgängliga: **{CFG['BONUS_AVAILABLE']}**")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (slump)")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1)

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        ["Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet"].index(st.session_state[SCENARIO_KEY])
    )

    # “Hämta värden” fyller endast formuläret – ingen sparning, inga Sheets-anrop.
    if st.button("⬇️ Hämta värden till formuläret"):
        # Hanteras i huvudflödet längre ner (vi triggar bara rerun-friendly flagga)
        st.session_state["DO_FILL_FROM_SCENARIO"] = True
        st.rerun()

# --------------------------------------------------
# Scenario-logik (fyller bara formuläret)
# --------------------------------------------------
def _min_max_from_local(colname: str):
    """Returnerar (min, max) utifrån lokalt sparade rader. Finns inget → (0,0)."""
    rows = st.session_state[DATA_KEY]
    if not rows:
        return (0, 0)
    vals = []
    for r in rows:
        try:
            vals.append(int(r.get(colname, 0) or 0))
        except Exception:
            pass
    if not vals:
        return (0, 0)
    return (min(vals), max(vals))

def apply_scenario_fill():
    scen_no = _next_scene_number()
    d, _ = _scene_date_and_weekday(scen_no)

    scenario = st.session_state[SCENARIO_KEY]
    base = {k: 0 for k in FORM_FIELDS}

    if scenario == "Ny scen":
        # lämna nollor, men förifyll personal till 0 (du anger själv varje rad)
        base["in_personal_deltagit"] = 0

    elif scenario == "Slumpa scen vit":
        # slumpa kring min/max från lokala data; om 0..0 blir det 0
        for f in ["Män","Fitta","Rumpa","DP","DPP","DAP","TAP","Svarta"]:
            mn, mx = _min_max_from_local(f)
            val = random.randint(mn, mx) if mx >= mn else 0
            key = {
                "Män":"in_man","Fitta":"in_fitta","Rumpa":"in_rumpa","DP":"in_dp",
                "DPP":"in_dpp","DAP":"in_dap","TAP":"in_tap","Svarta":"in_svarta"
            }[f]
            base[key] = val
        # Källor
        for f,name in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                       ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                       ("Bekanta","in_bekanta")]:
            mn, mx = _min_max_from_local(f)
            base[name] = random.randint(mn, mx) if mx >= mn else 0
        # Eskilstuna enligt intervall i sidopanel
        base["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        # default
        base["in_alskar"] = 8
        base["in_sover"] = 1
        base["in_personal_deltagit"] = 0  # du anger själv; tidigare var 80, men nu manual
        # bonus-deltagit sätter du själv; visa tillgängligt i labeln

    elif scenario == "Slumpa scen svart":
        # endast svarta + övriga aktions-fält; källor 0, personal 0
        for f in ["Fitta","Rumpa","DP","DPP","DAP","TAP","Svarta"]:
            mn, mx = _min_max_from_local(f)
            key = {"Fitta":"in_fitta","Rumpa":"in_rumpa","DP":"in_dp","DPP":"in_dpp","DAP":"in_dap","TAP":"in_tap","Svarta":"in_svarta"}[f]
            base[key] = random.randint(mn, mx) if mx >= mn else 0
        base["in_man"] = 0
        base["in_pappan"] = base["in_grannar"] = base["in_nils_vanner"] = base["in_nils_familj"] = base["in_bekanta"] = 0
        base["in_eskilstuna"] = 0
        base["in_personal_deltagit"] = 0
        base["in_alskar"] = 8
        base["in_sover"] = 1

    elif scenario == "Vila på jobbet":
        # slumpa fitta, rumpa, DP, DPP, DAP, TAP från lokala min/max; övrigt 0
        for f in ["Fitta","Rumpa","DP","DPP","DAP","TAP"]:
            mn, mx = _min_max_from_local(f)
            key = {"Fitta":"in_fitta","Rumpa":"in_rumpa","DP":"in_dp","DPP":"in_dpp","DAP":"in_dap","TAP":"in_tap"}[f]
            base[key] = random.randint(mn, mx) if mx >= mn else 0
        base["in_personal_deltagit"] = 0  # du anger själv
        base["in_alskar"]

# ======== Del 3/4 – Live-förhandsvisning, scenfyllnad & spar ========

def _calc_preview_row(base_row: dict):
    """
    Anropar beräkningarna (berakningar.py) helt utan några sheets-anrop.
    Returnerar en dict med ALLA beräknade fält för liven + det som sparas.
    """
    if not callable(calc_row_values):
        return {}

    # Dessa tre skickas alltid in (krävs av beräkningarna)
    rad_datum = base_row.get("_rad_datum")  # sätts i del 2/4 när scenen bestäms
    fodelsedatum = st.session_state["CFG"]["födelsedatum"]
    starttid = st.session_state["CFG"]["starttid"]

    # Se till att PROD_STAFF finns så löner alltid tar hela personalstyrkan, inte "deltagit"
    base_row.setdefault("PROD_STAFF", int(st.session_state["CFG"]["PROD_STAFF"]))

    try:
        res = calc_row_values(
            grund=base_row,
            rad_datum=rad_datum,
            fodelsedatum=fodelsedatum,
            starttid=starttid
        )
    except TypeError:
        # Fallback om ditt lokala beräkningsscript har äldre signatur
        res = calc_row_values(base_row, rad_datum, fodelsedatum, starttid)
    return res or {}


def _build_base_row_from_inputs():
    """
    Hämtar *ENBART* värden från input-fälten i minnet (session_state),
    samt injicerar metadata (datum/veckodag/avgift/typ etc).
    Inga sheets-anrop här.
    """
    scen, rad_datum, veckodag = st.session_state["CURRENT_SCENE_INFO"]
    avgift = float(st.session_state.get("in_avgift", st.session_state["CFG"]["avgift_usd"]))
    typ = st.session_state.get("in_typ", "Ny scen")

    base = {
        "_rad_datum": rad_datum,     # intern nyckel för beräkning
        "Datum": rad_datum.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen,
        "Typ": typ,

        # Inmatning (exakt ordning du önskat)
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

        "Bonus killar": st.session_state.get("bonus_total", 0),     # total tillgängliga (visning)
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

        # Tvinga igenom full personal i lönebas
        "PROD_STAFF": int(st.session_state["CFG"]["PROD_STAFF"]),
    }

    # Här beräknar vi "Känner" on-the-fly av fyra källor (sparas/visas också)
    base["Känner"] = (
        int(base["Pappans vänner"]) +
        int(base["Grannar"]) +
        int(base["Nils vänner"]) +
        int(base["Nils familj"])
    )
    return base


def _preview_live_panel(preview_dict: dict):
    """Visar komprimerad live-panel med nyckeltal + ålder."""
    if not preview_dict:
        st.info("Ingen förhandsdata – fyll i fält eller hämta scenvärden.")
        return

    # Överkant: datum/veckodag + ålder
    rad_datum = preview_dict.get("Datum")
    veckodag = preview_dict.get("Veckodag", "-")
    if isinstance(rad_datum, str):
        try:
            _d = datetime.fromisoformat(rad_datum).date()
        except Exception:
            _d = datetime.today().date()
    else:
        _d = datetime.today().date()

    fd = st.session_state["CFG"]["födelsedatum"]
    alder = _d.year - fd.year - (( _d.month, _d.day) < (fd.month, fd.day))

    st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

    # Tid / klocka
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", preview_dict.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(preview_dict.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid/kille", preview_dict.get("Tid per kille", "-"))
        st.metric("Tid/kille (sek)", int(preview_dict.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Klockan", preview_dict.get("Klockan", "-"))
        st.metric("Totalt män", int(preview_dict.get("Totalt Män", 0)))

    # Hångel/Sug
    c4, c5 = st.columns(2)
    with c4:
        st.metric("Hångel (m:s/kille)", preview_dict.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(preview_dict.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger (totalt sek)", int(preview_dict.get("Suger", 0)))
        st.metric("Suger per kille (sek)", int(preview_dict.get("Suger per kille (sek)", 0)))

    # Ekonomi
    st.markdown("**💵 Ekonomi (live)**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Prenumeranter", int(preview_dict.get("Prenumeranter", 0)))
        st.metric("Hårdhet", int(preview_dict.get("Hårdhet", 0)))
    with e2:
        st.metric("Intäkter", f"${float(preview_dict.get('Intäkter', 0)):,.2f}")
        st.metric("Intäkt Känner", f"${float(preview_dict.get('Intäkt Känner', 0)):,.2f}")
    with e3:
        st.metric("Utgift män", f"${float(preview_dict.get('Utgift män', 0)):,.2f}")
        st.metric("Lön Malin", f"${float(preview_dict.get('Lön Malin', 0)):,.2f}")
    with e4:
        st.metric("Vinst", f"${float(preview_dict.get('Vinst', 0)):,.2f}")
        st.metric("Älskar (sek)", int(preview_dict.get("Tid Älskar (sek)", 0)))
    st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men läggs på klockan.")

# ======== Del 4/4 – Hämta/Slumpa-värden + visa live + spara ========

st.markdown("---")
st.subheader("⚙️ Hämta eller slumpa scenvärden (skriver endast till inputfälten)")

colA, colB = st.columns([1, 2])

with colA:
    action = st.selectbox(
        "Välj åtgärd",
        ["—", "Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila i hemmet (dag 1–7)", "Vila på jobbet"],
        index=0,
        key="scenario_select"
    )

    if st.button("📥 Hämta/Slumpa till input", use_container_width=True, key="btn_fetch_fill"):
        # Viktigt: Rör bara session_state (inputs). INGA sheets-anrop här.
        scen, rad_datum, veckodag = st.session_state["CURRENT_SCENE_INFO"]

        if action == "—":
            st.info("Välj en åtgärd ovan först.")
        elif action == "Ny scen":
            # Nollställ de flesta, behåll Avgift, Personal delt. tom (du anger själv)
            for k in ["in_män","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
                      "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta",
                      "in_eskilstuna","in_alskar","in_sover","in_tid_s","in_tid_d","in_vila",
                      "in_dt_tid","in_dt_vila","in_nils"]:
                st.session_state[k] = st.session_state.get(k, 0)
            # Bonus deltagit sätter du manuellt – men visa "tillgängligt"
            st.session_state["in_bonus_deltagit"] = 0
            # Personaldeltagande sätter du manuellt (du ville inte ha % längre)
            st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)
            st.session_state["in_typ"] = "Ny scen"

        elif action == "Slumpa scen vit":
            # Slumpa varje fält utifrån historiska min/max (läs enbart från cache om sådan finns)
            # Här använder vi bara redan lagrade min/max i sessionen, inga sheets-anrop.
            def _rand_for(col, default_lo=0, default_hi=0):
                lo, hi = st.session_state.get("HIST_MINMAX", {}).get(col, (default_lo, default_hi))
                if hi < lo: hi = lo
                return int(random.randint(lo, hi)) if hi > lo else int(lo)

            st.session_state["in_män"]    = _rand_for("Män")
            st.session_state["in_svarta"] = _rand_for("Svarta")
            st.session_state["in_fitta"]  = _rand_for("Fitta")
            st.session_state["in_rumpa"]  = _rand_for("Rumpa")
            st.session_state["in_dp"]     = _rand_for("DP")
            st.session_state["in_dpp"]    = _rand_for("DPP")
            st.session_state["in_dap"]    = _rand_for("DAP")
            st.session_state["in_tap"]    = _rand_for("TAP")

            st.session_state["in_pappan"]      = _rand_for("Pappans vänner")
            st.session_state["in_grannar"]     = _rand_for("Grannar")
            st.session_state["in_nils_vanner"] = _rand_for("Nils vänner")
            st.session_state["in_nils_familj"] = _rand_for("Nils familj")
            st.session_state["in_bekanta"]     = _rand_for("Bekanta")

            # Eskilstuna-killar slumpas från sidopanel-intervall
            esk_lo = int(st.session_state.get("esk_min", 20))
            esk_hi = int(st.session_state.get("esk_max", 40))
            if esk_hi < esk_lo: esk_hi = esk_lo
            st.session_state["in_eskilstuna"] = random.randint(esk_lo, esk_hi)

            # Du anger "Bonus deltagit" själv – men vi visar tillgängligt separat i UI
            st.session_state["in_bonus_deltagit"] = st.session_state.get("in_bonus_deltagit", 0)

            # Personaldeltagande sätter du själv
            st.session_state["in_personal_deltagit"] = st.session_state.get("in_personal_deltagit", 0)

            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1
            st.session_state["in_typ"] = "Ny scen"

        elif action == "Slumpa scen svart":
            def _rand_for(col, default_lo=0, default_hi=0):
                lo, hi = st.session_state.get("HIST_MINMAX", {}).get(col, (default_lo, default_hi))
                if hi < lo: hi = lo
                return int(random.randint(lo, hi)) if hi > lo else int(lo)

            st.session_state["in_fitta"]  = _rand_for("Fitta")
            st.session_state["in_rumpa"]  = _rand_for("Rumpa")
            st.session_state["in_dp"]     = _rand_for("DP")
            st.session_state["in_dpp"]    = _rand_for("DPP")
            st.session_state["in_dap"]    = _rand_for("DAP")
            st.session_state["in_tap"]    = _rand_for("TAP")
            st.session_state["in_svarta"] = _rand_for("Svarta")

            # Alla andra källor 0 vid svart
            for k in ["in_män","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
                st.session_state[k] = 0

            # Bonus deltagit anger du manuellt (tillgängligt visas separat)
            st.session_state["in_bonus_deltagit"] = st.session_state.get("in_bonus_deltagit", 0)

            # Personal deltagit = 0 vid svart (enligt senaste)
            st.session_state["in_personal_deltagit"] = 0

            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1
            st.session_state["in_typ"] = "Ny scen (svart)"

        elif action == "Vila i hemmet (dag 1–7)":
            # Vi fyller *dag 1* i input (du kan sedan bläddra dag 2–7 med knappar om du vill,
            # men här följer din senaste önskan: visa/fyll en dag i taget).
            offset = st.session_state.get("home_day_offset", 0)
            offset = max(0, min(6, offset))
            st.session_state["home_day_offset"] = offset

            # Dag 1–5: slumpa källor (40–60% av max) + eskilstuna-intervall
            # Dag 6–7: källor=0, personal=0
            if offset <= 4:
                def _pct_of_max(key, lo=0.40, hi=0.60):
                    mx = int(st.session_state["CFG"].get(key, 0))
                    if mx <= 0: return 0
                    a = int(round(mx * lo))
                    b = int(round(mx * hi))
                    return random.randint(a, b) if b >= a else a

                st.session_state["in_pappan"]      = _pct_of_max("MAX_PAPPAN")
                st.session_state["in_grannar"]     = _pct_of_max("MAX_GRANNAR")
                st.session_state["in_nils_vanner"] = _pct_of_max("MAX_NILS_VANNER")
                st.session_state["in_nils_familj"] = _pct_of_max("MAX_NILS_FAMILJ")
                st.session_state["in_bekanta"]     = _pct_of_max("MAX_BEKANTA")

                esk_lo = int(st.session_state.get("esk_min", 20))
                esk_hi = int(st.session_state.get("esk_max", 40))
                if esk_hi < esk_lo: esk_hi = esk_lo
                st.session_state["in_eskilstuna"] = random.randint(esk_lo, esk_hi)
                st.session_state["in_personal_deltagit"] = 0  # enligt dig: personal inte auto-beräknad längre
            else:
                for k in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"]:
                    st.session_state[k] = 0
                st.session_state["in_eskilstuna"] = 0
                st.session_state["in_personal_deltagit"] = 0

            # Vila i hemmet: allt sexuell noll
            for k in ["in_män","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
                st.session_state[k] = 0

            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 1 if offset == 6 else 0
            st.session_state["in_typ"] = f"Vila i hemmet (dag {offset+1})"

        elif action == "Vila på jobbet":
            # Slumpa fitta/rumpa/DP/DPP/DAP/TAP mellan historiskt min/max (från cache),
            # men andra källor kan vara 40–60% (eller 0 om du vill).
            def _rand_for(col, default_lo=0, default_hi=0):
                lo, hi = st.session_state.get("HIST_MINMAX", {}).get(col, (default_lo, default_hi))
                if hi < lo: hi = lo
                return int(random.randint(lo, hi)) if hi > lo else int(lo)

            st.session_state["in_fitta"]  = _rand_for("Fitta")
            st.session_state["in_rumpa"]  = _rand_for("Rumpa")
            st.session_state["in_dp"]     = _rand_for("DP")
            st.session_state["in_dpp"]    = _rand_for("DPP")
            st.session_state["in_dap"]    = _rand_for("DAP")
            st.session_state["in_tap"]    = _rand_for("TAP")

            # Övrigt nollas (du matar själv in “deltagit” etc)
            for k in ["in_män","in_svarta","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
                st.session_state[k] = 0

            st.session_state["in_alskar"] = 12
            st.session_state["in_sover"]  = 1
            st.session_state["in_personal_deltagit"] = 0  # du anger manuellt
            st.session_state["in_typ"] = "Vila på jobbet"

        st.rerun()

with colB:
    # Bygg basrad av nuvarande inputs och visa live-förhandsvisning
    base = _build_base_row_from_inputs()
    preview = _calc_preview_row(base)
    _preview_live_panel(preview)

# Spara-knapp (DETTA är enda stället som får skriva till Sheets)
st.markdown("---")
if st.button("💾 Spara raden i databasen", use_container_width=True):
    try:
        # 1) räkna på nuvarande input
        base = _build_base_row_from_inputs()
        preview = _calc_preview_row(base)
        if not preview:
            st.error("Beräkningen misslyckades – kan inte spara.")
        else:
            # 2) transformera till rätt ordning enligt header (som skapats i del 1/4)
            row = [preview.get(col, "") for col in st.session_state["COLUMNS"]]
            # 3) skriv till Sheets
            _retry_call(sheet.append_row, row)
            st.session_state[ROW_COUNT_KEY] = st.session_state.get(ROW_COUNT_KEY, 0) + 1

            # 4) uppdatera BONUS_TOTAL i sidopanel (dra bort “deltagit”, lägg till ev. nya)
            #    Här utgår vi från att beräkningen inte skapar automatisk “nya bonus”,
            #    du matar in “Bonus deltagit” i inputfältet.
            new_left = max(0, int(st.session_state.get("bonus_total", 0)) - int(base.get("Bonus deltagit", 0)))
            st.session_state["bonus_total"] = new_left

            st.success("✅ Raden sparad.")
            st.rerun()
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
