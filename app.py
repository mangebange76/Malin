# app.py
import streamlit as st
import random
import json
import pandas as pd
from datetime import date, time, datetime, timedelta

from berakningar import calc_row_values
from statistik import compute_stats
import sheets_utils as su

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (Profiler + Google Sheets)")

# ======== State-nycklar ========
CFG_KEY       = "CFG"           # alla config + etiketter + bonus/superbonus
PROFILE_KEY   = "PROFILE_NAME"
ROWS_KEY      = "ROWS"          # lokalt cache av rader (för live + hist)
HIST_MM_KEY   = "HIST_MINMAX"   # min/max per fält
SCENEINFO_KEY = "CURRENT_SCENE" # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY  = "SCENARIO"      # rullist-valet

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
    "in_hander",  # <— NYTT (0/1)
    "in_nils",
]

# =========================
# Init state
# =========================
def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # datum/avgifter/bemanning
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,

            # Bonus (decimal-procent). 0.01 = 1 %
            "BONUS_PCT": 0.01,
            "BONUS_AVAILABLE": 0,

            # Super bonus (decimal-procent). 0.001 = 0.1 %
            "SUPER_BONUS_PCT": 0.001,
            "SUPER_BONUS_TOTAL": 0,

            # Esk-intervall
            "ESK_MIN": 20, "ESK_MAX": 40,

            # Maxvärden (källor)
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,

            # Etiketter
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",
        }
    if PROFILE_KEY not in st.session_state:
        # försök läsa första profilen
        profiles = su.list_profiles()
        st.session_state[PROFILE_KEY] = profiles[0] if profiles else "Standard"

    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    # defaults inputs
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander":1
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

CFG = st.session_state[CFG_KEY]

