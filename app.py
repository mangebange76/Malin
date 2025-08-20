# app.py
import streamlit as st
import pandas as pd
import datetime
import random
import json

# ========== Moduler ==========
from berakningar import calc_row_values
from statistik import compute_stats
import sheets_utils as su
from live_ui import fmt_money
# (valfritt)
# import statistik_affar as saff
# import statistik_relation as srel


# ========== App-ram ==========
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets + live)")

# --------- State-nycklar ----------
CFG_KEY        = "CFG"
ROWS_KEY       = "ROWS"
HIST_MM_KEY    = "HIST_MINMAX"
SCENEINFO_KEY  = "CURRENT_SCENE"
SCENARIO_KEY   = "SCENARIO"
PROFILE_LIST   = "PROFILE_LIST"
PROFILE_NAME   = "PROFILE_NAME"


# ========== Hjälp ==========
def _current_scene_info():
    """(scen_nr, datum, veckodag)"""
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d0 = st.session_state[CFG_KEY]["startdatum"]
    d  = d0 + datetime.timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def _init_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            # Start & person
            "startdatum":   datetime.date(1990,1,1),
            "starttid":     datetime.time(7,0),
            "fodelsedatum": datetime.date(1970,1,1),
            # Ekonomi
            "avgift_usd": 30.0,
            "PROD_STAFF": 800,
            # Bonus-system
            "BONUS_AVAILABLE": 0,
            "BONUS_PCT": 0.01,   # 1% default av prenumeranter → “bonus killar”
            # Eskilstuna-intervall
            "ESK_MIN": 20, "ESK_MAX": 40,
            # Maxvärden
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
            # Etiketter
            "LBL_PAPPAN":"Pappans vänner", "LBL_GRANNAR":"Grannar",
            "LBL_NILS_VANNER":"Nils vänner", "LBL_NILS_FAMILJ":"Nils familj",
            "LBL_BEKANTA":"Bekanta", "LBL_ESK":"Eskilstuna killar",
        }
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if PROFILE_LIST not in st.session_state:
        st.session_state[PROFILE_LIST] = []
    if PROFILE_NAME not in st.session_state:
        st.session_state[PROFILE_NAME] = ""
    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

_init_state()

def _add_hist_value(col, v):
    try:
        v = int(float(v))
    except Exception:
        v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if not mm:
        st.session_state[HIST_MM_KEY][col] = (v, v)
    else:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn, v), max(mx, v))

def _rebuild_hist_from_rows(cfg, rows_list):
    st.session_state[HIST_MM_KEY] = {}
    if not rows_list:
        return
    lbls = [
        cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"],
        cfg["LBL_NILS_FAMILJ"], cfg["LBL_BEKANTA"], cfg["LBL_ESK"],
    ]
    for r in rows_list:
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP", *lbls]:
            if col in r:
                _add_hist_value(col, r.get(col, 0))

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    # fallback 0..0
    st.session_state[HIST_MM_KEY][colname] = (0,0)
    return (0,0)

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo:
        hi = lo
    return random.randint(lo, hi) if hi > lo else lo


# ---------- Input-ordning ----------
INPUT_ORDER = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_hander_on",   # NYTT – Händer aktiv (0/1)
    "in_nils"
]


