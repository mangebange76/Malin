import streamlit as st
import random
import json
import pandas as pd
from datetime import date, time, datetime, timedelta

# ===== Moduler (måste finnas i samma mapp) =====
from sheets_utils import (
    list_profiles, read_profile_settings, read_profile_data,
    save_profile_settings, append_row_to_profile_data
)

# Beräkningar (din modul)
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

# Statistik (valfri modul)
try:
    from statistik import compute_stats
    _HAS_STATS = True
except Exception:
    _HAS_STATS = False

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Google Sheets)")

# ======== State-nycklar ========
CFG_KEY        = "CFG"           # alla config + etiketter
ROWS_KEY       = "ROWS"          # sparade rader lokalt (list[dict])
HIST_MM_KEY    = "HIST_MINMAX"   # min/max per fält för slump
SCENEINFO_KEY  = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY   = "SCENARIO"      # rullist-valet
PROFILE_KEY    = "PROFILE"       # vald profil
BONUS_LEFT_KEY = "BONUS_AVAILABLE"   # alias i CFG
SUPER_ACC_KEY  = "SUPER_BONUS_ACC"   # ack superbonus i CFG

# >>> BMI-ackumulatorer (nytt)
BMI_SUM_KEY     = "BMI_SUM"        # summa av individuella slumpade BMI (12–18)
BMI_CNT_KEY     = "BMI_CNT"        # antal prenumeranter som ingår i BMI-snittet historiskt
PENDING_BMI_KEY = "PENDING_BMI"    # cache för aktuell rad: {"scene":int,"sum":float,"count":int}

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
    "in_hander_aktiv",  # JA/NEJ -> 1/0
    "in_nils"
]

