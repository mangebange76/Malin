# app.py — version 250823-3 (Del 1/4)
import streamlit as st
import random
import json
import math
import pandas as pd
from datetime import date, time as dtime, datetime, timedelta

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
        "starttid":     dtime(7,0),
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

        # Form/height (BMI borttaget – HEIGHT sparas bara)
        "HEIGHT_CM": 164,

        # Standard SÖMN efter scen (timmar)
        EXTRA_SLEEP_KEY: 7,

        # Eskilstuna-intervall (fallback om ingen historik)
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

        # Hårdhet – kvar i UI men används ej för prenumeranter när rating-modellen är aktiv
        "HARD_PT_DP": 10,
        "HARD_PT_DPP": 1,
        "HARD_PT_DAP": 1,
        "HARD_PT_TAP": 1,
        "HARD_PT_SVARTA": 2,
        "HARD_PT_TOT50": 3,
        "HARD_PT_TOT300": 1,
        "HARD_PT_TOT500": 1,
        "HARD_PT_TOT800": 1,
        "HARD_PT_TOT1000": 1,
        "HARD_AGE_MULT": 1.0,

        # Prenumerant-modell: använd rating istället för hårdhet
        "SUBS_USE_RATING": True,
        "RATING_DP_MIN": 5,  "RATING_DP_MAX": 25,
        "RATING_DPP_MIN": 6, "RATING_DPP_MAX": 26,
        "RATING_DAP_MIN": 10,"RATING_DAP_MAX": 30,
        "RATING_TAP_MIN": 15,"RATING_TAP_MAX": 35,
        # Pren = TotaltMän * rating% (dvs rating / 100)
        "RATING_AS_PERCENT_OF_TOTAL": True,
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

    # Init profil från URL (låser profilen även när appen idlar)
    if PROFILE_KEY not in st.session_state:
        qp = st.query_params
        prof_in_url = qp.get("profile", [None])
        prof_in_url = prof_in_url[0] if isinstance(prof_in_url, list) else prof_in_url
        profs = list_profiles()
        if prof_in_url and prof_in_url in profs:
            st.session_state[PROFILE_KEY] = prof_in_url
        else:
            st.session_state[PROFILE_KEY] = (profs[0] if profs else "")

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
        if isinstance(v, dtime): return v
        if isinstance(v, str) and v.strip():
            parts = v.strip().split(":")
            try:
                hh = int(parts[0]); mm = int(parts[1]) if len(parts) > 1 else 0
                return dtime(hh, mm)
            except Exception:
                pass
        return out.get("starttid", dtime(7,0))  # fallback

    # Kända nycklar som kan komma som strängar
    if "startdatum"   in out: out["startdatum"]   = _to_date(out["startdatum"])
    if "fodelsedatum" in out: out["fodelsedatum"] = _to_date(out["fodelsedatum"])
    if "starttid"     in out: out["starttid"]     = _to_time(out["starttid"])

    # numeriska fält
    float_keys = (
        "avgift_usd","BONUS_PCT","SUPER_BONUS_PCT",
        "ECON_COST_PER_HOUR","ECON_REVENUE_PER_KANNER","ECON_WAGE_SHARE_PCT",
        "ECON_WAGE_MIN","ECON_WAGE_MAX","ECON_WAGE_AGE_MULT",
        "HARD_PT_DP","HARD_PT_DPP","HARD_PT_DAP","HARD_PT_TAP","HARD_PT_SVARTA",
        "HARD_PT_TOT50","HARD_PT_TOT300","HARD_PT_TOT500","HARD_PT_TOT800","HARD_PT_TOT1000",
        "HARD_AGE_MULT",
        "RATING_DP_MIN","RATING_DP_MAX","RATING_DPP_MIN","RATING_DPP_MAX",
        "RATING_DAP_MIN","RATING_DAP_MAX","RATING_TAP_MIN","RATING_TAP_MAX"
    )
    for k in float_keys:
        if k in out:
            try: out[k] = float(out[k])
            except Exception: pass

    int_keys = ("PROD_STAFF","HEIGHT_CM","ESK_MIN","ESK_MAX","MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA")
    for k in int_keys:
        if k in out:
            try: out[k] = int(float(out[k]))
            except Exception: pass

    # booleans
    if "SUBS_USE_RATING" in out:
        try:
            if isinstance(out["SUBS_USE_RATING"], str):
                out["SUBS_USE_RATING"] = out["SUBS_USE_RATING"].strip().lower() in ("1","true","yes","on")
            else:
                out["SUBS_USE_RATING"] = bool(out["SUBS_USE_RATING"])
        except Exception:
            out["SUBS_USE_RATING"] = True

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
            base7 = datetime.combine(end_sleep.date(), dtime(7,0))
            if end_sleep.time() <= dtime(7,0):
                cur = base7
            else:
                # ceil to next hour
                cur = (end_sleep.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        else:
            cur = datetime.combine(cur.date() + timedelta(days=1), dtime(7,0))
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

def _as_str(v) -> str:
    try:
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    except Exception:
        return ""

def _parse_float(s: str):
    if s is None:
        return None
    s = str(s).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None

def _float_text_input(label: str, cfgkey: str, *, min_value: float | None = None, max_value: float | None = None, help: str | None = None):
    """
    Text-input för decimaler som kan raderas fritt.
    Sparar tillbaka till CFG[cfgkey] ENDAST när parsningen lyckas och ev. min/max uppfylls.
    """
    CFG = st.session_state[CFG_KEY]
    raw_key = f"RAW_{cfgkey}"
    if raw_key not in st.session_state:
        st.session_state[raw_key] = _as_str(CFG.get(cfgkey, ""))

    raw = st.text_input(label, value=st.session_state[raw_key], key=raw_key, help=help)
    val = _parse_float(raw)
    if val is None:
        # tillåt mellanläge (tomt eller ogiltigt) – behåll gamla värdet i CFG
        return CFG.get(cfgkey, 0.0)
    if min_value is not None and val < min_value:
        return CFG.get(cfgkey, 0.0)
    if max_value is not None and val > max_value:
        return CFG.get(cfgkey, 0.0)
    CFG[cfgkey] = float(val)
    return val

CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")

    # Basdatum
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    # ===== Ekonomi =====
    st.subheader("Ekonomi")
    _float_text_input("Avgift per prenumerant (USD)", "avgift_usd", min_value=0.0)
    _float_text_input("Kostnad män (USD per person-timme)", "ECON_COST_PER_HOUR", min_value=0.0)
    _float_text_input("Intäkt per 'Känner' (USD)", "ECON_REVENUE_PER_KANNER", min_value=0.0)

    st.markdown("**Lön Malin – parametrar**")
    _float_text_input("Lön % av Intäkt företag", "ECON_WAGE_SHARE_PCT", min_value=0.0, max_value=100.0, help="Ange procent (t.ex. 8 för 8%)")
    _float_text_input("Lön min (USD)", "ECON_WAGE_MIN", min_value=0.0)
    _float_text_input("Lön max (USD)", "ECON_WAGE_MAX", min_value=0.0)
    _float_text_input("Lön ålders-multiplikator", "ECON_WAGE_AGE_MULT", min_value=0.0)

    CFG["PROD_STAFF"] = st.number_input("Totalt antal personal (lönebas)", min_value=0, value=int(CFG["PROD_STAFF"]), step=1)

    st.markdown(f"**Bonus killar kvar:** {int(CFG[BONUS_LEFT_KEY])}")
    st.markdown(f"**Super-bonus ack (antal):** {int(CFG.get(SUPER_ACC_KEY,0))}")

    _float_text_input("Bonus % (t.ex. 1 = 1%)", "BONUS_PCT", min_value=0.0)
    _float_text_input("Super-bonus % (t.ex. 0.1 = 0.1%)", "SUPER_BONUS_PCT", min_value=0.0)

    CFG["HEIGHT_CM"] = st.number_input("Längd (cm) – (ingår ej i beräkningar nu)", min_value=120, max_value=230, value=int(CFG.get("HEIGHT_CM",164)), step=1)

    # Sömn efter scen (timmar) – används i tvingad schemaläggning
    _float_text_input("Sömn efter scen (timmar)", EXTRA_SLEEP_KEY, min_value=0.0)

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (fallback om ingen historik)")
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
    st.subheader("Prenumerant-modell")
    CFG["SUBS_USE_RATING"] = st.checkbox("Använd rating istället för hårdhet", value=bool(CFG.get("SUBS_USE_RATING", True)))
    colR1, colR2 = st.columns(2)
    with colR1:
        _float_text_input("DP rating min",  "RATING_DP_MIN")
        _float_text_input("DPP rating min", "RATING_DPP_MIN")
        _float_text_input("DAP rating min", "RATING_DAP_MIN")
        _float_text_input("TAP rating min", "RATING_TAP_MIN")
    with colR2:
        _float_text_input("DP rating max",  "RATING_DP_MAX")
        _float_text_input("DPP rating max", "RATING_DPP_MAX")
        _float_text_input("DAP rating max", "RATING_DAP_MAX")
        _float_text_input("TAP rating max", "RATING_TAP_MAX")
    CFG["RATING_AS_PERCENT_OF_TOTAL"] = st.checkbox("Tolka rating som % av Totalt Män", value=bool(CFG.get("RATING_AS_PERCENT_OF_TOTAL", True)))

    st.markdown("---")
    st.subheader("Hårdhet – poäng (kvar för referens)")
    colH1, colH2 = st.columns(2)
    with colH1:
        CFG["HARD_PT_DP"]   = st.number_input("Poäng: DP>0",   min_value=0.0, value=float(CFG["HARD_PT_DP"]), step=1.0)
        CFG["HARD_PT_DPP"]  = st.number_input("Poäng: DPP>0",  min_value=0.0, value=float(CFG["HARD_PT_DPP"]), step=1.0)
        CFG["HARD_PT_DAP"]  = st.number_input("Poäng: DAP>0",  min_value=0.0, value=float(CFG["HARD_PT_DAP"]), step=1.0)
        CFG["HARD_PT_TAP"]  = st.number_input("Poäng: TAP>0",  min_value=0.0, value=float(CFG["HARD_PT_TAP"]), step=1.0)
        CFG["HARD_PT_SVARTA"]= st.number_input("Poäng: Svarta>0", min_value=0.0, value=float(CFG["HARD_PT_SVARTA"]), step=1.0)
    with colH2:
        CFG["HARD_PT_TOT50"]  = st.number_input("Poäng: Tot Män ≥ 50",  min_value=0.0, value=float(CFG["HARD_PT_TOT50"]), step=1.0)
        CFG["HARD_PT_TOT300"] = st.number_input("Poäng: Tot Män ≥ 300", min_value=0.0, value=float(CFG["HARD_PT_TOT300"]), step=1.0)
        CFG["HARD_PT_TOT500"] = st.number_input("Poäng: Tot Män ≥ 500", min_value=0.0, value=float(CFG["HARD_PT_TOT500"]), step=1.0)
        CFG["HARD_PT_TOT800"] = st.number_input("Poäng: Tot Män ≥ 800", min_value=0.0, value=float(CFG["HARD_PT_TOT800"]), step=1.0)
        CFG["HARD_PT_TOT1000"]= st.number_input("Poäng: Tot Män ≥ 1000",min_value=0.0, value=float(CFG["HARD_PT_TOT1000"]), step=1.0)

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
    profiles = []
    try:
        profiles = list_profiles()
    except Exception as e:
        st.warning(f"Kunde inte läsa profil-lista: {e}")

    if not profiles:
        st.info("Inga profiler funna i fliken 'Profil'. Lägg till namn i kolumn A i bladet 'Profil'.")
    # bevara aktiv profil om den fortfarande finns i listan
    current_profile = st.session_state.get(PROFILE_KEY, profiles[0] if profiles else "")
    idx = profiles.index(current_profile) if (profiles and current_profile in profiles) else 0
    selected_profile = st.selectbox("Välj profil", options=profiles or ["(saknas)"], index=idx, key="PROFILE_SELECT")
    if selected_profile != current_profile:
        st.session_state[PROFILE_KEY] = selected_profile
        # lås i URL:en
        try:
            st.query_params.update(profile=selected_profile)
        except Exception:
            pass

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

# ==== Del 3/4 – Live, rating-prenumeranter, 7-min-förslag, tider & ekonomi ====

st.markdown("---")
st.subheader("🔎 Live")

CFG = st.session_state[CFG_KEY]

# =========================
# Bygg basrad från inputs (funktionen finns i Del 1 – används här)
# =========================
base = build_base_from_inputs()

# 1) Beräkna grund via berakningar.py (calc_row_values)
try:
    preview = calc_row_values(base, base["_rad_datum"], base["_fodelsedatum"], base["_starttid"])
except TypeError:
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# ===== Prenumeranter – ratingmodell (eller fallback till hårdhet)
def _hardhet_from(base: dict, preview: dict, CFG: dict) -> float:
    """Kvar som backup – kumulativ enligt dina regler."""
    hard = 0.0
    if int(base.get("DP",0))  > 0: hard += float(CFG.get("HARD_PT_DP",10))
    if int(base.get("DPP",0)) > 0: hard += float(CFG.get("HARD_PT_DPP",1))
    if int(base.get("DAP",0)) > 0: hard += float(CFG.get("HARD_PT_DAP",1))
    if int(base.get("TAP",0)) > 0: hard += float(CFG.get("HARD_PT_TAP",1))

    tm = int(preview.get("Totalt Män",0))
    if tm >= 50:   hard += float(CFG.get("HARD_PT_TOT50",3))
    if tm >= 300:  hard += float(CFG.get("HARD_PT_TOT300",1))
    if tm >= 500:  hard += float(CFG.get("HARD_PT_TOT500",1))
    if tm >= 800:  hard += float(CFG.get("HARD_PT_TOT800",1))
    if tm >= 1000: hard += float(CFG.get("HARD_PT_TOT1000",1))

    if int(base.get("Svarta",0)) > 0:
        hard += float(CFG.get("HARD_PT_SVARTA",2))

    if "Vila" in str(base.get("Typ","")):
        hard = 0.0

    return float(hard)

def _rand_between(minv: float, maxv: float) -> float:
    lo = float(minv); hi = float(maxv)
    if hi < lo: lo, hi = hi, lo
    return random.uniform(lo, hi)

def _compute_subscribers(base: dict, preview: dict, CFG: dict) -> tuple[int, dict]:
    """
    Returnerar (pren, details_dict).
    Om SUBS_USE_RATING=True: rating per akt → % av Totalt Män.
    Fallback: hårdhet (legacy).
    """
    details = {}
    typ = str(base.get("Typ",""))
    if "Vila" in typ:
        return 0, {"model":"vila"}

    # Totalt män (från beräkningar), med fallback
    if "Totalt Män" in preview:
        tot_man = int(preview.get("Totalt Män", 0) or 0)
    else:
        # fallback: alla fält som definierar totalsumma (samma som i statistik)
        LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
        LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
        LBL_BEK = CFG["LBL_BEKANTA"];   LBL_ESK = CFG["LBL_ESK"]
        tot_man = (
            int(base.get("Män",0)) + int(base.get("Svarta",0)) +
            int(base.get(LBL_PAPPAN,0)) + int(base.get(LBL_GRANNAR,0)) +
            int(base.get(LBL_NV,0)) + int(base.get(LBL_NF,0)) +
            int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) +
            int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
        )

    if bool(CFG.get("SUBS_USE_RATING", True)):
        # rating-intervall (med standardvärden)
        r_dp_min  = float(CFG.get("RATING_DP_MIN",  5))
        r_dp_max  = float(CFG.get("RATING_DP_MAX", 25))
        r_dpp_min = float(CFG.get("RATING_DPP_MIN", 6))
        r_dpp_max = float(CFG.get("RATING_DPP_MAX",26))
        r_dap_min = float(CFG.get("RATING_DAP_MIN",10))
        r_dap_max = float(CFG.get("RATING_DAP_MAX",30))
        r_tap_min = float(CFG.get("RATING_TAP_MIN",15))
        r_tap_max = float(CFG.get("RATING_TAP_MAX",35))

        rating_sum = 0.0
        parts = {}
        if int(base.get("DP",0))  > 0:
            v = _rand_between(r_dp_min, r_dp_max);  rating_sum += v; parts["DP"]=v
        if int(base.get("DPP",0)) > 0:
            v = _rand_between(r_dpp_min, r_dpp_max); rating_sum += v; parts["DPP"]=v
        if int(base.get("DAP",0)) > 0:
            v = _rand_between(r_dap_min, r_dap_max); rating_sum += v; parts["DAP"]=v
        if int(base.get("TAP",0)) > 0:
            v = _rand_between(r_tap_min, r_tap_max); rating_sum += v; parts["TAP"]=v

        if bool(CFG.get("RATING_AS_PERCENT_OF_TOTAL", True)):
            pren = int(round(tot_man * (rating_sum / 100.0)))
            details = {"model":"rating%", "rating_total": rating_sum, "tot_män": tot_man, "parts": parts}
        else:
            # alternativ: direkt skala mot tot män (inte procent)
            pren = int(round(tot_man * rating_sum))
            details = {"model":"rating*tot", "rating_total": rating_sum, "tot_män": tot_man, "parts": parts}
        return max(0, pren), details

    # Fallback – hårdhet
    hard = _hardhet_from(base, preview, CFG)
    pren = ( int(base.get("DP",0)) + int(base.get("DPP",0)) + int(base.get("DAP",0)) +
             int(base.get("TAP",0)) + int(tot_man) ) * hard
    return int(max(0, round(pren))), {"model":"hardhet", "hardhet": hard, "tot_män": tot_man}