# ========== SIDOPANEL ==========
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if 'GOOGLE_CREDENTIALS' in st.secrets else '❌'}  •  SHEET_URL: {'✅' if 'SHEET_URL' in st.secrets else '❌'}")

    if st.button("🔄 Uppdatera profiler"):
        st.session_state[PROFILE_LIST] = su.list_profiles()
        st.success("Profiler uppdaterade.")

    prof_list = st.session_state[PROFILE_LIST] or ["— inga profiler funna —"]
    idx = 0
    if st.session_state[PROFILE_NAME] and st.session_state[PROFILE_NAME] in prof_list:
        idx = prof_list.index(st.session_state[PROFILE_NAME])
    sel = st.selectbox("Välj profil (från flik 'Profil')", prof_list, index=idx)
    if sel != "— inga profiler funna —":
        st.session_state[PROFILE_NAME] = sel

    colp1, colp2 = st.columns(2)
    with colp1:
        if st.button("📥 Läs in profil"):
            name = st.session_state[PROFILE_NAME]
            if not name:
                st.warning("Välj en profil först.")
            else:
                cfg_patch = su.load_profile_cfg(name)
                # typa kända datum/tid
                if "startdatum" in cfg_patch and isinstance(cfg_patch["startdatum"], str):
                    try:
                        y,m,d = [int(x) for x in cfg_patch["startdatum"].split("-")]
                        cfg_patch["startdatum"] = datetime.date(y,m,d)
                    except:
                        cfg_patch.pop("startdatum", None)
                if "fodelsedatum" in cfg_patch and isinstance(cfg_patch["fodelsedatum"], str):
                    try:
                        y,m,d = [int(x) for x in cfg_patch["fodelsedatum"].split("-")]
                        cfg_patch["fodelsedatum"] = datetime.date(y,m,d)
                    except:
                        cfg_patch.pop("fodelsedatum", None)
                # slå in i CFG
                st.session_state[CFG_KEY].update(cfg_patch)
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"Profil '{name}' inläst.")
    with colp2:
        if st.button("📑 Läs in profilens Data"):
            name = st.session_state[PROFILE_NAME]
            if not name:
                st.warning("Välj en profil först.")
            else:
                df = su.load_profile_rows(name, st.session_state[CFG_KEY])
                st.session_state[ROWS_KEY] = df.to_dict("records") if not df.empty else []
                _rebuild_hist_from_rows(st.session_state[CFG_KEY], st.session_state[ROWS_KEY])
                st.session_state[SCENEINFO_KEY] = _current_scene_info()
                st.success(f"Läste {len(st.session_state[ROWS_KEY])} rader från 'Data' för '{name}'.")

    st.markdown("---")
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    CFG["BONUS_PCT"]    = st.number_input("Bonus % av prenumeranter → killar", min_value=0.0, max_value=1.0, step=0.005, value=float(CFG["BONUS_PCT"]))
    st.markdown(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=int(CFG["ESK_MIN"]), value=int(CFG["ESK_MAX"]), step=1)

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
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet"].index(st.session_state[SCENARIO_KEY])
    )

    if st.button("⬇️ Hämta värden"):
        # nolla (behåll tidsstandarder och händer-on)
        keep = {"in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3, "in_hander_on":1}
        for k in INPUT_ORDER:
            st.session_state[k] = keep.get(k, 0)

        s = st.session_state[SCENARIO_KEY]
        LBLS = [CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"], CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]

        # Slump-funktion som tar höjd för historik per fält
        def _slump_fields(names):
            for nm in names:
                st.session_state[nm] = _rand_hist(labels_to_hist_key(nm, LBLS))

        def labels_to_hist_key(inp_key, lbls):
            # mappar input-key -> kolumnnamn
            mapping = {
                "in_man":"Män","in_svarta":"Svarta","in_fitta":"Fitta","in_rumpa":"Rumpa",
                "in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
                "in_pappan":lbls[0],"in_grannar":lbls[1],"in_nils_vanner":lbls[2],
                "in_nils_familj":lbls[3],"in_bekanta":lbls[4],"in_eskilstuna":lbls[5],
            }
            return mapping.get(inp_key, inp_key)

        if s == "Slumpa scen vit":
            _slump_fields(["in_man","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"])
            _slump_fields(["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"])
            st.session_state["in_svarta"] = 0
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1

        elif s == "Slumpa scen svart":
            _slump_fields(["in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"])
            st.session_state["in_alskar"] = 8
            st.session_state["in_sover"]  = 1

        elif s == "Vila på jobbet":
            _slump_fields(["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap"])
            _slump_fields(["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"])
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 12
            st.session_state["in_sover"]  = 1
            # 0 pren/0 intäkter hanteras inte här utan i beräkningar via dina inputs

        elif s == "Vila i hemmet":
            _slump_fields(["in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
                           "in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta"])
            st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
            st.session_state["in_alskar"] = 6
            st.session_state["in_sover"]  = 0
            st.session_state["in_nils"]   = 0

        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Google Sheets")
    cgs1, cgs2 = st.columns(2)
    with cgs1:
        if st.button("💾 Spara inställningar till Sheets"):
            try:
                su.save_settings(st.session_state[CFG_KEY])
                st.success("Inställningar sparade.")
            except Exception as e:
                st.error(f"Misslyckades att spara inställningar: {e}")
    with cgs2:
        st.caption("Profilens data läses via knappen ovan: **Läs in profilens Data**")

# ========== INPUTSEKTION ==========
st.subheader("Input (exakt ordning)")
c1, c2 = st.columns(2)

LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]; LBL_NV = CFG["LBL_NILS_VANNER"]
LBL_NF = CFG["LBL_NILS_FAMILJ"]; LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

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
    "in_hander_on":"Händer aktiv (0/1)",
    "in_nils":"Nils (0/1/2)"
}