# =========================
# Init state
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d  = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def _init_cfg_defaults():
    # Start/födelse + ekonomi + bonusar
    return {
        "startdatum":   date(1990,1,1),
        "starttid":     time(7,0),
        "fodelsedatum": date(1970,1,1),

        "avgift_usd":   30.0,
        "PROD_STAFF":   800,

        # Bonus kvar (kan vara profilspecifikt)
        BONUS_LEFT_KEY: 500,
        # Bonus-andel (decimal %): 1.0 = 1%, 0.5 = 0.5%, 1.5 = 1.5%
        "BONUS_PCT": 1.0,

        # Super-bonus
        "SUPER_BONUS_PCT": 0.1,  # decimal % av prenumeranter
        SUPER_ACC_KEY: 0,        # ackumulerat heltal

        # BM mål (BMI-mål) + längd (centimeter)
        "BMI_GOAL": 21.7,        # (visas i UI men ignoreras i beräkningen)
        "HEIGHT_CM": 164,        # centimeter

        # Eskilstuna-intervall
        "ESK_MIN": 20, "ESK_MAX": 40,

        # Maxvärden (källor)
        "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
        "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
        "MAX_BEKANTA": 100,

        # Etiketter (kan döpas om i sidopanel)
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
        profs = list_profiles()
        st.session_state[PROFILE_KEY] = (profs[0] if profs else "")
    # >>> BMI-ackumulatorer
    st.session_state.setdefault(BMI_SUM_KEY, 0.0)
    st.session_state.setdefault(BMI_CNT_KEY, 0)
    st.session_state.setdefault(PENDING_BMI_KEY, {"scene": None, "sum": 0.0, "count": 0})
    # default för tidsfält m.m.
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander_aktiv":1
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
    try:
        v = int(v)
    except Exception:
        v = 0
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
        try:
            vals.append(int(r.get(colname, 0)))
        except Exception:
            pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_1_to_max(colname: str):
    """Slumpar i intervallet 1..(historiskt max). Om max<=0 -> 0."""
    _, hi = _minmax_from_hist(colname)
    if hi <= 0:
        return 0
    return random.randint(1, hi)

def _rand_esk(CFG):
    lo = int(CFG.get("ESK_MIN", 0))
    hi = int(CFG.get("ESK_MAX", lo))
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder och händer aktiv)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_aktiv":st.session_state.get("in_hander_aktiv",1)}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    # gemensam slumpning för sex + källor där det ska slumpas
    def _slumpa_sexfalt():
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_1_to_max(f)

    def _slumpa_kallor():
        LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
        LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
        LBL_BEK = CFG["LBL_BEKANTA"]
        st.session_state["in_pappan"]      = _rand_1_to_max(LBL_PAPPAN)
        st.session_state["in_grannar"]     = _rand_1_to_max(LBL_GRANNAR)
        st.session_state["in_nils_vanner"] = _rand_1_to_max(LBL_NV)
        st.session_state["in_nils_familj"] = _rand_1_to_max(LBL_NF)
        st.session_state["in_bekanta"]     = _rand_1_to_max(LBL_BEK)
        st.session_state["in_eskilstuna"]  = _rand_esk(CFG)

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_1_to_max("Män")
        _slumpa_sexfalt()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_1_to_max("Svarta")
        _slumpa_sexfalt()
        # Källor -> 0 enligt din begäran
        st.session_state["in_pappan"] = 0
        st.session_state["in_grannar"] = 0
        st.session_state["in_nils_vanner"] = 0
        st.session_state["in_nils_familj"] = 0
        st.session_state["in_bekanta"] = 0
        st.session_state["in_eskilstuna"] = _rand_esk(CFG)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        _slumpa_sexfalt()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        _slumpa_sexfalt()
        _slumpa_kallor()
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    elif s == "Super bonus":
        # Lägg hela ackumulerade superbonusen i Svarta, resten styr du manuellt
        st.session_state["in_svarta"] = int(st.session_state[CFG_KEY].get(SUPER_ACC_KEY, 0))

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel – Inställningar & Profiler
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG[BONUS_LEFT_KEY])}")
    st.markdown(f"**Super-bonus ack (antal):** {int(CFG.get(SUPER_ACC_KEY,0))}")

    CFG["BONUS_PCT"]        = st.number_input("Bonus % (decimal, t.ex. 1.0 = 1%)", min_value=0.0, value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)
    CFG["SUPER_BONUS_PCT"]  = st.number_input("Super-bonus % (decimal, t.ex. 0.1 = 0.1%)", min_value=0.0, value=float(CFG.get("SUPER_BONUS_PCT",0.1)), step=0.1)
    CFG["BMI_GOAL"]         = st.number_input("BM mål (BMI)", min_value=10.0, max_value=40.0, value=float(CFG.get("BMI_GOAL",21.7)), step=0.1)
    CFG["HEIGHT_CM"]        = st.number_input("Längd (cm)", min_value=140, max_value=220, value=int(CFG.get("HEIGHT_CM",164)), step=1)

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
    st.subheader("Egna etiketter (slår igenom i input/live)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG["LBL_ESK"])

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)","Super bonus"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)","Super bonus"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

    # =========================
    # Profiler & Sheets
    # =========================
    st.markdown("---")
    st.subheader("Profiler (Sheets)")
    profiles = list_profiles()
    if not profiles:
        st.info("Inga profiler funna i fliken 'Profil'. Lägg till namn i kolumn A i bladet 'Profil'.")
    selected_profile = st.selectbox("Välj profil", options=profiles or ["(saknas)"],
                                    index=(profiles.index(st.session_state[PROFILE_KEY]) if st.session_state.get(PROFILE_KEY) in profiles else 0))
    st.session_state[PROFILE_KEY] = selected_profile

    colP1, colP2 = st.columns(2)
    with colP1:
        if st.button("📥 Läs in profilens inställningar"):
            try:
                prof_cfg = read_profile_settings(selected_profile)
                if prof_cfg:
                    st.session_state[CFG_KEY].update(prof_cfg)
                    st.success(f"✅ Läste in inställningar för '{selected_profile}'.")
                else:
                    st.warning(f"Inga inställningar hittades på bladet '{selected_profile}'.")
            except Exception as e:
                st.error(f"Kunde inte läsa profilens inställningar: {e}")

    with colP2:
        if st.button("📥 Läs in profilens data"):
            try:
                df = read_profile_data(selected_profile)
                st.session_state[ROWS_KEY] = df.to_dict(orient="records") if not df.empty else []
                # bygg min/max för slump
                st.session_state[HIST_MM_KEY] = {}
                LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
                LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
                LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]
                for r in st.session_state[ROWS_KEY]:
                    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                                LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF,
                                LBL_BEK, LBL_ESK]:
                        _add_hist_value(col, r.get(col, 0))
                # >>> Bygg BMI-ackumulatorer från befintliga rader (om fält finns)
                bmi_sum = 0.0
                bmi_cnt = 0
                for r in st.session_state[ROWS_KEY]:
                    try:
                        pren = int(float(r.get("Prenumeranter", 0)))
                        bm   = float(r.get("BM mål", 0))
                        if pren > 0 and bm > 0:
                            bmi_sum += bm * pren
                            bmi_cnt += pren
                    except Exception:
                        pass
                st.session_state[BMI_SUM_KEY] = float(bmi_sum)
                st.session_state[BMI_CNT_KEY] = int(bmi_cnt)
                st.session_state[PENDING_BMI_KEY] = {"scene": None, "sum": 0.0, "count": 0}

                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"✅ Läste in {len(st.session_state[ROWS_KEY])} rader för '{selected_profile}'.")
            except Exception as e:
                st.error(f"Kunde inte läsa profilens data: {e}")

    st.caption(f"GOOGLE_CREDENTIALS: {'✅' if 'GOOGLE_CREDENTIALS' in st.secrets else '❌'} • SHEET_URL: {'✅' if 'SHEET_URL' in st.secrets else '❌'}")

    if st.button("💾 Spara inställningar till profil"):
        try:
            save_profile_settings(selected_profile, st.session_state[CFG_KEY])
            st.success("✅ Inställningar sparade till profilbladet.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

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
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(CFG[BONUS_LEFT_KEY])})",
    "in_personal_deltagit":f"Personal deltagit (av {int(CFG['PROD_STAFF'])})",
    "in_hander_aktiv":"Händer aktiv (1=Ja, 0=Nej)",
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
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_hander_aktiv"], min_value=0, max_value=1, step=1, key="in_hander_aktiv")
    st.number_input(labels["in_nils"], min_value=0, step=1, key="in_nils")

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Profil": st.session_state.get(PROFILE_KEY,""),
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"],
        "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        CFG["LBL_PAPPAN"]: st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]: st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        CFG["LBL_ESK"]:      st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv":      st.session_state["in_hander_aktiv"],

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # labels och max in som referens till beräkningsmodul (om den vill)
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
        "MAX_BEKANTA": int(CFG["MAX_BEKANTA"]),
        "LBL_PAPPAN": CFG["LBL_PAPPAN"],
        "LBL_GRANNAR": CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER": CFG["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ": CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": CFG["LBL_BEKANTA"],
        "LBL_ESK": CFG["LBL_ESK"],
    }
    # Känner = summa av käll-etiketter (radnivå)
    base["Känner"] = (
        int(base[CFG["LBL_PAPPAN"]]) + int(base[CFG["LBL_GRANNAR"]]) +
        int(base[CFG["LBL_NILS_VANNER"]]) + int(base[CFG["LBL_NILS_FAMILJ"]])
    )
    # meta till beräkning
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# =========================
# Ekonomiberäkningar (i appen) – kompletterar preview
# =========================
def _hardhet_from(base, preview):
    hard = 0
    if int(base.get("DP",0))  > 0: hard += 3
    if int(base.get("DPP",0)) > 0: hard += 5
    if int(base.get("DAP",0)) > 0: hard += 7
    if int(base.get("TAP",0)) > 0: hard += 9
    tm = int(preview.get("Totalt Män",0))
    if tm > 100: hard += 1
    if tm > 200: hard += 2
    if tm > 400: hard += 4
    if tm > 700: hard += 7
    if tm > 1000: hard += 10
    if int(base.get("Svarta",0)) > 0: hard += 3
    # vila/super -> 0
    typ = str(base.get("Typ",""))
    if "Vila" in typ or "Super bonus" in typ:
        hard = 0
    return hard

