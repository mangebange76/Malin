import streamlit as st
import random
import json
import pandas as pd
from datetime import date, time, datetime, timedelta
from math import ceil

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

# BMI-ackumulatorer
BMI_SUM_KEY     = "BMI_SUM"
BMI_CNT_KEY     = "BMI_CNT"
PENDING_BMI_KEY = "PENDING_BMI"

# >>> Nycklar för tvingad scenstart
NEXT_START_DT_KEY = "NEXT_START_DT"   # datetime för nästa scenstart (tvingad)
EXTRA_SLEEP_KEY   = "EXTRA_SLEEP_H"   # timmar

# First-boot flagga (auto-laddning från Sheets)
FIRST_BOOT_KEY = "FIRST_BOOT_DONE"

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
    "in_hander_aktiv",
    "in_nils"
]

# =========================
# Init + Hjälpare
# =========================
def _init_cfg_defaults():
    return {
        "startdatum":   date(1990,1,1),
        "starttid":     time(7,0),
        "fodelsedatum": date(1970,1,1),

        # Ekonomi – justerbart i sidopanelen
        "avgift_usd":   30.0,     # pris per prenumerant (USD)
        "PROD_STAFF":   800,      # antal personal för kostnad
        "COST_HOURLY_PER_PERSON": 15.0,  # Kostnad män: $/timme/person
        "INTAKT_KANNER_USD": 30.0,       # Intäkt Känner per enhet

        # Lön-modell (kan styras i UI)
        "PAY_SHARE": 0.08,   # andel av "Intäkt företag"
        "PAY_MIN": 150.0,
        "PAY_MAX": 800.0,
        "AGE_FACTOR_LE_18": 1.00,
        "AGE_FACTOR_19_23": 0.90,
        "AGE_FACTOR_24_27": 0.85,
        "AGE_FACTOR_28_30": 0.80,
        "AGE_FACTOR_31_32": 0.75,
        "AGE_FACTOR_33_35": 0.70,
        "AGE_FACTOR_GE_36": 0.60,

        BONUS_LEFT_KEY: 500,
        "BONUS_PCT": 1.0,          # 1% i default
        "SUPER_BONUS_PCT": 0.1,    # 0.1% i default
        SUPER_ACC_KEY: 0,

        "BMI_GOAL": 21.7,
        "HEIGHT_CM": 164,

        # Standard SÖMN efter scen (timmar)
        EXTRA_SLEEP_KEY: 7,

        # Eskilstuna-intervall (fallback om ingen historik)
        "ESK_MIN": 20, "ESK_MAX": 40,

        # Maxvärden (källor) – visas i UI och används i statistik
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

        # — Hårdhet: vikter (styrbart från UI) —
        "HARD_W_DP": 10,
        "HARD_W_DPP": 1,
        "HARD_W_DAP": 1,
        "HARD_W_TAP": 1,
        "HARD_W_SVARTA": 2,

        # — Hårdhet: tröskelpoäng för Totalt män —
        "HARD_T50": 3,
        "HARD_T300": 1,
        "HARD_T500": 1,
        "HARD_T800": 1,
        "HARD_T1000": 1,
    }

def _ensure_next_start_dt_exists():
    if NEXT_START_DT_KEY not in st.session_state:
        cfg = st.session_state[CFG_KEY]
        st.session_state[NEXT_START_DT_KEY] = datetime.combine(cfg["startdatum"], cfg["starttid"])

def _current_scene_info():
    # Bygg sceninfo från T V I N G A D nästa-start (inte dag-index)
    _ensure_next_start_dt_exists()
    dt = st.session_state[NEXT_START_DT_KEY]
    veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
    nr = len(st.session_state.get(ROWS_KEY, [])) + 1
    return (nr, dt.date(), veckodagar[dt.weekday()])

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

    # BMI-ackumulatorer
    st.session_state.setdefault(BMI_SUM_KEY, 0.0)
    st.session_state.setdefault(BMI_CNT_KEY, 0)
    st.session_state.setdefault(PENDING_BMI_KEY, {"scene": None, "sum": 0.0, "count": 0})

    # Defaults till inputs
    defaults = {
        "in_tid_s":60, "in_tid_d":60, "in_vila":7, "in_dt_tid":60, "in_dt_vila":3,
        "in_sover":0, "in_alskar":0, "in_nils":0, "in_hander_aktiv":1
    }
    for k in INPUT_ORDER:
        st.session_state.setdefault(k, defaults.get(k, 0))

    # Tvingad nästa start
    _ensure_next_start_dt_exists()

    # First boot flag
    st.session_state.setdefault(FIRST_BOOT_KEY, False)

    if SCENEINFO_KEY not in st.session_state:
        st.session_state[SCENEINFO_KEY] = _current_scene_info()

init_state()

