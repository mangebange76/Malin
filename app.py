# app.py — version 250823-2 (med redigerbara decimalfält via dec_input)
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
        # Basdatum
        "startdatum":   date(1990,1,1),
        "starttid":     time(7,0),
        "fodelsedatum": date(1970,1,1),

        # Ekonomi – styrbart
        "avgift_usd":   30.0,     # Avgift per prenumerant
        "ECON_COST_PER_HOUR": 15.0,         # Kostnad män (USD per person-timme)
        "ECON_REVENUE_PER_KANNER": 30.0,    # Intäkt per "känner"-enhet
        "ECON_WAGE_SHARE_PCT": 8.0,         # Lön % av Intäkt företag
        "ECON_WAGE_MIN": 150.0,
        "ECON_WAGE_MAX": 800.0,
        "ECON_WAGE_AGE_MULT": 1.0,          # extra multiplikator på lön rel. ålder

        # Personal-bas
        "PROD_STAFF":   800,

        # Bonus
        BONUS_LEFT_KEY: 500,
        "BONUS_PCT": 1.0,
        "SUPER_BONUS_PCT": 0.1,
        SUPER_ACC_KEY: 0,

        # BMI
        "BMI_GOAL": 21.7,
        "HEIGHT_CM": 164,

        # Standard SÖMN efter scen (timmar)
        EXTRA_SLEEP_KEY: 7,

        # Eskilstuna-intervall (används endast om historik saknas)
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

        # Hårdhet – styrbart (poäng)
        "HARD_PT_DP": 10,
        "HARD_PT_DPP": 1,
        "HARD_PT_DAP": 1,
        "HARD_PT_TAP": 1,
        "HARD_PT_SVARTA": 2,
        # trösklar för Totalt Män
        "HARD_PT_TOT50": 3,
        "HARD_PT_TOT300": 1,
        "HARD_PT_TOT500": 1,
        "HARD_PT_TOT800": 1,
        "HARD_PT_TOT1000": 1,
        # Ålder → multiplikator i hårdhet (kan fintrimmas i sidopanelen)
        "HARD_AGE_MULT": 1.0,
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

# ===== Hjälpare: redigerbara decimaler (tillåter tom sträng) =====
def _parse_float_soft(s, fallback):
    """
    Försök parsa 's' till float (tillåt komma/punkt). Om s är tomt eller ogiltigt:
    returnera fallback (behåll nuvarande värde i CFG).
    """
    if s is None:
        return fallback
    s = str(s).strip()
    if s == "":
        return fallback
    try:
        return float(s.replace(",", "."))
    except Exception:
        return fallback

def dec_input(label: str, cfg: dict, key: str, step_hint: str = "0.1", help_text: str | None = None):
    """
    Textinput som beter sig som decimalfält men tillåter radering.
    Uppdaterar cfg[key] bara när parsning lyckas – annars ligger värdet kvar.
    """
    sval_key = f"__s_{key}"
    cur_val = cfg.get(key, 0.0)
    if sval_key not in st.session_state:
        st.session_state[sval_key] = ("" if cur_val is None else str(cur_val))
    s = st.text_input(label, value=st.session_state[sval_key], key=sval_key,
                      help=help_text or f"Använd punkt eller komma. Stegförslag: {step_hint}")
    new_val = _parse_float_soft(s, cur_val)
    cfg[key] = new_val

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
                  "ECON_COST_PER_HOUR","ECON_REVENUE_PER_KANNER","ECON_WAGE_SHARE_PCT",
                  "ECON_WAGE_MIN","ECON_WAGE_MAX","ECON_WAGE_AGE_MULT",
                  "HARD_PT_DP","HARD_PT_DPP","HARD_PT_DAP","HARD_PT_TAP","HARD_PT_SVARTA",
                  "HARD_PT_TOT50","HARD_PT_TOT300","HARD_PT_TOT500","HARD_PT_TOT800","HARD_PT_TOT1000",
                  "HARD_AGE_MULT")
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
        try: vals.append(int(r.get(colname, 0)))
        except Exception: pass
    mm = (min(vals), max(vals)) if vals else (0,0)
    st.session_state[HIST_MM_KEY][colname] = mm
    return mm

def _hist_hi(colname: str) -> int:
    _, hi = _minmax_from_hist(colname)
    try:
        return int(hi)
    except Exception:
        return 0