# init defaults om saknas
defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_alskar":0,"in_sover":0,"in_hander_on":1,"in_nils":0}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

with c1:
    for key in ["in_man","in_svarta","in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap","in_tid_s","in_tid_d","in_vila"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

with c2:
    for key in ["in_dt_tid","in_dt_vila","in_alskar"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_sover"], min_value=0, max_value=1, step=1, key="in_sover")
    for key in ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_eskilstuna","in_bonus_deltagit","in_personal_deltagit","in_nils"]:
        st.number_input(labels[key], min_value=0, step=1, key=key)
    st.number_input(labels["in_hander_on"], min_value=0, max_value=1, step=1, key="in_hander_on")


# ========== Bygg bas & live ==========
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Profil": st.session_state.get(PROFILE_NAME, ""),
        "Datum": d.isoformat(), "Veckodag": veckodag, "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        # inputs
        "Män": st.session_state["in_man"], "Svarta": st.session_state["in_svarta"],
        "Fitta": st.session_state["in_fitta"], "Rumpa": st.session_state["in_rumpa"],
        "DP": st.session_state["in_dp"], "DPP": st.session_state["in_dpp"], "DAP": st.session_state["in_dap"], "TAP": st.session_state["in_tap"],

        "Tid S": st.session_state["in_tid_s"], "Tid D": st.session_state["in_tid_d"], "Vila": st.session_state["in_vila"],
        "DT tid (sek/kille)": st.session_state["in_dt_tid"], "DT vila (sek/kille)": st.session_state["in_dt_vila"],
        "Älskar": st.session_state["in_alskar"], "Sover med": st.session_state["in_sover"],

        LBL_PAPPAN: st.session_state["in_pappan"], LBL_GRANNAR: st.session_state["in_grannar"],
        LBL_NV: st.session_state["in_nils_vanner"], LBL_NF: st.session_state["in_nils_familj"],
        LBL_BEK: st.session_state["in_bekanta"], LBL_ESK: st.session_state["in_eskilstuna"],

        "Bonus deltagit": st.session_state["in_bonus_deltagit"], "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv": st.session_state["in_hander_on"],

        "Nils": st.session_state["in_nils"],

        # config
        "Avgift": float(CFG["avgift_usd"]), "PROD_STAFF": int(CFG["PROD_STAFF"]),
        "LBL_PAPPAN": LBL_PAPPAN, "LBL_GRANNAR": LBL_GRANNAR, "LBL_NILS_VANNER": LBL_NV, "LBL_NILS_FAMILJ": LBL_NF,
        "LBL_BEKANTA": LBL_BEK, "LBL_ESK": LBL_ESK,

        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]), "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]), "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
    }
    # Känner
    base["Känner"] = int(base[LBL_PAPPAN]) + int(base[LBL_GRANNAR]) + int(base[LBL_NV]) + int(base[LBL_NF])

    # meta till calc
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = CFG["starttid"]
    return base

st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])

# Ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag  = preview.get("Veckodag", "-")
try:
    _d = datetime.date.fromisoformat(rad_datum)
except Exception:
    _d = datetime.date.today()
fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

# Ramar
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", preview.get("Tid per kille","-"))
    st.metric("Tid/kille (sek)", int(preview.get("Tid per kille (sek)",0)))