# ===== Hjälpare: typ-tvång från Sheets =====
def _coerce_cfg_types(cfg: dict) -> dict:
    """Gör om strängar från Sheets -> date/time/nummer, och behåll övrigt."""
    out = dict(cfg)

    def _to_date(v):
        if isinstance(v, date): return v
        if isinstance(v, str) and v.strip():
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
                try: return datetime.strptime(v.strip(), fmt).date()
                except Exception: pass
        return out.get("startdatum", date(1990,1,1))  # fallback

    def _to_time(v):
        if isinstance(v, time): return v
        if isinstance(v, str) and v.strip():
            parts = v.strip().split(":")
            try:
                hh = int(parts[0]); mm = int(parts[1]) if len(parts) > 1 else 0
                return time(hh, mm)
            except Exception:
                pass
        return out.get("starttid", time(7,0))  # fallback

    # Kända nycklar som kan komma som strängar
    if "startdatum"   in out: out["startdatum"]   = _to_date(out["startdatum"])
    if "fodelsedatum" in out: out["fodelsedatum"] = _to_date(out["fodelsedatum"])
    if "starttid"     in out: out["starttid"]     = _to_time(out["starttid"])

    # numeriska fält
    float_keys = ("avgift_usd","BONUS_PCT","SUPER_BONUS_PCT","BMI_GOAL",
                  "COST_HOURLY_PER_PERSON","INTAKT_KANNER_USD",
                  "PAY_SHARE","PAY_MIN","PAY_MAX",
                  "AGE_FACTOR_LE_18","AGE_FACTOR_19_23","AGE_FACTOR_24_27",
                  "AGE_FACTOR_28_30","AGE_FACTOR_31_32","AGE_FACTOR_33_35","AGE_FACTOR_GE_36",
                  "HARD_W_DP","HARD_W_DPP","HARD_W_DAP","HARD_W_TAP","HARD_W_SVARTA",
                  "HARD_T50","HARD_T300","HARD_T500","HARD_T800","HARD_T1000")
    for k in float_keys:
        if k in out:
            try: out[k] = float(out[k])
            except Exception: pass

    int_keys = ("PROD_STAFF","HEIGHT_CM","ESK_MIN","ESK_MAX",
                "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA")
    for k in int_keys:
        if k in out:
            try: out[k] = int(float(out[k]))
            except Exception: pass

    # sömn
    if EXTRA_SLEEP_KEY in out:
        try: out[EXTRA_SLEEP_KEY] = float(out[EXTRA_SLEEP_KEY])
        except Exception: pass

    return out

def _recompute_next_start_from_rows(rows):
    """Gå igenom historiken och räkna fram tvingad NEXT_START_DT."""
    cfg = st.session_state[CFG_KEY]
    cur = datetime.combine(cfg["startdatum"], cfg["starttid"])
    if not rows:
        return cur
    for r in rows:
        # Summa tid (sek) + 1h vila + 3h hångel + (älskar+sover)*20min + sömn(h)
        try: summa = float(r.get("Summa tid (sek)", 0))
        except Exception: summa = 0.0
        try: alskar = int(float(r.get("Älskar", 0)))
        except Exception: alskar = 0
        try: sover  = int(float(r.get("Sover med", 0)))
        except Exception: sover = 0
        try: sleep_h = float(r.get("Sömn (h)", cfg.get(EXTRA_SLEEP_KEY,7)))
        except Exception: sleep_h = float(cfg.get(EXTRA_SLEEP_KEY,7))

        end_dt = cur + timedelta(seconds=summa + 3600 + 10800 + (alskar+sover)*20*60)
        end_sleep = end_dt + timedelta(hours=sleep_h)

        if end_sleep.date() > cur.date():
            base7 = datetime.combine(end_sleep.date(), time(7,0))
            if end_sleep.time() <= time(7,0):
                cur = base7
            else:
                # ceil to next hour
                cur = (end_sleep.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        else:
            cur = datetime.combine(cur.date() + timedelta(days=1), time(7,0))
    return cur

def _add_hist_value(col, v):
    try: v = int(v)
    except Exception: v = 0
    mm = st.session_state[HIST_MM_KEY].get(col)
    if mm: st.session_state[HIST_MM_KEY][col] = (min(mm[0],v), max(mm[1],v))
    else:  st.session_state[HIST_MM_KEY][col] = (v, v)

def _minmax_from_hist(colname: str):
    mm = st.session_state[HIST_MM_KEY].get(colname)
    if mm: return mm
    vals = []
    for r in st.session_state[ROWS_KEY]:
        try: vals.append(int(float(r.get(colname, 0) or 0)))
        except Exception: pass
    mm = (min(vals), max(vals)) if vals else (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _hist_sum(colname: str) -> int:
    s = 0
    for r in st.session_state[ROWS_KEY]:
        try: s += int(float(r.get(colname, 0) or 0))
        except Exception: pass
    return s

def _rand_from_hist_range(colname: str, lo_pct=0.30, hi_pct=0.60) -> int:
    """Slumpar 30–60% av historiskt max. Vid 0-historia → 0."""
    _, hi = _minmax_from_hist(colname)
    if hi <= 0:
        return 0
    lo_v = max(0, int(ceil(hi * lo_pct)))
    hi_v = max(lo_v, int(ceil(hi * hi_pct)))
    if hi_v < lo_v:
        hi_v = lo_v
    return random.randint(lo_v, hi_v)

def _rand_esk(CFG):
    lo = int(CFG.get("ESK_MIN", 0)); hi = int(CFG.get("ESK_MAX", lo))
    if hi < lo: hi = lo
    return random.randint(lo, hi) if hi>lo else lo

def _load_profile_settings_and_data(profile_name: str):
    """Läs in inställningar + data från Sheets, tvångskonvertera typer och uppdatera state."""
    # 1) Inställningar
    try:
        prof_cfg = read_profile_settings(profile_name)
        if prof_cfg:
            coerced = _coerce_cfg_types(prof_cfg)
            st.session_state[CFG_KEY].update(coerced)
        else:
            st.warning(f"Inga inställningar hittades för '{profile_name}'. Använder lokala defaults.")
    except Exception as e:
        st.error(f"Kunde inte läsa profilens inställningar ({profile_name}): {e}")

    # 2) Data
    try:
        df = read_profile_data(profile_name)
        st.session_state[ROWS_KEY] = df.to_dict(orient="records") if (df is not None and not df.empty) else []
        # Bygg min/max för slump
        st.session_state[HIST_MM_KEY] = {}
        CFG = st.session_state[CFG_KEY]
        LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
        LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
        LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]
        for r in st.session_state[ROWS_KEY]:
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK, "Personal deltagit", "Bonus deltagit"]:
                _add_hist_value(col, r.get(col, 0))
        # BMI ack
        bmi_sum = 0.0; bmi_cnt = 0
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

        # >>> Tvingad nästa start beräknas från historiken
        st.session_state[NEXT_START_DT_KEY] = _recompute_next_start_from_rows(st.session_state[ROWS_KEY])

        st.session_state[SCENEINFO_KEY] = _current_scene_info()
        st.success(f"✅ Läste in {len(st.session_state[ROWS_KEY])} rader och inställningar för '{profile_name}'.")
    except Exception as e:
        st.error(f"Kunde inte läsa profilens data ({profile_name}): {e}")

