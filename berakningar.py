from datetime import datetime, timedelta
import random

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
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _compute_age(rad_datum, fodelsedatum):
    try:
        rd = rad_datum.date() if hasattr(rad_datum, "date") else rad_datum
        return rd.year - fodelsedatum.year - ((rd.month, rd.day) < (fodelsedatum.month, fodelsedatum.day))
    except Exception:
        return 0

def _age_factor(age: int) -> float:
    if age <= 18:   return 1.00
    if age <= 23:   return 0.90
    if age <= 27:   return 0.85
    if age <= 30:   return 0.80
    if age <= 32:   return 0.75
    if age <= 35:   return 0.70
    return 0.60


def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Förväntade extra nycklar från app.py (för BM/bonus):
      - HIST_PREN_TOTAL:  historisk SUM( Prenumeranter ) från redan sparade rader
      - BM_SUM:           ackumulerad summa av alla slumpade BM hittills (float)
      - BM_COUNT:         ackumulerat antal pren som BM_SUM baseras på (int)
      - BONUS_RATE_PCT:   procent (t.ex. 1 för 1%) för bonus-killar
      - LANGD_M:          längd i meter (för Mål vikt)
    """

    typ        = (grund.get("Typ") or "").lower()

    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))
    rumpa   = _safe_int(grund.get("Rumpa", 0))
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    pappan  = _safe_int(grund.get("Pappans vänner", grund.get(grund.get("LBL_PAPPAN","Pappans vänner"), 0)))
    grannar = _safe_int(grund.get("Grannar",        grund.get(grund.get("LBL_GRANNAR","Grannar"), 0)))
    n_van   = _safe_int(grund.get("Nils vänner",    grund.get(grund.get("LBL_NILS_VANNER","Nils vänner"), 0)))
    n_fam   = _safe_int(grund.get("Nils familj",    grund.get(grund.get("LBL_NILS_FAMILJ","Nils familj"), 0)))
    bek     = _safe_int(grund.get("Bekanta",        grund.get(grund.get("LBL_BEKANTA","Bekanta"), 0)))
    esk     = _safe_int(grund.get("Eskilstuna killar", grund.get(grund.get("LBL_ESK","Eskilstuna killar"), 0)))

    bonus_d = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d  = _safe_int(grund.get("Personal deltagit", 0))

    alskar  = _safe_int(grund.get("Älskar", 0))
    sover   = _safe_int(grund.get("Sover med", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))
    tid_d   = _safe_int(grund.get("Tid D", 0))
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))

    avgift  = _safe_float(grund.get("Avgift", 0.0))
    prod    = _safe_int(grund.get("PROD_STAFF", 0))

    # BM/bonus inputs
    hist_pren_total = _safe_int(grund.get("HIST_PRENUMERANTER", grund.get("HIST_PREN_TOTAL", 0)))
    bm_sum_hist     = _safe_float(grund.get("BM_SUM", 0.0))
    bm_cnt_hist     = _safe_int(grund.get("BM_COUNT", 0))
    bonus_rate_pct  = _safe_float(grund.get("BONUS_RATE_PCT", 1.0))
    langd_m         = _safe_float(grund.get("LANGD_M", 1.70), 1.70)

    datum_str = grund.get("Datum", "")
    veckodag  = grund.get("Veckodag", "")

    # Känner (rad)
    kanner = pappan + grannar + n_van + n_fam

    # Totalt män (rad)
    totalt_man = man + kanner + svarta + bek + esk + bonus_d + pers_d
    if totalt_man < 0: totalt_man = 0

    # Summa S/D/TP + tid
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # Hårdhet
    hardhet = 0
    if dp   > 0: hardhet += 3
    if dpp  > 0: hardhet += 5
    if dap  > 0: hardhet += 7
    if tap  > 0: hardhet += 9
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 2
    if totalt_man > 400:  hardhet += 4
    if totalt_man > 700:  hardhet += 7
    if totalt_man > 1000: hardhet += 10
    if svarta > 0:        hardhet += 3

    # Prenumeranter (rad)
    pren = (dp + dpp + dap + tap + totalt_man) * hardhet

    # Vila-override
    is_vila = ("vila" in typ)
    if is_vila:
        pren = 0

    # Ekonomi
    if is_vila:
        intakter = 0.0
        intakt_kanner = 0.0
        timmar = 0.0
        utgift_man = 0.0
        intakt_foret = 0.0
        lon_malin = 0.0
        vinst = 0.0
    else:
        intakter = pren * avgift
        intakt_kanner = kanner * 30.0
        timmar = (summa_tid_sek / 3600.0)
        bas_antal = (man + svarta + bek + esk) + prod
        utgift_man = timmar * bas_antal * 15.0
        intakt_foret = intakter - utgift_man - intakt_kanner
        alder = _safe_int(_compute_age(rad_datum, fodelsedatum), 0)
        grundlon = max(150.0, min(800.0, 0.08 * max(0.0, intakt_foret)))
        lon_malin = grundlon * _age_factor(alder)
        vinst = intakt_foret - lon_malin

    # Hångel/per-kille
    tot_for_hang = man + svarta + bek + esk + bonus_d + pers_d
    hang_per_k = 0 if tot_for_hang <= 0 else 10800.0 / tot_for_hang
    if totalt_man > 0:
        tid_per_k = (summa_s + 2*summa_d + 3*summa_tp) / float(totalt_man)
        suger_per_k = summa_tid_sek / float(totalt_man)
    else:
        tid_per_k = 0.0
        suger_per_k = 0.0

    # Älskar/Sover
    tid_alskar = (alskar + sover) * 20 * 60

    # Klocka
    try:
        if hasattr(rad_datum, "date"):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        k1 = (base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)).strftime("%H:%M")
        k2 = (base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar)).strftime("%H:%M")
    except Exception:
        k1 = "-"
        k2 = "-"

    # ----- BONUS ny (beräknad enligt % i inställningar) -----
    bonus_new = 0
    if not is_vila and pren > 0 and bonus_rate_pct > 0:
        bonus_new = int((bonus_rate_pct / 100.0) * pren)

    # ----- BM mål (TOTAL) & Mål vikt (TOTAL) – bara nya pren slumpas -----
    # hur många pren historiskt + denna rad?
    target_total_pren = hist_pren_total + pren
    delta_new = max(0, target_total_pren - bm_cnt_hist)
    bm_sum_add = 0.0
    bm_cnt_add = 0
    bm_goal_total = None
    mal_vikt_total = None

    if delta_new > 0:
        # slumpa 12–18 för enbart "nya" pren
        for _ in range(int(delta_new)):
            bm_sum_add += random.randint(12, 18)
        bm_cnt_add = int(delta_new)

    denom = bm_cnt_hist + bm_cnt_add
    if denom > 0:
        bm_goal_total = (bm_sum_hist + bm_sum_add) / float(denom)
        mal_vikt_total = bm_goal_total * (langd_m ** 2)

    # ---- OUT ----
    out = {
        "Datum": datum_str,
        "Veckodag": veckodag,

        "Totalt Män": int(totalt_man),
        "Känner": int(kanner),

        "Summa S (sek)": int(summa_s),
        "Summa D (sek)": int(summa_d),
        "Summa TP (sek)": int(summa_tp),
        "Summa tid (sek)": int(summa_tid_sek),
        "Summa tid": _hhmm(summa_tid_sek),

        "Tid per kille (sek)": float(tid_per_k),
        "Tid per kille": _mmss(tid_per_k),

        "Hångel (sek/kille)": float(hang_per_k),
        "Hångel (m:s/kille)": _mmss(hang_per_k),

        "Suger": int(summa_tid_sek),
        "Suger per kille (sek)": float(suger_per_k),

        "Tid Älskar (sek)": int(tid_alskar),

        "Klockan": k1,
        "Klockan inkl älskar/sover": k2,

        "Hårdhet": int(hardhet),
        "Prenumeranter": int(pren),
        "Intäkter": float(intakter),
        "Intäkt Känner": float(intakt_kanner),
        "Utgift män": float(utgift_man),
        "Intäkt företaget": float(intakt_foret),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # bonus/BM som app.py använder vid spar
        "Bonus ny": int(bonus_new),
        "BM_sum_add": float(bm_sum_add),
        "BM_count_add": int(bm_cnt_add),
    }
    if bm_goal_total is not None:
        out["BM mål (total)"] = float(bm_goal_total)
    if mal_vikt_total is not None:
        out["Mål vikt (total)"] = float(mal_vikt_total)

    return out
