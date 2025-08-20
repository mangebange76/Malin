# app.py
import streamlit as st
import json
import random
import pandas as pd
import datetime as dt

# ===== Importer av egna moduler =====
# - berakningar: din logik för radsummeringar (calc_row_values)
# - sheets_utils: get_client() + ensure_ws() för Google Sheets
# - profiler: helper för profiler (listor, ladda/spara profil-Config, läsa profilens rader)
try:
    from berakningar import calc_row_values
except Exception as e:
    st.error(f"Kunde inte importera beräkningar: {e}")
    st.stop()

try:
    import sheets_utils as SU
except Exception as e:
    st.error(f"Kunde inte importera sheets_utils: {e}")
    st.stop()

try:
    import profiler as PRO
except Exception as e:
    st.error(f"Kunde inte importera profiler: {e}")
    st.stop()

# statistik är frivillig – finns filen så kör vi, annars hoppar vi.
try:
    from statistik import compute_stats as compute_stats_df
except Exception:
    compute_stats_df = None

# =========================
# Grundinställningar
# =========================
st.set_page_config(page_title="Malin – produktionsapp", layout="wide")
st.title("Malin – produktionsapp (profiler + Sheets + liven)")

# ======== State-nycklar ========
CFG_KEY         = "CFG"            # alla config + etiketter (för vald profil)
ROWS_KEY        = "ROWS"           # sparade rader (lokalt minne) FÖR VALD PROFIL
HIST_MM_KEY     = "HIST_MINMAX"    # min/max per fält (bygger vi vid inläsning/spar)
SCENEINFO_KEY   = "CURRENT_SCENE"  # (scen_nr, rad_datum, veckodag)
SCENARIO_KEY    = "SCENARIO"       # rullist-valet
PROFILE_KEY     = "PROFILE"        # valt profilnamn
PROFILE_LIST    = "PROFILE_LIST"   # cache av profilnamn
BONUS_LEFT_KEY  = "BONUS_LEFT"     # bonus-killar kvar (visas i inputlabel)

# =========================
# Input-ordning (EXAKT)
# =========================
INPUT_ORDER = [
    "in_man","in_svarta",
    "in_fitta","in_rumpa","in_dp","in_dpp","in_dap","in_tap",
    "in_tid_s","in_tid_d","in_vila",
    "in_dt_tid","in_dt_vila",
    "in_alskar","in_sover","in_hander",   # <- NYTT: händer aktiv
    "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
    "in_bekanta","in_eskilstuna",
    "in_bonus_deltagit","in_personal_deltagit",
    "in_nils"
]

# =========================
# Init state
# =========================
def _veckodag(d: dt.date) -> str:
    dagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    return dagar[d.weekday()]

def _current_scene_info():
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    d = st.session_state[CFG_KEY]["startdatum"] + dt.timedelta(days=nr-1)
    return (nr, d, _veckodag(d))

