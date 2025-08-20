# app.py
import streamlit as st
from datetime import date, time, datetime, timedelta
import random
import pandas as pd
import json

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets + live)")

# =========================
# Import av moduler
# =========================
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar (berakningar.py): {e}")
    st.stop()

# Hjälpmoduler (valfria men rekommenderas)
try:
    import sheets_utils as SU
except Exception:
    SU = None
try:
    import profiler as PROF
except Exception:
    PROF = None
try:
    from statistik import compute_stats as compute_stats_main
except Exception:
    compute_stats_main = None
# Valfria statistikmoduler (om de finns)
try:
    from statistik_affar import compute_stats as compute_stats_affar
except Exception:
    compute_stats_affar = None
try:
    from statistik_relation import compute_stats as compute_stats_relation
except Exception:
    compute_stats_relation = None

# =========================
# State-nycklar
# =========================
CFG_KEY        = "CFG"            # alla config + etiketter
ROWS_KEY       = "ROWS"           # sparade rader (lokalt minne / inläst från Data)
HIST_MM_KEY    = "HIST_MINMAX"    # min/max per fält
SCENEINFO_KEY  = "CURRENT_SCENE"  # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"       # rullist-valet
PROFILE_KEY    = "PROFILE"        # valt profilnamn
PROFILE_LIST   = "PROFILE_LIST"   # lista med profiler
HANDS_KEY      = "HANDS_ON"       # “Händer aktiv” (0/1) på radnivå (widget)
BONUS_RATE_KEY = "BONUS_RATE"     # % av prenumeranter -> bonus-killar

# =========================
# Input-ordning (EXAKT)
# =========================
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

# =========================
# Init state
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def _init_cfg_defaults():
    return {
        # Start/Födelse (enligt önskemål)
        "startdatum":   date(1990,1,1),
        "starttid":     time(7,0),
        "fodelsedatum": date(1970,1,1),

        # Ekonomi & personal
        "avgift_usd":   30.0,
        "PROD_STAFF":   800,
        "BONUS_AVAILABLE": 500,    # “Bonus killar kvar”
        BONUS_RATE_KEY: 0.01,      # andel prenumeranter → bonus-killar (justerbart)

        # Eskilstuna-intervall
        "ESK_MIN": 20, "ESK_MAX": 40,

        # Maxvärden (källor)
        "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
        "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
        "MAX_BEKANTA": 100,

        # Etiketter (kan döpas om; slår igenom i input/live/statistik)
        "LBL_PAPPAN": "Pappans vänner",
        "LBL_GRANNAR": "Grannar",
        "LBL_NILS_VANNER": "Nils vänner",
        "LBL_NILS_FAMILJ": "Nils familj",
        "LBL_BEKANTA": "Bekanta",
        "LBL_ESK": "Eskilstuna killar",
    }

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = _init_cfg_defaults()
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = "Malin"
    if PROFILE_LIST not in st.session_state:
        st.session_state[PROFILE_LIST] = []
    if HANDS_KEY not in st.session_state:
        st.session_state[HANDS_KEY] = 1  # “Händer aktiv” default: Ja

    # defaults för input (tidsfält etc.)
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7,
        "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))

    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# =========================