# =========================
# Scenario-fill (med 30–60%-regeln + DP/DPP/DAP/TAP)
# =========================
def _apply_dp_dpp_dap_tap_from_total(total_sum: int):
    """DP = 60% av totalen (ceil). DPP & DAP = 60% om kolumnen historiskt använts, annars 0.
       TAP = 40% om kolumnen historiskt använts, annars 0."""
    dp_val  = int(ceil(0.60 * total_sum))

    used_dpp = _hist_sum("DPP") > 0
    used_dap = _hist_sum("DAP") > 0
    used_tap = _hist_sum("TAP") > 0

    dpp_val = dp_val if used_dpp else 0
    dap_val = dp_val if used_dap else 0
    tap_val = int(ceil(0.40 * total_sum)) if used_tap else 0

    st.session_state["in_dp"]  = dp_val
    st.session_state["in_dpp"] = dpp_val
    st.session_state["in_dap"] = dap_val
    st.session_state["in_tap"] = tap_val

def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # Nollställ inputs till rimliga defaults
    keep_defaults = {"in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,"in_hander_aktiv":st.session_state.get("in_hander_aktiv",1)}
    for k in INPUT_ORDER: st.session_state[k] = keep_defaults.get(k, 0)

    LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]; LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

    def _slumpa_sexfalt():
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa")]:
            # 30–60% av historiskt max
            st.session_state[key] = _rand_from_hist_range(f)

    def _slumpa_kallor(hist_based=True, zero_these=None):
        zero_these = zero_these or []
        if "in_pappan" not in zero_these:
            st.session_state["in_pappan"]      = 0 if not hist_based else _rand_from_hist_range(LBL_PAPPAN)
        if "in_grannar" not in zero_these:
            st.session_state["in_grannar"]     = 0 if not hist_based else _rand_from_hist_range(LBL_GRANNAR)
        if "in_nils_vanner" not in zero_these:
            st.session_state["in_nils_vanner"] = 0 if not hist_based else _rand_from_hist_range(LBL_NV)
        if "in_nils_familj" not in zero_these:
            st.session_state["in_nils_familj"] = 0 if not hist_based else _rand_from_hist_range(LBL_NF)
        if "in_bekanta" not in zero_these:
            st.session_state["in_bekanta"]     = 0 if not hist_based else _rand_from_hist_range(LBL_BEK)
        if "in_personal_deltagit" not in zero_these:
            st.session_state["in_personal_deltagit"] = 0 if not hist_based else _rand_from_hist_range("Personal deltagit")
        # Eskilstuna – använd historik om finns, annars profilens intervall
        if "in_eskilstuna" not in zero_these:
            _, esk_hi = _minmax_from_hist(LBL_ESK)
            st.session_state["in_eskilstuna"] = (_rand_from_hist_range(LBL_ESK) if esk_hi>0 else _rand_esk(CFG))

    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        # Män: 30–60% historiskt max, Svarta = 0
        st.session_state["in_man"]    = _rand_from_hist_range("Män")
        st.session_state["in_svarta"] = 0
        _slumpa_sexfalt()
        _slumpa_kallor(hist_based=True)

        # DP/DPP/DAP/TAP från totalen
        total = (
            st.session_state["in_man"] + st.session_state["in_svarta"] +
            st.session_state["in_pappan"] + st.session_state["in_grannar"] +
            st.session_state["in_nils_vanner"] + st.session_state["in_nils_familj"] +
            st.session_state["in_bekanta"] + st.session_state["in_personal_deltagit"] +
            st.session_state["in_eskilstuna"]
        )
        _apply_dp_dpp_dap_tap_from_total(total)

        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        # Män = 0, Svarta = 30–60% historiskt max
        st.session_state["in_man"]    = 0
        st.session_state["in_svarta"] = _rand_from_hist_range("Svarta")
        _slumpa_sexfalt()
        # Dessa ska vara 0
        zeros = ["in_pappan","in_grannar","in_nils_vanner","in_nils_familj","in_bekanta","in_personal_deltagit"]
        _slumpa_kallor(hist_based=True, zero_these=zeros)  # Esk fortfarande historik/fallback

        total = (
            st.session_state["in_man"] + st.session_state["in_svarta"] +
            st.session_state["in_pappan"] + st.session_state["in_grannar"] +
            st.session_state["in_nils_vanner"] + st.session_state["in_nils_familj"] +
            st.session_state["in_bekanta"] + st.session_state["in_personal_deltagit"] +
            st.session_state["in_eskilstuna"]
        )
        _apply_dp_dpp_dap_tap_from_total(total)
        st.session_state["in_alskar"]=8
        st.session_state["in_sover"]=1

    elif s == "Vila på jobbet":
        # Män/Svarta ska vara 0 på VILA-scenarion
        st.session_state["in_man"]    = 0
        st.session_state["in_svarta"] = 0
        _slumpa_sexfalt()
        _slumpa_kallor(hist_based=True)
        st.session_state["in_alskar"]=8
        st.session_state["in_sover"]=1

        total = (
            st.session_state["in_man"] + st.session_state["in_svarta"] +
            st.session_state["in_pappan"] + st.session_state["in_grannar"] +
            st.session_state["in_nils_vanner"] + st.session_state["in_nils_familj"] +
            st.session_state["in_bekanta"] + st.session_state["in_personal_deltagit"] +
            st.session_state["in_eskilstuna"]
        )
        _apply_dp_dpp_dap_tap_from_total(total)

    elif s == "Vila i hemmet (dag 1–7)":
        # Män/Svarta = 0 (enligt önskan)
        st.session_state["in_man"]    = 0
        st.session_state["in_svarta"] = 0
        _slumpa_sexfalt()
        _slumpa_kallor(hist_based=True)
        st.session_state["in_alskar"]=6
        st.session_state["in_sover"]=0
        st.session_state["in_nils"]=0

        total = (
            st.session_state["in_man"] + st.session_state["in_svarta"] +
            st.session_state["in_pappan"] + st.session_state["in_grannar"] +
            st.session_state["in_nils_vanner"] + st.session_state["in_nils_familj"] +
            st.session_state["in_bekanta"] + st.session_state["in_personal_deltagit"] +
            st.session_state["in_eskilstuna"]
        )
        _apply_dp_dpp_dap_tap_from_total(total)

    elif s == "Super bonus":
        st.session_state["in_svarta"] = int(st.session_state[CFG_KEY].get(SUPER_ACC_KEY, 0))
        # övrigt lämnas enligt defaults

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel – Inställningar & Profiler
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")

    # Tidsinställningar
    CFG["startdatum"]   = st.date_input("Startdatum (tidslinje)", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid (tidslinje)", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    # Ekonomi – pris/kostnad
    CFG["avgift_usd"]   = st.number_input("Avgift per prenumerant (USD)", min_value=0.0, value=float(CFG["avgift_usd"]), step=1.0)
    CFG["PROD_STAFF"]   = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)
    CFG["COST_HOURLY_PER_PERSON"] = st.number_input("Kostnad män: $/timme/person", min_value=0.0, step=1.0, value=float(CFG.get("COST_HOURLY_PER_PERSON",15.0)))
    CFG["INTAKT_KANNER_USD"]      = st.number_input("Intäkt Känner per enhet (USD)", min_value=0.0, step=1.0, value=float(CFG.get("INTAKT_KANNER_USD",30.0)))

    st.markdown(f"**Bonus killar kvar:** {int(CFG[BONUS_LEFT_KEY])}")
    st.markdown(f"**Super-bonus ack (antal):** {int(CFG.get(SUPER_ACC_KEY,0))}")

    CFG["BONUS_PCT"]        = st.number_input("Bonus % (decimal, t.ex. 1.0 = 1%)", min_value=0.0, value=float(CFG.get("BONUS_PCT",1.0)), step=0.1)
    CFG["SUPER_BONUS_PCT"]  = st.number_input("Super-bonus % (decimal, t.ex. 0.1 = 0.1%)", min_value=0.0, value=float(CFG.get("SUPER_BONUS_PCT",0.1)), step=0.1)
    CFG["BMI_GOAL"]         = st.number_input("BM mål (BMI)", min_value=10.0, max_value=40.0, value=float(CFG.get("BMI_GOAL",21.7)), step=0.1)
    CFG["HEIGHT_CM"]        = st.number_input("Längd (cm)", min_value=140, max_value=220, value=int(CFG.get("HEIGHT_CM",164)), step=1)

    # Lön-inställningar
    with st.expander("Lön – parametrar", expanded=False):
        CFG["PAY_SHARE"] = st.number_input("Andel av 'Intäkt företag'", min_value=0.0, step=0.01, value=float(CFG.get("PAY_SHARE",0.08)))
        CFG["PAY_MIN"]   = st.number_input("Lön min ($)", min_value=0.0, step=10.0, value=float(CFG.get("PAY_MIN",150.0)))
        CFG["PAY_MAX"]   = st.number_input("Lön max ($)", min_value=0.0, step=10.0, value=float(CFG.get("PAY_MAX",800.0)))

        cAF1, cAF2, cAF3 = st.columns(3)
        with cAF1:
            CFG["AGE_FACTOR_LE_18"] = st.number_input("≤18", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_LE_18",1.00)))
            CFG["AGE_FACTOR_19_23"] = st.number_input("19–23", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_19_23",0.90)))
            CFG["AGE_FACTOR_24_27"] = st.number_input("24–27", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_24_27",0.85)))
        with cAF2:
            CFG["AGE_FACTOR_28_30"] = st.number_input("28–30", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_28_30",0.80)))
            CFG["AGE_FACTOR_31_32"] = st.number_input("31–32", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_31_32",0.75)))
            CFG["AGE_FACTOR_33_35"] = st.number_input("33–35", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_33_35",0.70)))
        with cAF3:
            CFG["AGE_FACTOR_GE_36"] = st.number_input("≥36", min_value=0.0, step=0.01, value=float(CFG.get("AGE_FACTOR_GE_36",0.60)))

    # >>> NYTT: Sömn efter scen (timmar) – används i tvingad schemaläggning
    CFG[EXTRA_SLEEP_KEY]    = st.number_input("Sömn efter scen (timmar)", min_value=0.0, step=0.5, value=float(CFG.get(EXTRA_SLEEP_KEY,7)))

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (fallback)")
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
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett – Pappans vänner", value=CFG["LBL_PAPPAN"])
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett – Grannar", value=CFG["LBL_GRANNAR"])
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett – Nils vänner", value=CFG["LBL_NILS_VANNER"])
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett – Nils familj", value=CFG["LBL_NILS_FAMILJ"])
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett – Bekanta", value=CFG["LBL_BEKANTA"])
    CFG["LBL_ESK"]         = st.text_input("Etikett – Eskilstuna killar", value=CFG["LBL_ESK"])

    st.markdown("---")
    with st.expander("Hårdhet – regler", expanded=False):
        st.caption("Styr hur Hårdhet räknas. Alla värden sparas per profil.")
        colH1, colH2, colH3 = st.columns(3)
        with colH1:
            CFG["HARD_W_DP"]     = st.number_input("Vikt: DP>0", min_value=0.0, step=1.0, value=float(CFG.get("HARD_W_DP",10)))
            CFG["HARD_W_DPP"]    = st.number_input("Vikt: DPP>0", min_value=0.0, step=1.0, value=float(CFG.get("HARD_W_DPP",1)))
        with colH2:
            CFG["HARD_W_DAP"]    = st.number_input("Vikt: DAP>0", min_value=0.0, step=1.0, value=float(CFG.get("HARD_W_DAP",1)))
            CFG["HARD_W_TAP"]    = st.number_input("Vikt: TAP>0", min_value=0.0, step=1.0, value=float(CFG.get("HARD_W_TAP",1)))
        with colH3:
            CFG["HARD_W_SVARTA"] = st.number_input("Vikt: Svarta>0", min_value=0.0, step=1.0, value=float(CFG.get("HARD_W_SVARTA",2)))

        st.write("**Tröskelpoäng för Totalt Män (adderas om över gränsen):**")
        cA, cB, cC, cD, cE = st.columns(5)
        with cA:
            CFG["HARD_T50"]   = st.number_input("> 50  ⇒ +", min_value=0.0, step=1.0, value=float(CFG.get("HARD_T50",3)))
        with cB:
            CFG["HARD_T300"]  = st.number_input("> 300 ⇒ +", min_value=0.0, step=1.0, value=float(CFG.get("HARD_T300",1)))
        with cC:
            CFG["HARD_T500"]  = st.number_input("> 500 ⇒ +", min_value=0.0, step=1.0, value=float(CFG.get("HARD_T500",1)))
        with cD:
            CFG["HARD_T800"]  = st.number_input("> 800 ⇒ +", min_value=0.0, step=1.0, value=float(CFG.get("HARD_T800",1)))
        with cE:
            CFG["HARD_T1000"] = st.number_input("> 1000 ⇒ +", min_value=0.0, step=1.0, value=float(CFG.get("HARD_T1000",1)))

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
        if st.button("📥 Läs in profilens inställningar (endast)"):
            try:
                prof_cfg = read_profile_settings(selected_profile)
                if prof_cfg:
                    coerced = _coerce_cfg_types(prof_cfg)
                    st.session_state[CFG_KEY].update(coerced)
                    st.success(f"✅ Läste in inställningar för '{selected_profile}'.")
                else:
                    st.warning(f"Inga inställningar hittades på bladet '{selected_profile}'.")
            except Exception as e:
                st.error(f"Kunde inte läsa profilens inställningar: {e}")

    with colP2:
        if st.button("📥 Läs in profilens data (allt)"):
            _load_profile_settings_and_data(selected_profile)

    st.caption(f"GOOGLE_CREDENTIALS: {'✅' if 'GOOGLE_CREDENTIALS' in st.secrets else '❌'} • SHEET_URL: {'✅' if 'SHEET_URL' in st.secrets else '❌'}")

    if st.button("💾 Spara inställningar till profil"):
        try:
            save_profile_settings(selected_profile, st.session_state[CFG_KEY])
            st.success("✅ Inställningar sparade till profilbladet.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

# ==== Auto-ladda profil vid första sidladdning ====
if not st.session_state.get(FIRST_BOOT_KEY, False):
    prof = st.session_state.get(PROFILE_KEY, "")
    if prof:
        _load_profile_settings_and_data(prof)
        st.session_state[FIRST_BOOT_KEY] = True
    else:
        st.warning("Hittade ingen profil att läsa in.")

# =========================
# Inmatning (etiketter av inställningar), exakt ordning
# =========================
st.subheader("Input (exakt ordning)")
c1,c2 = st.columns(2)

CFG = st.session_state[CFG_KEY]
LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]

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
    "in_eskilstuna":f"{LBL_ESK}",
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
    start_dt = st.session_state[NEXT_START_DT_KEY]  # tvingad
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
    base["_rad_datum"]    = start_dt.date()
    base["_fodelsedatum"] = CFG["fodelsedatum"]
    base["_starttid"]     = start_dt.time()  # T V I N G A D starttid
    return base

# =========================
# Ekonomiberäkningar (i appen) – kompletterar preview
# =========================
def _hardhet_from(base, preview):
    CFG = st.session_state[CFG_KEY]

    # Vikter
    w_dp     = int(CFG.get("HARD_W_DP", 10))
    w_dpp    = int(CFG.get("HARD_W_DPP", 1))
    w_dap    = int(CFG.get("HARD_W_DAP", 1))
    w_tap    = int(CFG.get("HARD_W_TAP", 1))
    w_svarta = int(CFG.get("HARD_W_SVARTA", 2))

    # Tröskelpoäng för Totalt Män
    t50   = int(CFG.get("HARD_T50",   3))
    t300  = int(CFG.get("HARD_T300",  1))
    t500  = int(CFG.get("HARD_T500",  1))
    t800  = int(CFG.get("HARD_T800",  1))
    t1000 = int(CFG.get("HARD_T1000", 1))

    hard = 0

    # Bas: additivt enligt om > 0
    if int(base.get("DP", 0))  > 0: hard += w_dp
    if int(base.get("DPP", 0)) > 0: hard += w_dpp
    if int(base.get("DAP", 0)) > 0: hard += w_dap
    if int(base.get("TAP", 0)) > 0: hard += w_tap

    # Totalt Män – gränser är additiva (t.ex. 600 ⇒ +t50 +t300 +t500)
    tm = int(preview.get("Totalt Män", 0))
    if tm > 50:   hard += t50
    if tm > 300:  hard += t300
    if tm > 500:  hard += t500
    if tm > 800:  hard += t800
    if tm > 1000: hard += t1000

    # Svarta > 0
    if int(base.get("Svarta", 0)) > 0:
        hard += w_svarta

    # Vila nollställer hårdhet
    if "Vila" in str(base.get("Typ", "")):
        hard = 0

    return hard

def _econ_compute(base, preview):
    out = {}
    typ = str(base.get("Typ",""))
    CFG = st.session_state[CFG_KEY]

    hardhet = _hardhet_from(base, preview)
    out["Hårdhet"] = hardhet

    # Prenumeranter
    if "Vila" in typ:
        pren = 0
    else:
        pren = ( int(base.get("DP",0)) + int(base.get("DPP",0)) + int(base.get("DAP",0)) +
                 int(base.get("TAP",0)) + int(preview.get("Totalt Män",0)) ) * hardhet
    out["Prenumeranter"] = int(pren)

    # Intäkter
    avg = float(base.get("Avgift", 0.0))
    out["Intäkter"] = float(pren) * avg

    # Intäkt Känner
    ksam = int(preview.get("Känner sammanlagt", 0)) or int(preview.get("Känner", 0))
    out["Intäkt Känner"] = 0.0 if "Vila" in typ else float(ksam) * float(CFG.get("INTAKT_KANNER_USD",30.0))

    # Kostnad män
    if "Vila" in typ:
        kost = 0.0
    else:
        timmar = float(preview.get("Summa tid (sek)", 0)) / 3600.0
        bas_mann = int(base.get("Män",0)) + int(base.get("Svarta",0)) + int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0))
        tot_personer = bas_mann + int(CFG.get("PROD_STAFF",0))
        kost = timmar * tot_personer * float(CFG.get("COST_HOURLY_PER_PERSON",15.0))
    out["Kostnad män"] = float(kost)

    # Intäkt företag, Lön, Vinst
    out["Intäkt företag"] = float(out["Intäkter"]) - float(out["Kostnad män"]) - float(out["Intäkt Känner"])

    # Åldersfaktor (styrbar)
    try:
        rad_dat = base["_rad_datum"]; fd = base["_fodelsedatum"]
        alder = rad_dat.year - fd.year - ((rad_dat.month, rad_dat.day) < (fd.month, fd.day))
    except Exception:
        alder = 30

    share = float(CFG.get("PAY_SHARE", 0.08))
    lon_raw = share * float(out["Intäkt företag"])

    if   alder <= 18: faktor = float(CFG.get("AGE_FACTOR_LE_18",1.00))
    elif 19 <= alder <= 23: faktor = float(CFG.get("AGE_FACTOR_19_23",0.90))
    elif 24 <= alder <= 27: faktor = float(CFG.get("AGE_FACTOR_24_27",0.85))
    elif 28 <= alder <= 30: faktor = float(CFG.get("AGE_FACTOR_28_30",0.80))
    elif 31 <= alder <= 32: faktor = float(CFG.get("AGE_FACTOR_31_32",0.75))
    elif 33 <= alder <= 35: faktor = float(CFG.get("AGE_FACTOR_33_35",0.70))
    else: faktor = float(CFG.get("AGE_FACTOR_GE_36",0.60))

    pay_min = float(CFG.get("PAY_MIN",150.0))
    pay_max = float(CFG.get("PAY_MAX",800.0))
    lon = 0.0 if "Vila" in typ else max(pay_min, min(pay_max, lon_raw * faktor))
    out["Lön Malin"] = float(lon)
    out["Vinst"] = float(out["Intäkt företag"]) - float(out["Lön Malin"])
    return out

def _after_save_housekeeping(preview, is_vila: bool, is_superbonus: bool):
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

# 3) BMI – slump per ny prenumerant (12–18) med viktning (10,14,19,17,15,13,12)
def _compute_bmi_pending_for_current_row(pren: int, scen_typ: str):
    if pren <= 0 or ("Vila" in scen_typ):
        return 0.0, 0
    values  = [12, 13, 14, 15, 16, 17, 18]
    weights = [10, 14, 19, 17, 15, 13, 12]
    draws = random.choices(values, weights=weights, k=pren)
    return float(sum(draws)), pren

current_scene = st.session_state[SCENEINFO_KEY][0]
scen_typ = str(base.get("Typ",""))
pren_now = int(preview.get("Prenumeranter", 0))
pend_sum, pend_cnt = _compute_bmi_pending_for_current_row(pren_now, scen_typ)

hist_sum = float(st.session_state.get(BMI_SUM_KEY, 0.0))
hist_cnt = int(st.session_state.get(BMI_CNT_KEY, 0))
total_sum = hist_sum + pend_sum
total_cnt = hist_cnt + pend_cnt
bmi_mean  = (total_sum / total_cnt) if total_cnt > 0 else 0.0

height_m = float(CFG.get("HEIGHT_CM", 164)) / 100.0
preview["BM mål"] = round(bmi_mean, 2)
preview["Mål vikt (kg)"] = round(bmi_mean * (height_m ** 2), 1)
preview["Super bonus ack"] = int(CFG.get(SUPER_ACC_KEY, 0))

st.session_state[PENDING_BMI_KEY] = {"scene": current_scene, "sum": float(pend_sum), "count": int(pend_cnt)}

# ===== T V I N G A D schemaläggning: beräkna slut + nästa start
def _ceil_to_next_hour(dt: datetime) -> datetime:
    if dt.minute==0 and dt.second==0 and dt.microsecond==0:
        return dt
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

def _compute_end_and_next(start_dt: datetime, base: dict, preview: dict, sleep_h: float):
    summa_sec = float(preview.get("Summa tid (sek)", 0.0))
    alskar = int(base.get("Älskar",0)); sover = int(base.get("Sover med",0))
    # Klockan = summa + 1h vila + 3h hångel
    end_dt = start_dt + timedelta(seconds = summa_sec + 3600 + 10800)
    # Klockan inkl älskar/sover
    end_incl = end_dt + timedelta(seconds=(alskar+sover)*20*60)
    # + sömn
    end_sleep = end_incl + timedelta(hours=float(sleep_h))

    # Nästa start (tvingad)
    if end_sleep.date() > start_dt.date():
        base7 = datetime.combine(end_sleep.date(), time(7,0))
        next_start = base7 if end_sleep.time() <= time(7,0) else _ceil_to_next_hour(end_sleep)
    else:
        # Samma datum -> nästa dag 07:00
        next_start = datetime.combine(start_dt.date() + timedelta(days=1), time(7,0))
    return end_incl, end_sleep, next_start

start_dt = st.session_state[NEXT_START_DT_KEY]
sleep_h  = float(CFG.get(EXTRA_SLEEP_KEY, 7))
end_incl, end_sleep, forced_next = _compute_end_and_next(start_dt, base, preview, sleep_h)

# Liten varning om extrem längd (>36h innan sömn)
if (end_incl - start_dt) > timedelta(hours=36):
    st.warning("Scenen har pågått väldigt länge (>36 timmar) innan sömn. Nästa start är tvingad enligt reglerna.")

# ===== NY LIVE-ORDNING (tider + snitt)
def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds))); m, s = divmod(s, 60); return f"{m}:{s:02d}"
    except Exception: return "-"

def _hhmm(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds))); h, rem = divmod(s, 3600); m = rem // 60; return f"{h}:{m:02d}"
    except Exception: return "-"