def _rand_pct_of_hi(hi: int, lo_pct: float=0.30, hi_pct: float=0.60) -> int:
    hi = max(0, int(hi))
    if hi <= 0:
        return 0
    lo_val = max(0, int(round(lo_pct * hi)))
    hi_val = max(lo_val, int(round(hi_pct * hi)))
    return random.randint(lo_val, hi_val) if hi_val > 0 else 0

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
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
                        "Personal deltagit","Bonus deltagit"]:
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
# Scenario-fill (uppdaterad slump 30–60% + DP/DPP/DAP/TAP-regler)
# =========================
def apply_scenario_fill():
    CFG = st.session_state[CFG_KEY]
    s = st.session_state[SCENARIO_KEY]

    # nollställ och behåll vissa standarder
    keep_defaults = {
        "in_tid_s":60,"in_tid_d":60,"in_vila":7,"in_dt_tid":60,"in_dt_vila":3,
        "in_hander_aktiv":st.session_state.get("in_hander_aktiv",1),
        "in_alskar":0,"in_sover":0,"in_nils":0
    }
    for k in INPUT_ORDER:
        st.session_state[k] = keep_defaults.get(k, 0)

    # Hjälpare – slumpa sex-fält från historikmax 1..hi
    def _slumpa_sexfalt():
        for f,key in [("Fitta","in_fitta"),("Rumpa","in_rumpa")]:
            _, hi = _minmax_from_hist(f)
            st.session_state[key] = 0 if hi<=0 else random.randint(1, int(hi))
        # DP/DPP/DAP/TAP sätts separat enligt regler nedan

    # Läs dynamiska etiketter
    LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_BEK = CFG["LBL_BEKANTA"];   LBL_ESK = CFG["LBL_ESK"]

    # ===== Slump basfält (9 st) 30–60% av historiska max =====
    def _slump_9_fields(vit: bool, svart: bool):
        # Hämta hi från historik
        hi_man  = _hist_hi("Män")
        hi_svart= _hist_hi("Svarta")
        hi_pap  = _hist_hi(LBL_PAPPAN)
        hi_gra  = _hist_hi(LBL_GRANNAR)
        hi_nv   = _hist_hi(LBL_NV)
        hi_nf   = _hist_hi(LBL_NF)
        hi_bek  = _hist_hi(LBL_BEK)
        hi_pd   = _hist_hi("Personal deltagit")
        hi_esk  = _hist_hi(LBL_ESK)

        # Slumpa 30–60% av hi
        v_man   = _rand_pct_of_hi(hi_man)
        v_svart = _rand_pct_of_hi(hi_svart)
        v_pap   = _rand_pct_of_hi(hi_pap)
        v_gra   = _rand_pct_of_hi(hi_gra)
        v_nv    = _rand_pct_of_hi(hi_nv)
        v_nf    = _rand_pct_of_hi(hi_nf)
        v_bek   = _rand_pct_of_hi(hi_bek)
        v_pd    = _rand_pct_of_hi(hi_pd)
        v_esk   = _rand_pct_of_hi(hi_esk)

        # Särregler för vit/svart
        if vit:
            v_svart = 0
        if svart:
            v_man = 0
            # nollställ privata källor + personal enligt dina regler
            v_pap = v_gra = v_nv = v_nf = v_bek = v_pd = 0

        # Sätt indata
        st.session_state["in_man"] = int(v_man)
        st.session_state["in_svarta"] = int(v_svart)
        st.session_state["in_pappan"] = int(v_pap)
        st.session_state["in_grannar"] = int(v_gra)
        st.session_state["in_nils_vanner"] = int(v_nv)
        st.session_state["in_nils_familj"] = int(v_nf)
        st.session_state["in_bekanta"] = int(v_bek)
        st.session_state["in_personal_deltagit"] = int(v_pd)
        st.session_state["in_eskilstuna"] = int(v_esk)

        # total för DP-reglerna
        total_bas = v_man + v_svart + v_pap + v_gra + v_nv + v_nf + v_bek + v_pd + v_esk
        return int(total_bas)

    # ===== Räkna DP/DPP/DAP/TAP enligt dina regler =====
    def _satt_dp_suite(total_bas: int):
        # DP = 60% av totalsumman (avrundat)
        dp = int(round(0.60 * max(0, total_bas)))

        # DPP/DAP: = DP om kolumnens historik-summa >0, annars 0
        def _col_sum(col: str) -> int:
            s = 0
            for r in st.session_state[ROWS_KEY]:
                try:
                    s += int(float(r.get(col, 0) or 0))
                except Exception:
                    pass
            return s

        dpp = dp if _col_sum("DPP") > 0 else 0
        dap = dp if _col_sum("DAP") > 0 else 0

        # TAP = 40% av detta värde (dvs DP), men endast om historik i TAP >0
        tap = int(round(0.40 * dp)) if _col_sum("TAP") > 0 else 0

        st.session_state["in_dp"]  = int(dp)
        st.session_state["in_dpp"] = int(dpp)
        st.session_state["in_dap"] = int(dap)
        st.session_state["in_tap"] = int(tap)

    # === Branch per scenario
    if s == "Ny scen":
        pass

    elif s == "Slumpa scen vit":
        _slumpa_sexfalt()
        tot = _slump_9_fields(vit=True, svart=False)
        _satt_dp_suite(tot)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Slumpa scen svart":
        _slumpa_sexfalt()
        tot = _slump_9_fields(vit=False, svart=True)
        _satt_dp_suite(tot)
        st.session_state["in_alskar"] = 8
        st.session_state["in_sover"]  = 1

    elif s == "Vila på jobbet":
        _slumpa_sexfalt()
        tot = _slump_9_fields(vit=False, svart=False)
        _satt_dp_suite(tot)
        st.session_state["in_alskar"]=8
        st.session_state["in_sover"]=1
        # >>> krav: Män/Svarta alltid 0 på Vila
        st.session_state["in_man"] = 0
        st.session_state["in_svarta"] = 0

    elif s == "Vila i hemmet (dag 1–7)":
        _slumpa_sexfalt()
        tot = _slump_9_fields(vit=False, svart=False)
        _satt_dp_suite(tot)
        st.session_state["in_alskar"]=6
        st.session_state["in_sover"]=0
        st.session_state["in_nils"]=0
        # >>> krav: Män/Svarta alltid 0 på Vila
        st.session_state["in_man"] = 0
        st.session_state["in_svarta"] = 0

    elif s == "Super bonus":
        # spegla nuvarande super-ack till 'svarta' för översikt
        st.session_state["in_svarta"] = int(st.session_state[CFG_KEY].get(SUPER_ACC_KEY, 0))

    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Sidopanel – Inställningar & Profiler
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")

    # Basdatum
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG.get("startdatum", date(1990,1,1)))
    CFG["starttid"]     = st.time_input("Starttid",   value=CFG.get("starttid", time(7,0)))
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG.get("fodelsedatum", date(1970,1,1)))

    # ===== Ekonomi =====
    st.subheader("Ekonomi")
    dec_input("Avgift per prenumerant (USD)", CFG, "avgift_usd", step_hint="0.50")
    dec_input("Kostnad män (USD per person-timme)", CFG, "ECON_COST_PER_HOUR", step_hint="0.50")
    dec_input("Intäkt per 'Känner' (USD)", CFG, "ECON_REVENUE_PER_KANNER", step_hint="0.50")

    st.markdown("**Lön Malin – parametrar**")
    dec_input("Lön % av Intäkt företag", CFG, "ECON_WAGE_SHARE_PCT", step_hint="0.5")
    dec_input("Lön min (USD)", CFG, "ECON_WAGE_MIN", step_hint="5")
    dec_input("Lön max (USD)", CFG, "ECON_WAGE_MAX", step_hint="5")
    dec_input("Lön ålders-multiplikator", CFG, "ECON_WAGE_AGE_MULT", step_hint="0.05")

    CFG["PROD_STAFF"] = st.number_input(
        "Totalt antal personal (lönebas)",
        min_value=0,
        value=int(CFG.get("PROD_STAFF", 800)),
        step=1
    )

    st.markdown(f"**Bonus killar kvar:** {int(CFG.get(BONUS_LEFT_KEY, 0))}")
    st.markdown(f"**Super-bonus ack (antal):** {int(CFG.get(SUPER_ACC_KEY, 0))}")

    dec_input("Bonus % (decimal, t.ex. 1.0 = 1%)", CFG, "BONUS_PCT", step_hint="0.1")
    dec_input("Super-bonus % (decimal, t.ex. 0.1 = 0.1%)", CFG, "SUPER_BONUS_PCT", step_hint="0.1")
    dec_input("BM mål (BMI)", CFG, "BMI_GOAL", step_hint="0.1")
    CFG["HEIGHT_CM"] = st.number_input("Längd (cm)", min_value=140, max_value=220, value=int(CFG.get("HEIGHT_CM",164)), step=1)

    # Sömn efter scen (timmar) – används i tvingad schemaläggning
    dec_input("Sömn efter scen (timmar)", CFG, EXTRA_SLEEP_KEY, step_hint="0.5")

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (fallback om ingen historik)")
    CFG["ESK_MIN"] = st.number_input("Eskilstuna min", min_value=0, value=int(CFG.get("ESK_MIN", 20)), step=1)
    CFG["ESK_MAX"] = st.number_input("Eskilstuna max", min_value=int(CFG.get("ESK_MIN", 20)), value=int(CFG.get("ESK_MAX", 40)), step=1)

    st.markdown("---")
    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]      = st.number_input("MAX Pappans vänner", min_value=0, value=int(CFG.get("MAX_PAPPAN",100)), step=1)
    CFG["MAX_GRANNAR"]     = st.number_input("MAX Grannar",        min_value=0, value=int(CFG.get("MAX_GRANNAR",100)), step=1)
    CFG["MAX_NILS_VANNER"] = st.number_input("MAX Nils vänner",    min_value=0, value=int(CFG.get("MAX_NILS_VANNER",100)), step=1)
    CFG["MAX_NILS_FAMILJ"] = st.number_input("MAX Nils familj",    min_value=0, value=int(CFG.get("MAX_NILS_FAMILJ",100)), step=1)
    CFG["MAX_BEKANTA"]     = st.number_input("MAX Bekanta",        min_value=0, value=int(CFG.get("MAX_BEKANTA",100)), step=1)

    st.markdown("---")
    st.subheader("Egna etiketter (slår igenom i input/live)")
    CFG["LBL_PAPPAN"]      = st.text_input("Etikett för Pappans vänner", value=str(CFG.get("LBL_PAPPAN","Pappans vänner")))
    CFG["LBL_GRANNAR"]     = st.text_input("Etikett för Grannar", value=str(CFG.get("LBL_GRANNAR","Grannar")))
    CFG["LBL_NILS_VANNER"] = st.text_input("Etikett för Nils vänner", value=str(CFG.get("LBL_NILS_VANNER","Nils vänner")))
    CFG["LBL_NILS_FAMILJ"] = st.text_input("Etikett för Nils familj", value=str(CFG.get("LBL_NILS_FAMILJ","Nils familj")))
    CFG["LBL_BEKANTA"]     = st.text_input("Etikett för Bekanta", value=str(CFG.get("LBL_BEKANTA","Bekanta")))
    CFG["LBL_ESK"]         = st.text_input("Etikett för Eskilstuna killar", value=str(CFG.get("LBL_ESK","Eskilstuna killar")))

    st.markdown("---")
    st.subheader("Hårdhet – poäng (styrbart)")
    colH1, colH2 = st.columns(2)
    with colH1:
        dec_input("Poäng: DP>0",   CFG, "HARD_PT_DP",   step_hint="1")
        dec_input("Poäng: DPP>0",  CFG, "HARD_PT_DPP",  step_hint="1")
        dec_input("Poäng: DAP>0",  CFG, "HARD_PT_DAP",  step_hint="1")
        dec_input("Poäng: TAP>0",  CFG, "HARD_PT_TAP",  step_hint="1")
        dec_input("Poäng: Svarta>0", CFG, "HARD_PT_SVARTA", step_hint="1")
    with colH2:
        dec_input("Poäng: Tot Män ≥ 50",   CFG, "HARD_PT_TOT50",  step_hint="1")
        dec_input("Poäng: Tot Män ≥ 300",  CFG, "HARD_PT_TOT300", step_hint="1")
        dec_input("Poäng: Tot Män ≥ 500",  CFG, "HARD_PT_TOT500", step_hint="1")
        dec_input("Poäng: Tot Män ≥ 800",  CFG, "HARD_PT_TOT800", step_hint="1")
        dec_input("Poäng: Tot Män ≥ 1000", CFG, "HARD_PT_TOT1000", step_hint="1")

    # Ålder för hårdhet – räkna ut & låt användaren fintrimma multiplikatorn
    try:
        alder = CFG["startdatum"].year - CFG["fodelsedatum"].year - (
            (CFG["startdatum"].month, CFG["startdatum"].day) < (CFG["fodelsedatum"].month, CFG["fodelsedatum"].day)
        )
    except Exception:
        alder = 30
    st.caption(f"Ålder (beräknad): {alder} år")
    dec_input("Hårdhet – ålders-multiplikator", CFG, "HARD_AGE_MULT", step_hint="0.1")

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

    # Hämta profil från query param (p) om finns och vi inte redan valt en i sessionen
    url_prof = st.query_params.get("p")
    current_profile = st.session_state.get(PROFILE_KEY, None)

    if current_profile is None and url_prof and profiles and url_prof in profiles:
        current_profile = url_prof

    if profiles:
        if current_profile not in profiles:
            current_profile = profiles[0]
        idx = profiles.index(current_profile)
        selected_profile = st.selectbox("Välj profil", options=profiles, index=idx)
    else:
        selected_profile = ""

    # Spara val i session + uppdatera URL-param
    st.session_state[PROFILE_KEY] = selected_profile
    if selected_profile:
        st.query_params["p"] = selected_profile

    colP1, colP2 = st.columns(2)
    with colP1:
        if st.button("📥 Läs in profilens inställningar (endast)") and selected_profile:
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
        if st.button("📥 Läs in profilens data (allt)") and selected_profile:
            _load_profile_settings_and_data(selected_profile)

    st.caption(f"GOOGLE_CREDENTIALS: {'✅' if 'GOOGLE_CREDENTIALS' in st.secrets else '❌'} • SHEET_URL: {'✅' if 'SHEET_URL' in st.secrets else '❌'}")

    if st.button("💾 Spara inställningar till profil") and selected_profile:
        try:
            save_profile_settings(selected_profile, st.session_state[CFG_KEY])
            st.success("✅ Inställningar sparade till profilbladet.")
        except Exception as e:
            st.error(f"Misslyckades att spara inställningar: {e}")