def _econ_compute(base, preview):
    out = {}
    typ = str(base.get("Typ",""))

    hardhet = _hardhet_from(base, preview)
    out["Hårdhet"] = hardhet

    # Prenumeranter
    if "Vila" in typ or "Super bonus" in typ:
        pren = 0
    else:
        pren = ( int(base.get("DP",0)) + int(base.get("DPP",0)) + int(base.get("DAP",0)) +
                 int(base.get("TAP",0)) + int(preview.get("Totalt Män",0)) ) * hardhet
    out["Prenumeranter"] = int(pren)

    # Intäkter
    avg = float(base.get("Avgift", 0.0))
    out["Intäkter"] = float(pren) * avg

    # Intäkt Känner
    ksam = int(preview.get("Känner sammanlagt", 0))
    if ksam == 0:
        ksam = int(preview.get("Känner", 0))
    out["Intäkt Känner"] = float(ksam) * 30.0 if not ("Vila" in typ or "Super bonus" in typ) else 0.0

    # Kostnad män
    if "Vila" in typ or "Super bonus" in typ:
        kost = 0.0
    else:
        timmar = float(preview.get("Summa tid (sek)", 0)) / 3600.0
        bas_mann = int(base.get("Män",0)) + int(base.get("Svarta",0)) + int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0))
        tot_personer = bas_mann + int(CFG.get("PROD_STAFF",0))
        kost = timmar * tot_personer * 15.0
    out["Kostnad män"] = float(kost)

    # Intäkt företag, Lön, Vinst
    out["Intäkt företag"] = float(out["Intäkter"]) - float(out["Kostnad män"]) - float(out["Intäkt Känner"])

    # Åldersfaktor
    try:
        rad_dat = base["_rad_datum"]
        fd = base["_fodelsedatum"]
        alder = rad_dat.year - fd.year - ((rad_dat.month, rad_dat.day) < (fd.month, fd.day))
    except Exception:
        alder = 30
    grund_lon = max(150.0, min(800.0, 0.08 * float(out["Intäkt företag"])))
    if alder <= 18:
        faktor = 1.00
    elif 19 <= alder <= 23:
        faktor = 0.90
    elif 24 <= alder <= 27:
        faktor = 0.85
    elif 28 <= alder <= 30:
        faktor = 0.80
    elif 31 <= alder <= 32:
        faktor = 0.75
    elif 33 <= alder <= 35:
        faktor = 0.70
    else:
        faktor = 0.60
    lon = grund_lon * faktor
    if "Vila" in typ or "Super bonus" in typ:
        lon = 0.0
    out["Lön Malin"] = float(lon)
    out["Vinst"] = float(out["Intäkt företag"]) - float(out["Lön Malin"])
    return out