# 2) Prenumeranter + Ekonomi
pren, subs_meta = _compute_subscribers(base, preview, CFG)
preview["Prenumeranter"] = int(pren)

def _econ_compute(base, preview, CFG):
    out = {}
    typ = str(base.get("Typ",""))

    # Intäkter
    avg = float(CFG.get("avgift_usd", 0.0))
    pren = int(preview.get("Prenumeranter", 0))
    out["Intäkter"] = 0.0 if "Vila" in typ else float(pren) * avg

    # Intäkt Känner
    ksam = int(preview.get("Känner sammanlagt", 0)) or int(preview.get("Känner", 0))
    rev_per_kanner = float(CFG.get("ECON_REVENUE_PER_KANNER", 30.0))
    out["Intäkt Känner"] = 0.0 if "Vila" in typ else float(ksam) * rev_per_kanner

    # Kostnad män
    if "Vila" in typ:
        kost = 0.0
    else:
        timmar = float(preview.get("Summa tid (sek)", 0)) / 3600.0
        LBL_BEK = CFG["LBL_BEKANTA"]; LBL_ESK = CFG["LBL_ESK"]
        bas_mann = ( int(base.get("Män",0)) + int(base.get("Svarta",0)) +
                     int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) )
        tot_personer = bas_mann + int(CFG.get("PROD_STAFF",0))
        cost_per_hour = float(CFG.get("ECON_COST_PER_HOUR", 15.0))
        kost = timmar * tot_personer * cost_per_hour
    out["Kostnad män"] = float(kost)

    # Intäkt företag, Lön, Vinst
    out["Intäkt företag"] = float(out["Intäkter"]) - float(out["Kostnad män"]) - float(out["Intäkt Känner"])

    wage_share = float(CFG.get("ECON_WAGE_SHARE_PCT", 8.0)) / 100.0
    wage_min   = float(CFG.get("ECON_WAGE_MIN", 150.0))
    wage_max   = float(CFG.get("ECON_WAGE_MAX", 800.0))
    wage_age_m = float(CFG.get("ECON_WAGE_AGE_MULT", 1.0))
    base_wage  = max(wage_min, min(wage_max, wage_share * float(out["Intäkt företag"])))
    lon = 0.0 if "Vila" in typ else base_wage * wage_age_m
    out["Lön Malin"] = float(lon)

    out["Vinst"] = float(out["Intäkt företag"]) - float(out["Lön Malin"])
    return out