# ==== Auto-ladda profil vid första sidladdning ====
if not st.session_state.get(FIRST_BOOT_KEY, False):
    prof = st.session_state.get(PROFILE_KEY, "")
    if not prof:
        # prova URL-param
        url_prof = st.query_params.get("p")
        if url_prof:
            prof = url_prof
            st.session_state[PROFILE_KEY] = prof
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

# ==== Del 3/4 – Live, hårdhet, ekonomi, BMI, tider, varningar ====

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs() -> dict:
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    start_dt = st.session_state[NEXT_START_DT_KEY]  # tvingad start för raden
    CFG = st.session_state[CFG_KEY]
    base = {
        "Profil": st.session_state.get(PROFILE_KEY, ""),
        "Datum": d.isoformat(),
        "Veckodag": veckodag,
        "Scen": scen,
        "Typ": st.session_state.get(SCENARIO_KEY, "Ny scen"),

        "Män":    st.session_state["in_man"],
        "Svarta": st.session_state["in_svarta"],
        "Fitta":  st.session_state["in_fitta"],
        "Rumpa":  st.session_state["in_rumpa"],
        "DP":     st.session_state["in_dp"],
        "DPP":    st.session_state["in_dpp"],
        "DAP":    st.session_state["in_dap"],
        "TAP":    st.session_state["in_tap"],

        "Tid S":  st.session_state["in_tid_s"],
        "Tid D":  st.session_state["in_tid_d"],
        "Vila":   st.session_state["in_vila"],

        "DT tid (sek/kille)":  st.session_state["in_dt_tid"],
        "DT vila (sek/kille)": st.session_state["in_dt_vila"],

        "Älskar":    st.session_state["in_alskar"],
        "Sover med": st.session_state["in_sover"],

        CFG["LBL_PAPPAN"]:      st.session_state["in_pappan"],
        CFG["LBL_GRANNAR"]:     st.session_state["in_grannar"],
        CFG["LBL_NILS_VANNER"]: st.session_state["in_nils_vanner"],
        CFG["LBL_NILS_FAMILJ"]: st.session_state["in_nils_familj"],
        CFG["LBL_BEKANTA"]:     st.session_state["in_bekanta"],
        CFG["LBL_ESK"]:         st.session_state["in_eskilstuna"],

        "Bonus deltagit":    st.session_state["in_bonus_deltagit"],
        "Personal deltagit": st.session_state["in_personal_deltagit"],

        "Händer aktiv": st.session_state["in_hander_aktiv"],

        "Nils":       st.session_state["in_nils"],
        "Avgift":     float(CFG.get("avgift_usd", 0.0)),
        "PROD_STAFF": int(CFG.get("PROD_STAFF", 0)),

        # referenser (om beräkningsmodulen vill titta)
        "MAX_PAPPAN":       int(CFG.get("MAX_PAPPAN", 0)),
        "MAX_GRANNAR":      int(CFG.get("MAX_GRANNAR", 0)),
        "MAX_NILS_VANNER":  int(CFG.get("MAX_NILS_VANNER", 0)),
        "MAX_NILS_FAMILJ":  int(CFG.get("MAX_NILS_FAMILJ", 0)),
        "MAX_BEKANTA":      int(CFG.get("MAX_BEKANTA", 0)),
        "LBL_PAPPAN":       CFG["LBL_PAPPAN"],
        "LBL_GRANNAR":      CFG["LBL_GRANNAR"],
        "LBL_NILS_VANNER":  CFG["LBL_NILS_VANNER"],
        "LBL_NILS_FAMILJ":  CFG["LBL_NILS_FAMILJ"],
        "LBL_BEKANTA":      CFG["LBL_BEKANTA"],
        "LBL_ESK":          CFG["LBL_ESK"],
    }
    # Känner = summa av käll-etiketter (radnivå)
    base["Känner"] = (
        int(base[CFG["LBL_PAPPAN"]]) +
        int(base[CFG["LBL_GRANNAR"]]) +
        int(base[CFG["LBL_NILS_VANNER"]]) +
        int(base[CFG["LBL_NILS_FAMILJ"]])
    )
    # meta till beräkning
    base["_rad_datum"]    = start_dt.date()
    base["_fodelsedatum"] = CFG.get("fodelsedatum", date(1970, 1, 1))
    base["_starttid"]     = start_dt.time()  # tvingad starttid
    return base


