# berakningar.py
from datetime import datetime, timedelta

# ------------------------- Hjälpfunktioner -------------------------

def _mmss(total_seconds: float) -> str:
    """mm:ss av antal sekunder."""
    try:
        s = max(0, int(round(float(total_seconds))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    """HH:MM av antal sekunder."""
    try:
        s = max(0, int(round(float(total_seconds))))
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    try:
        return int(float(str(x).replace(",", ".")))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default


# ------------------------- Hårdhet -------------------------

def _calc_hardhet(dp, dpp, dap, tap, totalt_man, svarta) -> int:
    """Regelbaserad poängsumma för Hårdhet."""
    h = 0
    if dp  > 0: h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9

    # thresholds för Totalt män
    if totalt_man > 100:  h += 1
    if totalt_man > 200:  h += 2
    if totalt_man > 400:  h += 4
    if totalt_man > 700:  h += 7
    if totalt_man > 1000: h += 10

    if svarta > 0: h += 3
    return h


# ------------------------- Lön Malin -------------------------

def _age_years(on_date, birth_date) -> int:
    try:
        return on_date.year - birth_date.year - (
            (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
        )
    except Exception:
        return 0

def _malin_cut(age: int) -> float:
    """
    Åldersfaktor:
      18 => 1.00
      19–23 => 0.90
      24–27 => 0.85
      28–30 => 0.80
      31–32 => 0.75
      33–35 => 0.70
      36–    => 0.60
    """
    if age <= 18: return 1.00
    if 19 <= age <= 23: return 0.90
    if 24 <= age <= 27: return 0.85
    if 28 <= age <= 30: return 0.80
    if 31 <= age <= 32: return 0.75
    if 33 <= age <= 35: return 0.70
    return 0.60

def _calc_lon_malin(intakt_foretag: float, age_years: int) -> float:
    """Bas = clamp(8% av intäkt företag, 150..800), därefter åldersfaktor."""
    base = max(150.0, min(800.0, 0.08 * float(intakt_foretag)))
    return base * _malin_cut(age_years)


# ------------------------- Huvudberäkning -------------------------

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med alla beräknade fält för liven / sparraden.

    Viktiga definitioner:
      - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
        (stöd för om etiketter har bytts i appen)
      - Känner sammanlagt (statistik) = SUM(MAX_*) för dessa fyra (om skickas in; annars 0)
      - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit
      - Summa S (sek)  = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
      - Summa D (sek)  = Tid D * (DP + DPP + DAP)
      - Summa TP (sek) = Tid D * TAP
      - Summa tid (sek) = Summa S + Summa D + Summa TP
      - Hångel total = 3h => per kille = 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
        (Känner räknas ej här, enligt specifikationen)
      - NYTT: Suger per kille (sek) = 0.8*(S/TM) + 0.8*(D/TM) + 0.8*(TP/TM)
              Händer per kille (sek) = 2 * (Suger per kille) om “Händer aktiv”=1, annars 0
              “Tid per kille” (i liven) = (gamla tid per kille) + (Händer per kille)
      - Prenumeranter (rad) = Hårdhet * (DP + DPP + DAP + TAP + Totalt Män)
      - Intäkter = Prenumeranter * Avgift
      - Kostnad män = (Summa tid i timmar) * ((Män + Svarta + Bekanta + Eskilstuna) + PROD_STAFF) * 15 USD
        (OBS: Känner/Bonus deltagit/Personal deltagit ingår inte i denna multiplikator)
      - Intäkt Känner = Känner sammanlagt * 30 USD
      - Intäkt företag = Intäkter - Kostnad män - Intäkt Känner
      - Lön Malin = clamp(8% av Intäkt företag, 150..800) * åldersfaktor (se tabell ovan)
      - Vinst = Intäkt företag - Lön Malin
      - Klockan = starttid + 3h (hångel) + 1h (vila) + Summa tid (sek)
      - “Vila”-scenarier: Prenumeranter=0, Intäkter=0, Kostnad män=0, Lön=0 (övrigt beräknas som vanligt)
    """

    # ----------- Hämta råvärden (med etikettstöd) -----------
    man       = _safe_int(grund.get("Män", 0))
    svarta    = _safe_int(grund.get("Svarta", 0))
    fitta     = _safe_int(grund.get("Fitta", 0))
    rumpa     = _safe_int(grund.get("Rumpa", 0))
    dp        = _safe_int(grund.get("DP", 0))
    dpp       = _safe_int(grund.get("DPP", 0))
    dap       = _safe_int(grund.get("DAP", 0))
    tap       = _safe_int(grund.get("TAP", 0))

    # Stöd för om appen har bytt etiketter i CFG
    lbl_p = grund.get("LBL_PAPPAN", "Pappans vänner")
    lbl_g = grund.get("LBL_GRANNAR", "Grannar")
    lbl_nv= grund.get("LBL_NILS_VANNER", "Nils vänner")
    lbl_nf= grund.get("LBL_NILS_FAMILJ", "Nils familj")
    lbl_b = grund.get("LBL_BEKANTA", "Bekanta")
    lbl_esk = grund.get("LBL_ESK", "Eskilstuna killar")

    pappan   = _safe_int(grund.get("Pappans vänner", grund.get(lbl_p, 0)))
    grannar  = _safe_int(grund.get("Grannar",        grund.get(lbl_g, 0)))
    n_vanner = _safe_int(grund.get("Nils vänner",    grund.get(lbl_nv, 0)))
    n_familj = _safe_int(grund.get("Nils familj",    grund.get(lbl_nf, 0)))
    bekanta  = _safe_int(grund.get("Bekanta",        grund.get(lbl_b, 0)))
    esk      = _safe_int(grund.get("Eskilstuna killar", grund.get(lbl_esk, 0)))

    bonus_d  = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d   = _safe_int(grund.get("Personal deltagit", 0))

    alskar   = _safe_int(grund.get("Älskar", 0))
    sover    = _safe_int(grund.get("Sover med", 0))

    # Händer aktiv (1 = på, 0 = av)
    hander_on = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))

    # Tider
    tid_s   = _safe_int(grund.get("Tid S", 0))
    tid_d   = _safe_int(grund.get("Tid D", 0))
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # reserverad

    # Ekonomi/metadata
    avgift      = _safe_float(grund.get("Avgift", 0.0))
    prod_staff  = _safe_int(grund.get("PROD_STAFF", 0))
    datum_str   = grund.get("Datum")
    veckodag    = grund.get("Veckodag", "")
    scen_typ    = str(grund.get("Typ", "")).lower()

    # ----------- Känner & Känner sammanlagt -----------
    kanner = pappan + grannar + n_vanner + n_familj

    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ----------- Totalt män (rad) -----------
    totalt_man = man + kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ----------- Summa S/D/TP + total tid -----------
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ----------- Hångel (3h) -----------
    hang_divisor = man + svarta + bekanta + esk + bonus_d + pers_d  # exkl. "Känner"
    hang_per_kille_sek = 0.0 if hang_divisor <= 0 else 10800.0 / float(hang_divisor)

    # ----------- Gamla "tid per kille" enligt viktning -----------
    if totalt_man > 0:
        tid_per_kille_sek_old = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
    else:
        tid_per_kille_sek_old = 0.0

    # ----------- NYTT: Suger/Händer per kille -----------
    if totalt_man > 0:
        suger_per_kille = 0.8 * (summa_s / totalt_man) \
                        + 0.8 * (summa_d / totalt_man) \
                        + 0.8 * (summa_tp / totalt_man)
    else:
        suger_per_kille = 0.0

    hander_per_kille = (2.0 * suger_per_kille) if hander_on else 0.0

    # "Tid per kille" som visas i liven = gamla tid per kille + händer
    tid_per_kille_display = tid_per_kille_sek_old + hander_per_kille

    # ----------- Älskar/Sover, klocka -----------
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # Klockan (start + 3h + 1h + summa tid)
    try:
        if isinstance(rad_datum, datetime):
            start_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            start_dt = datetime.combine(rad_datum, starttid)
        klockan_dt = start_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan_str = klockan_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"
    try:
        klockan2_dt = start_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan2_str = "-"

    # ----------- Hårdhet & Prenumeranter -----------
    hardhet = _calc_hardhet(dp, dpp, dap, tap, totalt_man, svarta)
    pren = hardhet * (dp + dpp + dap + tap + totalt_man)

    # “Vila”-typer: pren/intäkt/kostnad/lön = 0
    is_vila = ("vila" in scen_typ)

    # ----------- Intäkter, kostnader, intäkt företag, lön, vinst -----------
    intakter = 0.0 if is_vila else float(pren) * float(avgift)

    # Kostnad män (exkl. Känner, Bonus, Personal deltagit)
    timmar = float(summa_tid_sek) / 3600.0
    kostnads_multiplikator = (man + svarta + bekanta + esk) + prod_staff
    kostnad_man = 0.0 if is_vila else timmar * float(kostnads_multiplikator) * 15.0

    # Intäkt Känner (rad) = Känner sammanlagt * 30 USD (enligt din spec)
    intakt_kanner = float(kanner_sammanlagt) * 30.0

    intakt_foretag = float(intakter) - float(kostnad_man) - float(intakt_kanner)

    # Lön Malin
    # Ålder räknas på radens datum mot fodelsedatum
    try:
        row_date = rad_datum if isinstance(rad_datum, datetime) else datetime.combine(rad_datum, starttid)
    except Exception:
        row_date = datetime.now()
    age = _age_years(row_date.date(), fodelsedatum)

    lon_malin = 0.0 if is_vila else _calc_lon_malin(intakt_foretag, age)

    vinst = float(intakt_foretag) - float(lon_malin)

    # ------------------------- Utdata -------------------------
    out = {}

    # Bas-info
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Nyckeltal
    out["Totalt Män"] = int(totalt_man)
    out["Känner"] = int(kanner)
    out["Känner sammanlagt"] = int(kanner_sammanlagt)

    # Tider
    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)

    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"]       = _hhmm(summa_tid_sek)

    # Per-kille
    out["Tid per kille (sek)"] = float(tid_per_kille_display)
    out["Tid per kille"]       = _mmss(tid_per_kille_display)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    # Nya fält (suger/händer)
    out["Suger per kille (sek)"]  = float(suger_per_kille)
    out["Händer per kille (sek)"] = float(hander_per_kille)
    out["Händer aktiv"]           = int(1 if hander_on else 0)

    # “Suger (totalt sek)” – behåller kompatibilitet: lika med Summa tid (sek)
    out["Suger"] = int(summa_tid_sek)

    # Älskar/klocka
    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi
    out["Hårdhet"]        = int(hardhet)
    out["Prenumeranter"]  = int(0 if is_vila else pren)
    out["Intäkter"]       = float(intakter)
    out["Kostnad män"]    = float(0.0 if is_vila else kostnad_man)
    out["Intäkt Känner"]  = float(intakt_kanner)
    out["Intäkt företag"] = float(intakt_foretag)
    out["Lön Malin"]      = float(0.0 if is_vila else lon_malin)
    out["Vinst"]          = float(vinst)

    return out