st.markdown("**🕒 Tider (live)**")
rowA = st.columns(3)
with rowA[0]:
    st.metric("Klockan", preview.get("Klockan","-"))
with rowA[1]:
    st.metric("Klockan + älskar/sover med", preview.get("Klockan inkl älskar/sover","-"))
with rowA[2]:
    st.metric("Sömn (h)", sleep_h)

rowA2 = st.columns(3)
with rowA2[0]:
    st.metric("Start (tvingad)", start_dt.strftime("%Y-%m-%d %H:%M"))
with rowA2[1]:
    st.metric("Slut inkl älskar/sover", end_incl.strftime("%Y-%m-%d %H:%M"))
with rowA2[2]:
    st.metric("Nästa scen start (T V I N G A D)", forced_next.strftime("%Y-%m-%d %H:%M"))

rowB = st.columns(3)
with rowB[0]:
    st.metric("Summa tid (timmar:minuter)", _hhmm(float(preview.get("Summa tid (sek)",0))))
with rowB[1]:
    st.metric("Totalt män", int(preview.get("Totalt Män",0)))
with rowB[2]:
    # Egen totalsiffra inkl alla (som tidigare)
    tot_men_including = (
        int(base.get("Män",0)) + int(base.get("Svarta",0)) +
        int(base.get(CFG["LBL_PAPPAN"],0)) + int(base.get(CFG["LBL_GRANNAR"],0)) +
        int(base.get(CFG["LBL_NILS_VANNER"],0)) + int(base.get(CFG["LBL_NILS_FAMILJ"],0)) +
        int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0)) +
        int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
    )
    st.metric("Totalt män (inkl alla)", int(tot_men_including))

