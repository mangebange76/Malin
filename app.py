# app.py — version 250901-prestation (Del 1/4)
import math
import random
from datetime import date, time as dtime, datetime, timedelta

import pandas as pd
import streamlit as st

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

# BMI togs bort (height får vara kvar i inställningar men används inte)

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
# Hjälpare – textbaserade decimalfält (lättare att radera värden)
# =========================
def _float_text_input(cfg: dict, key: str, label: str, default: float, step_hint: str = "t.ex. 12.5"):
    raw_key = f"__raw_{key}"
    # startvärde i rutan = tidigare inmatning eller nuvarande cfg
    default_str = st.session_state.get(raw_key, str(cfg.get(key, default)))
    val_str = st.text_input(label, value=default_str, placeholder=step_hint, key=raw_key)
    # Tillåt tomt fält (rör inte cfg) tills användaren skriver en siffra
    s = (val_str or "").strip()
    if s == "":
        return cfg.get(key, default)  # visa gammalt värde tills nytt kommer
    # försök parsa
    try:
        s = s.replace(",", ".")
        v = float(s)
        cfg[key] = v
        return v
    except Exception:
        # lämna oförändrat om ogiltig input
        return cfg.get(key, default)

def _int_text_input(cfg: dict, key: str, label: str, default: int):
    raw_key = f"__raw_{key}"
    default_str = st.session_state.get(raw_key, str(cfg.get(key, default)))
    val_str = st.text_input(label, value=default_str, key=raw_key)
    s = (val_str or "").strip()
    if s == "":
        return cfg.get(key, default)
    try:
        v = int(float(s.replace(",", ".")))
        cfg[key] = v
        return v
    except Exception:
        return cfg.get(key, default)

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
        "ECON_WAGE_AGE_MULT": 1.0,          # extra multiplikator på lön rel. ålder (finns kvar)

        # Personal-bas
        "PROD_STAFF":   800,

        # Bonus
        BONUS_LEFT_KEY: 500,
        "BONUS_PCT": 1.0,
        "SUPER_BONUS_PCT": 0.1,
        SUPER_ACC_KEY: 0,

        # Height kvar, men används ej i beräkningar nu
        "HEIGHT_CM": 164,

        # Standard SÖMN efter scen (timmar)
        EXTRA_SLEEP_KEY: 7,

        # Eskilstuna-intervall (fallback om historik saknas)
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

    # Profil – läs från URL om finns, annars första i listan
    if PROFILE_KEY not in st.session_state:
        profs = list_profiles()
        url_prof = st.query_params.get("profile") if "profile" in st.query_params else None
        if url_prof and url_prof in profs:
            st.session_state[PROFILE_KEY] = url_prof
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
    float_keys = ("avgift_usd","BONUS_PCT","SUPER_BONUS_PCT",
                  "ECON_COST_PER_HOUR","ECON_REVENUE_PER_KANNER","ECON_WAGE_SHARE_PCT",
                  "ECON_WAGE_MIN","ECON_WAGE_MAX","ECON_WAGE_AGE_MULT")
    for k in float_keys:
        if k in out:
            try: out[k] = float(str(out[k]).replace(",", "."))
            except Exception: pass

    int_keys = ("PROD_STAFF","HEIGHT_CM","ESK_MIN","ESK_MAX",
                "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA")
    for k in int_keys:
        if k in out:
            try: out[k] = int(float(str(out[k]).replace(",", ".")))
            except Exception: pass

    # sömn
    if EXTRA_SLEEP_KEY in out:
        try: out[EXTRA_SLEEP_KEY] = float(str(out[EXTRA_SLEEP_KEY]).replace(",", "."))
        except Exception: pass

    return out

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
                cur = (end_sleep.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        else:
            cur = datetime.combine(cur.date() + timedelta(days=1), dtime(7,0))
    return cur

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

    # Hjälpare – slumpa sex-fält Fitta/Rumpa från historikmax 1..hi
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

        # TAP = 40% av DP, men endast om historik i TAP >0
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
# Sidopanel – Inställningar & Profiler (med text-baserade decimalfält)
# =========================
CFG = st.session_state[CFG_KEY]
with st.sidebar:
    st.header("Inställningar (lokalt)")

    # Basdatum
    CFG["startdatum"]   = st.date_input("Startdatum", value=CFG["startdatum"])
    CFG["starttid"]     = st.time_input("Starttid", value=CFG["starttid"])
    CFG["fodelsedatum"] = st.date_input("Födelsedatum", value=CFG["fodelsedatum"])

    # ===== Ekonomi =====
    st.subheader("Ekonomi")
    _float_text_input(CFG, "avgift_usd", "Avgift per prenumerant (USD)", CFG.get("avgift_usd", 30.0))
    _float_text_input(CFG, "ECON_COST_PER_HOUR", "Kostnad män (USD per person-timme)", CFG.get("ECON_COST_PER_HOUR", 15.0))
    _float_text_input(CFG, "ECON_REVENUE_PER_KANNER", "Intäkt per 'Känner' (USD)", CFG.get("ECON_REVENUE_PER_KANNER", 30.0))

    st.markdown("**Lön Malin – parametrar**")
    _float_text_input(CFG, "ECON_WAGE_SHARE_PCT", "Lön % av Intäkt företag", CFG.get("ECON_WAGE_SHARE_PCT", 8.0))
    _float_text_input(CFG, "ECON_WAGE_MIN", "Lön min (USD)", CFG.get("ECON_WAGE_MIN", 150.0))
    _float_text_input(CFG, "ECON_WAGE_MAX", "Lön max (USD)", CFG.get("ECON_WAGE_MAX", 800.0))
    _float_text_input(CFG, "ECON_WAGE_AGE_MULT", "Lön ålders-multiplikator", CFG.get("ECON_WAGE_AGE_MULT", 1.0))

    CFG["PROD_STAFF"] = _int_text_input(CFG, "PROD_STAFF", "Totalt antal personal (lönebas)", CFG.get("PROD_STAFF", 800))

    st.markdown(f"**Bonus killar kvar:** {int(CFG[BONUS_LEFT_KEY])}")
    st.markdown(f"**Super-bonus ack (antal):** {int(CFG.get(SUPER_ACC_KEY,0))}")

    _float_text_input(CFG, "BONUS_PCT", "Bonus % (decimal, t.ex. 1.0 = 1%)", CFG.get("BONUS_PCT", 1.0))
    _float_text_input(CFG, "SUPER_BONUS_PCT", "Super-bonus % (decimal, t.ex. 0.1 = 0.1%)", CFG.get("SUPER_BONUS_PCT", 0.1))
    _float_text_input(CFG, "HEIGHT_CM", "Längd (cm) – används ej i beräkning nu", CFG.get("HEIGHT_CM", 164))

    # Sömn efter scen (timmar) – används i tvingad schemaläggning
    _float_text_input(CFG, EXTRA_SLEEP_KEY, "Sömn efter scen (timmar)", CFG.get(EXTRA_SLEEP_KEY, 7))

    st.markdown("---")
    st.subheader("Eskilstuna-intervall (fallback om ingen historik)")
    CFG["ESK_MIN"] = _int_text_input(CFG, "ESK_MIN", "Eskilstuna min", CFG.get("ESK_MIN", 20))
    CFG["ESK_MAX"] = _int_text_input(CFG, "ESK_MAX", "Eskilstuna max", CFG.get("ESK_MAX", 40))

    st.markdown("---")
    st.subheader("Maxvärden (källor)")
    CFG["MAX_PAPPAN"]       = _int_text_input(CFG, "MAX_PAPPAN",      "MAX Pappans vänner", CFG.get("MAX_PAPPAN", 100))
    CFG["MAX_GRANNAR"]      = _int_text_input(CFG, "MAX_GRANNAR",     "MAX Grannar",        CFG.get("MAX_GRANNAR", 100))
    CFG["MAX_NILS_VANNER"]  = _int_text_input(CFG, "MAX_NILS_VANNER", "MAX Nils vänner",    CFG.get("MAX_NILS_VANNER", 100))
    CFG["MAX_NILS_FAMILJ"]  = _int_text_input(CFG, "MAX_NILS_FAMILJ", "MAX Nils familj",    CFG.get("MAX_NILS_FAMILJ", 100))
    CFG["MAX_BEKANTA"]      = _int_text_input(CFG, "MAX_BEKANTA",     "MAX Bekanta",        CFG.get("MAX_BEKANTA", 100))

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
    # bevara aktiv profil om den fortfarande finns i listan
    current_profile = st.session_state.get(PROFILE_KEY, profiles[0] if profiles else "")
    idx = profiles.index(current_profile) if (profiles and current_profile in profiles) else 0
    selected_profile = st.selectbox("Välj profil", options=profiles or ["(saknas)"], index=idx)
    if selected_profile != st.session_state.get(PROFILE_KEY):
        st.session_state[PROFILE_KEY] = selected_profile
        # skriv till query params så den inte tappas vid idle
        try:
            st.query_params.update({"profile": selected_profile})
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
        try:
            st.query_params.update({"profile": prof})
        except Exception:
            pass
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

# ==== Del 3/4 – Live, prenumeranter-betyg, ekonomi, tider, varningar ====

# =========================
# Bygg basrad från inputs
# =========================
def build_base_from_inputs():
    scen, d, veckodag = st.session_state[SCENEINFO_KEY]
    start_dt = st.session_state[NEXT_START_DT_KEY]  # tvingad
    CFG = st.session_state[CFG_KEY]
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
        "Avgift":  float(CFG.get("avgift_usd", 0)),
        "PROD_STAFF": int(CFG.get("PROD_STAFF", 0)),

        # referens till etiketter/max – om beräkningsmodul vill
        "MAX_PAPPAN": int(CFG.get("MAX_PAPPAN", 0)),
        "MAX_GRANNAR": int(CFG.get("MAX_GRANNAR", 0)),
        "MAX_NILS_VANNER": int(CFG.get("MAX_NILS_VANNER", 0)),
        "MAX_NILS_FAMILJ": int(CFG.get("MAX_NILS_FAMILJ", 0)),
        "MAX_BEKANTA": int(CFG.get("MAX_BEKANTA", 0)),
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
# Prenumeranter via betyg (slump) + Ekonomi
# =========================
def _compute_subscriber_score_and_econ(base, preview, CFG):
    out = {}
    typ = str(base.get("Typ",""))

    # ---- Prenumeranter via betyg på aktiva kategorier ----
    if "Vila" in typ:
        pren = 0
        score_used = []
    else:
        # rating per aktiv kategori
        scores = []
        if int(base.get("DP",0))  > 0: scores.append(random.randint(5, 25))
        if int(base.get("DPP",0)) > 0: scores.append(random.randint(6, 26))
        if int(base.get("DAP",0)) > 0: scores.append(random.randint(10, 30))
        if int(base.get("TAP",0)) > 0: scores.append(random.randint(15, 35))

        score_used = scores[:]  # för visning om du vill senare
        rating = (sum(scores) / len(scores)) if scores else 0.0

        tot_man = int(preview.get("Totalt Män", 0))
        # Skala: rating/10 så 5–35 blir faktor 0.5–3.5
        pren = int(round(tot_man * (rating / 10.0)))

    out["Prenumeranter"] = int(pren)
    out["_ScoreLista"] = score_used

    # ---- Intäkter ----
    avg_price = float(CFG.get("avgift_usd", 0.0))
    out["Intäkter"] = float(pren) * avg_price

    # ---- Intäkt Känner ----
    ksam = int(preview.get("Känner sammanlagt", 0)) or int(preview.get("Känner", 0))
    rev_per_kanner = float(CFG.get("ECON_REVENUE_PER_KANNER", 30.0))
    out["Intäkt Känner"] = 0.0 if "Vila" in typ else float(ksam) * rev_per_kanner

    # ---- Kostnad män ----
    if "Vila" in typ:
        kost = 0.0
    else:
        timmar = float(preview.get("Summa tid (sek)", 0)) / 3600.0
        bas_mann = (
            int(base.get("Män",0)) + int(base.get("Svarta",0)) +
            int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0))
        )
        tot_personer = bas_mann + int(CFG.get("PROD_STAFF",0))
        cost_per_hour = float(CFG.get("ECON_COST_PER_HOUR", 15.0))
        kost = timmar * tot_personer * cost_per_hour
    out["Kostnad män"] = float(kost)

    # ---- Intäkt företag, Lön, Vinst ----
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
    preview = calc_row_values(base, base["_rad_datum"], CFG["fodelsedatum"], CFG["starttid"])

