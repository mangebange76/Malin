# app.py
import streamlit as st
import json
from datetime import date, time, datetime, timedelta
import pandas as pd
import random

# ==== App ====
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Google Sheets)")

# ==== Importera moduler ====
try:
    import sheets_utils as su          # vår util för Sheets (per-profil)
    from berakningar import calc_row_values
    from statistik import compute_stats
except Exception as e:
    st.error(f"Kunde inte importera moduler: {e}")
    st.stop()

# ==== State-nycklar ====
CFG_KEY        = "CFG"
ROWS_KEY       = "ROWS"
HIST_MM_KEY    = "HIST_MINMAX"
SCENEINFO_KEY  = "CURRENT_SCENE"
SCENARIO_KEY   = "SCENARIO"
PROFILE_KEY    = "ACTIVE_PROFILE"  # valt prof-namn i sidopanelen

# ==== Input-ordning (exakt) ====
INPUT_ORDER = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover",
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_hander",           # NYTT: Händer aktiv (0/1)
    "in_nils"
]

def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + timedelta(days=nr-1)
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return (nr, d, veckodagar[d.weekday()])

def _ensure_state():
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = {
            "startdatum":   date(1990,1,1),
            "starttid":     time(7,0),
            "fodelsedatum": date(1970,1,1),
            "avgift_usd":   30.0,
            "PROD_STAFF":   800,
            "BONUS_AVAILABLE": 500,
            "BONUS_PERCENT": 1.0,       # % av prenumeranter som blir bonus-killar
            "ESK_MIN": 20, "ESK_MAX": 40,
            "MAX_PAPPAN": 100, "MAX_GRANNAR": 100,
            "MAX_NILS_VANNER": 100, "MAX_NILS_FAMILJ": 100,
            "MAX_BEKANTA": 100,
            "LBL_PAPPAN": "Pappans vänner",
            "LBL_GRANNAR": "Grannar",
            "LBL_NILS_VANNER": "Nils vänner",
            "LBL_NILS_FAMILJ": "Nils familj",
            "LBL_BEKANTA": "Bekanta",
            "LBL_ESK": "Eskilstuna killar",
        }
    st.session_state.setdefault(ROWS_KEY, [])
    st.session_state.setdefault(HIST_MM_KEY, {})
    st.session_state.setdefault(SCENARIO_KEY, "Ny scen")
    st.session_state.setdefault(PROFILE_KEY, "")
    # defaults för inputs
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander":1
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))
    st.session_state.setdefault(SCENEINFO_KEY, _current_scene_info())

_ensure_state()

