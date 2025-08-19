import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
import random

# =========================================================
# App-inställningar (offline, inga Sheets-anrop alls)
# =========================================================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (offline)")

# (valfri) beräkningar – om filen saknas kör appen ändå, men utan live-beräkning
try:
    from berakningar import berakna_radvarden as calc_row_values
except Exception:
    calc_row_values = None

# =========================================================
# Session keys & defaults
# =========================================================
CFG_KEY         = "CFG"
DATA_KEY        = "LOCAL_ROWS"          # lokalt arkiv (lista av dicts)
ROWCOUNT_KEY    = "ROWCOUNT_LOCAL"      # lokalt scennummer (bara för datum/veckodag)
SCENE_INFO_KEY  = "CURRENT_SCENE_INFO"  # (scen, datum, veckodag)
HIST_MINMAX_KEY = "HIST_MINMAX"         # cache för slump (min/max per kolumn)

# Alla inputfält i exakt ordning du begärt
INPUT_ORDER = [
    ("in_man", "Män"),
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

# extra (används av beräkningar/metadata)
AUX_KEYS = ["in_nils", "in_typ", "in_avgift"]

def _init_defaults():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum": date.today(),
            "starttid": time(7, 0),
            "fodelsedatum": date(1995, 1, 1),   # OBS: utan åäö i nyckeln
            "avgift_usd": 30.0,

            # Viktigt: ALL personal får lön, inte bara “deltagit”
            "PROD_STAFF": 800,

            # Bonuskillar tillgängliga (du minskar själv via "Bonus deltagit" när du sparar)
            "BONUS_AVAILABLE": 500,

            # Slumpintervall för Eskilstuna
            "ESK_MIN": 20,
            "ESK_MAX": 40,

            # Maxvärden för källor (för t.ex. "Vila i hemmet" 40–60 %)
            "MAX_PAPPAN": 10,
            "MAX_GRANNAR": 10,
            "MAX_NILS_VANNER": 10,
            "MAX_NILS_FAMILJ": 10,
            "MAX_BEKANTA": 10,
        }
    if DATA_KEY not in st.session_state:
        st.session_state[DATA_KEY] = []   # lista av dictar (offline databas)
    if ROWCOUNT_KEY not in st.session_state:
        st.session_state[ROWCOUNT_KEY] = 0
    if HIST_MINMAX_KEY not in st.session_state:
        st.session_state[HIST_MINMAX_KEY] = {}

    for k, _ in INPUT_ORDER:
        st.session_state.setdefault(k, 0)
    for k in AUX_KEYS:
        st.session_state.setdefault(k, 0)

_init_defaults()
CFG = st.session_state[CFG_KEY]

# =========================================================
# Hjälp
# =========================================================
_VECKODAGAR = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]

def _scene_info():
    """Helt offline: scennummer = lokalt sparade + 1, datum = start + (scen-1)."""
    scen = st.session_state[ROWCOUNT_KEY] + 1
    d = CFG["startdatum"] + timedelta(days=scen - 1)
    return scen, d, _VECKODAGAR[d.weekday()]

def _ensure_scene_info(force=False):
    if force or (SCENE_INFO_KEY not in st.session_state):
        st.session_state[SCENE_INFO_KEY] = _scene_info()

def _hist_minmax(colname: str):
    """Min/max baserat på lokalt arkiv."""
    rows = st.session_state[DATA_KEY]
    vals = []
    for r in rows:
        try:
            v = int(r.get(colname, 0) or 0)
            vals.append(v)
        except Exception:
            pass
    return (min(vals), max(vals)) if vals else (0, 0)

def _refresh_hist_minmax():
    cols = ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
            "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]
    cache = {}
    for c in cols:
        cache[c] = _hist_minmax(c)
    st.session_state[HIST_MINMAX_KEY] = cache

def _age_on(d: date, born: date) -> int:
    return d.year - born.year - ((d.month, d.day) < (born.month, born.day))