def _after_save_housekeeping(preview, is_vila: bool, is_superbonus: bool):
    """Uppdatera BONUS kvar och SUPER_BONUS_ACC enligt regeln."""
    CFG = st.session_state[CFG_KEY]
    pren = int(preview.get("Prenumeranter", 0))
    bonus_pct = float(CFG.get("BONUS_PCT", 1.0)) / 100.0
    sb_pct    = float(CFG.get("SUPER_BONUS_PCT", 0.1)) / 100.0

    add_bonus = 0 if (is_vila or is_superbonus) else int(pren * bonus_pct)
    add_super = 0 if (is_vila or is_superbonus) else int(pren * sb_pct)

    minus_bonus = int(preview.get("Bonus deltagit", 0))
    CFG[BONUS_LEFT_KEY] = max(0, int(CFG.get(BONUS_LEFT_KEY,0)) - minus_bonus + add_bonus)
    CFG[SUPER_ACC_KEY]  = max(0, int(CFG.get(SUPER_ACC_KEY,0)) + add_super)

# =========================
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()

# 1) Beräkna grund via berakningar.py
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# 2) Ekonomi & hårdhet i appen
econ = _econ_compute(base, preview)
preview.update(econ)

# 3) BMI – slump per ny prenumerant (12–18), ackumulerat historiskt
def _compute_bmi_pending_for_current_row(pren: int, scen_typ: str):
    if pren <= 0 or ("Vila" in scen_typ) or ("Super bonus" in scen_typ):
        return 0.0, 0
    s = 0.0
    # slumpa 'pren' BMI-värden i intervallet 12–18 och summera
    for _ in range(pren):
        s += random.uniform(12.0, 18.0)
    return s, pren