# ==== Hjälpare min/max + slump ====
def _add_hist_value(col, v):
    try: v = int(v)
    except: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm:
        mn, mx = mm
        st.session_state[HIST_MM_KEY][col] = (min(mn, v), max(mx, v))
    else:
        st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(r.get(colname, 0)))
        except: pass
    if vals: mm = (min(vals), max(vals))
    else: mm = (0, 0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# ==== Scenario-fill ====
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander":1}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    # Slump per dina regler – alltid via histogram min/max
    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Bekanta","in_bekanta"),
                      ("Grannar","in_grannar"),("Nils vänner","in_nils_vanner"),
                      ("Nils familj","in_nils_familj")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1

    elif s == "Vila i hemmet (dag 1–7)":
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),
                      ("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]:
            st.session_state[key] = _rand_hist(f)
        for f,key in [("Pappans vänner","in_pappan"),("Grannar","in_grannar"),
                      ("Nils vänner","in_nils_vanner"),("Nils familj","in_nils_familj"),
                      ("Bekanta","in_bekanta")]:
            st.session_state[key] = _rand_hist(f)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# ==== Sidopanel ====
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    # refresh lista
    if st.button("🔄 Uppdatera profiler"):
        st.session_state["__profiles__"] = su.get_profile_names()
        st.success("Profiler uppdaterade.")
    profiles = st.session_state.get("__profiles__", su.get_profile_names())
    prof = st.selectbox("Välj profil (från flik 'Profil')", [""] + profiles, index=0 if st.session_state.get(PROFILE_KEY,"")=="" else ([""]+profiles).index(st.session_state.get(PROFILE_KEY,"")))
    st.session_state[PROFILE_KEY] = prof

    colp1, colp2 = st.columns(2)
    with colp1:
        if st.button("📥 Läs in profil (inställningar)"):
            if not prof:
                st.warning("Välj först en profil.")
            else:
                try:
                    cfg_in = su.load_profile_config(prof)
                    # applicera på CFG (bevara saknade nycklar)
                    for k,v in cfg_in.items():
                        if k in ("startdatum","fodelsedatum"):
                            try:
                                y,m,d = [int(x) for x in str(v).split("-")]
                                CFG[k] = date(y,m,d)
                            except:
                                pass
                        elif k == "starttid":
                            try:
                                hh,mm = [int(x) for x in str(v).split(":")[:2]]
                                CFG["starttid"] = time(hh,mm)
                            except:
                                pass
                        else:
                            CFG[k] = v
                    st.success(f"✅ Inställningar laddade för {prof}.")
                except Exception as e:
                    st.error(f"Kunde inte läsa profil: {e}")
    with colp2:
        if st.button("📑 Läs in profilens Data"):
            if not prof:
                st.warning("Välj först en profil.")
            else:
                try:
                    df = su.load_profile_rows(prof)
                    st.session_state[ROWS_KEY] = df.to_dict("records") if not df.empty else []
                    st.session_state[HIST_MM_KEY] = {}
                    for r in st.session_state[ROWS_KEY]:
                        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                                    CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"],
                                    CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
                            _add_hist_value(col, r.get(col, 0))
                    st.session_state[SCENEINFO_KEY] = _current_scene_info()
                    st.success(f"✅ Läste {len(st.session_state[ROWS_KEY])} rader från {su.data_title_for(prof)}.")
                except Exception as e:
                    st.error(f"Kunde inte läsa profilens data: {e}")

    st.markdown("---")
    st.subheader("Aktiv profil:")
    st.write(prof if prof else "— ingen vald —")

    st.markdown("---")
    st.header("Inställningar (lokalt)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["BONUS_PERCENT"]= st.number_input("Bonus % från prenumeranter", min_value=0.0, value=float(CFG["BONUS_PERCENT"]), step=0.1)
    st.markdown(f"**Bonus killar kvar:** {int(CFG['BONUS_AVAILABLE'])}")

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG["ESK_MIN"]), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=int(CFG["ESK_MIN"]), value=int(CFG["ESK_MAX"]), step=1)

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
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden"):
        apply_scenario_fill()
        st.rerun()

# ==== Inmatning (exakt ordning) ====
st.subheader("Input (exakt ordning)")
c1, c2 = st.columns(2)

LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"];    LBL_ESK = CFG["LBL_ESK"]

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

# ==== Bygg base för beräkning ====
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
        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Nils": st.session_state["in_nils"],
        "Händer aktiv": st.session_state["in_hander"],
        # etikett-fält (både kanoniska och etikett-nycklar för safety)
        "Pappans vänner": st.session_state["in_pappan"],
        "Grannar":        st.session_state["in_grannar"],
        "Nils vänner":    st.session_state["in_nils_vanner"],
        "Nils familj":    st.session_state["in_nils_familj"],
        "Bekanta":        st.session_state["in_bekanta"],
        "Eskilstuna killar": st.session_state["in_eskilstuna"],
        CFG["LBL_PAPPAN"]: st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]: st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]: st.session_state["in_bekanta"],
        CFG["LBL_ESK"]: st.session_state["in_eskilstuna"],
        # meta
        "_rad_datum": st.session_state[SCENEINFO_KEY][1],
        "_fodelsedatum": CFG["fodelsedatum"],
        "_starttid": CFG["starttid"],
        "Avgift": float(CFG["avgift_usd"]),
        "PROD_STAFF": int(CFG["PROD_STAFF"]),
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
    }
    base["Känner"] = int(base["Pappans vänner"]) + int(base["Grannar"]) + int(base["Nils vänner"]) + int(base["Nils familj"])
    return base

# liten hjälpare
def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(float(total_seconds))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except:
        return "-"

# ==== Live ====
st.markdown("---")
st.subheader("🔎 Live")

base = build_base_from_inputs()
preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])

# Visa mm:ss för *Tid/kille* men med HÄNDER inkluderat
tid_kille_total_sec = float(preview.get("Tid per kille (sek)", 0)) + float(preview.get("Händer per kille (sek)", 0))