# =========================
# Hårdhet enligt styrbara regler
# =========================
def _hardhet_from(base: dict, preview: dict, CFG: dict) -> float:
    hard = 0.0
    # Poäng på närvaro av DP/DPP/DAP/TAP
    if int(base.get("DP", 0))  > 0: hard += float(CFG.get("HARD_PT_DP", 10))
    if int(base.get("DPP", 0)) > 0: hard += float(CFG.get("HARD_PT_DPP", 1))
    if int(base.get("DAP", 0)) > 0: hard += float(CFG.get("HARD_PT_DAP", 1))
    if int(base.get("TAP", 0)) > 0: hard += float(CFG.get("HARD_PT_TAP", 1))

    # Kumulativa trösklar för Totalt Män
    tm = int(preview.get("Totalt Män", 0))
    if tm >= 50:   hard += float(CFG.get("HARD_PT_TOT50", 3))
    if tm >= 300:  hard += float(CFG.get("HARD_PT_TOT300", 1))
    if tm >= 500:  hard += float(CFG.get("HARD_PT_TOT500", 1))
    if tm >= 800:  hard += float(CFG.get("HARD_PT_TOT800", 1))
    if tm >= 1000: hard += float(CFG.get("HARD_PT_TOT1000", 1))

    # Svarta > 0
    if int(base.get("Svarta", 0)) > 0:
        hard += float(CFG.get("HARD_PT_SVARTA", 2))

    # Åldersmultiplikator
    hard *= float(CFG.get("HARD_AGE_MULT", 1.0))

    # Vila = hårdhet noll
    if "Vila" in str(base.get("Typ", "")):
        hard = 0.0

    return float(hard)


