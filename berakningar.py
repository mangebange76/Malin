# berakningar.py
from datetime import datetime, timedelta

# ---------- Hjälp ----------

def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(float(total_seconds))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    try:
        s = max(0, int(round(float(total_seconds))))
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


# ---------- Hårdhet ----------

def _hardhet(dp, dpp, dap, tap, totalt_man, svarta):
    poang = 0
    if dp  > 0: poang += 3
    if dpp > 0: poang += 5
    if dap > 0: poang += 7
    if tap > 0: poang += 9
    if totalt_man > 100:  poang += 1
    if totalt_man > 200:  poang += 2
    if totalt_man > 400:  poang += 4
    if totalt_man > 700:  poang += 7
    if totalt_man > 1000: poang += 10
    if svarta > 0:        poang += 3
    return poang


# ---------- Lön-justering mot ålder ----------

def _alder(datum, fodelsedatum):
    try:
        y = datum.year - fodelsedatum.year - ((datum.month, datum.day) < (fodelsedatum.month, fodelsedatum.day))
        return max(0, y)
    except Exception:
        return 0

def _lon_malin(intakt_foretag, alder):
    """8% av intäkt företag inom 150–800 USD och viktning efter ålder."""
    grund = max(150.0, min(800.0, 0.08 * max(0.0, float(intakt_foretag))))

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

    return round(grund * faktor, 2)


# ---------- Huvudberäkning ----------

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Beräknar alla nyckeltal för en rad (live + som sparas).
    Förväntar samma fältnamn som appen skickar in.
    """

    # --- Inputs (säkra) ---
    man       = _safe_int(grund.get("Män", 0))
    svarta    = _safe_int(grund.get("Svarta", 0))
    fitta     = _safe_int(grund.get("Fitta", 0))
    rumpa     = _safe_int(grund.get("Rumpa", 0))
    dp        = _safe_int(grund.get("DP", 0))
    dpp       = _safe_int(grund.get("DPP", 0))
    dap       = _safe_int(grund.get("DAP", 0))
    tap       = _safe_int(grund.get("TAP", 0))

    # etiketter kan vara egna — prova båda
    pappan   = _safe_int(grund.get("Pappans vänner", grund.get(grund.get("LBL_PAPPAN","Pappans vänner"), 0)))
    grannar  = _safe_int(grund.get("Grannar",        grund.get(grund.get("LBL_GRANNAR","Grannar"), 0)))
    n_vanner = _safe_int(grund.get("Nils vänner",    grund.get(grund.get("LBL_NILS_VANNER","Nils vänner"), 0)))
    n_familj = _safe_int(grund.get("Nils familj",    grund.get(grund.get("LBL_NILS_FAMILJ","Nils familj"), 0)))
    bekanta  = _safe_int(grund.get("Bekanta",        grund.get(grund.get("LBL_BEKANTA","Bekanta"), 0)))
    esk      = _safe_int(grund.get("Eskilstuna killar", grund.get(grund.get("LBL_ESK","Eskilstuna killar"), 0)))

    bonus_d  = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d   = _safe_int(grund.get("Personal deltagit", 0))

    alskar   = _safe_int(grund.get("Älskar", 0))
    sover    = _safe_int(grund.get("Sover med", 0))

    hander_on = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))

    tid_s    = _safe_int(grund.get("Tid S", 0))
    tid_d    = _safe_int(grund.get("Tid D", 0))
    dt_tid   = _safe_int(grund.get("DT tid (sek/kille)", 0))

    avgift     = _safe_float(grund.get("Avgift", 0.0))
    prod_staff = _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # --- Känner ---
    kanner = pappan + grannar + n_vanner + n_familj

    # maxvärden för statistik (om skickas)
    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # --- Totalt Män (rad) ---
    totalt_man = man + kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # --- Summa S/D/TP & tid ---
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # --- Hångel (totalt 3h fördelat – utan Känner) ---
    hang_div = man + svarta + bekanta + esk + bonus_d + pers_d
    hang_per_kille_sek = 0 if hang_div <= 0 else 10800.0 / hang_div  # 3h = 10800 s

    # --- Tid per kille (enligt din regel) ---
    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0

    # --- NYTT: Suger/Händer per kille ---
    if totalt_man > 0:
        suger_per_kille = 0.8 * (summa_s / totalt_man) + 0.8 * (summa_d / totalt_man) + 0.8 * (summa_tp / totalt_man)
    else:
        suger_per_kille = 0.0

    hander_per_kille = (2.0 * suger_per_kille) if hander_on else 0.0
    tid_per_kille_inkl_hander = tid_per_kille_sek + hander_per_kille

    # --- Älskar/Sover ---
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # --- Klockan ---
    try:
        if isinstance(rad_datum, datetime):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        klockan_dt  = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan2_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan_str  = klockan_dt.strftime("%H:%M")
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan_str = klockan2_str = "-"

    # --- Hårdhet/ekonomi ---
    hardhet = _hardhet(dp, dpp, dap, tap, totalt_man, svarta)

    prenumeranter = int(max(0, hardhet * (dp + dpp + dap + tap + totalt_man)))

    intakter = float(prenumeranter) * avgift

    timmar = float(summa_tid_sek) / 3600.0
    kostnad_man = 15.0 * timmar * ((man + svarta + bekanta + esk) + prod_staff)

    intakt_kanner = 30.0 * kanner_sammanlagt

    intakt_foretag = max(0.0, intakter - kostnad_man - intakt_kanner)

    alder = _alder(rad_datum if hasattr(rad_datum, "year") else datetime.now().date(), fodelsedatum)
    lon_malin = _lon_malin(intakt_foretag, alder)

    vinst = max(0.0, intakt_foretag - lon_malin)

    # --- Out ---
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

    out["Tid per kille (sek)"]        = float(tid_per_kille_sek)
    out["Tid per kille"]              = _mmss(tid_per_kille_sek)
    out["Hångel (sek/kille)"]         = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]         = _mmss(hang_per_kille_sek)
    out["Suger per kille (sek)"]      = float(suger_per_kille)
    out["Händer per kille (sek)"]     = float(hander_per_kille)
    out["Tid/kille inkl händer (sek)"]= float(tid_per_kille_inkl_hander)
    out["Tid/kille inkl händer"]      = _mmss(tid_per_kille_inkl_hander)
    out["Händer aktiv"]               = int(1 if hander_on else 0)

    out["Suger"] = int(summa_tid_sek)  # behåller som ”totalt sek” för kompatibilitet

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    out["Hårdhet"]       = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Intäkter"]      = float(round(intakter, 2))
    out["Kostnad män"]   = float(round(kostnad_man, 2))
    out["Intäkt Känner"] = float(round(intakt_kanner, 2))
    out["Intäkt företag"]= float(round(intakt_foretag, 2))
    out["Lön Malin"]     = float(round(lon_malin, 2))
    out["Vinst"]         = float(round(vinst, 2))

    return out