# Tid/kille inkl händer (visning)
tid_kille_sek = float(preview.get("Tid per kille (sek)", 0.0))
hander_kille_sek = float(preview.get("Händer per kille (sek)", 0.0))
tid_kille_inkl_hander = _mmss(tid_kille_sek + (hander_kille_sek if int(base.get("Händer aktiv",1))==1 else 0))

rowC = st.columns(2)
with rowC[0]:
    st.metric("Tid/kille inkl händer", tid_kille_inkl_hander)
with rowC[1]:
    st.metric("Tid/kille ex händer", _mmss(tid_kille_sek))

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
    st.metric("Älskar (timmar:minuter)", _hhmm(float(preview.get("Tid Älskar (sek)", 0))))

rowH = st.columns(3)
with rowH[0]:
    st.metric("Bonus kvar", int(CFG.get(BONUS_LEFT_KEY,0)))
with rowH[1]:
    st.metric("BM mål (BMI)", preview.get("BM mål", "-"))
with rowH[2]:
    st.metric("Mål vikt (kg)", preview.get("Mål vikt (kg)", "-"))

# === Vila i hemmet – dagar sedan (beräknat mot appens tidslinje) ===
senaste_vila_datum = None
for rad in reversed(st.session_state.get(ROWS_KEY, [])):
    if str(rad.get("Typ", "")).strip().startswith("Vila i hemmet"):
        try:
            senaste_vila_datum = datetime.strptime(rad.get("Datum", ""), "%Y-%m-%d").date()
            break
        except Exception:
            continue