# Hjälpare: min/max + slump
# =========================
def _add_hist_value(col, v):
    try: v = int(v)
    except: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(r.get(colname, 0)))
        except: pass
    mm = (min(vals), max(vals)) if vals else (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)
    st.session_state[HANDS_KEY] = 1  # default Ja vid hämtning

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_BEKANTA"],"in_bekanta"),
                      (CFG["LBL_GRANNAR"],"in_grannar"),(CFG["LBL_NILS_VANNER"],"in_nils_vanner"),
                      (CFG["LBL_NILS_FAMILJ"],"in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        # På vila-rader sätter vi “Händer aktiv” = Nej (0) och låser ekonomi till 0 vid spar/preview
        st.session_state[HANDS_KEY] = 0

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag enligt din senare beskrivning
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                      (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                      (CFG["LBL_BEKANTA"],"in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0
        st.session_state[HANDS_KEY]   = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel: Profil & Inställningar & Sheets
# =========================
CFG = st.session_state[CFG_KEY]

with st.sidebar:
    st.header("Profil & Google Sheets")

    # Secrets status
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Läs profiler
    if SU and PROF and has_creds and has_url:
        try:
            ss = SU.get_client()
            profiles = PROF.get_profiles(ss)
            st.session_state[PROFILE_LIST] = profiles or ["Malin"]
        except Exception as e:
            st.info(f"Kunde inte läsa profil-lista: {e}")
            if not st.session_state[PROFILE_LIST]:
                st.session_state[PROFILE_LIST] = ["Malin"]
    else:
        if not st.session_state[PROFILE_LIST]:
            st.session_state[PROFILE_LIST] = ["Malin"]

    # Välj profil
    st.session_state[PROFILE_KEY] = st.selectbox(
        "Välj profil",
        st.session_state[PROFILE_LIST],
        index=max(0, st.session_state[PROFILE_LIST].index(st.session_state[PROFILE_KEY]) if st.session_state[PROFILE_KEY] in st.session_state[PROFILE_LIST] else 0)
    )

    # Läs in vald profil (inställningar + Data)
    if st.button("📥 Läs in vald profil"):
        if SU and PROF and has_creds and has_url:
            try:
                ss = SU.get_client()
                # Ladda CFG från profil-blad
                cfg_from_sheet = PROF.load_profile_cfg(ss, st.session_state[PROFILE_KEY])
                if cfg_from_sheet:
                    # behåll etiketter om saknas i bladet
                    base_defaults = _init_cfg_defaults()
                    merged = {**base_defaults, **CFG, **cfg_from_sheet}
                    st.session_state[CFG_KEY] = merged
                    CFG = merged
                # Ladda rader för profilen
                rows_df = PROF.load_profile_rows(ss, st.session_state[PROFILE_KEY])
                if isinstance(rows_df, pd.DataFrame) and not rows_df.empty:
                    st.session_state[ROWS_KEY] = rows_df.to_dict(orient="records")
                else:
                    st.session_state[ROWS_KEY] = []
                # Bygg om min/max
                st.session_state[HIST_MM_KEY] = {}
                for r in st.session_state[ROWS_KEY]:
                    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                                CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                        _add_hist_value(col, r.get(col, 0))
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"✅ Läste in profil '{st.session_state[PROFILE_KEY]}' (inställningar + data).")
            except Exception as e:
                st.error(f"Kunde inte läsa profil: {e}")
        else:
            st.warning("Lägg till sheets-modulerna/smarta secrets för att läsa profiler.")

    st.markdown("---")
    st.header("Inställningar")

    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG[BONUS_RATE_KEY] = st.number_input("Bonus-killar procent (0–100)", min_value=0.0, max_value=100.0, value=float(CFG[BONUS_RATE_KEY]*100.0), step=0.1) / 100.0

    st.markdown(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=CFG["ESK_MIN"], value=int(CFG["ESK_MAX"]), step=1)

    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG["MAX_PAPPAN"]), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG["MAX_GRANNAR"]), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG["MAX_NILS_VANNER"]), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG["MAX_NILS_FAMILJ"]), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG["MAX_BEKANTA"]), step=1)

    st.subheader("Egna etiketter")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG["LBL_ESK"])

    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj scenario",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

    st.markdown("---")
    st.subheader("Spara/Läs Inställningar (Sheets)")
    colA, colB = st.columns(2)
    with colA:
        if st.button("💾 Spara inställningar till Sheets"):
            if SU and PROF and has_creds and has_url:
                try:
                    ss = SU.get_client()
                    PROF.save_profile_cfg(ss, st.session_state[PROFILE_KEY], st.session_state[CFG_KEY])
                    st.success("✅ Inställningar sparade till profil-bladet.")
                except Exception as e:
                    st.error(f"Misslyckades att spara inställningar: {e}")
            else:
                st.warning("Sheets-utils/profiler saknas eller secrets saknas.")

    with colB:
        if st.button("📥 Läs inställningar (endast)"):
            if SU and PROF and has_creds and has_url:
                try:
                    ss = SU.get_client()
                    cfg_from_sheet = PROF.load_profile_cfg(ss, st.session_state[PROFILE_KEY])
                    if cfg_from_sheet:
                        base_defaults = _init_cfg_defaults()
                        merged = {**base_defaults, **CFG, **cfg_from_sheet}
                        st.session_state[CFG_KEY] = merged
                        st.success("✅ Inställningar laddade från profil-bladet.")
                except Exception as e:
                    st.error(f"Kunde inte läsa inställningar: {e}")
            else:
                st.warning("Sheets-utils/profiler saknas eller secrets saknas.")