# Datum/ålder
rad_datum = preview.get("Datum", base["Datum"])
veckodag = preview.get("Veckodag", "-")
try:
    _d = datetime.fromisoformat(rad_datum).date()
except Exception:
    _d = datetime.today().date()
fd = CFG["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} • **Ålder:** {alder} år")

# Tid/Klocka/Män
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille (inkl händer)", _mmss(tid_kille_total_sec))
    st.metric("Tid/kille (sek, inkl händer)", int(tid_kille_total_sec))
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
    st.metric("Händer aktiv", "Ja" if int(preview.get("Händer aktiv",1))==1 else "Nej")
with c6:
    st.metric("Händer/kille (sek)", int(preview.get("Händer per kille (sek)", 0)))
    st.metric("Älskar (sek)", int(preview.get("Tid Älskar (sek)", 0)))

# Ekonomi
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
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag',0)):,.2f}")
with e4:
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin',0)):,.2f}")
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")

st.caption("Obs: Älskar/Sover-med-tider ingår inte i scenens 'Summa tid', men lägger på klockan. Tid/kille här inkluderar händer.")

# ==== Spara ====
st.markdown("---")
cL, cR = st.columns([1,1])

def _row_to_save(base: dict, preview: dict) -> dict:
    """Mergar alla råa inmatningar + beräknade fält till en rad att spara."""
    row = {}
    # Bas & råvärden (kanon + etiketter)
    keep_keys = [
        "Datum","Veckodag","Scen","Typ",
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
        "Älskar","Sover med","Bonus deltagit","Personal deltagit",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar",
        CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"], CFG["LBL_NILS_FAMILJ"], CFG["LBL_BEKANTA"], CFG["LBL_ESK"],
        "Nils","Händer aktiv"
    ]
    for k in keep_keys:
        if k in base:
            row[k] = base[k]
    # Beräkningar
    row.update(preview)
    # Lägg in profilnamn
    row["Profil"] = st.session_state.get(PROFILE_KEY, "")
    # Lägg till “Tid/kille (sek, inkl händer)” för tydlighet i export
    row["Tid per kille (sek, inkl händer)"] = int(float(preview.get("Tid per kille (sek)",0)) + float(preview.get("Händer per kille (sek)",0)))
    return row

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        row = _row_to_save(base, preview)
        st.session_state[ROWS_KEY].append(row)
        # uppdatera histogram
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
            _add_hist_value(col, row.get(col, 0))
        # uppdatera bonus-killar kvar (add från pren + subtract deltagit)
        gen_bonus = int(round(float(preview.get("Prenumeranter",0)) * float(CFG["BONUS_PERCENT"]) / 100.0))
        CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + gen_bonus - int(row.get("Bonus deltagit",0)))
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success("✅ Sparad i minnet.")

def _save_to_profile_sheet(row: dict):
    prof = st.session_state.get(PROFILE_KEY, "")
    if not prof:
        raise RuntimeError("Ingen profil vald.")
    su.append_row_to_profile(prof, row)

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            row = _row_to_save(base, preview)
            _save_to_profile_sheet(row)
            st.success(f"✅ Sparad till {su.data_title_for(st.session_state.get(PROFILE_KEY,''))}.")
            # spegla lokalt + histogram + bonus + sceninfo
            st.session_state[ROWS_KEY].append(row)
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
                _add_hist_value(col, row.get(col, 0))
            gen_bonus = int(round(float(preview.get("Prenumeranter",0)) * float(CFG["BONUS_PERCENT"]) / 100.0))
            CFG["BONUS_AVAILABLE"] = max(0, int(CFG["BONUS_AVAILABLE"]) + gen_bonus - int(row.get("Bonus deltagit",0)))
            st.session_state[SCENEINFO_KEY] = _current_scene_info()
        except Exception as e:
            st.error(f"Misslyckades att spara: {e}")

# ==== Visa lokala rader ====
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=340)
else:
    st.info("Inga lokala rader ännu.")

# ==== Statistik ====
st.markdown("---")
st.subheader("📊 Statistik")
try:
    rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
    if rows_df.empty:
        st.info("Ingen data att visa statistik för.")
    else:
        stats = compute_stats(rows_df, CFG)
        for k, v in stats.items():
            st.write(f"**{k}**: {v}")
except Exception as e:
    st.error(f"Kunde inte beräkna statistik: {e}")