timeline_today = st.session_state[NEXT_START_DT_KEY].date()
if senaste_vila_datum:
    anchor = max(senaste_vila_datum, CFG["startdatum"])
    dagar_sedan_vila = (timeline_today - anchor).days
    st.markdown(f"**🛏️ Senaste 'Vila i hemmet': {dagar_sedan_vila} dagar sedan**")
    if dagar_sedan_vila >= 21:
        st.error(f"⚠️ Dags för semester! Det var {dagar_sedan_vila} dagar sedan senaste 'Vila i hemmet'.")
else:
    # Ingen 'Vila i hemmet' ännu → räkna från startdatum i tidslinjen
    dagar_sedan_start = (timeline_today - CFG["startdatum"]).days
    st.info(f"Ingen 'Vila i hemmet' hittad ännu. ({dagar_sedan_start} dagar sedan start i tidslinjen)")

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

# BM mål / Mål vikt (dubbelvisning för bakåtkomp.)
mv1, mv2 = st.columns(2)
with mv1:
    st.metric("BM mål (BMI)", preview.get("BM mål", "-"))
with mv2:
    st.metric("Mål vikt (kg)", preview.get("Mål vikt (kg)", "-"))

# ===== Nils – längst ner i liven =====
try:
    nils_total = int(base.get("Nils",0)) + sum(int(float(r.get("Nils",0) or 0)) for r in st.session_state[ROWS_KEY])