# =========================
# Ekonomiberäkningar (styrbara)
# =========================
def _econ_compute(base: dict, preview: dict, CFG: dict) -> dict:
    out = {}
    typ = str(base.get("Typ", ""))

    hardhet = _hardhet_from(base, preview, CFG)
    out["Hårdhet"] = hardhet

    # Prenumeranter
    if "Vila" in typ:
        pren = 0
    else:
        pren = (
            int(base.get("DP", 0)) +
            int(base.get("DPP", 0)) +
            int(base.get("DAP", 0)) +
            int(base.get("TAP", 0)) +
            int(preview.get("Totalt Män", 0))
        ) * hardhet
    out["Prenumeranter"] = int(pren)

    # Intäkter
    avg = float(CFG.get("avgift_usd", 0.0))
    out["Intäkter"] = float(pren) * avg

    # Intäkt Känner
    ksam = int(preview.get("Känner sammanlagt", 0)) or int(preview.get("Känner", 0))
    rev_per_kanner = float(CFG.get("ECON_REVENUE_PER_KANNER", 30.0))
    out["Intäkt Känner"] = 0.0 if "Vila" in typ else float(ksam) * rev_per_kanner

    # Kostnad män
    if "Vila" in typ:
        kost = 0.0
    else:
        timmar = float(preview.get("Summa tid (sek)", 0.0)) / 3600.0
        bas_mann = (
            int(base.get("Män", 0)) +
            int(base.get("Svarta", 0)) +
            int(base.get(CFG["LBL_BEKANTA"], 0)) +
            int(base.get(CFG["LBL_ESK"], 0))
        )
        tot_personer = bas_mann + int(CFG.get("PROD_STAFF", 0))
        cost_per_hour = float(CFG.get("ECON_COST_PER_HOUR", 15.0))
        kost = timmar * tot_personer * cost_per_hour
    out["Kostnad män"] = float(kost)

    # Intäkt företag, Lön, Vinst
    out["Intäkt företag"] = float(out["Intäkter"]) - float(out["Kostnad män"]) - float(out["Intäkt Känner"])

    # Lön Malin – styrbar via % och intervall + åldersmult
    wage_share = float(CFG.get("ECON_WAGE_SHARE_PCT", 8.0)) / 100.0
    wage_min   = float(CFG.get("ECON_WAGE_MIN", 150.0))
    wage_max   = float(CFG.get("ECON_WAGE_MAX", 800.0))
    wage_age_m = float(CFG.get("ECON_WAGE_AGE_MULT", 1.0))
    base_wage  = max(wage_min, min(wage_max, wage_share * float(out["Intäkt företag"])))
    lon = 0.0 if "Vila" in typ else base_wage * wage_age_m
    out["Lön Malin"] = float(lon)

    out["Vinst"] = float(out["Intäkt företag"]) - float(out["Lön Malin"])
    return out


# =========================
# Live
# =========================
st.markdown("---")
st.subheader("🔎 Live")

CFG = st.session_state[CFG_KEY]
base = build_base_from_inputs()