# 2) Prenumeranter/ekonomi (ny logik)
econ = _compute_subscriber_score_and_econ(base, preview, CFG)
preview.update(econ)

# 3) Tid/kille – "hur mycket saknas till 7 min exkl. händer?"
TPK_ex = float(preview.get("Tid per kille (sek)", 0.0))  # exkl. händer
target_sec = 7 * 60  # 420 sek
deficit = max(0.0, target_sec - TPK_ex)

# Förslag på extra sekunder i DP/DPP/DAP (2x effekt) resp. TAP (3x effekt)
need_dp_like = int((deficit + 1) // 2) if deficit > 0 else 0
need_tap     = int((deficit + 2) // 3) if deficit > 0 else 0
preview["Behöver +sek (DP/DPP/DAP)"] = need_dp_like
preview["Behöver +sek (TAP)"] = need_tap

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
    # totalsiffra inkl alla fält
    tot_men_including = (
        int(base.get("Män",0)) + int(base.get("Svarta",0)) +
        int(base.get(CFG["LBL_PAPPAN"],0)) + int(base.get(CFG["LBL_GRANNAR"],0)) +
        int(base.get(CFG["LBL_NILS_VANNER"],0)) + int(base.get(CFG["LBL_NILS_FAMILJ"],0)) +
        int(base.get(CFG["LBL_BEKANTA"],0)) + int(base.get(CFG["LBL_ESK"],0)) +
        int(base.get("Bonus deltagit",0)) + int(base.get("Personal deltagit",0))
    )
    st.metric("Totalt män (inkl alla)", int(tot_men_including))

# Tid/kille inkl händer (visning) + behov till 7 min
tid_kille_sek = float(preview.get("Tid per kille (sek)", 0.0))          # exkl. händer
hander_kille_sek = float(preview.get("Händer per kille (sek)", 0.0))
tid_kille_inkl_hander = _mmss(tid_kille_sek + (hander_kille_sek if int(base.get("Händer aktiv",1))==1 else 0))

rowC = st.columns(3)
with rowC[0]:
    st.metric("Tid/kille inkl händer", tid_kille_inkl_hander)
with rowC[1]:
    st.metric("Tid/kille ex händer", _mmss(tid_kille_sek))
with rowC[2]:
    if deficit > 0:
        st.metric("Behov till 7:00", f"+{need_dp_like}s (DP/DPP/DAP) / +{need_tap}s (TAP)")
    else:
        st.metric("Behov till 7:00", "0s")

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
    st.metric("Lön Malin (rad)", f"${float(preview.get('Lön Malin',0)):,.2f}")
with rowH[2]:
    st.metric("Super bonus ack", int(CFG.get(SUPER_ACC_KEY, 0)))

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
    st.metric("Vinst", f"${float(preview.get('Vinst',0)):,.2f}")
with e4:
    st.metric("DP/DPP/DAP extra sek → +TPK", f"+{need_dp_like}s")
    st.metric("TAP extra sek → +TPK", f"+{need_tap}s")

# ===== Nils – längst ner i liven =====
try:
    nils_total = int(base.get("Nils",0)) + sum(int(r.get("Nils",0) or 0) for r in st.session_state[ROWS_KEY])
except Exception:
    nils_total = int(base.get("Nils",0))
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

# ==== Del 4/4 – Spara, kopiera (~365 dgr) med progress/ETA, lokala rader & statistik ====

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

def _update_forced_next_start_after_save(saved_row: dict, forced_next_dt: datetime):
    """Efter sparning: uppdatera tvingad NEXT_START_DT."""
    st.session_state[NEXT_START_DT_KEY] = forced_next_dt
    st.session_state[SCENEINFO_KEY] = _current_scene_info()

# =========================
# Spara lokalt & till Sheets
# =========================
st.markdown("---")
st.subheader("Spara rad")

cL, cR = st.columns([1,1])

def _save_to_sheets_for_profile(profile: str, row_dict: dict):
    # wrapper för att kunna byta implementation centralt senare
    append_row_to_profile_data(profile, row_dict)

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

        _update_forced_next_start_after_save(full_row, forced_next)
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

            _update_forced_next_start_after_save(full_row, forced_next)
            st.success("✅ Sparad till Google Sheets.")
        except Exception as e:
            st.error(f"Misslyckades att spara till Sheets: {e}")

# =========================
# Kopiera rader för ~365 dagar (med progress & ETA)
# =========================
st.markdown("---")
st.subheader("📦 Kopiera befintliga rader till ~365 dagar")

COPY_BUF_KEY = "COPIED_ROWS_BUFFER"
PROG_KEY     = "COPY_PROGRESS"

st.session_state.setdefault(COPY_BUF_KEY, [])
st.session_state.setdefault(PROG_KEY, {"running": False, "total": 0, "done": 0, "started_at": None, "last_error": None})

def _parse_date_safe(datestr: str) -> date | None:
    try:
        return datetime.strptime(datestr, "%Y-%m-%d").date()
    except Exception:
        try:
            return pd.to_datetime(datestr).date()
        except Exception:
            return None

def _weekday_sv(d: date) -> str:
    return ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]

def _copy_rows_to_fill_year(rows: list[dict], target_days: int = 365) -> list[dict]:
    """Skapa kopior av existerande rader för att nå ungefär target_days olika datum."""
    if not rows:
        return []

    # sortera efter Datum
    base_rows = [r for r in rows if r.get("Datum")]
    base_rows.sort(key=lambda r: r.get("Datum"))

    # räkna unika datum idag
    existing_dates = []
    for r in base_rows:
        d = _parse_date_safe(str(r.get("Datum","")))
        if d: existing_dates.append(d)
    unique_dates = sorted(set(existing_dates))
    if not unique_dates:
        return []

    last_date = max(unique_dates)
    need_days = max(0, target_days - len(unique_dates))
    if need_days == 0:
        return []

    copied: list[dict] = []
    scene_start = int(len(rows)) + 1
    day_offset = 1
    bi = 0  # index i basraderna (cykliskt)

    while len(copied) < need_days:
        base_row = dict(base_rows[bi])  # kopia
        new_date = last_date + timedelta(days=day_offset)

        base_row["Datum"]    = new_date.isoformat()
        base_row["Veckodag"] = _weekday_sv(new_date)
        base_row["Scen"]     = scene_start
        # behåll "Typ", tider, etc. som i källraden

        # defensiv: säkerställ obligatoriska fält
        for k in SAVE_NUM_COLS:
            if base_row.get(k) is None:
                base_row[k] = 0
        for k in ["Klockan","Klockan inkl älskar/sover"]:
            base_row.setdefault(k, "")

        copied.append(base_row)

        # framåt
        scene_start += 1
        day_offset  += 1
        bi = (bi + 1) % len(base_rows)

    return copied

col_copy1, col_copy2 = st.columns([1,2])
with col_copy1:
    target_days = st.number_input("Dagar att fylla till", min_value=1, max_value=400, value=365, step=1)
    btn_make_local = st.button("🧬 Generera kopior (lokalt)")

with col_copy2:
    st.caption("Steg 1 skapar kopior lokalt. Steg 2 nedan kan spara dessa kopior till Google Sheets med throttling.")

if btn_make_local:
    new_copies = _copy_rows_to_fill_year(st.session_state[ROWS_KEY], target_days=int(target_days))
    if not new_copies:
        st.warning("Inga kopior genererade (kanske redan ≥ önskat antal dagar, eller saknar giltiga datum).")
    else:
        # lägg i buffer och även till lokala rader om du vill se dem direkt
        st.session_state[COPY_BUF_KEY] = new_copies
        st.session_state[ROWS_KEY].extend(new_copies)
        st.success(f"✅ Skapade {len(new_copies)} kopior lokalt.")

# ---- Spara kopior till Sheets med throttling + progress/ETA ----
st.markdown("#### Spara lokala kopior till Google Sheets (throttle)")
throttle_ms = st.number_input("Paus mellan rader (ms)", min_value=0, max_value=5000, value=600, step=50)
long_pause_every = st.number_input("Lång paus var N:e rad", min_value=1, max_value=200, value=20, step=1)
long_pause_ms = st.number_input("Lång paus (ms)", min_value=0, max_value=10000, value=2000, step=100)

btn_save_copies = st.button("📥 Spara kopior → Sheets (risk för kvot)")

def _fmt_eta(sec: float) -> str:
    if sec <= 0:
        return "0s"
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}m {s}s" if m else f"{s}s"

