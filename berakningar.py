import datetime

def _safe_int(val, default=0):
    try:
        return int(val) if val not in (None, "", "nan") else default
    except Exception:
        return default

def _safe_float(val, default=0.0):
    try:
        return float(val) if val not in (None, "", "nan") else default
    except Exception:
        return default

def _format_time(seconds):
    """Returnera tid i mm:ss-format."""
    try:
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"
    except Exception:
        return "00:00"

def _format_hours_minutes(seconds):
    """Returnera tid i hh:mm-format."""
    try:
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "00:00"

# --------------------------------------------------------
# Datumvalidering (för att aldrig hamna bakåt i tiden fel)
# --------------------------------------------------------
def validate_startdatum(startdatum: datetime.date) -> datetime.date:
    min_date = datetime.date(1990, 1, 1)
    if startdatum < min_date:
        return min_date
    return startdatum

def validate_fodelsedatum(fodelsedatum: datetime.date) -> datetime.date:
    min_date = datetime.date(1970, 1, 1)
    if fodelsedatum < min_date:
        return min_date
    return fodelsedatum

# --------------------------------------------------------
# Huvudberäkning för en rad
# --------------------------------------------------------
def berakna_radvarden(rad: dict, grund: dict) -> dict:
    out = {}

    # ---- Grunddata ----
    man      = _safe_int(rad.get("Män"))
    svarta   = _safe_int(rad.get("Svarta"))
    bekanta  = _safe_int(rad.get("Bekanta"))
    eskilstuna = _safe_int(rad.get("Eskilstuna killar"))
    bonus_deltagit = _safe_int(rad.get("Bonus deltagit"))
    personal_deltagit = _safe_int(rad.get("Personal deltagit"))

    pappan   = _safe_int(rad.get("Pappans vänner"))
    grannar  = _safe_int(rad.get("Grannar"))
    n_vanner = _safe_int(rad.get("Nils vänner"))
    n_familj = _safe_int(rad.get("Nils familj"))

    dp   = _safe_int(rad.get("DP"))
    dpp  = _safe_int(rad.get("DPP"))
    dap  = _safe_int(rad.get("DAP"))
    tap  = _safe_int(rad.get("TAP"))

    tid_s = _safe_int(rad.get("Tid S"))
    tid_d = _safe_int(rad.get("Tid D"))
    dt_tid = _safe_int(grund.get("DT_tid", 0))
    dt_vila = _safe_int(grund.get("DT_vila", 0))
    vila   = _safe_int(rad.get("Vila"))

    alskar   = _safe_int(rad.get("Älskar"))
    sovermed = _safe_int(rad.get("Sover med"))

    # ---- Känner ----
    kanner = pappan + grannar + n_vanner + n_familj
    if kanner < 0:
        kanner = 0

    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj
    if kanner_sammanlagt <= 0:
        kanner_sammanlagt = kanner

    # ---- Totalt män ----
    totalt_man = (
        man + kanner + svarta + bekanta + eskilstuna + bonus_deltagit + personal_deltagit
    )

    # ---- Summa S, D, TP ----
    summa_s  = tid_s * (dp + dpp + dap)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap

    summa_tid_sek = summa_s + summa_d + summa_tp
    summa_tid_h = summa_tid_sek / 3600.0

    # ---- Tid per kille & Suger ----
    tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / max(totalt_man, 1)
    tid_per_kille_fmt = _format_time(tid_per_kille_sek)

    suger_per_kille = summa_tid_sek / max(totalt_man, 1)

    # ---- Hårdhet ----
    hardhet = 0
    if dp > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    if totalt_man > 100: hardhet += 1
    if totalt_man > 200: hardhet += 2
    if totalt_man > 400: hardhet += 4
    if totalt_man > 700: hardhet += 7
    if totalt_man > 1000: hardhet += 10
    if svarta > 0: hardhet += 3

    # ---- Prenumeranter ----
    nya_pren = (dp + dpp + dap + tap + totalt_man) * hardhet

    # ---- Intäkter ----
    avgift = _safe_float(grund.get("AVGIFT_USD", 39.99))
    intakter = nya_pren * avgift

    # ---- Kostnad män ----
    personal_max = _safe_int(grund.get("MAX_PERSONAL", 0))
    kostnad_man = summa_tid_h * ((man + svarta + bekanta + eskilstuna) + personal_max) * 15.0

    # ---- Intäkt Känner ----
    intakt_kanner = kanner_sammanlagt * 30.0

    # ---- Intäkt Företaget ----
    intakt_foretaget = intakter - kostnad_man - intakt_kanner

    # ---- Lön Malin ----
    # ålder från inställningar
    startdatum = validate_startdatum(grund.get("STARTDATUM", datetime.date.today()))
    fodelsedatum = validate_fodelsedatum(grund.get("FODELSEDATUM", datetime.date(1970,1,1)))
    alder = (startdatum.year - fodelsedatum.year) - (
        (startdatum.month, startdatum.day) < (fodelsedatum.month, fodelsedatum.day)
    )

    grundlon = max(150, min(800, intakt_foretaget * 0.08))
    faktor = 1.0
    if 19 <= alder <= 23: faktor = 0.9
    elif 24 <= alder <= 27: faktor = 0.85
    elif 28 <= alder <= 30: faktor = 0.8
    elif 31 <= alder <= 32: faktor = 0.75
    elif 33 <= alder <= 35: faktor = 0.7
    elif alder >= 36: faktor = 0.6
    lon_malin = grundlon * faktor

    # ---- Vinst ----
    vinst = intakt_foretaget - lon_malin

    # ---- Output ----
    out["Känner"] = kanner
    out["Känner sammanlagt"] = kanner_sammanlagt
    out["Totalt män"] = totalt_man
    out["Summa tid (sek)"] = summa_tid_sek
    out["Tid per kille"] = tid_per_kille_fmt
    out["Suger per kille (sek)"] = suger_per_kille
    out["Hårdhet"] = hardhet
    out["Prenumeranter"] = nya_pren
    out["Intäkter"] = intakter
    out["Kostnad män"] = kostnad_man
    out["Intäkt Känner"] = intakt_kanner
    out["Intäkt Företaget"] = intakt_foretaget
    out["Lön Malin"] = lon_malin
    out["Vinst"] = vinst

    return out