# 1) Beräkna grund via berakningar.py
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    # fallback-variant om signaturen skiljer sig
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# 2) Ekonomi & hårdhet i appen (styrbart)
econ = _econ_compute(base, preview, CFG)
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
scen_typ = str(base.get("Typ", ""))
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
    if dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

def _compute_end_and_next(start_dt: datetime, base: dict, preview: dict, sleep_h: float):
    summa_sec = float(preview.get("Summa tid (sek)", 0.0))
    alskar = int(base.get("Älskar", 0))
    sover  = int(base.get("Sover med", 0))
    # Klockan = summa + 1h vila + 3h hångel
    end_dt = start_dt + timedelta(seconds=summa_sec + 3600 + 10800)
    # Klockan inkl älskar/sover
    end_incl = end_dt + timedelta(seconds=(alskar + sover) * 20 * 60)
    # + sömn
    end_sleep = end_incl + timedelta(hours=float(sleep_h))

    # Nästa start (tvingad)
    if end_sleep.date() > start_dt.date():
        base7 = datetime.combine(end_sleep.date(), time(7, 0))
        next_start = base7 if end_sleep.time() <= time(7, 0) else _ceil_to_next_hour(end_sleep)
    else:
        # Samma datum -> nästa dag 07:00
        next_start = datetime.combine(start_dt.date() + timedelta(days=1), time(7, 0))
    return end_incl, end_sleep, next_start

start_dt = st.session_state[NEXT_START_DT_KEY]
sleep_h  = float(CFG.get(EXTRA_SLEEP_KEY, 7))
end_incl, end_sleep, forced_next = _compute_end_and_next(start_dt, base, preview, sleep_h)

# Varning om extrem längd (>36h innan sömn)
if (end_incl - start_dt) > timedelta(hours=36):
    st.warning("Scenen har pågått väldigt länge (>36 timmar) innan sömn. Nästa start är tvingad enligt reglerna.")

# ===== NY LIVE-ORDNING (tider + snitt)
def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds)))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds)))
        h, rem = divmod(s, 3600)
        m = rem // 60
        return f"{h}:{m:02d}"
    except Exception:
        return "-"

st.markdown("**🕒 Tider (live)**")
rowA = st.columns(3)
with rowA[0]:
    st.metric("Klockan", preview.get("Klockan", "-"))
with rowA[1]:
    st.metric("Klockan + älskar/sover med", preview.get("Klockan inkl älskar/sover", "-"))
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
    st.metric("Summa tid (timmar:minuter)", _hhmm(float(preview.get("Summa tid (sek)", 0))))
with rowB[1]:
    st.metric("Totalt män", int(preview.get("Totalt Män", 0)))
with rowB[2]:
    # Egen totalsiffra inkl alla fält
    tot_men_including = (
        int(base.get("Män", 0)) + int(base.get("Svarta", 0)) +
        int(base.get(CFG["LBL_PAPPAN"], 0)) + int(base.get(CFG["LBL_GRANNAR"], 0)) +
        int(base.get(CFG["LBL_NILS_VANNER"], 0)) + int(base.get(CFG["LBL_NILS_FAMILJ"], 0)) +
        int(base.get(CFG["LBL_BEKANTA"], 0)) + int(base.get(CFG["LBL_ESK"], 0)) +
        int(base.get("Bonus deltagit", 0)) + int(base.get("Personal deltagit", 0))
    )
    st.metric("Totalt män (inkl alla)", int(tot_men_including))

# Tid/kille inkl händer (visning)
tid_kille_sek = float(preview.get("Tid per kille (sek)", 0.0))
hander_kille_sek = float(preview.get("Händer per kille (sek)", 0.0))
tid_kille_inkl_hander = _mmss(tid_kille_sek + (hander_kille_sek if int(base.get("Händer aktiv", 1)) == 1 else 0))

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
    st.metric("Bonus kvar", int(CFG.get(BONUS_LEFT_KEY, 0)))
with rowH[1]:
    st.metric("BM mål (BMI)", preview.get("BM mål", "-"))
with rowH[2]:
    st.metric("Mål vikt (kg)", preview.get("Mål vikt (kg)", "-"))

# Ekonomi
st.markdown("**💵 Ekonomi (live)**")
e1, e2, e3, e4 = st.columns(4)
with e1:
    st.metric("Prenumeranter (rad)", int(preview.get("Prenumeranter", 0)))
    st.metric("Intäkter", f"${float(preview.get('Intäkter', 0)):,.2f}")
with e2:
    st.metric("Kostnad män", f"${float(preview.get('Kostnad män', 0)):,.2f}")
    st.metric("Intäkt Känner", f"${float(preview.get('Intäkt Känner', 0)):,.2f}")
with e3:
    st.metric("Intäkt företag", f"${float(preview.get('Intäkt företag', 0)):,.2f}")
    st.metric("Lön Malin", f"${float(preview.get('Lön Malin', 0)):,.2f}")
with e4:
    st.metric("Vinst", f"${float(preview.get('Vinst', 0)):,.2f}")
    st.metric("Super bonus ack", int(preview.get("Super bonus ack", 0)))

# BM mål / Mål vikt (dubbelvisning för bakåtkomp.)
mv1, mv2 = st.columns(2)
with mv1:
    st.metric("BM mål (BMI)", preview.get("BM mål", "-"))
with mv2:
    st.metric("Mål vikt (kg)", preview.get("Mål vikt (kg)", "-"))

# ===== Nils – längst ner i liven =====
try:
    nils_total = int(base.get("Nils", 0)) + sum(int(r.get("Nils", 0) or 0) for r in st.session_state[ROWS_KEY])
except Exception:
    nils_total = int(base.get("Nils", 0))
st.markdown("**👤 Nils (live)**")
st.metric("Nils (total)", nils_total)