def _init_cfg_defaults() -> dict:
    # Grund-CFG (kan överskrivas av profilbladet)
    return {
        # start/födelse enligt din begäran
        "startdatum":   dt.date(1990,1,1),
        "starttid":     dt.time(7,0),
        "fodelsedatum": dt.date(1970,1,1),

        "avgift_usd":   30.0,
        "PROD_STAFF":   800,

        # Bonus – startvärde kan ersättas av profilens blad
        "BONUS_AVAILABLE": 500,
        "BONUS_RATE": 0.01,  # 1% default – kan ändras i profilbladet (0.01 eller 1..100)

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
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = None
    if PROFILE_LIST not in st.session_state:
        # Hämta listan från Sheets (om secrets finns)
        try:
            ss = SU.get_client()
            st.session_state[PROFILE_LIST] = PRO.get_profiles(ss)
        except Exception:
            st.session_state[PROFILE_LIST] = ["Malin"]
    if CFG_KEY not in st.session_state:
        st.session_state[CFG_KEY] = _init_cfg_defaults()
    if ROWS_KEY not in st.session_state:
        st.session_state[ROWS_KEY] = []
    if HIST_MM_KEY not in st.session_state:
        st.session_state[HIST_MM_KEY] = {}
    if SCENARIO_KEY not in st.session_state:
        st.session_state[SCENARIO_KEY] = "Ny scen"
    if BONUS_LEFT_KEY not in st.session_state:
        st.session_state[BONUS_LEFT_KEY] = st.session_state[CFG_KEY].get("BONUS_AVAILABLE", 0)

    # defaults för inputs (inkl händer aktiv = 1)
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander":1
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
    # bygg från lokala ROWS om saknas
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try:
            vals.append(int(r.get(colname, 0)))
        except:
            pass
    if vals:
        mm = (min(vals), max(vals))
    else:
        mm = (0, 0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _rand_hist(colname: str):
    lo, hi = _minmax_from_hist(colname)
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi > lo else lo

# =========================
# Läsa/spara profil + data
# =========================
def load_profile_from_sheets(profile_name: str):
    """Läser profilens CFG + rader från Sheets. Bygger även HIST_MINMAX."""
    try:
        ss = SU.get_client()
        # 1) Ladda och slå ihop CFG (defaults + profilbladets key/value)
        cfg = _init_cfg_defaults()
        cfg_profile = PRO.load_profile_cfg(ss, profile_name)
        cfg.update(cfg_profile)

        # om bonus-rate lagras som 1..100 → konvertera till 0..1
        try:
            br = float(cfg.get("BONUS_RATE", 0.01))
            cfg["BONUS_RATE"] = br/100.0 if br > 1.0 else br
        except Exception:
            cfg["BONUS_RATE"] = 0.01

        st.session_state[CFG_KEY] = cfg
        st.session_state[BONUS_LEFT_KEY] = int(cfg.get("BONUS_AVAILABLE", 0))

        # 2) Läs profilens rader
        rows_df = PRO.load_profile_rows(ss, profile_name)
        rows_list = rows_df.to_dict(orient="records") if not rows_df.empty else []
        st.session_state[ROWS_KEY] = rows_list

        # 3) Bygg om historik min/max från dessa rader
        st.session_state[HIST_MM_KEY] = {}
        for r in rows_list:
            for col in [
                "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                cfg["LBL_PAPPAN"], cfg["LBL_GRANNAR"], cfg["LBL_NILS_VANNER"], cfg["LBL_NILS_FAMILJ"],
                cfg["LBL_BEKANTA"], cfg["LBL_ESK"]
            ]:
                if col in r:
                    _add_hist_value(col, r.get(col, 0))

        # 4) Reset sceninfo (nästa datum)
        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success(f"✅ Läste in profil '{profile_name}' (inställningar + data).")
    except Exception as e:
        st.error(f"Kunde inte läsa profil-data: {e}")

def save_profile_cfg_to_sheets(profile_name: str):
    """Sparar hela nuvarande CFG till profilens blad (Key/Value)."""
    try:
        ss = SU.get_client()
        PRO.save_profile_cfg(ss, profile_name, st.session_state[CFG_KEY])
        st.success(f"✅ Sparade inställningar för '{profile_name}'.")
    except Exception as e:
        st.error(f"Misslyckades att spara inställningar: {e}")

def append_row_to_data_sheet(profile_name: str, row_dict: dict):
    """Appendar en rad till fliken Data (lägger till Profil-kolumnen)."""
    try:
        ss = SU.get_client()
        ws = SU.ensure_ws(ss, "Data")
        # läs header
        header = ws.row_values(1)
        row_with_profile = {"Profil": profile_name}
        row_with_profile.update(row_dict)

        if not header:
            header = list(row_with_profile.keys())
            ws.update("A1", [header])

        # säkerställ ordning enligt header
        values = [row_with_profile.get(col, "") for col in header]
        ws.append_row(values)
        st.success("✅ Sparad till Google Sheets (flik: Data).")
    except Exception as e:
        st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Scenario-fill
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nolla (behåll tidsstandarder + händer)
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander":st.session_state.get("in_hander",1)}
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

    # hjälplista för slumprader (läser min/max från historik – som nu byggs från Data + lokalt)
    sex_cols = [("Fitta","in_fitta"),("Rumpa","in_rumpa"),("DP","in_dp"),("DPP","in_dpp"),("DAP","in_dap"),("TAP","in_tap")]
    src_cols = [(LBL_PAPPAN,"in_pappan"),(LBL_GRANNAR,"in_grannar"),(LBL_NV,"in_nils_vanner"),(LBL_NF,"in_nils_familj"),(LBL_BEK,"in_bekanta")]

    if s == "Ny scen":
        return

    elif s == "Slumpa scen vit":
        st.session_state["in_svarta"] = 0
        st.session_state["in_man"]    = _rand_hist("Män")
        for col, key in sex_cols:
            st.session_state[key] = _rand_hist(col)
        for col, key in src_cols:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        st.session_state["in_svarta"] = _rand_hist("Svarta")
        for col, key in sex_cols:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        for col, key in sex_cols:
            st.session_state[key] = _rand_hist(col)
        for col, key in src_cols:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_eskilstuna"]  = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 12
        st.session_state["in_sover"]  = 1
        # bonus/personaldeltagit matar du själv

    elif s == "Vila i hemmet (dag 1–7)":
        # Förenklad: EN dag – slumpar sex+sources
        for col, key in sex_cols:
            st.session_state[key] = _rand_hist(col)
        for col, key in src_cols:
            st.session_state[key] = _rand_hist(col)
        st.session_state["in_eskilstuna"] = random.randint(int(CFG["ESK_MIN"]), int(CFG["ESK_MAX"]))
        st.session_state["in_alskar"] = 6
        st.session_state["in_sover"]  = 0
        st.session_state["in_nils"]   = 0

    # uppdatera sceninfo (datum/veckodag i liven)
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Profil")
    profiles = st.session_state[PROFILE_LIST]
    sel = st.selectbox("Välj profil", options=profiles, index=profiles.index(st.session_state[PROFILE_KEY]) if st.session_state[PROFILE_KEY] in profiles else 0, key="PROFILE_SELECT")
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("📥 Läs in vald profil"):
            st.session_state[PROFILE] = sel if (PROFILE:=PROFILE_KEY) else None  # just to avoid linter
            st.session_state[PROFILE] = None  # no-op, will set properly below
        # Streamlit kräver sättning utanför on_click för att persist
    # Sätt faktiskt vald profil och ladda
    if st.session_state.get("PROFILE_SELECT") and st.session_state.get(PROFILE_KEY) != st.session_state["PROFILE_SELECT"]:
        st.session_state[PROFILE_KEY] = st.session_state["PROFILE_SELECT"]
        load_profile_from_sheets(st.session_state[PROFILE_KEY])

    st.markdown("---")
    st.header("Inställningar (profil)")
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG.get("startdatum", dt.date(1990,1,1)))
    CFG["starttid"]     = st.time_input("Starttid", value=CFG.get("starttid", dt.time(7,0)))
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG.get("fodelsedatum", dt.date(1970,1,1)))
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG.get("avgift_usd",30.0)), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG.get("PROD_STAFF",800)), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(st.session_state.get(BONUS_LEFT_KEY, CFG.get('BONUS_AVAILABLE',0)))}")
    CFG["BONUS_RATE"]   = st.number_input("Bonus % av prenumeranter", min_value=0.0, max_value=100.0, value=float(100*CFG.get("BONUS_RATE",0.01) if CFG.get("BONUS_RATE",0.01) <= 1 else CFG.get("BONUS_RATE",1.0)), step=0.5)/100.0

    st.subheader("Eskilstuna-intervall")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG.get("ESK_MIN",20)), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=int(CFG.get("ESK_MIN",20)), value=int(CFG.get("ESK_MAX",40)), step=1)

    st.markdown("---")
    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG.get("MAX_PAPPAN",100)), step=1)
    CFG["MAX_GRANNAR"]      = st.number_input("MAX Grannar",        min_value=0, value=int(CFG.get("MAX_GRANNAR",100)), step=1)
    CFG["MAX_NILS_VANNER"]  = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG.get("MAX_NILS_VANNER",100)), step=1)
    CFG["MAX_NILS_FAMILJ"]  = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG.get("MAX_NILS_FAMILJ",100)), step=1)
    CFG["MAX_BEKANTA"]      = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG.get("MAX_BEKANTA",100)), step=1)

    st.markdown("---")
    st.subheader("Egna etiketter (slår igenom i input/live)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=CFG.get("LBL_PAPPAN","Pappans vänner"))
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=CFG.get("LBL_GRANNAR","Grannar"))
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=CFG.get("LBL_NILS_VANNER","Nils vänner"))
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=CFG.get("LBL_NILS_FAMILJ","Nils familj"))
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=CFG.get("LBL_BEKANTA","Bekanta"))
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=CFG.get("LBL_ESK","Eskilstuna killar"))

    st.markdown("---")
    st.subheader("Scenario")
    st.session_state[SCENARIO_KEY] = st.selectbox(
        "Välj",
        ["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"],
        index=["Ny scen","Slumpa scen vit","Slumpa scen svart","Vila på jobbet","Vila i hemmet (dag 1–7)"].index(st.session_state[SCENARIO_KEY])
    )
    if st.button("⬇️ Hämta värden (slump)"):
        apply_scenario_fill()
        st.experimental_rerun()  # säkrast för att widgets uppdateras direkt

    st.markdown("---")
    st.subheader("Sheets-status")
    has_creds = "GOOGLE_CREDENTIALS" in st.secrets
    has_url   = "SHEET_URL" in st.secrets
    st.write(f"GOOGLE_CREDENTIALS: {'✅' if has_creds else '❌'}")
    st.write(f"SHEET_URL: {'✅' if has_url else '❌'}")

    # Spara nuvarande CFG till profilens blad
    if st.button("💾 Spara inställningar (profil-blad)"):
        if not st.session_state[PROFILE_KEY]:
            st.error("Välj en profil först.")
        else:
            save_profile_cfg_to_sheets(st.session_state[PROFILE_KEY])