with c3:
    st.metric("Klockan", preview.get("Klockan","-"))
    st.metric("Totalt Män", int(preview.get("Totalt Män",0)))

c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))

st.metric("Tid/kille inkl händer", preview.get("Tid/kille inkl händer", "-"))

st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(preview.get("Hårdhet",0)))
with e2:
    st.metric("Intäkter", fmt_money(preview.get("Intäkter",0)))
    st.metric("Intäkt Känner", fmt_money(preview.get("Intäkt Känner",0)))
with e3:
    st.metric("Kostnad män", fmt_money(preview.get("Kostnad män",0)))
    st.metric("Lön Malin", fmt_money(preview.get("Lön Malin",0)))
with e4:
    st.metric("Intäkt företag", fmt_money(preview.get("Intäkt företag",0)))
    st.metric("Vinst", fmt_money(preview.get("Vinst",0)))

st.caption("Obs: Älskar/Sover med räknas separat till ”Klockan inkl älskar/sover” och ingår ej i 'Summa tid'.")


# ========== Spara ==========
st.markdown("---")
cL, cR = st.columns(2)

def _bonus_created(preview_row, cfg):
    try:
        pct = float(cfg.get("BONUS_PCT", 0.01))
        return int(round(float(preview_row.get("Prenumeranter",0)) * pct))
    except Exception:
        return 0

def _row_for_saving(base, preview):
    """Mergear bas + preview och lägger till bonusfält."""
    row = {}
    row.update(base)
    row.update(preview)
    row["Profil"] = st.session_state.get(PROFILE_NAME, "")
    row["Bonus skapade"] = _bonus_created(preview, CFG)
    row["Bonus kvar efter"] = int(CFG["BONUS_AVAILABLE"]) + row["Bonus skapade"] - int(base.get("Bonus deltagit",0))
    return row

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        to_save = _row_for_saving(build_base_from_inputs(), preview)

        # uppdatera bonus-kvar
        CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + int(to_save["Bonus skapade"]) - int(base.get("Bonus deltagit",0)))

        # lägg till lokalt
        st.session_state[ROWS_KEY].append(to_save)

        # uppdatera histogram
        _rebuild_hist_from_rows(CFG, st.session_state[ROWS_KEY])

        # bumpa sceninfo
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad lokalt.")

def _save_to_google(row_dict: dict):
    su.append_row_to_data(row_dict)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            to_save = _row_for_saving(build_base_from_inputs(), preview)

            # bonus kvar
            CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + int(to_save["Bonus skapade"]) - int(base.get("Bonus deltagit",0)))

            _save_to_google(to_save)

            # spegla lokalt
            st.session_state[ROWS_KEY].append(to_save)
            _rebuild_hist_from_rows(CFG, st.session_state[ROWS_KEY])
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
            st.success("✅ Sparad till Google Sheets (flik: Data).")
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")


# ========== Visa lokala rader ==========
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df_local = pd.DataFrame(st.session_state[ROWS_KEY])
    # Visa några nyckelkolumner först (orden är valfria — pandastabellen är scrollbar)
    st.dataframe(df_local, use_container_width=True, height=340)
else:
    st.info("Inga lokala rader ännu.")


# ========== Statistik ==========
st.markdown("---")
st.subheader("📊 Statistik")
try:
    rows_df = pd.DataFrame(st.session_state[ROWS_KEY]) if st.session_state[ROWS_KEY] else pd.DataFrame()
    stats = compute_stats(rows_df, CFG)
    if not stats:
        st.info("Ingen data att visa statistik för ännu.")
    else:
        for k, v in stats.items():
            st.write(f"**{k}:** {v}")
except Exception as e:
    st.error(f"Kunde inte beräkna statistik: {e}")

# (valfri detaljerad affär/relations-statistik)
# if not rows_df.empty:
#     st.markdown("#### 📈 Affärsstatistik (extra)")
#     st.write(saff.compute(rows_df, CFG))
#     st.markdown("#### 👥 Relationsstatistik (extra)")
#     st.write(srel.compute(rows_df, CFG))