# =========================
# Inmatning (etiketter av inställningar), exakt ordning
# =========================
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)

LBL_PAPPAN = CFG["LBL_PAPPAN"]
LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]
LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"]
LBL_ESK = CFG["LBL_ESK"]

labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)",
    "in_pappan":f"{LBL_PAPPAN} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{LBL_GRANNAR} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{LBL_NV} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{LBL_NF} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{LBL_BEK} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{LBL_ESK} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG['BONUS_AVAILABLE'])})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_nils":"Nils (0/1/2)"
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

# Händer aktiv (Ja/Nej)
st.checkbox("Händer aktiv (påverkar 'Händer per kille')", value=bool(st.session_state[HANDS_KEY]), key=HANDS_KEY)

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs() -> dict:
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        LBL_PAPPAN: st.session_state["in_pappan"],
        LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV:      st.session_state["in_nils_vanner"],
        LBL_NF:      st.session_state["in_nils_familj"],
        LBL_BEK:     st.session_state["in_bekanta"],
        LBL_ESK:     st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # ge berakningar “label-nycklarna” så modul klarar båda varianter
        "LBL_PAPPAN": LBL_PAPPAN, "LBL_GRANNAR": LBL_GRANNAR,
        "LBL_NILS_VANNER": LBL_NV, "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK, "LBL_ESK": LBL_ESK,

        # maxvärden (för Känner sammanlagt)
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]), "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]), "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
    }
    # Känner
    base["Känner"] = (
        int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) +
        int(base[LBL_NV]) + int(base[LBL_NF])
    )
    # Händer
    base["Händer aktiv"] = int(bool(st.session_state[HANDS_KEY]))

    # meta till beräkning
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# =========================
# Live (preview) + förstärkta affärsberäkningar
# =========================
st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
# 1) kärnberäkningar (tid/klocka/händer/suger etc) från berakningar.py
preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])

# 2) här lägger vi på “affärs”-delen (Hårdhet, Prenumeranter, Intäkter, Kostnad, Intäkt Känner, Intäkt företag, Lön, Vinst)
def _hardhet(row: dict) -> int:
    score = 0
    if int(row.get("DP",0))  > 0: score += 3
    if int(row.get("DPP",0)) > 0: score += 5
    if int(row.get("DAP",0)) > 0: score += 7
    if int(row.get("TAP",0)) > 0: score += 9
    tm = int(preview.get("Totalt Män",0))
    # thresholds
    if tm > 100: score += 1
    if tm > 200: score += 2
    if tm > 400: score += 4
    if tm > 700: score += 7
    if tm > 1000: score += 10
    if int(row.get("Svarta",0)) > 0: score += 3
    return score

def _age_years(at_date: date, born: date) -> int:
    if not isinstance(at_date, (date, datetime)) or not isinstance(born, (date, datetime)):
        return 0
    if isinstance(at_date, datetime): at_date = at_date.date()
    if isinstance(born, datetime): born = born.date()
    return at_date.year - born.year - ((at_date.month, at_date.day) < (born.month, born.day))

# Hårdhet
hardhet = _hardhet(base)
preview["Hårdhet"] = hardhet

# Prenumeranter (rad) = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
tot_m = int(preview.get("Totalt Män",0))
pren = (int(base.get("DP",0)) + int(base.get("DPP",0)) + int(base.get("DAP",0)) + int(base.get("TAP",0)) + tot_m) * hardhet
preview["Prenumeranter"] = int(pren)

# Bonus-killar uppdateras vid spar – här visar vi bara aktuell procentsats i live
bonus_rate = float(CFG.get(BONUS_RATE_KEY, 0.01))

# Intäkter = pren * avgift
preview["Intäkter"] = float(preview["Prenumeranter"]) * float(CFG["avgift_usd"])

# Kostnad män = (summa tid (sek)/3600) * ((män + svarta + bekanta + esk) + PROD_STAFF) * 15 USD
summa_tid_sek = int(preview.get("Summa tid (sek)",0))
hours = summa_tid_sek / 3600.0
kostnads_mangd = (int(base.get("Män",0)) + int(base.get("Svarta",0)) + int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0))) + int(CFG["PROD_STAFF"])
preview["Kostnad män"] = float(hours * kostnads_mangd * 15.0)