# =========================
# Hjälpare: min/max + slump
# =========================
def _add_hist_value(col, v):
    try:
        v = int(v)
    except:
        v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn,v), max(mx,v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: 
        return mm
    # bygg från redan inlästa rader
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try:
            vals.append(int(r.get(colname, 0)))
        except:
            pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_upto_max(colname: str):
    """Slump 1..max (om max>0), annars 0."""
    _, hi = _minmax_from_hist(colname)
    return random.randint(1, hi) if hi > 0 else 0

# =========================
# Profiler (sidhuvud)
# =========================
with st.sidebar:
    st.subheader("Profil")
    profiles = su.list_profiles()
    sel = st.selectbox("Välj profil", profiles or ["Standard"], index=0 if not profiles else max(0, profiles.index(st.session_state[PROFILE_KEY]) if st.session_state[PROFILE_KEY] in profiles else 0))
    st.session_state[PROFILE_KEY] = sel

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 Läs in inställningar"):
            cfg_in = su.load_profile_config(sel)
            if cfg_in:
                # slå ihop – behåll okända nycklar också
                st.session_state[CFG_KEY].update(cfg_in)
                st.success(f"Inställningar inlästa för {sel}.")
    with c2:
        if st.button("📥 Läs in data"):
            rows = su.load_profile_rows(sel)
            st.session_state[ROWS_KEY] = rows
            # bygg hist av alla relevanta kolumner
            st.session_state[HIST_MM_KEY] = {}
            for r in rows:
                for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                            CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                    _add_hist_value(col, r.get(col, 0))
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
            st.success(f"{len(rows)} rader inlästa från Data_{sel}.")

# =========================
# Sidopanel – Inställningar
# =========================
with st.sidebar:
    st.header("Inställningar")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=0.5)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown("---")
    st.subheader("Bonus & Super bonus")
    CFG["BONUS_PCT"] = st.number_input("Bonus procent (decimal, t.ex. 0.5% = 0.005)", min_value=0.0, value=float(CFG.get("BONUS_PCT",0.01)), step=0.0005, format="%.4f")
    st.caption("Nya bonus-killar = Prenumeranter × BONUS_PCT (avrundat).")
    CFG["BONUS_AVAILABLE"] = st.number_input("Bonus killar kvar (manuell justering)", min_value=0, value=int(CFG.get("BONUS_AVAILABLE",0)), step=1)

    CFG["SUPER_BONUS_PCT"] = st.number_input("Super bonus andel (decimal, ex 0.1% = 0.001)", min_value=0.0, value=float(CFG.get("SUPER_BONUS_PCT",0.001)), step=0.0005, format="%.4f")
    st.caption("Ackumuleras: super bonus += Prenumeranter × SUPER_BONUS_PCT (avrundat).")
    st.write(f"**Super bonus (ack)**: {int(CFG.get('SUPER_BONUS_TOTAL',0))}")

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
    st.subheader("Egna etiketter")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG["LBL_ESK"])

    st.markdown("---")
    st.subheader("Google Sheets")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    c3, c4 = st.columns(2)
    with c3:
        if st.button("💾 Spara inställningar → profil"):
            su.save_profile_config(st.session_state[PROFILE_KEY], st.session_state[CFG_KEY])
            st.success("Inställningar sparade.")
    with c4:
        if st.button("↺ Bygg om min/max från laddade rader"):
            st.session_state[HIST_MM_KEY] = {}
            for r in st.session_state[ROWS_KEY]:
                for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                            CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                    _add_hist_value(col, r.get(col, 0))
            st.success("Min/max uppdaterat.")

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)","Super bonus"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)","Super bonus"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        s = st.session_state[SCENARIO_KEY]
        # nolla (behåll tidsstandarder)
        keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander":1}
        for k in INPUT_ORDER:
            st.session_state[k] = keep_defaults.get(k, 0)

        if s == "Slumpa scen vit":
            st.session_state["in_svarta"] = 0
            st.session_state["in_man"]    = _rand_upto_max("Män")
            for f,k in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[k] = _rand_upto_max(f)
            for f,k in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                        (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                        (CFG["LBL_BEKANTA"],"in_bekanta")]:
                st.session_state[k] = _rand_upto_max(f)
            st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1

        elif s == "Slumpa scen svart":
            st.session_state["in_svarta"] = _rand_upto_max("Svarta")
            for f,k in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[k] = _rand_upto_max(f)
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1

        elif s == "Vila på jobbet":
            for f,k in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[k] = _rand_upto_max(f)
            for f,k in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_BEKANTA"],"in_bekanta"),
                        (CFG["LBL_GRANNAR"],"in_grannar"),(CFG["LBL_NILS_VANNER"],"in_nils_vanner"),
                        (CFG["LBL_NILS_FAMILJ"],"in_nils_familj")]:
                st.session_state[k] = _rand_upto_max(f)
            st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1

        elif s == "Vila i hemmet (dag 1–7)":
            for f,k in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
                st.session_state[k] = _rand_upto_max(f)
            for f,k in [(CFG["LBL_PAPPAN"],"in_pappan"),(CFG["LBL_GRANNAR"],"in_grannar"),
                        (CFG["LBL_NILS_VANNER"],"in_nils_vanner"),(CFG["LBL_NILS_FAMILJ"],"in_nils_familj"),
                        (CFG["LBL_BEKANTA"],"in_bekanta")]:
                st.session_state[k] = _rand_upto_max(f)
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 0
            st.session_state["in_nils"]   = 0

        elif s == "Super bonus":
            # lägg HELA ackumulerade super bonus-värdet i Svarta
            st.session_state["in_svarta"] = int(CFG.get("SUPER_BONUS_TOTAL", 0))

        st.experimental_rerun()

# =========================
# Inmatning (UI)
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
    "in_hander":"Händer aktiv (0/1)",
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
        "in_hander","in_nils"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs():
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

        CFG["LBL_PAPPAN"]:   st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]:  st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]:  st.session_state["in_bekanta"],
        CFG["LBL_ESK"]:      st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv": st.session_state["in_hander"],
        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),

        # skicka med max/etiketter (för beräkning + export)
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]), "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]), "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
        "LBL_PAPPAN": CFG["LBL_PAPPAN"], "LBL_GRANNAR": CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER": CFG["LBL_NILS_VANNER"], "LBL_NILS_FAMILJ": CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": CFG["LBL_BEKANTA"], "LBL_ESK": CFG["LBL_ESK"],
    }
    # meta till beräkning
    base["_rad_datum"]    = st.session_state[SCENEINFO_KEY][1]
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