# ===== Senaste "Vila i hemmet" – räkna dagar mot SIMULERAT 'idag' =====
# Referensdatum = nuvarande scenens startdatum (tvingat schema), inte realtidens date.today()
sim_today = st.session_state[NEXT_START_DT_KEY].date()
senaste_vila_datum = None
for rad in reversed(st.session_state.get(ROWS_KEY, [])):
    if str(rad.get("Typ", "")).strip().startswith("Vila i hemmet"):
        try:
            senaste_vila_datum = datetime.strptime(rad.get("Datum", ""), "%Y-%m-%d").date()
            break
        except Exception:
            continue

if senaste_vila_datum:
    dagar_sedan_vila = (sim_today - senaste_vila_datum).days
    st.markdown(f"**🛏️ Senaste 'Vila i hemmet': {dagar_sedan_vila} dagar sedan (simulerat)**")
    if dagar_sedan_vila >= 21:
        st.error(f"⚠️ Dags för semester! Det var {dagar_sedan_vila} dagar sedan senaste 'Vila i hemmet'.")
else:
    st.info("Ingen 'Vila i hemmet' hittad ännu.")

st.caption("Obs: Vila-scenarion genererar inga prenumeranter, intäkter, kostnader eller lön. Bonus kvar minskas dock med 'Bonus deltagit'.")

# ==== Del 4/4 – Spara, lokala rader, statistik + "kopiera till 365 dagar" ====

# =========================
# Sparrad – full rad (base + preview) och nollställ None
# =========================
CFG = st.session_state[CFG_KEY]
LBL_PAPPAN   = CFG["LBL_PAPPAN"]
LBL_GRANNAR  = CFG["LBL_GRANNAR"]
LBL_NV       = CFG["LBL_NILS_VANNER"]
LBL_NF       = CFG["LBL_NILS_FAMILJ"]
LBL_BEK      = CFG["LBL_BEKANTA"]
LBL_ESK      = CFG["LBL_ESK"]

SAVE_NUM_COLS = [
    "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
    "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
    "Älskar","Sover med",
    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
    "Bonus deltagit","Personal deltagit","Händer aktiv","Nils"
]

def _prepare_row_for_save(_preview: dict, _base: dict, _cfg: dict) -> dict:
    """Bygger en sammanfogad rad för visning/spar samt inkluderar sömn(h)."""
    row = dict(_base)
    row.update(_preview)
    row["Profil"] = st.session_state.get(PROFILE_KEY, "")
    row["BM mål"] = _preview.get("BM mål")
    row["Mål vikt (kg)"] = _preview.get("Mål vikt (kg)")
    row["Super bonus ack"] = _preview.get("Super bonus ack")
    # Spara även sömn(h) för historik-återspelning
    row["Sömn (h)"] = float(_cfg.get(EXTRA_SLEEP_KEY, 7))

    for k in SAVE_NUM_COLS:
        if row.get(k) is None:
            row[k] = 0
    for k in ["Datum","Veckodag","Typ","Scen","Klockan","Klockan inkl älskar/sover"]:
        if row.get(k) is None:
            row[k] = ""
    return row

def _to_writable_value(v):
    """Gör värden kompatibla med Sheets (strängifiera datum/tid)."""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.strftime("%H:%M:%S")
    return v

def _row_for_sheets(row_dict: dict) -> dict:
    """Konvertera alla värden till typer som gspread accepterar."""
    return {k: _to_writable_value(v) for k, v in row_dict.items()}

# =========================
# Spara lokalt & till Sheets (enstaka rad)
# =========================
st.markdown("---")
st.subheader("Spara rad")

cL, cR = st.columns([1,1])

def _save_to_sheets_for_profile(profile: str, row_dict: dict):
    append_row_to_profile_data(profile, row_dict)

def _after_save_housekeeping(preview_row: dict, is_vila: bool, is_superbonus: bool):
    """Bonus- och superbonuslogik + uppdatera ack i CFG."""
    CFG = st.session_state[CFG_KEY]
    pren = int(preview_row.get("Prenumeranter", 0))
    bonus_pct = float(CFG.get("BONUS_PCT", 1.0)) / 100.0
    sb_pct    = float(CFG.get("SUPER_BONUS_PCT", 0.1)) / 100.0

    add_bonus = 0 if (is_vila or is_superbonus) else int(pren * bonus_pct)
    add_super = 0 if (is_vila or is_superbonus) else int(pren * sb_pct)

    minus_bonus = int(preview_row.get("Bonus deltagit", 0))
    CFG[BONUS_LEFT_KEY] = max(0, int(CFG.get(BONUS_LEFT_KEY,0)) - minus_bonus + add_bonus)
    CFG[SUPER_ACC_KEY]  = max(0, int(CFG.get(SUPER_ACC_KEY,0)) + add_super)

def _update_forced_next_start_after_save(saved_row: dict):
    """Efter sparning: frys BMI-sample + uppdatera tvingad NEXT_START_DT."""
    # BMI – lås in pendings till historik
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
                    LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
                    "Personal deltagit","Bonus deltagit"]:
            _add_hist_value(col, int(full_row.get(col,0)))

        scen_typ = str(base.get("Typ",""))
        _after_save_housekeeping(full_row, is_vila=("Vila" in scen_typ), is_superbonus=("Super bonus" in scen_typ))

        _update_forced_next_start_after_save(full_row)
        st.success("✅ Sparad lokalt.")