if btn_save_copies:
    copies = st.session_state.get(COPY_BUF_KEY, [])
    if not copies:
        st.warning("Det finns inga kopior i bufferten att spara. Kör 'Generera kopior (lokalt)' först.")
    else:
        prog = st.session_state[PROG_KEY]
        prog.update({"running": True, "total": len(copies), "done": 0, "started_at": datetime.now().timestamp(), "last_error": None})
        st.session_state[PROG_KEY] = prog

        progress_bar = st.progress(0)
        status_box = st.empty()

        start_ts = prog["started_at"]
        errors = 0

        for i, row in enumerate(copies, start=1):
            try:
                _save_to_sheets_for_profile(st.session_state.get(PROFILE_KEY,""), _row_for_sheets(row))
            except Exception as e:
                errors += 1
                prog["last_error"] = str(e)
                # visa fel men fortsätt
                st.warning(f"Misslyckades att spara en kopierad rad till Sheets: {e}")

            # progress
            prog["done"] = i
            st.session_state[PROG_KEY] = prog
            pct = int(100 * i / max(1, prog["total"]))
            progress_bar.progress(min(100, pct))

            # ETA
            elapsed = max(0.001, datetime.now().timestamp() - start_ts)
            rate = i / elapsed  # rows/s
            remaining = prog["total"] - i
            eta_sec = remaining / rate if rate > 0 else 0

            status_box.info(
                f"Framsteg: {i}/{prog['total']} ({pct}%) • Fel: {errors} • "
                f"ETA: {_fmt_eta(eta_sec)}"
            )

            # throttling
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000.0)
            if long_pause_every > 0 and (i % int(long_pause_every) == 0) and long_pause_ms > 0:
                time.sleep(long_pause_ms / 1000.0)

        prog["running"] = False
        st.session_state[PROG_KEY] = prog
        st.success(f"✅ Klart: sparade {prog['done']}/{prog['total']} kopior till Sheets. Fel: {errors}")

# Visa liten “faktaruta” även när inte aktiv loop körs
prog = st.session_state.get(PROG_KEY, {})
if prog.get("total", 0) > 0:
    done = int(prog.get("done", 0)); total = int(prog.get("total", 0))
    pct = int(100 * done / max(1, total))
    if prog.get("running"):
        elapsed = max(0.001, datetime.now().timestamp() - prog.get("started_at", datetime.now().timestamp()))
        rate = done / elapsed if elapsed > 0 else 0
        remaining = total - done
        eta = remaining / rate if rate > 0 else 0
        st.info(f"Status: {done}/{total} ({pct}%) • ETA: {_fmt_eta(eta)}")
    else:
        st.caption(f"Senaste körning: {done}/{total} ({pct}%). Senaste fel: {prog.get('last_error') or '–'}")

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
            for k,v in stats.items():
                st.write(f"**{k}**: {v}")
        else:
            st.caption("Statistik-modulen returnerade inget att visa ännu.")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")