# Intäkt Känner = Känner sammanlagt (rad) * 30 USD
preview["Intäkt Känner"] = float(int(preview.get("Känner sammanlagt",0)) * 30.0)

# Intäkt företag = Intäkter - Kostnad män - Intäkt Känner
preview["Intäkt företag"] = float(preview["Intäkter"] - preview["Kostnad män"] - preview["Intäkt Känner"])

# Lön Malin = min(max(0.08 * intäkt_företag, 150), 800) * åldersfaktor
age = _age_years(base["_rad_datum"], base["_fodelsedatum"])
base_pay = max(150.0, min(0.08 * max(preview["Intäkt företag"], 0.0), 800.0))
if age <= 18:
    age_factor = 1.00
elif 19 <= age <= 23:
    age_factor = 0.90
elif 24 <= age <= 27:
    age_factor = 0.85
elif 28 <= age <= 30:
    age_factor = 0.80
elif 31 <= age <= 32:
    age_factor = 0.75
elif 33 <= age <= 35:
    age_factor = 0.70
else:
    age_factor = 0.60
preview["Lön Malin"] = float(base_pay * age_factor)

# Vinst = Intäkt företag - Lön Malin
preview["Vinst"] = float(preview["Intäkter"] - preview["Kostnad män"] - preview["Intäkt Känner"] - preview["Lön Malin"])

# Special: Om scenario är en av “Vila …” ska pren/intäkt/kostnad/lön vara 0
if st.session_state[SCENARIO_KEY] in ("Vila på jobbet","Vila i hemmet (dag 1–7)"):
    preview["Prenumeranter"]  = 0
    preview["Intäkter"]       = 0.0
    preview["Kostnad män"]    = 0.0
    preview["Lön Malin"]      = 0.0
    preview["Intäkt företag"] = float(0.0)
    preview["Vinst"]          = float(0.0)

# =========================
# Live-visning
# =========================
# Egen kontrollsumma (alla inräknade källor)
tot_men_including = (
    int(base.get("Män",0)) + int(base.get("Svarta",0)) +
    int(base.get(LBL_PAPPAN,0)) + int(base.get(LBL_GRANNAR,0)) +
    int(base.get(LBL_NV,0)) + int(base.get(LBL_NF,0)) +
    int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) +
    int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
)

# Datum/ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try:
        _d = datetime.fromisoformat(rad_datum).date()
    except Exception:
        _d = datetime.today().date()
else:
    _d = datetime.today().date()

fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille","-"))
    st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
with c3:
    st.metric("Klockan", preview.get("Klockan","-"))
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
with c5:
    st.metric("Händer aktiv", "Ja" if base.get("Händer aktiv",1) else "Nej")
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))

st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
with e2:
    st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