econ = _econ_compute(base, preview, CFG)
preview.update(econ)

# ===== 7-min-förslag (≥ 420 sek exkl. händer)
def _suggest_seconds_to_reach_7min(preview: dict, base: dict) -> dict:
    """
    Returnerar förslag i sekunder:
      - only_DP:    sekunder att lägga på DP om enbart DP ska bära uppgapet (2x-vikt)
      - only_TAP:   sekunder om enbart TAP (3x-vikt)
      - split_DP_TAP_equal: sekunder per kategori om DP+TAP delas lika (2+3=5x)
    Vi räknar på 'Tid per kille (sek)' (exkl. händer).
    """
    tpk_ex = float(preview.get("Tid per kille (sek)", 0.0))
    target = 420.0  # 7 min
    if tpk_ex >= target:
        return {"delta": 0, "only_DP": 0, "only_TAP": 0, "split_DP_TAP_equal": 0}

    delta = target - tpk_ex
    # vikter: DP/DPP/DAP = 2x, TAP = 3x
    only_dp  = int((delta + 1.9999) // 2)   # ceil(delta/2) utan import math
    only_tap = int((delta + 2.9999) // 3)   # ceil(delta/3)
    split_eq = int((delta + 4.9999) // 5)   # ceil(delta/5) om lika sekunder på DP och TAP

    return {"delta": int(round(delta)), "only_DP": only_dp, "only_TAP": only_tap, "split_DP_TAP_equal": split_eq}

suggest = _suggest_seconds_to_reach_7min(preview, base)

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

# ===== Visning – tider
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
    # Egen totalsiffra inkl alla fält (fallback)
    LBL_PAPPAN = CFG["LBL_PAPPAN"]; LBL_GRANNAR = CFG["LBL_GRANNAR"]
    LBL_NV = CFG["LBL_NILS_VANNER"]; LBL_NF = CFG["LBL_NILS_FAMILJ"]
    LBL_BEK = CFG["LBL_BEKANTA"];   LBL_ESK = CFG["LBL_ESK"]
    tot_men_including = (
        int(base.get("Män",0)) + int(base.get("Svarta",0)) +
        int(base.get(LBL_PAPPAN,0)) + int(base.get(LBL_GRANNAR,0)) +
        int(base.get(LBL_NV,0)) + int(base.get(LBL_NF,0)) +
        int(base.get(LBL_BEK,0)) + int(base.get(LBL_ESK,0)) +
        int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
    )
    st.metric("Totalt män (inkl alla)", int(tot_men_including))

# Tid/kille inkl händer (visning)
tid_kille_sek = float(preview.get("Tid per kille (sek)", 0.0))
hander_kille_sek = float(preview.get("Händer per kille (sek)", 0.0))
tid_kille_inkl_hander = _mmss(tid_kille_sek + (hander_kille_sek if int(base.get("Händer aktiv",1))==1 else 0))

rowC = st.columns(3)
with rowC[0]:
    st.metric("Tid/kille inkl händer", tid_kille_inkl_hander)
with rowC[1]:
    st.metric("Tid/kille ex händer", _mmss(tid_kille_sek))
with rowC[2]:
    if suggest["delta"] > 0:
        st.metric("Behövs till 7 min (sek)", suggest["delta"])
    else:
        st.metric("Behövs till 7 min (sek)", 0)

# Förslagsektion (7-min)
if suggest["delta"] > 0:
    st.info(
        f"För att nå **7 min per kille** (exklusive händer) saknas **{suggest['delta']} sek**.\n\n"
        f"- Om du lägger allt på **DP**: lägg till ~ **{suggest['only_DP']} sek** (2×-vikt).\n"
        f"- Om du lägger allt på **TAP**: lägg till ~ **{suggest['only_TAP']} sek** (3×-vikt).\n"
        f"- Om du delar lika på **DP + TAP**: ~ **{suggest['split_DP_TAP_equal']} sek** på vardera."
    )

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
    st.metric("Super bonus ack", int(CFG.get(SUPER_ACC_KEY, 0)))

# Dubbelvisning BM/vikt borttagen (BMI-logik borttagen enligt önskemål)

# ===== Nils – längst ner i liven =====
try:
    nils_total = int(base.get("Nils",0)) + sum(int(r.get("Nils",0) or 0) for r in st.session_state[ROWS_KEY])
except Exception:
    nils_total = int(base.get("Nils",0))
st.markdown("**👤 Nils (live)**")
st.metric("Nils (total)", nils_total)

# ===== Senaste "Vila i hemmet" – räkna dagar mot SIMULERAT 'idag'
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

# ==== Del 4/4 – Spara, kopiera ~365d (progress + ETA + backoff), lokala rader & statistik ====

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
    """Gör värden kompatibla med Sheets (strängifiera datum/tid och nolla None)."""
    if v is None:
        return ""
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
# Spara lokalt & till Sheets (en rad)
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
    """Efter sparning: uppdatera tvingad NEXT_START_DT."""
    st.session_state[NEXT_START_DT_KEY] = datetime.combine(
        datetime.strptime(saved_row.get("Datum","1970-01-01"), "%Y-%m-%d").date(),
        st.session_state[NEXT_START_DT_KEY].time()
    )
    st.session_state[NEXT_START_DT_KEY] = st.session_state[NEXT_START_DT_KEY] + timedelta(days=1)
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
            row_for_sheets = _row_for_sheets(full_row)
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
# Kopiera rader för att fylla ~365 dagar (med progress, ETA och backoff)
# =========================
st.markdown("---")
st.subheader("📆 Kopiera befintliga rader för att fylla ca 365 dagar")

copy_days = st.number_input("Måldagar (≈)", min_value=1, max_value=400, value=365, step=1)
save_to_sheets_too = st.checkbox("Spara även kopiorna till Google Sheets (kan vara långsamt p.g.a. API-kvoter)", value=False)

def _weekday_name(d: date) -> str:
    return ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]

def _safe_parse_date(s: str, fallback: date) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback

def _backoff_sleep(attempt: int):
    # 1 -> 2s, 2 -> 4s, 3 -> 8s
    pause = 2 ** attempt
    time.sleep(pause)

if st.button("📑 Starta kopiering (~365d)"):
    rows = st.session_state.get(ROWS_KEY, [])
    if not rows:
        st.warning("Det finns inga rader att kopiera.")
    else:
        # Starta från sista radens datum eller profilens startdatum
        last_date = None
        try:
            if rows and "Datum" in rows[-1] and rows[-1]["Datum"]:
                last_date = _safe_parse_date(str(rows[-1]["Datum"]), st.session_state[CFG_KEY]["startdatum"])
        except Exception:
            last_date = None
        if last_date is None:
            last_date = st.session_state[CFG_KEY]["startdatum"]

        current_count = len(rows)
        target = int(copy_days)
        if current_count >= target:
            st.info(f"Inga kopior behövs – har redan {current_count} rader (≥ {target}).")
        else:
            to_make = target - current_count
            progress = st.progress(0)
            status_box = st.empty()
            start_ts = time.time()

            # Vi loopar och duplicerar befintliga rader i ordning
            made = 0
            src = rows[:]  # snapshot av exist. rader (så att vi inte itererar över växande lista)
            scene_no = (int(rows[-1].get("Scen", current_count)) if rows else 0)

            for i in range(to_make):
                proto = src[i % len(src)]
                # Nytt datum = föregående datum + 1 dag
                new_date = last_date + timedelta(days=1)
                new_weekday = _weekday_name(new_date)
                last_date = new_date

                # Bygg kopia
                clone = dict(proto)
                scene_no += 1
                clone["Scen"] = scene_no
                clone["Datum"] = new_date.isoformat()
                clone["Veckodag"] = new_weekday
                # Lämna övriga fält oförändrade (du bad om "samma data")

                # Lägg till lokalt
                st.session_state[ROWS_KEY].append(clone)

                # Uppdatera min/max för slump
                for col in ["Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
                            LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK,
                            "Personal deltagit","Bonus deltagit"]:
                    try:
                        _add_hist_value(col, int(float(clone.get(col, 0) or 0)))
                    except Exception:
                        pass

                # Spara även till Sheets (valfritt) med backoff
                if save_to_sheets_too:
                    tries = 0
                    while True:
                        try:
                            _save_to_sheets_for_profile(st.session_state.get(PROFILE_KEY,""), _row_for_sheets(clone))
                            break
                        except Exception as e:
                            tries += 1
                            # Om vi stöter på rate limit – backoff och försök igen, max 3 försök/rad
                            msg = str(e)
                            if tries <= 3 and ("429" in msg or "RATE_LIMIT" in msg or "RESOURCE_EXHAUSTED" in msg):
                                st.warning(f"Rate limit – pausar och försöker igen (försök {tries}/3)...")
                                _backoff_sleep(tries)  # 2s, 4s, 8s
                                continue
                            else:
                                st.error(f"Misslyckades att spara en kopierad rad till Sheets: {e}")
                                break

                # Progress & ETA
                made += 1
                elapsed = time.time() - start_ts
                pct = int(made * 100 / to_make)
                progress.progress(min(100, pct))

                if made > 0:
                    avg_per = elapsed / made
                    remain = to_make - made
                    eta_s = int(avg_per * remain)
                    eta_min = eta_s // 60
                    eta_sec = eta_s % 60
                else:
                    eta_min = 0; eta_sec = 0

                status_box.info(
                    f"Kopierar… {made}/{to_make} rader ({pct}%). "
                    f"Uppskattad tid kvar: ~{eta_min}m {eta_sec}s."
                )

            progress.progress(100)
            status_box.success(f"✅ Färdigt! La till {made} kopior. Totalt nu: {len(st.session_state[ROWS_KEY])} rader.")

# =========================
# Visa lokala rader + Statistik
# =========================
st.markdown("---")
st.subheader("📋 Lokala rader (förhandslagrade)")

if st.session_state[ROWS_KEY]:
    df = pd.DataFrame(st.session_state[ROWS_KEY])
    st.dataframe(df, use_container_width=True, height=360)
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
            for k,v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.caption("Statistik-modulen returnerade inget att visa ännu.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
