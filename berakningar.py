# berakningar.py
from datetime import datetime, timedelta

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


def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Bygger alla beräknade fält.

    Ekonomi-regler (överenskommet tidigare):
    - Hårdhet = poäng om DP/DPP/DAP/TAP finns + trösklar på Totalt Män + 3p om Svarta>0
    - Prenumeranter (rad) = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    - Intäkter = Prenumeranter * Avgift
    - Kostnad män = (Summa tid (sek) / 3600) * ( (Män + Svarta + Bekanta + Eskilstuna) + PROD_STAFF ) * 15
    - Intäkt Känner = Känner sammanlagt * 30 USD
    - Intäkt företag = Intäkter - Kostnad män - Intäkt Känner
    - Lön Malin = clamp(150, 0.08 * Intäkt företag, 800) * åldersfaktor
    - Vinst = Intäkt företag - Lön Malin

    Nya regler:
    - Suger per kille (sek) = 0.8*(S/Total) + 0.8*(D/Total) + 0.8*(TP/Total)
    - Händer per kille (sek) = 2 * (Suger per kille) om "Händer aktiv"=1 annars 0
    - "Tid per kille" i liven = (gamla "Tid per kille (sek)") + "Händer per kille"
    - Vila-scenarier (Typ börjar med "Vila"): Hårdhet=0, Prenumeranter=0, Intäkter=0, Kostnad män=0, Lön Malin=0, Vinst=0
    """

    # ---------------- Råvärden ----------------
    # antal
    man       = _safe_int(grund.get("Män", 0))
    svarta    = _safe_int(grund.get("Svarta", 0))
    fitta     = _safe_int(grund.get("Fitta", 0))
    rumpa     = _safe_int(grund.get("Rumpa", 0))
    dp        = _safe_int(grund.get("DP", 0))
    dpp       = _safe_int(grund.get("DPP", 0))
    dap       = _safe_int(grund.get("DAP", 0))
    tap       = _safe_int(grund.get("TAP", 0))

    # etikett-stöd (om appen skickar värden med omdöpta etiketter)
    pappan    = _safe_int(grund.get("Pappans vänner", grund.get(grund.get("LBL_PAPPAN","Pappans vänner"), 0)))
    grannar   = _safe_int(grund.get("Grannar",        grund.get(grund.get("LBL_GRANNAR","Grannar"), 0)))
    n_vanner  = _safe_int(grund.get("Nils vänner",    grund.get(grund.get("LBL_NILS_VANNER","Nils vänner"), 0)))
    n_familj  = _safe_int(grund.get("Nils familj",    grund.get(grund.get("LBL_NILS_FAMILJ","Nils familj"), 0)))
    bekanta   = _safe_int(grund.get("Bekanta",        grund.get(grund.get("LBL_BEKANTA","Bekanta"), 0)))
    esk       = _safe_int(grund.get("Eskilstuna killar", grund.get(grund.get("LBL_ESK","Eskilstuna killar"), 0)))

    bonus_d   = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d    = _safe_int(grund.get("Personal deltagit", 0))

    alskar    = _safe_int(grund.get("Älskar", 0))
    sover     = _safe_int(grund.get("Sover med", 0))

    hander_on = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))

    # tider (sek)
    tid_s     = _safe_int(grund.get("Tid S", 0))
    tid_d     = _safe_int(grund.get("Tid D", 0))
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))

    # meta
    avgift    = _safe_float(grund.get("Avgift", 0.0))
    prod_staff= _safe_int(grund.get("PROD_STAFF", 0))
    typ_scen  = str(grund.get("Typ", "") or "")

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # ---------------- Känner ----------------
    kanner = pappan + grannar + n_vanner + n_familj
    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---------------- Totalt män ----------------
    totalt_man = max(0, man + kanner + svarta + bekanta + esk + bonus_d + pers_d)

    # ---------------- Summa S/D/TP ----------------
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---------------- Hångel ----------------
    # (OBS: inte "Känner" enligt tidigare spec)
    total_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d
    hang_per_kille_sek = 0 if total_for_hang <= 0 else 10800.0 / total_for_hang  # 3h

    # ---------------- Tid per kille (gamla) + nya "Suger/Händer" ----------------
    if totalt_man > 0:
        tid_per_kille_gammal = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille = 0.8 * (summa_s / totalt_man) + 0.8 * (summa_d / totalt_man) + 0.8 * (summa_tp / totalt_man)
    else:
        tid_per_kille_gammal = 0.0
        suger_per_kille = 0.0

    hander_per_kille = 2.0 * suger_per_kille if hander_on else 0.0
    tid_per_kille_total = tid_per_kille_gammal + hander_per_kille  # <- detta visar vi i liven

    # ---------------- Älskar/Sover ----------------
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # ---------------- Klockan ----------------
    try:
        if isinstance(rad_datum, datetime):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        klockan_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan_str = klockan_dt.strftime("%H:%M")
        klockan2_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"
        klockan2_str = "-"

    # ---------------- Hårdhet ----------------
    hardhet = 0
    if dp > 0:  hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    if svarta > 0: hardhet += 3
    # trösklar på totalt män
    for thr, pts in [(100,1),(200,2),(400,4),(700,7),(1000,10)]:
        if totalt_man > thr:
            hardhet += pts

    # ---------------- Prenumeranter / Ekonomi ----------------
    pren = (dp + dpp + dap + tap + totalt_man) * hardhet
    intakter = pren * avgift
    # kostnad män
    timmar = summa_tid_sek / 3600.0
    kostnad_man = timmar * ((man + svarta + bekanta + esk) + prod_staff) * 15.0
    intakt_kanner = kanner_sammanlagt * 30.0
    intakt_foretag = intakter - kostnad_man - intakt_kanner

    # åldersfaktor
    # (vi räknar ålder utifrån rad_datum och fodelsedatum)
    try:
        alder = rad_datum.year - fodelsedatum.year - ((rad_datum.month, rad_datum.day) < (fodelsedatum.month, fodelsedatum.day))
    except Exception:
        alder = 30
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

    lon_malin_raw = max(150.0, min(800.0, 0.08 * intakt_foretag))
    lon_malin = lon_malin_raw * faktor
    vinst = intakt_foretag - lon_malin

    # ---------------- Vila-scenarier = noll ekonomi ----------------
    if typ_scen.lower().startswith("vila"):
        hardhet = 0
        pren = 0
        intakter = 0.0
        kostnad_man = 0.0
        lon_malin = 0.0
        intakt_foretag = 0.0
        vinst = 0.0

    # ---------------- Out ----------------
    out = {}
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    out["Totalt Män"] = totalt_man
    out["Känner"] = kanner
    out["Känner sammanlagt"] = kanner_sammanlagt

    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"]       = _hhmm(summa_tid_sek)

    out["Tid per kille (sek)"] = float(tid_per_kille_total)  # inkluderar händer
    out["Tid per kille"]       = _mmss(tid_per_kille_total)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    out["Suger per kille (sek)"]  = float(suger_per_kille)
    out["Händer per kille (sek)"] = float(hander_per_kille)
    out["Händer aktiv"] = int(1 if hander_on else 0)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi
    out["Hårdhet"]        = int(hardhet)
    out["Prenumeranter"]  = int(pren)
    out["Intäkter"]       = float(intakter)
    out["Kostnad män"]    = float(kostnad_man)
    out["Intäkt Känner"]  = float(intakt_kanner)
    out["Intäkt företag"] = float(intakt_foretag)
    out["Lön Malin"]      = float(lon_malin)
    out["Vinst"]          = float(vinst)

    return out