# =========================
# Inmatning (etiketter av inställningar), exakt ordning
# =========================
st.subheader("Input (exakt ordning)")
CFG = st.session_state[CFG_KEY]
LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

c1,c2 = st.columns(2)
labels = {
    "in_man":"Män","in_svarta":"Svarta",
    "in_fitta":"Fitta","in_rumpa":"Rumpa","in_dp":"DP","in_dpp":"DPP","in_dap":"DAP","in_tap":"TAP",
    "in_tid_s":"Tid S (sek)","in_tid_d":"Tid D (sek)","in_vila":"Vila (sek)",
    "in_dt_tid":"DT tid (sek/kille)","in_dt_vila":"DT vila (sek/kille)",
    "in_alskar":"Älskar","in_sover":"Sover med (0/1)","in_hander":"Händer aktiv (0/1)",
    "in_pappan":f"{LBL_PAPPAN} (MAX {int(CFG['MAX_PAPPAN'])})",
    "in_grannar":f"{LBL_GRANNAR} (MAX {int(CFG['MAX_GRANNAR'])})",
    "in_nils_vanner":f"{LBL_NV} (MAX {int(CFG['MAX_NILS_VANNER'])})",
    "in_nils_familj":f"{LBL_NF} (MAX {int(CFG['MAX_NILS_FAMILJ'])})",
    "in_bekanta":f"{LBL_BEK} (MAX {int(CFG['MAX_BEKANTA'])})",
    "in_eskilstuna":f"{LBL_ESK} ({int(CFG['ESK_MIN'])}–{int(CFG['ESK_MAX'])})",
    "in_bonus_deltagit":f"Bonus deltagit (kvar {int(st.session_state.get(BONUS_LEFT_KEY,0))})",
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
    st.number_input(labels["in_hander"], min_value=0, max_value=1, step=1, key="in_hander")
    for key in [
        "in_pappan","in_grannar","in_nils_vanner","in_nils_familj",
        "in_bekanta","in_eskilstuna",
        "in_bonus_deltagit","in_personal_deltagit",
        "in_nils"
    ]:
        st.number_input(labels[key], min_value=0, step=1, key=key)

# =========================
# Bygg basrad från inputs
# =========================
def _mmss(x: float) -> str:
    try:
        s = max(0, int(round(float(x))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    base = {
        "Profil": st.session_state.get(PROFILE_KEY) or "",
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
        CFG["LBL_ESK"]: st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],
        "Händer aktiv":      st.session_state.get("in_hander", 1),

        "Nils":    st.session_state["in_nils"],
        "Avgift":  float(st.session_state[CFG_KEY]["avgift_usd"]),
        "PROD_STAFF": int(st.session_state[CFG_KEY]["PROD_STAFF"]),

        # Skicka även med max/etiketter till beräkning om den vill nyttja dem
        "MAX_PAPPAN": int(CFG["MAX_PAPPAN"]),
        "MAX_GRANNAR": int(CFG["MAX_GRANNAR"]),
        "MAX_NILS_VANNER": int(CFG["MAX_NILS_VANNER"]),
        "MAX_NILS_FAMILJ": int(CFG["MAX_NILS_FAMILJ"]),
        "LBL_PAPPAN": CFG["LBL_PAPPAN"],
        "LBL_GRANNAR": CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER": CFG["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ": CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA": CFG["LBL_BEKANTA"],
        "LBL_ESK": CFG["LBL_ESK"],
    }
    # Känner = summa av käll-etiketter
    base["Känner"] = (
        int(base[CFG["LBL_PAPPAN"]]) + int(base[CFG["LBL_GRANNAR"]]) +
        int(base[CFG["LBL_NILS_VANNER"]]) + int(base[CFG["LBL_NILS_FAMILJ"]])
    )
    # meta till beräkning
    base["_rad_datum"]    = d
    base["_fodelsedatum"] = st.session_state[CFG_KEY]["fodelsedatum"]
    base["_starttid"]     = st.session_state[CFG_KEY]["starttid"]
    return base

# =========================
# Live (preview)
# =========================
st.markdown("---")
st.subheader("🔎 Live")

_base = build_base_from_inputs()
try:
    _preview = calc_row_values(_base, _base["_rad_datum"], _base["_fodelsedatum"], _base["_starttid"])
except TypeError:
    _preview = calc_row_values(_base, _base["_rad_datum"], st.session_state[CFG_KEY]["fodelsedatum"], st.session_state[CFG_KEY]["starttid"])

# Tot män inkl allt (kontroll)
tot_men_including = (
    int(_base.get("Män",0)) + int(_base.get("Svarta",0)) +
    int(_base.get(CFG["LBL_PAPPAN"],0)) + int(_base.get(CFG["LBL_GRANNAR"],0)) +
    int(_base.get(CFG["LBL_NILS_VANNER"],0)) + int(_base.get(CFG["LBL_NILS_FAMILJ"],0)) +
    int(_base.get(CFG["LBL_BEKANTA"],0)) + int(_base.get(CFG["LBL_ESK"],0)) +
    int(_base.get("Bonus deltagit",0)) + int(_base.get("Personal deltagit",0))
)

# Datum/ålder
rad_datum = _preview.get("Datum", _base["Datum"])
veckodag = _preview.get("Veckodag", "-")
if isinstance(rad_datum, str):
    try:
        _d = dt.datetime.fromisoformat(rad_datum).date()
    except Exception:
        _d = dt.date.today()
else:
    _d = dt.date.today()

fd = st.session_state[CFG_KEY]["fodelsedatum"]
alder = _d.year - fd.year - ((_d.month, _d.day) < (fd.month, fd.day))
st.markdown(f"**Datum/Veckodag:** {rad_datum} / {veckodag} &nbsp;•&nbsp; **Ålder:** {alder} år")

# Tid/Klocka/Män
# Viktigt: Tid/kille i liven ska inkludera HÄNDER.
tk_base = float(_preview.get("Tid per kille (sek)", 0.0))
tk_hander = float(_preview.get("Händer per kille (sek)", 0.0))
tk_total = max(0.0, tk_base + tk_hander)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Summa tid", _preview.get("Summa tid","-"))
    st.metric("Summa tid (sek)", int(_preview.get("Summa tid (sek)",0)))
with c2:
    st.metric("Tid/kille", _mmss(tk_total))
    st.metric("Tid/kille (sek)", int(round(tk_total)))
with c3:
    st.metric("Klockan", _preview.get("Klockan","-"))
    st.metric("Totalt män (beräkningar)", int(_preview.get("Totalt Män",0)))

# Hångel/Sug/Händer
c4, c5 = st.columns(2)
with c4:
    st.metric("Hångel (m:s/kille)", _preview.get("Hångel (m:s/kille)", "-"))
    st.metric("Hångel (sek/kille)", int(_preview.get("Hångel (sek/kille)", 0)))
with c5:
    st.metric("Suger/kille (sek)", int(_preview.get("Suger per kille (sek)", 0)))
    st.metric("Händer/kille (sek)", int(_preview.get("Händer per kille (sek)", 0)))

# Ekonomi
st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter", int(_preview.get("Prenumeranter",0)))
    st.metric("Hårdhet", int(_preview.get("Hårdhet",0)))
with e2:
    st.metric("Intäkter", f"${float(_preview.get('Intäkter',0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(_preview.get('Intäkt Känner',0)):,.2f}")
with e3:
    st.metric("Kostnad män", f"${float(_preview.get('Kostnad män',0)):,.2f}")
    st.metric("Lön Malin", f"${float(_preview.get('Lön Malin',0)):,.2f}")
with e4:
    st.metric("Intäkt företag", f"${float(_preview.get('Intäkt företag',0)):,.2f}")
    st.metric("Vinst", f"${float(_preview.get('Vinst',0)):,.2f}")

# Käll-brakeout
st.markdown("**👥 Källor (live)**")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric(CFG["LBL_PAPPAN"], int(_base.get(CFG["LBL_PAPPAN"],0)))
with k2: st.metric(CFG["LBL_GRANNAR"], int(_base.get(CFG["LBL_GRANNAR"],0)))
with k3: st.metric(CFG["LBL_NILS_VANNER"], int(_base.get(CFG["LBL_NILS_VANNER"],0)))
with k4: st.metric(CFG["LBL_NILS_FAMILJ"], int(_base.get(CFG["LBL_NILS_FAMILJ"],0)))
with k5: st.metric(CFG["LBL_BEKANTA"], int(_base.get(CFG["LBL_BEKANTA"],0)))
with k6: st.metric(CFG["LBL_ESK"], int(_base.get(CFG["LBL_ESK"],0)))
st.metric("Totalt män (inkl. källor/bonus/personal/Eskilstuna)", tot_men_including)

st.caption("Obs: Älskar/Sover-med-tider ingår **inte** i scenens 'Summa tid', men lägger på klockan. Tid/kille inkluderar HÄNDER om aktivt.")

# =========================
# Spara lokalt + spara till Sheets
# =========================
st.markdown("---")
cL, cR = st.columns([1,1])

def _bump_hist_from_preview(preview: dict):
    for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                CFG["LBL_PAPPAN"], CFG["LBL_GRANNAR"], CFG["LBL_NILS_VANNER"], CFG["LBL_NILS_FAMILJ"],
                CFG["LBL_BEKANTA"], CFG["LBL_ESK"]]:
        if col in preview:
            try:
                _add_hist_value(col, int(preview.get(col,0)))
            except:
                pass

def _post_save_housekeeping(preview: dict):
    # minska bonus kvar med "Bonus deltagit"
    try:
        used = int(preview.get("Bonus deltagit",0))
    except:
        used = 0
    left_before = int(st.session_state.get(BONUS_LEFT_KEY, 0))
    st.session_state[BONUS_LEFT_KEY] = max(0, left_before - used)
    # sceninfo → nästa dag
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        st.session_state[ROWS_KEY].append(_preview)
        _bump_hist_from_preview(_preview)
        _post_save_housekeeping(_preview)
        st.success("✅ Sparad i minnet.")

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        if not st.session_state.get(PROFILE_KEY):
            st.error("Välj en profil först.")
        else:
            # Lägg in 'Profil' i raden och spara
            row_to_save = dict(_preview)  # redan beräknade nycklar + inputnamn
            row_to_save["Profil"] = st.session_state[PROFILE_KEY]
            append_row_to_data_sheet(st.session_state[PROFILE_KEY], row_to_save)

            # Spegla lokalt
            st.session_state[ROWS_KEY].append(_preview)
            _bump_hist_from_preview(_preview)
            _post_save_housekeeping(_preview)

# =========================
# Visa lokala rader + Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")
if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=320)
else:
    st.info("Inga lokala rader ännu.")

st.markdown("---")
st.subheader("📊 Statistik")
if compute_stats_df:
    try:
        rows_df = pd.DataFrame(st.session_state[ROWS_KEY])
        stats = compute_stats_df(rows_df, st.session_state[CFG_KEY])
        if stats:
            for k, v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.info("Ingen statistik ännu.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
else:
    st.info("Ingen statistik-modul hittad (statistik.py). Lägg till compute_stats(rows_df, cfg) om du vill visa summeringar.")
