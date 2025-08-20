# berakningar.py
from datetime import datetime, timedelta

# ---------- Små hjälpmetoder ----------

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


# ---------- Huvudberäkning ----------

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Beräknar radnivåns nyckeltal (för liven).

    Regler (från vår genomgång):
    - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
    - Känner sammanlagt (stat) fås från MAX_* om de skickas in (här bara speglat ut)
    - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit + Personal deltagit
    - Summa S (sek)  = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    - Summa D (sek)  = Tid D * (DP + DPP + DAP)
    - Summa TP (sek) = Tid D * (TAP)
    - Summa tid (sek) = Summa S + Summa D + Summa TP
    - Hångel total = 3 h (10800 s); per kille = 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
      (OBS: Känner ingår inte)
    - Tid per kille (sek) = (Summa S + 2*Summa D + 3*Summa TP) / Totalt Män
    - Suger per kille (sek) = Summa tid (sek) / Totalt Män
    - Klockan = starttid + 3h (hångel) + 1h (vila) + Summa tid (sek)
      (Klockan inkl älskar/sover = ovan + (Älskar + Sover med) * 20 min)
    - Hårdhet:
        DP>0  +3
        DPP>0 +5
        DAP>0 +7
        TAP>0 +9
        Svarta>0 +3
        Totalt Män >100 +1, >200 +2, >400 +4, >700 +7, >1000 +10
      (summeras)
    - Prenumeranter = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    """

    # ---- Plocka in råvärden ----
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

    # Tider (sek)
    tid_s     = _safe_int(grund.get("Tid S", 0))
    tid_d     = _safe_int(grund.get("Tid D", 0))
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila   = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej använd just nu men kvar för framtiden

    # Metadata
    avgift    = _safe_float(grund.get("Avgift", 0.0))
    prod_staff= _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # ---- Känner (rad) + Känner sammanlagt (MAX_*) ----
    kar_kanner = pappan + grannar + n_vanner + n_familj

    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---- Totalt Män (rad) ----
    totalt_man = man + kar_kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP (sek) & Summa tid (sek) ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel och per-kille tider ----
    total_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d  # OBS: Känner ingår inte
    hang_per_kille_sek = 0 if total_for_hang <= 0 else 10800.0 / total_for_hang  # 3h = 10800s

    if totalt_man > 0:
        tid_per_kille_sek   = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille_sek = summa_tid_sek / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0
        suger_per_kille_sek = 0.0

    # ---- Älskar/Sover med (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # ---- Klockan (huvud + inkl älskar/sover) ----
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

    # ---- HÅRDHET ----
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    if svarta > 0: hardhet += 3

    # trappor för Totalt Män
    if totalt_man > 1000:
        hardhet += 10
    elif totalt_man > 700:
        hardhet += 7
    elif totalt_man > 400:
        hardhet += 4
    elif totalt_man > 200:
        hardhet += 2
    elif totalt_man > 100:
        hardhet += 1

    # ---- PRENUMERANTER ----
    prenumeranter = (dp + dpp + dap + tap + totalt_man) * hardhet

    # ---- Återlämna allt ----
    out = {}

    # Bas
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Nyckeltal
    out["Totalt Män"] = totalt_man
    out["Känner"] = kar_kanner
    out["Känner sammanlagt"] = kanner_sammanlagt

    # Tider
    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"] = _hhmm(summa_tid_sek)  # HH:MM

    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    out["Suger"] = int(summa_tid_sek)
    out["Suger per kille (sek)"] = float(suger_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)

    # Klocka
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi/Övrigt (nu med Hårdhet & Prenumeranter)
    out["Hårdhet"]       = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)

    # placeholders tills vi sätter regler
    out["Intäkter"]      = 0.0
    out["Intäkt Känner"] = 0.0
    out["Utgift män"]    = 0.0
    out["Lön Malin"]     = 0.0
    out["Vinst"]         = 0.0

    return out