# =========================================================
# Sidopanel – inställningar
# =========================================================
with st.sidebar:
    st.header("Inställningar (offline)")
    CFG["startdatum"] = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]   = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    st.markdown("---")
    st.subheader("Ekonomi/Personal")
    CFG["avgift_usd"]  = st.number_input("Avgift (USD per prenumerant)", min_value=0.0, step=1.0, value=float(CFG["avgift_usd"]))
    CFG["PROD_STAFF"]  = st.number_input("Totalt antal personal (ALLA får lön)", min_value=0, step=1, value=int(CFG["PROD_STAFF"]))
    st.caption("Personalens lön baseras alltid på hela personalstyrkan – inte 'deltagit'.")

    st.markdown("---")
    st.subheader("Bonus & Eskilstuna")
    CFG["BONUS_AVAILABLE"] = st.number_input("Bonus killar tillgängliga (kan ändras manuellt)", min_value=0, step=1,
                                             value=int(CFG["BONUS_AVAILABLE"]))
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, step=1, value=int(CFG["ESK_MIN"]))
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], step=1, value=int(CFG["ESK_MAX"]))

# =========================================================
# Input – exakt ordning
# =========================================================
st.markdown("### 🎛️ Input (i rätt ordning)")
cols = st.columns(4)
for idx, (key, label) in enumerate(INPUT_ORDER):
    col = cols[idx % 4]
    with col:
        if key == "in_sover":
            st.session_state[key] = st.number_input(label, min_value=0, max_value=1, step=1, value=int(st.session_state[key]))
        elif key == "in_bonus_deltagit":
            st.session_state[key] = st.number_input(f"{label} (tillgängligt: {CFG['BONUS_AVAILABLE']})",
                                                    min_value=0, step=1, value=int(st.session_state[key]))
        else:
            st.session_state[key] = st.number_input(label, min_value=0, step=1, value=int(st.session_state[key]))

# Extra valfria fält
st.session_state["in_nils"]   = st.number_input("Nils (valfritt)", min_value=0, step=1, value=int(st.session_state["in_nils"]))
st.session_state["in_avgift"] = st.number_input("Avgift (USD, lämna 0 för standard)", min_value=0.0, step=1.0,
                                                value=float(st.session_state["in_avgift"]))

# =========================================================
# Hämta/Slumpa inmatning (skriver bara till inputs)
# =========================================================
st.markdown("---")
st.subheader("⚙️ Hämta/Slumpa scenvärden (påverkar endast input ovan)")

_ensure_scene_info()
scen, rad_datum, veckodag = st.session_state[SCENE_INFO_KEY]
st.caption(f"Scen #{scen} — {rad_datum} ({veckodag})")

action = st.selectbox(
    "Välj åtgärd",
    ["—", "Ny scen", "Slumpa scen vit", "Slumpa scen svart", "Vila på jobbet", "Vila i hemmet (dag 1–7)"],
    index=0
)