# =========================
# Live/Preview
# =========================
st.markdown("---")
st.subheader("🔎 Live")

_base = build_base_from_inputs()
preview = calc_row_values(_base, _base["_rad_datum"], _base["_fodelsedatum"], _base["_starttid"])

# Datum/ålder
rad_datum = preview.get("Datum", _base["Datum"])
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
    st.metric("Totalt män (beräkningar)", int(preview.get("Totalt Män",0)))

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
    st.metric("Händer aktiv", int(preview.get("Händer aktiv", 0)))

# Ekonomi + Super bonus
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
    st.metric("Super bonus (ack)", int(CFG.get("SUPER_BONUS_TOTAL",0)))
    st.metric("Super bonus andel", f"{float(CFG.get('SUPER_BONUS_PCT',0.001))*100:.3f}%")

# Källor
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(CFG["LBL_PAPPAN"], int(_base.get(CFG["LBL_PAPPAN"],0)))
with k2: st.metric(CFG["LBL_GRANNAR"], int(_base.get(CFG["LBL_GRANNAR"],0)))
with k3: st.metric(CFG["LBL_NILS_VANNER"], int(_base.get(CFG["LBL_NILS_VANNER"],0)))
with k4: st.metric(CFG["LBL_NILS_FAMILJ"], int(_base.get(CFG["LBL_NILS_FAMILJ"],0)))
with k5: st.metric(CFG["LBL_BEKANTA"], int(_base.get(CFG["LBL_BEKANTA"],0)))
with k6: st.metric(CFG["LBL_ESK"], int(_base.get(CFG["LBL_ESK"],0)))

# =========================
# Spara lokalt & till Google Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _after_save_housekeeping(preview_row: dict):
    """Min/max + bonusuppdatering (BONUS_AVAILABLE och SUPER_BONUS_TOTAL) + bump sceninfo."""
    # uppdatera min/max
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
        _add_hist_value(col, preview_row.get(col, 0))

    # Bonus logik:
    scen_typ = str(preview_row.get("Typ","")).lower()
    pren = int(preview_row.get("Prenumeranter",0))
    bonus_deltagit = int(preview_row.get("Bonus deltagit",0))
    # ny bonus från prenumeranter (endast om ej 'vila')
    ny_bonus = 0 if scen_typ.startswith("vila") else int(round(pren * float(CFG.get("BONUS_PCT",0.01))))
    CFG["BONUS_AVAILABLE"] = max(0, int(CFG.get("BONUS_AVAILABLE",0)) - bonus_deltagit + ny_bonus)

    # Super bonus upp
    ny_super = 0 if scen_typ.startswith("vila") else int(round(pren * float(CFG.get("SUPER_BONUS_PCT",0.001))))
    CFG["SUPER_BONUS_TOTAL"] = int(CFG.get("SUPER_BONUS_TOTAL", 0)) + ny_super

    # bump sceninfo
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        # gör en JSON-safe rad (inga None)
        safe_row = {k:(0 if v is None else v) for k,v in preview.items()}
        st.session_state[ROWS_KEY].append(safe_row)
        _after_save_housekeeping(safe_row)
        st.success("✅ Sparad i minnet.")

def _save_to_profile_sheets(row_dict: dict):
    # Lägg till profilnamn i raden så det syns i data
    row_dict = dict(row_dict)
    row_dict["Profil"] = st.session_state[PROFILE_KEY]
    su.append_profile_row(st.session_state[PROFILE_KEY], row_dict)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            safe_row = {k:(0 if v is None else v) for k,v in preview.items()}
            _save_to_profile_sheets(safe_row)
            # spegla lokalt
            st.session_state[ROWS_KEY].append(safe_row)
            _after_save_housekeeping(safe_row)
            st.success(f"✅ Sparad till Data_{st.session_state[PROFILE_KEY]}.")
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
try:
    rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
    stats = compute_stats(rows_df, CFG)
    if stats:
        for k,v in stats.items():
            st.write(f"**{k}**: {v}")
    else:
        st.info("Ingen statistik ännu.")
except Exception as e:
    st.error(f"Kunde inte beräkna statistik: {e}")