current_scene = st.session_state[SCENEINFO_KEY][0]
scen_typ = str(base.get("Typ",""))

pren_now = int(preview.get("Prenumeranter", 0))
pend_sum, pend_cnt = _compute_bmi_pending_for_current_row(pren_now, scen_typ)

# lägg på historik för att visa “BM mål” live
hist_sum = float(st.session_state.get(BMI_SUM_KEY, 0.0))
hist_cnt = int(st.session_state.get(BMI_CNT_KEY, 0))
total_sum = hist_sum + pend_sum
total_cnt = hist_cnt + pend_cnt
bmi_mean  = (total_sum / total_cnt) if total_cnt > 0 else 0.0

height_m = float(CFG.get("HEIGHT_CM", 164)) / 100.0
preview["BM mål"] = round(bmi_mean, 2)
preview["Mål vikt (kg)"] = round(bmi_mean * (height_m ** 2), 1)
preview["Super bonus ack"] = int(CFG.get(SUPER_ACC_KEY, 0))

# spara den “pendande” BMI-summan/räknaren i state, så spar-fasen kan addera samma sample
st.session_state[PENDING_BMI_KEY] = {"scene": current_scene, "sum": float(pend_sum), "count": int(pend_cnt)}

# Tid/kille inkl händer
tid_kille_sek = float(preview.get("Tid per kille (sek)", 0.0))
hander_kille_sek = float(preview.get("Händer per kille (sek)", 0.0))
def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds)))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"
tid_kille_inkl_hander = _mmss(tid_kille_sek + (hander_kille_sek if int(base.get("Händer aktiv",1))==1 else 0))

# Egen totalsiffra inkl källor/bonus/personal/Eskilstuna
tot_men_including = (
    int(base.get("Män",0)) + int(base.get("Svarta",0)) +
    int(base.get(CFG["LBL_PAPPAN"],0)) + int(base.get(CFG["LBL_GRANNAR"],0)) +
    int(base.get(CFG["LBL_NILS_VANNER"],0)) + int(base.get(CFG["LBL_NILS_FAMILJ"],0)) +
    int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0)) +
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
    _d = base["_rad_datum"] if isinstance(base["_rad_datum"], date) else datetime.today().date()

fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
top_line = st.columns([2,1,1,1])
with top_line[0]:
    st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")
with top_line[1]:
    st.metric("Klockan", preview.get("Klockan","-"))
with top_line[2]:
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))
with top_line[3]:
    st.metric("Super-bonus ack", int(CFG.get(SUPER_ACC_KEY,0)))

# Tid/Klocka/Män
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille","-"))
    st.metric("Tid/kille inkl händer", tid_kille_inkl_hander)
with c3:
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
    st.metric("Totalt män (inkl alla)", int(tot_men_including))

# Hångel/Sug/Händer
c4, c5, c6 = st.columns(3)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))
with c6:
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))
    st.metric("Klockan + älskar/sover", preview.get("Klockan inkl älskar/sover","-"))

# Ekonomi
st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter",0)))
    st.metric("Intäkter", f"${float(preview.get('Intäkter',0)):,.2f}")
with e2:
    st.metric("Kostnad män", f"${float(preview.get('Kostnad män',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner',0)):,.2f}")
with e3:
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
    st.metric("Bonus kvar", int(CFG.get(BONUS_LEFT_KEY,0)))

# BM mål / Mål vikt
mv1, mv2 = st.columns(2)
with mv1:
    st.metric("BM mål (BMI)", preview.get("BM mål", "-"))
with mv2:
    st.metric("Mål vikt (kg)", preview.get("Mål vikt (kg)", "-"))

st.caption("Obs: Vila-scenarion och Super bonus genererar inga prenumeranter, intäkter, kostnader eller lön. Bonus kvar minskas dock med 'Bonus deltagit'.")

# =========================
# Sparrad – full rad (base + preview) och nollställ None
# =========================
SAVE_NUM_COLS = [
    "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
    "Älskar","Sover med",
    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
    "Bonus deltagit","Personal deltagit","Händer aktiv","Nils"
]

