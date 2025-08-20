# berakningar.py
# Version 1.0 – alla rad-beräkningar för liven, frikopplade från app.py

from datetime import datetime, timedelta

# ---------- Hjälpare ----------

def _mmss(total_seconds: float) -> str:
    """Format mm:ss med avrundade sekunder (aldrig negativ)."""
    try:
        s = max(0, int(round(float(total_seconds))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    """Format HH:MM med avrundade sekunder (aldrig negativ)."""
    try:
        s = max(0, int(round(float(total_seconds))))
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------- Huvudberäkning per rad ----------

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med alla fält som liven visar.
    Kräver att appen skickar in rådata i 'grund' samt:
      rad_datum: date eller datetime (radens datum)
      fodelsedatum: date (för ålder)
      starttid: time (dagens starttid)
    """

    # ---- Plocka in råvärden (säker konvertering) ----
    # Antal (från inputs)
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
    tid_s     = _safe_int(grund.get("Tid S", 0))                 # sek
    tid_d     = _safe_int(grund.get("Tid D", 0))                 # sek
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))    # sek/kille
    dt_vila   = _safe_int(grund.get("DT vila (sek/kille)", 0))   # (inte i bruk nu men kvar för framtid)

    # Metadata
    avgift_usd = _safe_float(grund.get("Avgift", 0.0))
    prod_staff = _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # Max-värden (för Känner sammanlagt på radnivå – behövs för Intäkt Känner)
    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---- Känner (rad) ----
    kanner = pappan + grannar + n_vanner + n_familj
    if kanner < 0:
        kanner = 0

    # ---- Totalt män (rad) ----
    totalt_man = man + kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP (sek) & Summa tid (sek) ----
    # Summa S (sek) = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    # Summa D (sek) = Tid D * (DP + DPP + DAP)
    summa_d  = tid_d * (dp + dpp + dap)
    # Summa TP (sek)= Tid D * TAP
    summa_tp = tid_d * tap
    # Summa tid (sek) = S + D + TP
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel och tider per kille ----
    # Hångel total = 3h (10800 sek). Delas på (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)
    hang_denom = man + svarta + bekanta + esk + bonus_d + pers_d  # OBS: Känner ingår ej
    hang_per_kille_sek = 0.0 if hang_denom <= 0 else 10800.0 / hang_denom

    # Tid per kille (sek) = (S + 2*D + 3*TP) / Totalt Män
    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
        suger_per_kille_sek = summa_tid_sek / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0
        suger_per_kille_sek = 0.0

    # ---- Älskar/Sover (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min var

    # ---- Hårdhet ----
    # Regler:
    # DP>0 => +3, DPP>0 => +5, DAP>0 => +7, TAP>0 => +9
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9

    # Totalt män trösklar
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 2
    if totalt_man > 400:  hardhet += 4
    if totalt_man > 700:  hardhet += 7
    if totalt_man > 1000: hardhet += 10

    # Svarta > 0 => +3
    if svarta > 0:
        hardhet += 3

    # ---- Prenumeranter (nya på rad) ----
    # = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    pren = (dp + dpp + dap + tap + totalt_man) * max(0, hardhet)
    pren = int(pren)

    # ---- Intäkter ----
    intakter = pren * avgift_usd  # USD

    # ---- Kostnad män (Utgift män) ----
    # Summa tid i timmar * ( (Män+Svarta+Bekanta+Eskilstuna) + PROD_STAFF ) * 15 USD
    tid_timmar = float(summa_tid_sek) / 3600.0
    basantal = (man + svarta + bekanta + esk) + prod_staff
    if basantal < 0:
        basantal = 0
    utgift_man = tid_timmar * basantal * 15.0

    # ---- Intäkt Känner ----
    # = Känner sammanlagt (från inställningar MAX_*) * 30 USD
    intakt_kanner = kanner_sammanlagt * 30.0

    # ---- Intäkt företaget ----
    intakt_foret = intakter - utgift_man - intakt_kanner

    # ---- Lön Malin ----
    # 1) Grundbelopp = 8% av Intäkt företaget, klampat till [150, 800]
    grundlon = _clamp(0.08 * intakt_foret, 150.0, 800.0)

    # 2) Åldersfaktor
    # beräkna ålder på rad_datum
    try:
        if isinstance(rad_datum, datetime):
            rd = rad_datum.date()
        else:
            rd = rad_datum
        fd = fodelsedatum
        alder = rd.year - fd.year - ((rd.month, rd.day) < (fd.month, fd.day))
    except Exception:
        alder = 0

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
        faktor = 0.60  # 36+

    lon_malin = max(0.0, grundlon * faktor)

    # ---- Vinst ----
    vinst = intakt_foret - lon_malin

    # ---- Klockan ----
    # Klockan = start + 3h (hångel) + 1h (vila) + summa tid (sek)
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

    # ---- Utdata till liven ----
    out = {}

    # Bas
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Mängder
    out["Känner"] = int(kanner)
    out["Känner sammanlagt"] = int(kanner_sammanlagt)
    out["Totalt Män"] = int(totalt_man)

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

    out["Suger"] = int(summa_tid_sek)  # tot sek
    out["Suger per kille (sek)"] = float(suger_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)

    # Klockor
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Poäng/ekonomi
    out["Hårdhet"]       = int(hardhet)
    out["Prenumeranter"] = int(pren)
    out["Intäkter"]      = float(intakter)
    out["Utgift män"]    = float(utgift_man)         # = Kostnad män
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Intäkt företaget"] = float(intakt_foret)
    out["Lön Malin"]     = float(lon_malin)
    out["Vinst"]         = float(vinst)

    return out