with cR:
    if st.button("📤 Spara raden till Google Sheets"):
        try:
            full_row = _prepare_row_for_save(preview, base, CFG)
            row_for_sheets = _row_for_sheets(full_row)  # datum/tid → str
            _save_to_sheets_for_profile(st.session_state.get(PROFILE_KEY,""), row_for_sheets)

            # spegla lokalt
            st.session_state[ROWS_KEY].append(full_row)
            for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                        LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
                        "Personal deltagit","Bonus deltagit"]:
                _add_hist_value(col, int(full_row.get(col,0)))

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
        stats = compute_stats(rows_df, CFG)
        if isinstance(stats, dict) and stats:
            for k, v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.caption("Statistik-modulen returnerade inget att visa ännu.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")

# =========================
# Masskopiering till ~365 rader + progress/ETA + kvot-skydd
# =========================
st.markdown("---")
st.subheader("🧰 Fyll året med kopior (~365 rader)")

opt_col1, opt_col2, opt_col3 = st.columns([1,1,1])
with opt_col1:
    write_to_sheets = st.checkbox("Spara även till Google Sheets", value=False, help="Kryssa i för att skriva varje kopia till kalkylarket (risk för kvotbegränsning).")
with opt_col2:
    delay_per_row = st.number_input("Fördröjning per rad (sek)", min_value=0.0, step=0.1, value=1.3, help="Hjälper att undvika Google Sheets-kvoter när du sparar många rader.")
with opt_col3:
    target_rows = st.number_input("Målantal rader", min_value=1, step=1, value=365, help="Hur många rader du vill ha totalt (exkl. överstigande).")

if st.button("📄 Kopiera befintliga rader tills totalt ≈ målantal"):
    if not st.session_state[ROWS_KEY]:
        st.warning("Det finns inga rader att kopiera från.")
    else:
        # Samla bas
        existing_rows = list(st.session_state[ROWS_KEY])
        cur_total = len(existing_rows)
        if cur_total >= int(target_rows):
            st.info(f"Redan {cur_total} rader ≥ mål {int(target_rows)}. Ingen kopiering behövs.")
        else:
            import time as _time
            # Progress & ETA
            progress_bar = st.progress(0.0)
            status_box = st.empty()

            to_add = int(target_rows) - cur_total
            # Hitta sista datum vi har (fallback = simulerat "idag")
            def _parse_date(s):
                try:
                    return datetime.strptime(str(s), "%Y-%m-%d").date()
                except Exception:
                    return None
            last_date = None
            for r in reversed(existing_rows):
                last_date = _parse_date(r.get("Datum", ""))
                if last_date:
                    break
            if not last_date:
                last_date = st.session_state[NEXT_START_DT_KEY].date()

            start_t = _time.perf_counter()
            done = 0

            # Hjälpare för veckodag
            veckodagar = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]

            # Backoff-wrapper för Sheets-append
            def _append_with_backoff(profile: str, row_dict: dict, base_sleep: float = 1.2, max_retries: int = 5) -> None:
                for attempt in range(max_retries):
                    try:
                        _save_to_sheets_for_profile(profile, row_dict)
                        return
                    except Exception as e:
                        msg = str(e)
                        # Det här fångar 429/rate limit ganska bra
                        if "RESOURCE_EXHAUSTED" in msg or "RATE_LIMIT_EXCEEDED" in msg or "quota" in msg.lower():
                            wait_s = base_sleep * (2 ** attempt)
                            st.warning(f"Rate limit – pausar {wait_s:.1f}s (försök {attempt+1}/{max_retries})")
                            _time.sleep(wait_s)
                            continue
                        else:
                            # annat fel, bubbla upp
                            raise

            # Skapa kopior
            i = 0
            while done < to_add:
                src = existing_rows[i % cur_total]
                new_date = last_date + timedelta(days=done + 1)
                new_week = veckodagar[new_date.weekday()]

                new_row = dict(src)
                new_row["Datum"] = new_date.isoformat()
                new_row["Veckodag"] = new_week
                # Öka scen-löpnumret (fortsätt efter befintliga)
                try:
                    new_row["Scen"] = int(new_row.get("Scen", 0)) + (cur_total + done)
                except Exception:
                    new_row["Scen"] = cur_total + done
                # Låt Typ/Klockor ligga kvar som i källraden
                # Profil tvingas till aktiv
                new_row["Profil"] = st.session_state.get(PROFILE_KEY, new_row.get("Profil", ""))

                # Lokalt: lägg in direkt (behåll risk att datumfältet redan sträng)
                st.session_state[ROWS_KEY].append(new_row)

                # Uppdatera slump-min/max
                for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
                            "Personal deltagit","Bonus deltagit"]:
                    _add_hist_value(col, int(float(new_row.get(col, 0) or 0)))

                # Skriv till Sheets om valt
                if write_to_sheets:
                    try:
                        _append_with_backoff(st.session_state.get(PROFILE_KEY, ""), _row_for_sheets(new_row),
                                             base_sleep=max(0.8, float(delay_per_row)))
                    except Exception as e:
                        st.error(f"Misslyckades att spara en kopierad rad till Sheets: {e}")

                # Taktning för att inte överstiga kvoter
                if write_to_sheets and float(delay_per_row) > 0.0:
                    _time.sleep(float(delay_per_row))

                done += 1
                # Progress/ETA
                perc = done / to_add
                progress_bar.progress(min(1.0, perc))
                elapsed = max(0.001, _time.perf_counter() - start_t)
                rate = done / elapsed
                remaining = to_add - done
                eta = (remaining / rate) if rate > 0 else 0.0
                status_box.info(f"Kopierar… {done}/{to_add} ({perc*100:.1f}%). "
                                f"Tempo: {rate:.2f} r/s. ETA: ~{eta:.1f}s kvar.")

            status_box.success(f"Klar! Lade till {to_add} rader. Totalt nu: {len(st.session_state[ROWS_KEY])}.")
            progress_bar.progress(1.0)