with e3:
    st.metric("Kostnad män", f"${float(preview.get('Kostnad män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(LBL_PAPPAN, int(base.get(LBL_PAPPAN,0)))
with k2: st.metric(LBL_GRANNAR, int(base.get(LBL_GRANNAR,0)))
with k3: st.metric(LBL_NV, int(base.get(LBL_NV,0)))
with k4: st.metric(LBL_NF, int(base.get(LBL_NF,0)))
with k5: st.metric(LBL_BEK, int(base.get(LBL_BEK,0)))
with k6: st.metric(LBL_ESK, int(base.get(LBL_ESK,0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men lägger på klockan. På 'Vila' är pren/intäkt/kostnad/lön = 0.")

# =========================
# Spara lokalt / till Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _after_save_side_effects(preview_row: dict):
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        v = int(preview_row.get(col,0))
        _add_hist_value(col, v)
    # bonus kvar: + (bonus från pren) - (bonus deltagit)
    try:
        bonus_from_pren = int((int(preview_row.get("Prenumeranter",0)) * float(CFG.get(BONUS_RATE_KEY,0.01))))
    except Exception:
        bonus_from_pren = 0
    b_delt = int(preview_row.get("Bonus deltagit",0))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + bonus_from_pren - b_delt)

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        # bygg rad som skrivs (lägg på profil + händer + etiketter)
        row_to_save = dict(preview)
        row_to_save["Profil"] = st.session_state[PROFILE_KEY]
        row_to_save["Händer aktiv"] = int(bool(base.get("Händer aktiv",1)))
        # ersätt label-kolumner med deras värden (så det stämmer mot Data-fliken)
        row_to_save[LBL_PAPPAN]  = int(base.get(LBL_PAPPAN,0))
        row_to_save[LBL_GRANNAR] = int(base.get(LBL_GRANNAR,0))
        row_to_save[LBL_NV]      = int(base.get(LBL_NV,0))
        row_to_save[LBL_NF]      = int(base.get(LBL_NF,0))
        row_to_save[LBL_BEK]     = int(base.get(LBL_BEK,0))
        row_to_save[LBL_ESK]     = int(base.get(LBL_ESK,0))

        st.session_state[ROWS_KEY].append(row_to_save)
        _after_save_side_effects(row_to_save)
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad lokalt.")

def save_row_to_sheets(row_dict: dict):
    if not (SU and PROF and ("GOOGLE_CREDENTIALS" in st.secrets) and ("SHEET_URL" in st.secrets)):
        raise RuntimeError("Sheets-utils/profiler saknas eller secrets saknas.")
    ss = SU.get_client()
    ws = SU.ensure_ws(ss, "Data")
    # Header
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    # Ordna i headerordning
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            row_to_save = dict(preview)
            row_to_save["Profil"] = st.session_state[PROFILE_KEY]
            row_to_save["Händer aktiv"] = int(bool(base.get("Händer aktiv",1)))
            # label-kolumner
            row_to_save[LBL_PAPPAN]  = int(base.get(LBL_PAPPAN,0))
            row_to_save[LBL_GRANNAR] = int(base.get(LBL_GRANNAR,0))
            row_to_save[LBL_NV]      = int(base.get(LBL_NV,0))
            row_to_save[LBL_NF]      = int(base.get(LBL_NF,0))
            row_to_save[LBL_BEK]     = int(base.get(LBL_BEK,0))
            row_to_save[LBL_ESK]     = int(base.get(LBL_ESK,0))

            save_row_to_sheets(row_to_save)
            st.success("✅ Sparad till Google Sheets (Data).")

            # spegla lokalt + side effects
            st.session_state[ROWS_KEY].append(row_to_save)
            _after_save_side_effects(row_to_save)
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
        except Exception as e:
            st.error(f"Misslyckades att spara: {e}")

# =========================
# Visa lokala rader
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

# =========================
# Statistik
# =========================
st.markdown("---")
st.subheader("📊 Statistik")

rows_df = pd.DataFrame(st.session_state[ROWS_KEY])

cols = st.columns(3)

with cols[0]:
    if compute_stats_main:
        try:
            # prova (rows_df, cfg) – annars (rows_df) – annars (rows list)
            try:
                res = compute_stats_main(rows_df, CFG)
            except TypeError:
                try:
                    res = compute_stats_main(rows_df)
                except TypeError:
                    res = compute_stats_main(st.session_state[ROWS_KEY])
            st.markdown("**Allmänt**")
            if isinstance(res, dict):
                for k,v in res.items():
                    st.write(f"- **{k}**: {v}")
            else:
                st.write(res)
        except Exception as e:
            st.error(f"Kunde inte beräkna statistik (statistik.py): {e}")
    else:
        st.info("statistik.py saknas – lägg filen i samma mapp.")

with cols[1]:
    if compute_stats_affar:
        try:
            res = compute_stats_affar(rows_df, CFG)
            st.markdown("**Affär**")
            if isinstance(res, dict):
                for k,v in res.items():
                    st.write(f"- **{k}**: {v}")
            else:
                st.write(res)
        except Exception as e:
            st.error(f"Kunde inte beräkna affärsstatistik: {e}")
    else:
        st.caption("statistik_affar.py ej funnen (valfri).")

with cols[2]:
    if compute_stats_relation:
        try:
            res = compute_stats_relation(rows_df, CFG)
            st.markdown("**Relations**")
            if isinstance(res, dict):
                for k,v in res.items():
                    st.write(f"- **{k}**: {v}")
            else:
                st.write(res)
        except Exception as e:
            st.error(f"Kunde inte beräkna relationsstatistik: {e}")
    else:
        st.caption("statistik_relation.py ej funnen (valfri).")