except Exception:
    nils_total = int(base.get("Nils",0))
st.markdown("**👤 Nils (live)**")
st.metric("Nils (total)", nils_total)

st.caption("Obs: Vila-scenarion genererar inga prenumeranter, intäkter, kostnader eller lön. Bonus kvar minskas dock med 'Bonus deltagit'.")

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
    row = dict(_base)
    row.update(_preview)
    row["Profil"] = st.session_state.get(PROFILE_KEY, "")
    row["BM mål"] = _preview.get("BM mål")
    row["Mål vikt (kg)"] = _preview.get("Mål vikt (kg)")
    row["Super bonus ack"] = _preview.get("Super bonus ack")
    # Spara även sömn(h) för historik-återspelning
    row["Sömn (h)"] = float(_cfg.get(EXTRA_SLEEP_KEY, 7))

    for k in SAVE_NUM_COLS:
        if row.get(k) is None: row[k] = 0
    for k in ["Datum","Veckodag","Typ","Scen","Klockan","Klockan inkl älskar/sover"]:
        if row.get(k) is None: row[k] = ""
    return row

# =========================
# Spara lokalt & till Sheets
# =========================
st.markdown("---")
st.subheader("Spara rad")

cL, cR = st.columns([1,1])

def _to_writable(v):
    try:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
    except Exception:
        pass
    return v