colA, colB = st.columns([1, 3])
with colA:
    if st.button("📥 Hämta/Slumpa till input", use_container_width=True):
        # hjälp-funktion
        def _rand_from_hist(col):
            lo, hi = st.session_state[HIST_MINMAX_KEY].get(col, (0, 0))
            hi = max(hi, lo)
            return random.randint(lo, hi) if hi > lo else lo

        # kör scenario
        if action == "Ny scen":
            for k, _ in INPUT_ORDER:
                st.session_state[k] = 0
            st.session_state["in_typ"] = "Ny scen"

        elif action == "Slumpa scen vit":
            st.session_state["in_man"]    = _rand_from_hist("Män")
            st.session_state["in_svarta"] = _rand_from_hist("Svarta")
            st.session_state["in_fitta"]  = _rand_from_hist("Fitta")
            st.session_state["in_rumpa"]  = _rand_from_hist("Rumpa")
            st.session_state["in_dp"]     = _rand_from_hist("DP")
            st.session_state["in_dpp"]    = _rand_from_hist("DPP")
            st.session_state["in_dap"]    = _rand_from_hist("DAP")
            st.session_state["in_tap"]    = _rand_from_hist("TAP")
            st.session_state["in_pappan"]      = _rand_from_hist("Pappans vänner")
            st.session_state["in_grannar"]     = _rand_from_hist("Grannar")
            st.session_state["in_nils_vanner"] = _rand_from_hist("Nils vänner")
            st.session_state["in_nils_familj"] = _rand_from_hist("Nils familj")
            st.session_state["in_bekanta"]     = _rand_from_hist("Bekanta")
            lo, hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
            hi = max(hi, lo)
            st.session_state["in_eskilstuna"] = random.randint(lo, hi)
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1
            st.session_state["in_personal_deltagit"] = st.session_state["in_personal_deltagit"]
            st.session_state["in_bonus_deltagit"]    = st.session_state["in_bonus_deltagit"]
            st.session_state["in_typ"] = "Ny scen"

        elif action == "Slumpa scen svart":
            st.session_state["in_fitta"]  = _rand_from_hist("Fitta")
            st.session_state["in_rumpa"]  = _rand_from_hist("Rumpa")
            st.session_state["in_dp"]     = _rand_from_hist("DP")
            st.session_state["in_dpp"]    = _rand_from_hist("DPP")
            st.session_state["in_dap"]    = _rand_from_hist("DAP")
            st.session_state["in_tap"]    = _rand_from_hist("TAP")
            st.session_state["in_svarta"] = _rand_from_hist("Svarta")
            for k in ["in_man","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
                st.session_state[k] = 0
            st.session_state["in_personal_deltagit"] = 0
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1
            st.session_state["in_typ"] = "Ny scen (svart)"

        elif action == "Vila på jobbet":
            # slumpa sex aktionsfält utifrån historik
            for col, key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                             ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[key] = _rand_from_hist(col)
            # övrigt noll/du anger själv
            for k in ["in_man","in_svarta","in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna"]:
                st.session_state[k] = 0
            st.session_state["in_personal_deltagit"] = st.session_state["in_personal_deltagit"]
            st.session_state["in_alskar"] = 12
            st.session_state["in_sover"]  = 1
            st.session_state["in_typ"] = "Vila på jobbet"

        elif action == "Vila i hemmet (dag 1–7)":
            # Dagindex i separat selectbox till höger
            pass

        st.rerun()

with colB:
    if action == "Vila i hemmet (dag 1–7)":
        day_idx = st.number_input("Vilken dag (1–7)?", min_value=1, max_value=7, step=1, value=1)
        if st.button("📥 Hämta 'Vila i hemmet' för vald dag", use_container_width=True):
            # Dag 1–5: 40–60 % av max; Dag 6–7: källor=0
            offset = int(day_idx - 1)

            def _pct_of_max(key, lo=0.40, hi=0.60):
                mx = int(CFG.get(key, 0))
                if mx <= 0:
                    return 0
                a = int(round(mx * lo))
                b = int(round(mx * hi))
                return random.randint(a, b) if b >= a else a

            if offset <= 4:
                st.session_state["in_pappan"]      = _pct_of_max("MAX_PAPPAN")
                st.session_state["in_grannar"]     = _pct_of_max("MAX_GRANNAR")
                st.session_state["in_nils_vanner"] = _pct_of_max("MAX_NILS_VANNER")
                st.session_state["in_nils_familj"] = _pct_of_max("MAX_NILS_FAMILJ")
                st.session_state["in_bekanta"]     = _pct_of_max("MAX_BEKANTA")
                lo, hi = int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"])
                hi = max(hi, lo)
                st.session_state["in_eskilstuna"] = random.randint(lo, hi)
            else:
                for k in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"]:
                    st.session_state[k] = 0
                st.session_state["in_eskilstuna"] = 0

            # Allt sexuellt 0 på vilodagar
            for k in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"]:
                st.session_state[k] = 0

            st.session_state["in_personal_deltagit"] = st.session_state["in_personal_deltagit"]
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 1 if offset == 6 else 0
            st.session_state["in_typ"]    = f"Vila i hemmet (dag {day_idx})"
            st.rerun()

# =========================================================
# Bygg basrad + liveförhandsvisning
# =========================================================
def _build_base_row_from_inputs():
    scen, rad_datum, veckodag = st.session_state[SCENE_INFO_KEY]
    avgift = float(st.session_state.get("in_avgift") or CFG["avgift_usd"])
    typ    = st.session_state.get("in_typ") or "Ny scen"

    # Hämta inmatningar
    def gi(k): return int(st.session_state.get(k, 0) or 0)

    base = {
        "_rad_datum": rad_datum,
        "Datum": rad_datum.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen,
        "Typ": typ,

        "Män": gi("in_man"),
        "Svarta": gi("in_svarta"),
        "Fitta": gi("in_fitta"),
        "Rumpa": gi("in_rumpa"),
        "DP": gi("in_dp"),
        "DPP": gi("in_dpp"),
        "DAP": gi("in_dap"),
        "TAP": gi("in_tap"),

        "Pappans vänner": gi("in_pappan"),
        "Grannar": gi("in_grannar"),
        "Nils vänner": gi("in_nils_vanner"),
        "Nils familj": gi("in_nils_familj"),
        "Bekanta": gi("in_bekanta"),
        "Eskilstuna killar": gi("in_eskilstuna"),

        # du anger själv antal som deltar; vi visar tillgängligt separat
        "Bonus killar": int(CFG["BONUS_AVAILABLE"]),
        "Bonus deltagit": gi("in_bonus_deltagit"),

        "Personal deltagit": gi("in_personal_deltagit"),

        "Älskar": gi("in_alskar"),
        "Sover med": gi("in_sover"),

        "Tid S": gi("in_tid_s"),
        "Tid D": gi("in_tid_d"),
        "Vila":  gi("in_vila"),
        "DT tid (sek/kille)":  gi("in_dt_tid"),
        "DT vila (sek/kille)": gi("in_dt_vila"),

        "Nils": gi("in_nils"),
        "Avgift": avgift,

        # viktigt: all personal får lön
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
    }

    # "Känner" = summan av fyra källor
    base["Känner"] = base["Pappans vänner"] + base["Grannar"] + base["Nils vänner"] + base["Nils familj"]
    return base

def _calc_preview_row(base):
    if not callable(calc_row_values):
        return {}
    try:
        return calc_row_values(grund=base, rad_datum=base["_rad_datum"],
                               fodelsedatum=CFG["fodelsedatum"], starttid=CFG["starttid"]) or {}
    except TypeError:
        # bakåtkompatibel signatur
        return calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"]) or {}

def _ms(sec: int) -> str:
    m = sec // 60; s = sec % 60
    return f"{m}m {s}s"

def _preview_panel(pre):
    if not pre:
        st.info("Ingen förhandsdata – fyll i fält eller hämta scenvärden.")
        return

    # överkant
    dd = pre.get("Datum", "-")
    vd = pre.get("Veckodag", "-")
    try:
        d = datetime.fromisoformat(dd).date()
    except Exception:
        d = date.today()
    alder = _age_on(d, CFG["fodelsedatum"])
    st.markdown(f"**Datum/Veckodag:** {dd} / {vd} • **Ålder:** {alder} år")

    # tider
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Summa tid", pre.get("Summa tid", "-"))
        st.metric("Summa tid (sek)", int(pre.get("Summa tid (sek)", 0)))
    with c2:
        st.metric("Tid/kille", pre.get("Tid per kille", "-"))
        st.metric("Tid/kille (sek)", int(pre.get("Tid per kille (sek)", 0)))
    with c3:
        st.metric("Klockan", pre.get("Klockan", "-"))
        st.metric("Totalt män", int(pre.get("Totalt Män", 0)))

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Hångel (m:s/kille)", pre.get("Hångel (m:s/kille)", "-"))
        st.metric("Hångel (sek/kille)", int(pre.get("Hångel (sek/kille)", 0)))
    with c5:
        st.metric("Suger (totalt sek)", int(pre.get("Suger", 0)))
        st.metric("Suger per kille (sek)", int(pre.get("Suger per kille (sek)", 0)))
    st.caption("Obs: Älskar/Sover ingår inte i Summa tid, men läggs på klockan.")

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
        st.metric("Tid Älskar (sek)", int(pre.get("Tid Älskar (sek)", 0)))

# Förhandsvisning
base = _build_base_row_from_inputs()
preview = _calc_preview_row(base)
st.markdown("---")
st.subheader("🔎 Förhandsvisning (live, offline)")
_preview_panel(preview)

# =========================================================
# Spara (offline – till minnet)
# =========================================================
st.markdown("---")
if st.button("💾 Spara raden (offline)", use_container_width=True):
    base = _build_base_row_from_inputs()
    pre = _calc_preview_row(base)
    if not pre:
        st.error("Beräkningen saknas eller misslyckades – kan inte spara.")
    else:
        # spara lokalt
        st.session_state[DATA_KEY].append(pre)

        # uppdatera lokalt scennummer & sceninfo
        st.session_state[ROWCOUNT_KEY] += 1
        _ensure_scene_info(force=True)

        # minska BONUS_AVAILABLE med "Bonus deltagit"
        try:
            used = int(base.get("Bonus deltagit", 0))
            CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) - used)
        except Exception:
            pass

        # uppdatera historik för bättre slump framåt
        _refresh_hist_minmax()

        st.success("✅ Raden sparad (offline).")
        st.rerun()

# =========================================================
# Visa lokalt arkiv
# =========================================================
st.markdown("---")
st.subheader("📄 Lokala rader (offline)")
if st.session_state[DATA_KEY]:
    df = pd.DataFrame(st.session_state[DATA_KEY])
    st.dataframe(df, use_container_width=True)
else:
    st.info("Inga rader sparade ännu.")