def _prepare_row_for_save(_preview: dict, _base: dict, _cfg: dict) -> dict:
    row = dict(_base)   # börja med base (alla inmatningar)
    row.update(_preview)  # lägg på beräkningar
    # extra metadata
    row["Profil"] = st.session_state.get(PROFILE_KEY, "")
    row["BM mål"] = _preview.get("BM mål")
    row["Mål vikt (kg)"] = _preview.get("Mål vikt (kg)")
    row["Super bonus ack"] = _preview.get("Super bonus ack")

    # sanera None -> 0/"" så vi slipper 'None' i DF/Sheets
    for k in SAVE_NUM_COLS:
        if row.get(k) is None:
            row[k] = 0
    for k in ["Datum","Veckodag","Typ","Scen","Klockan","Klockan inkl älskar/sover"]:
        if row.get(k) is None:
            row[k] = ""
    return row

# =========================
# Spara lokalt & till Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        full_row = _prepare_row_for_save(preview, base, CFG)
        st.session_state[ROWS_KEY].append(full_row)

        # >>> Frys in BMI-samplet i historiken
        pend = st.session_state.get(PENDING_BMI_KEY, {"scene": None, "sum": 0.0, "count": 0})
        st.session_state[BMI_SUM_KEY] = float(st.session_state.get(BMI_SUM_KEY, 0.0)) + float(pend.get("sum", 0.0))
        st.session_state[BMI_CNT_KEY] = int(st.session_state.get(BMI_CNT_KEY, 0)) + int(pend.get("count", 0))
        st.session_state[PENDING_BMI_KEY] = {"scene": None, "sum": 0.0, "count": 0}

        # uppdatera min/max (för slump)
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
            v = int(full_row.get(col,0))
            _add_hist_value(col, v)
        # justera Bonus/ Superbonus
        scen_typ = str(base.get("Typ",""))
        is_vila  = "Vila" in scen_typ
        is_super = "Super bonus" in scen_typ
        _after_save_housekeeping(full_row, is_vila=is_vila, is_superbonus=is_super)
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad lokalt.")

def _save_to_sheets_for_profile(profile: str, row_dict: dict):
    append_row_to_profile_data(profile, row_dict)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            full_row = _prepare_row_for_save(preview, base, CFG)

            # >>> Frys in BMI-samplet i historiken (samma sample som i live)
            pend = st.session_state.get(PENDING_BMI_KEY, {"scene": None, "sum": 0.0, "count": 0})
            st.session_state[BMI_SUM_KEY] = float(st.session_state.get(BMI_SUM_KEY, 0.0)) + float(pend.get("sum", 0.0))
            st.session_state[BMI_CNT_KEY] = int(st.session_state.get(BMI_CNT_KEY, 0)) + int(pend.get("count", 0))
            st.session_state[PENDING_BMI_KEY] = {"scene": None, "sum": 0.0, "count": 0}

            _save_to_sheets_for_profile(st.session_state.get(PROFILE_KEY,""), full_row)

            # spegla lokalt
            st.session_state[ROWS_KEY].append(full_row)
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
                v = int(full_row.get(col,0))
                _add_hist_value(col, v)

            scen_typ = str(base.get("Typ",""))
            is_vila  = "Vila" in scen_typ
            is_super = "Super bonus" in scen_typ
            _after_save_housekeeping(full_row, is_vila=is_vila, is_superbonus=is_super)

            st.session_state[SCENEINFO_KEY] = _current_scene_info()
            st.success("✅ Sparad till Google Sheets.")
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Visa lokala rader + Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")

if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=340)
else:
    st.info("Inga lokala rader ännu.")

# (valfri) Statistik
if _HAS_STATS:
    try:
        st.markdown("---")
        st.subheader("📊 Statistik")
        rows_df = pd.DataFrame(st.session_state[ROWS_KEY]) if st.session_state[ROWS_KEY] else pd.DataFrame()
        # stöd både compute_stats(rows) och compute_stats(rows, cfg)
        if "cfg" in compute_stats.__code__.co_varnames or compute_stats.__code__.co_argcount >= 2:
            stats = compute_stats(rows_df, CFG)
        else:
            stats = compute_stats(rows_df)
        if isinstance(stats, dict) and stats:
            for k,v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.caption("Statistik-modulen returnerade inget att visa ännu.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
