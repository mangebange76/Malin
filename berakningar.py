# berakningar.py
from datetime import datetime, timedelta

# ---------- Hjälpmetoder ----------

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

def _age_on(day, born_date) -> int:
    try:
        return day.year - born_date.year - ((day.month, day.day) < (born_date.month, born_date.day))
    except Exception:
        return 0


# ---------- Huvudberäkning ----------
def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med alla beräknade fält som appen visar i liven.

    Överenskommen logik:
    - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
    - Känner sammanlagt (statistik) = SUM(max) via nycklar:
        MAX_PAPPAN, MAX_GRANNAR, MAX_NILS_VANNER, MAX_NILS_FAMILJ (om de finns)
    - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit

    - Summa S (sek)  = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    - Summa D (sek)  = Tid D * (DP + DPP + DAP)
    - Summa TP (sek) = Tid D * TAP
    - Summa tid (sek) = Summa S + Summa D + Summa TP
    - Tid per kille (sek) = (Summa S + 2*Summa D + 3*Summa TP) / Totalt Män
    - Suger per kille (sek) = Summa tid (sek) / Totalt Män

    - Hångel total = 3h (10800 s). Hångel per kille = 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
      (Obs: Känner ingår ej här, enligt specifikation.)

    - Klockan = starttid + 3h (hångel) + 1h (vila) + Summa tid (sek)
      Klockan inkl älskar/sover = ovan + (Älskar + Sover med) * 20 min

    - Hårdhet:
        +3 om DP>0
        +5 om DPP>0
        +7 om DAP>0
        +9 om TAP>0
        +1 om Totalt Män > 100
        +2 om Totalt Män > 200
        +4 om Totalt Män > 400
        +7 om Totalt Män > 700
        +10 om Totalt Män > 1000
        +3 om Svarta > 0
      (summeras)

    - Prenumeranter (rad) = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    - Intäkter = Prenumeranter * Avgift (USD)
    - Kostnad män (rad) = (Summa tid (sek)/3600) * ((Män + Svarta + Bekanta + Eskilstuna killar) + TOTAL PERSONAL) * 15 USD
        (Total personal hämtas från PRO D_STAFF om finns, annars MAX_PERSONAL)
        (Känner, Bonus deltagit, Personal deltagit ingår ej i kostnadsdelen)
    - Intäkt Känner = Känner sammanlagt * 30 USD
    - Intäkt Företaget = Intäkter - Kostnad män - Intäkt Känner
    - Lön Malin = clamp(150, 800, 8% av Intäkt Företaget) * åldersfaktor
        Åldersfaktor:
          18y: 100%
          19–23: 90%
          24–27: 85%
          28–30: 80%
          31–32: 75%
          33–35: 70%
          36+:  60%
    - Vinst = Intäkt Företaget - Lön Malin
    """

    # ---- Plocka råvärden ----
    man       = _safe_int(grund.get("Män", 0))
    svarta    = _safe_int(grund.get("Svarta", 0))
    fitta     = _safe_int(grund.get("Fitta", 0))
    rumpa     = _safe_int(grund.get("Rumpa", 0))
    dp        = _safe_int(grund.get("DP", 0))
    dpp       = _safe_int(grund.get("DPP", 0))
    dap       = _safe_int(grund.get("DAP", 0))
    tap       = _safe_int(grund.get("TAP", 0))

    pappan    = _safe_int(grund.get("Pappans vänner", 0))
    grannar   = _safe_int(grund.get("Grannar", 0))
    n_vanner  = _safe_int(grund.get("Nils vänner", 0))
    n_familj  = _safe_int(grund.get("Nils familj", 0))
    bekanta   = _safe_int(grund.get("Bekanta", 0))
    esk       = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_d   = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d    = _safe_int(grund.get("Personal deltagit", 0))

    alskar    = _safe_int(grund.get("Älskar", 0))
    sover     = _safe_int(grund.get("Sover med", 0))

    tid_s     = _safe_int(grund.get("Tid S", 0))
    tid_d     = _safe_int(grund.get("Tid D", 0))
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej med i nuvarande modell

    avgift    = _safe_float(grund.get("Avgift", 0.0))

    # personal för kostnadsdelen (TOTAL personal – inte deltagit)
    total_personal = _safe_int(grund.get("PROD_STAFF", grund.get("MAX_PERSONAL", 0)))

    # meta
    datum_str = grund.get("Datum", "")
    veckodag  = grund.get("Veckodag", "")

    # ---- Känner (rad) + Känner sammanlagt (maxvärden) ----
    kar_kanner = pappan + grannar + n_vanner + n_familj

    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---- Totalt män (rad) ----
    totalt_man = man + kar_kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP och Summa tid ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel per kille ----
    tot_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d  # ej Känner
    hang_per_kille_sek = 0.0 if tot_for_hang <= 0 else 10800.0 / float(tot_for_hang)

    # ---- per-kille tider ----
    if totalt_man > 0:
        tid_per_kille_sek   = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille_sek = summa_tid_sek / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0
        suger_per_kille_sek = 0.0

    # ---- Älskar/Sover med (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60

    # ---- Klockan ----
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
        klockan_str = "-"
        klockan2_str = "-"

    # ---- Hårdhet ----
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    # thresholds på totalt män
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 2
    if totalt_man > 400:  hardhet += 4
    if totalt_man > 700:  hardhet += 7
    if totalt_man > 1000: hardhet += 10
    # svarta bonus
    if svarta > 0: hardhet += 3

    # ---- Prenumeranter & Intäkter ----
    pren = max(0, (dp + dpp + dap + tap + totalt_man) * hardhet)
    intakter = pren * avgift

    # ---- Kostnad män ----
    timmar = summa_tid_sek / 3600.0
    kostnads_mannskap = (man + svarta + bekanta + esk + total_personal)
    kostnad_man = timmar * kostnads_mannskap * 15.0

    # ---- Intäkt Känner ----
    intakt_kanner = kanner_sammanlagt * 30.0

    # ---- Intäkt Företaget ----
    intakt_foretag = intakter - kostnad_man - intakt_kanner

    # ---- Lön Malin (8% clamped, åldersfaktor) ----
    # 1) 8% av intäkt företaget, clamp 150–800
    base_lon = max(150.0, min(800.0, 0.08 * max(0.0, intakt_foretag)))

    # 2) åldersfaktor
    alder = _age_on(rad_datum if isinstance(rad_datum, datetime) else rad_datum, fodelsedatum)
    if   alder <= 18: faktor = 1.00
    elif 19 <= alder <= 23: faktor = 0.90
    elif 24 <= alder <= 27: faktor = 0.85
    elif 28 <= alder <= 30: faktor = 0.80
    elif 31 <= alder <= 32: faktor = 0.75
    elif 33 <= alder <= 35: faktor = 0.70
    else: faktor = 0.60
    lon_malin = base_lon * faktor

    # ---- Vinst ----
    vinst = intakt_foretag - lon_malin

    # ---- Utdata ----
    out = {}

    # Bas
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Nyckeltal antal
    out["Totalt Män"] = int(totalt_man)
    out["Känner"] = int(kar_kanner)
    out["Känner sammanlagt"] = int(kanner_sammanlagt)

    # Tider
    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"] = _hhmm(summa_tid_sek)

    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    out["Suger"] = int(summa_tid_sek)  # total sek
    out["Suger per kille (sek)"] = float(suger_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)

    # Klocka
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Hårdhet & ekonomi
    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(pren)
    out["Intäkter"] = float(intakter)
    out["Utgift män"] = float(kostnad_man)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Intäkt Företaget"] = float(intakt_foretag)
    out["Lön Malin"] = float(lon_malin)
    out["Vinst"] = float(vinst)

    return out
