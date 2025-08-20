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
    Returnerar en dict med alla beräknade fält som appen visar i liven.

    Antaganden (överenskommet):
    - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
    - Känner sammanlagt (statistik) = SUM(maxvärden) för dessa fyra, OM de skickas in via
      nycklarna: MAX_PAPPAN, MAX_GRANNAR, MAX_NILS_VANNER, MAX_NILS_FAMILJ. Annars 0.
    - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit
    - Summa S (sek) = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    - Summa D (sek) = Tid D * (DP + DPP + DAP)
    - Summa TP (sek)= Tid D * (TAP)
    - Summa tid (sek) = Summa S + Summa D + Summa TP
    - Hångel total = 3 timmar (10800 s). Hångel per kille = 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
      (Obs: Känner ingår INTE här enligt din specifikation.)
    - Tid per kille (sek) = (Summa S + 2*Summa D + 3*Summa TP) / Totalt Män
      (D dubblas, TP tredubblas enligt din fördelningsregel)
    - Suger per kille (sek) = Summa tid (sek) / Totalt Män
    - Tid per kille och Hångel visas som mm:ss
    - Klockan = starttid + 3h (hångel) + 1h (vila) + Summa tid (sek)
      (Separat: Tid Älskar (sek) = (Älskar + Sover med) * 20 min * 60)
    - Prenumeranter, Intäkter, Intäkt Känner, Utgift män, Lön Malin, Vinst lämnas 0 tills vi definierar dem senare.
    """

    # ---- Plocka in råvärden (säker konvertering) ----
    # Input-antal
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
    dt_vila   = _safe_int(grund.get("DT vila (sek/kille)", 0))  # används inte nu men finns kvar

    # Metadata
    avgift    = _safe_float(grund.get("Avgift", 0.0))
    prod_staff= _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # ---- Känner (rad) + Känner sammanlagt (från MAX-inställningar om skickade) ----
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

    # ---- Summa S/D/TP (sek) & Summa tid (sek) ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel och per-kille tider ----
    # Hångel total 3h = 10800 sek
    total_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d  # OBS: inte "Känner"
    hang_per_kille_sek = 0 if total_for_hang <= 0 else 10800.0 / total_for_hang

    # Tid per kille (sek): S + 2*D + 3*TP fördelat på Totalt män
    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille_sek = summa_tid_sek / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0
        suger_per_kille_sek = 0.0

    # ---- Älskar/Sover med (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 minuter per person

    # ---- Klockan (huvud) ----
    try:
        if isinstance(rad_datum, datetime):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        klockan_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan_str = klockan_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"

    # Klockan inkl älskar/sover
    try:
        klockan2_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan2_str = "-"

    # ---- Hårdhet ----
    hardhet = 0
    # DP/DPP/DAP/TAP
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    # Totalt män trösklar (adderas kumulativt)
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 2
    if totalt_man > 400:  hardhet += 4
    if totalt_man > 700:  hardhet += 7
    if totalt_man > 1000: hardhet += 10
    # Svarta
    if svarta > 0: hardhet += 3

    # ---- Återlämna allt appen använder ----
    out = {}

    # Bas-info
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

    out["Suger"] = int(summa_tid_sek)  # ”totalt sek”
    out["Suger per kille (sek)"] = float(suger_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)

    # Klocka
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi (placeholder tills vi definierar)
    out["Prenumeranter"]   = 0
    out["Hårdhet"]         = hardhet
    out["Intäkter"]        = 0.0
    out["Intäkt Känner"]   = 0.0
    out["Utgift män"]      = 0.0
    out["Lön Malin"]       = 0.0
    out["Vinst"]           = 0.0

    return out
