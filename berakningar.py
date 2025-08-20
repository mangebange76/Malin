# berakningar.py — v0.9.3
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


# ---------- Huvudberäkning (radnivå) ----------

def calc_row_values(grund: dict, rad_datum, starttid):
    """
    Returnerar en dict med alla beräknade fält som appen visar i liven.

    Överenskommet:
    - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
    - Känner sammanlagt (statistik) = SUM(maxvärden) via MAX_* om de skickas in; annars 0.
    - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit
    - Summa S (sek) = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    - Summa D (sek) = Tid D * (DP + DPP + DAP)
    - Summa TP (sek)= Tid D * TAP
    - Summa tid (sek) = Summa S + Summa D + Summa TP
    - Hångel per kille = 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
      (Känner ingår inte här.)
    - Tid per kille (sek) = (Summa S + 2*Summa D + 3*Summa TP) / Totalt Män
    - Suger per kille (sek) = Summa tid (sek) / Totalt Män
    - Klockan = starttid + 3h (hångel) + 1h (vila) + Summa tid (sek)
    - Prenumeranter = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    - Intäkter = Prenumeranter * Avgift
    - Utgift män = Summa tid (h) * ((Män + Svarta + Bekanta + Eskilstuna) + PROD_STAFF) * 15
    - Intäkt Känner = Känner (rad) * 30   <-- FIX: tidigare använde vi Känner sammanlagt
    - Intäkt Företaget = Intäkter - Utgift män - Intäkt Känner
    - Lön Malin = min(max(0.08 * Intäkt Företaget, 150), 800) * åldersfaktor
    - Vinst = Intäkt Företaget - Lön Malin
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

    # tider (sek)
    tid_s     = _safe_int(grund.get("Tid S", 0))
    tid_d     = _safe_int(grund.get("Tid D", 0))
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej i bruk just nu

    avgift    = _safe_float(grund.get("Avgift", 0.0))
    prod_staff= _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # max-värden (om skickas in, för statistikfältet "Känner sammanlagt")
    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))

    # ---- Känner (rad) + Känner sammanlagt (max) ----
    kanner_rad = pappan + grannar + n_vanner + n_familj
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---- Totalt män (rad) ----
    totalt_man = man + kanner_rad + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hårdhet ----
    hardhet = 0
    if dp   > 0: hardhet += 3
    if dpp  > 0: hardhet += 5
    if dap  > 0: hardhet += 7
    if tap  > 0: hardhet += 9
    # trösklar på totalt män
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 2
    if totalt_man > 400:  hardhet += 4
    if totalt_man > 700:  hardhet += 7
    if totalt_man > 1000: hardhet += 10
    if svarta > 0:        hardhet += 3

    # ---- Per-kille tider ----
    base_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d
    hang_per_kille_sek = 0 if base_for_hang <= 0 else 10800.0 / base_for_hang

    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille_sek = summa_tid_sek / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0
        suger_per_kille_sek = 0.0

    # ---- Älskar/Sover med ----
    tid_alskar_sek = (alskar + sover) * 20 * 60

    # ---- Klockan ----
    try:
        if isinstance(rad_datum, datetime):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        klockan_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan_str = klockan_dt.strftime("%H:%M")
        klockan2_dt = base_dt + timedelta(hours=4) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"
        klockan2_str = "-"

    # ---- Ekonomi ----
    prenumeranter = (dp + dpp + dap + tap + totalt_man) * hardhet
    intakter = prenumeranter * avgift

    # Utgift män – använder INTE Känner, Bonus deltagit, Personal deltagit
    summa_tid_timmar = summa_tid_sek / 3600.0
    kostnadsman_underlag = (man + svarta + bekanta + esk) + prod_staff
    utgift_man = summa_tid_timmar * kostnadsman_underlag * 15.0

    # *** FIX: Intäkt Känner ska använda KÄNNER (rad) ***
    intakt_kanner = kanner_rad * 30.0

    intakt_foretaget = intakter - utgift_man - intakt_kanner

    # Lön Malin (gränser + åldersfaktor)
    # Ålder: hämtas via datum i grund om finns, annars 0
    aldersfaktor = 1.0
    # åldersintervall definierat av dig
    # 18:100%, 19–23:90%, 24–27:85%, 28–30:80%, 31–32:75%, 33–35:70%, 36–:60%
    alder = _safe_int(grund.get("Ålder", 0))
    if alder >= 36:   aldersfaktor = 0.60
    elif alder >= 33: aldersfaktor = 0.70
    elif alder >= 31: aldersfaktor = 0.75
    elif alder >= 28: aldersfaktor = 0.80
    elif alder >= 24: aldersfaktor = 0.85
    elif alder >= 19: aldersfaktor = 0.90
    else:             aldersfaktor = 1.00

    lon_malin_bas = max(150.0, min(0.08 * intakt_foretaget, 800.0))
    lon_malin = lon_malin_bas * aldersfaktor

    vinst = intakt_foretaget - lon_malin

    # ---- Ut ----
    out = {}

    out["Datum"] = datum_str or (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    out["Totalt Män"] = int(totalt_man)
    out["Känner"] = int(kanner_rad)
    out["Känner sammanlagt"] = int(kanner_sammanlagt)

    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"] = _hhmm(summa_tid_sek)

    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    out["Suger"] = int(summa_tid_sek)
    out["Suger per kille (sek)"] = float(suger_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)

    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Intäkter"] = float(intakter)
    out["Utgift män"] = float(utgift_man)
    out["Intäkt Känner"] = float(intakt_kanner)     # <— FIX APPLIED
    out["Intäkt Företaget"] = float(intakt_foretaget)
    out["Lön Malin"] = float(lon_malin)
    out["Vinst"] = float(vinst)

    return out


# ---------- Statistik (summeringar över flera rader) ----------

def calc_stats(rows: list, cfg: dict):
    """
    Enkel statistik-summering över rader.
    rows: lista av dictar som kommer från calc_row_values.
    cfg:  kan innehålla max-inställningar och PROD_STAFF om behövs.
    """
    out = {}

    # Totalt män (summa radnivå)
    tot_man = sum(_safe_int(r.get("Totalt Män", 0)) for r in rows)
    out["Totalt Män (sum)"] = int(tot_man)

    # Andel svarta (statistikregeln du gav)
    sum_svarta = sum(_safe_int(r.get("Svarta", 0)) for r in rows)
    max_bekanta = _safe_int(cfg.get("MAX_BEKANTA", 0))
    prod_staff  = _safe_int(cfg.get("PROD_STAFF", 0))
    # Känner sammanlagt här = från maxvärden i cfg
    kanner_sam = (
        _safe_int(cfg.get("MAX_PAPPAN", 0)) +
        _safe_int(cfg.get("MAX_GRANNAR", 0)) +
        _safe_int(cfg.get("MAX_NILS_VANNER", 0)) +
        _safe_int(cfg.get("MAX_NILS_FAMILJ", 0))
    )
    sum_man_col   = sum(_safe_int(r.get("Män", 0)) for r in rows)
    sum_svarta_col= sum_svarta
    sum_esk_col   = sum(_safe_int(r.get("Eskilstuna killar", 0)) for r in rows)
    sum_bonus_col = sum(_safe_int(r.get("Bonus deltagit", 0)) for r in rows)

    denom = (sum_man_col + kanner_sam + sum_svarta_col + max_bekanta +
             sum_esk_col + sum_bonus_col + prod_staff)
    andel_svarta = (sum_svarta / denom) * 100.0 if denom > 0 else 0.0
    out["Andel svarta (%)"] = float(andel_svarta)

    # Ekonomi-summor (enkelt)
    out["Intäkter (sum)"]       = float(sum(_safe_float(r.get("Intäkter", 0.0)) for r in rows))
    out["Intäkt Känner (sum)"]  = float(sum(_safe_float(r.get("Intäkt Känner", 0.0)) for r in rows))
    out["Utgift män (sum)"]     = float(sum(_safe_float(r.get("Utgift män", 0.0)) for r in rows))
    out["Lön Malin (sum)"]      = float(sum(_safe_float(r.get("Lön Malin", 0.0)) for r in rows))
    out["Vinst (sum)"]          = float(sum(_safe_float(r.get("Vinst", 0.0)) for r in rows))

    # Känner sammanlagt (statistik) direkt från cfg-max (enligt dina regler)
    out["Känner sammanlagt (max)"] = int(kanner_sam)

    return out