def _save_to_sheets_for_profile(profile: str, row_dict: dict):
    # Serialisera datum/tid till strängar för Google Sheets
    safe_row = {k: _to_writable(v) for k, v in row_dict.items()}
    append_row_to_profile_data(profile, safe_row)

def _update_forced_next_start_after_save(saved_row: dict):
    """Efter sparning: frys BMI-sample + uppdatera tvingad NEXT_START_DT."""
    # BMI
    pend = st.session_state.get(PENDING_BMI_KEY, {"scene": None, "sum": 0.0, "count": 0})
    st.session_state[BMI_SUM_KEY] = float(st.session_state.get(BMI_SUM_KEY, 0.0)) + float(pend.get("sum", 0.0))
    st.session_state[BMI_CNT_KEY] = int(st.session_state.get(BMI_CNT_KEY, 0)) + int(pend.get("count", 0))
    st.session_state[PENDING_BMI_KEY] = {"scene": None, "sum": 0.0, "count": 0}

    # Tvingad nästa start (använd live-beräknad)
    st.session_state[NEXT_START_DT_KEY] = forced_next
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

with cL:
    if st.button("💾 Spara raden (lokalt)"):
        full_row = _prepare_row_for_save(preview, base, CFG)
        st.session_state[ROWS_KEY].append(full_row)

        # uppdatera min/max (för slump)
        for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK, "Personal deltagit", "Bonus deltagit"]:
            _add_hist_value(col, int(full_row.get(col,0) or 0))

        scen_typ = str(base.get("Typ",""))
        _after_save_housekeeping(full_row, is_vila=("Vila" in scen_typ), is_superbonus=("Super bonus" in scen_typ))

        _update_forced_next_start_after_save(full_row)
        st.success("✅ Sparad lokalt.")

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            full_row = _prepare_row_for_save(preview, base, CFG)
            _save_to_sheets_for_profile(st.session_state.get(PROFILE_KEY,""), full_row)
            # spegla lokalt
            st.session_state[ROWS_KEY].append(full_row)
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK, "Personal deltagit", "Bonus deltagit"]:
                _add_hist_value(col, int(full_row.get(col,0) or 0))

            scen_typ = str(base.get("Typ",""))
            _after_save_housekeeping(full_row, is_vila=("Vila" in scen_typ), is_superbonus=("Super bonus" in scen_typ))

            _update_forced_next_start_after_save(full_row)
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
