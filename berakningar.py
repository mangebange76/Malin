# berakningar.py
from datetime import datetime, timedelta

# ---------- Hjälpmetoder ----------

def _mmss(total_seconds: float) -> str:
    """Format: m:ss (avrundar till närmaste sekund, aldrig negativt)."""
    try:
        s = max(0, int(round(total_seconds)))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    """Format: HH:MM (avrundar till närmaste minut, aldrig negativt)."""
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
    Ekonomin kompletteras i app.py (hårdhet, prenumeranter, intäkter, kostnader, lön, vinst).
    """

    # ---- Etiketter (för käll-fält) ----
    lbl_pappan = str(grund.get("LBL_PAPPAN", "Pappans vänner"))
    lbl_grann  = str(grund.get("LBL_GRANNAR", "Grannar"))
    lbl_nv     = str(grund.get("LBL_NILS_VANNER", "Nils vänner"))
    lbl_nf     = str(grund.get("LBL_NILS_FAMILJ", "Nils familj"))
    lbl_bek    = str(grund.get("LBL_BEKANTA", "Bekanta"))
    lbl_esk    = str(grund.get("LBL_ESK", "Eskilstuna killar"))

    # ---- Inputs ----
    man       = _safe_int(grund.get("Män", 0))
    svarta    = _safe_int(grund.get("Svarta", 0))
    fitta     = _safe_int(grund.get("Fitta", 0))
    rumpa     = _safe_int(grund.get("Rumpa", 0))
    dp        = _safe_int(grund.get("DP", 0))
    dpp       = _safe_int(grund.get("DPP", 0))
    dap       = _safe_int(grund.get("DAP", 0))
    tap       = _safe_int(grund.get("TAP", 0))

    pappan    = _safe_int(grund.get(lbl_pappan, 0))
    grannar   = _safe_int(grund.get(lbl_grann, 0))
    n_vanner  = _safe_int(grund.get(lbl_nv, 0))
    n_familj  = _safe_int(grund.get(lbl_nf, 0))
    bekanta   = _safe_int(grund.get(lbl_bek, 0))
    esk       = _safe_int(grund.get(lbl_esk, 0))

    bonus_d   = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d    = _safe_int(grund.get("Personal deltagit", 0))

    alskar    = _safe_int(grund.get("Älskar", 0))
    sover     = _safe_int(grund.get("Sover med", 0))

    # Händer (0/1)
    hander_on = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))

    # Tider (sek)
    tid_s     = _safe_int(grund.get("Tid S", 0))
    tid_d     = _safe_int(grund.get("Tid D", 0))
    dt_tid    = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila   = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej i användning nu

    # Metadata/övrigt
    avgift    = _safe_float(grund.get("Avgift", 0.0))
    prod_staff= _safe_int(grund.get("PROD_STAFF", 0))

    datum_str = grund.get("Datum")
    veckodag  = grund.get("Veckodag", "")

    # ---- Känner (rad) + Känner sammanlagt (från MAX-inställningar) ----
    kanner = pappan + grannar + n_vanner + n_familj

    max_pappan   = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_grannar  = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_n_vanner = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_n_familj = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_pappan + max_grannar + max_n_vanner + max_n_familj

    # ---- Totalt män (rad) ----
    totalt_man = man + kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP (sek) & Summa tid (sek) ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel ----
    # 3h = 10800s, per kille fördelas på Män + Svarta + Bekanta + Esk + Bonus + Personal (ej Känner enligt din spec)
    total_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d
    hang_per_kille_sek = 0 if total_for_hang <= 0 else 10800.0 / total_for_hang

    # ---- Tid per kille (sek): S + 2*D + 3*TP fördelat på Totalt män ----
    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0

    # ---- Suger/Händer per kille (sek) enligt nya regler ----
    # Suger/kille = 0.8*(S/tot) + 0.8*(D/tot) + 0.8*(TP/tot)
    if totalt_man > 0:
        suger_per_kille = 0.8 * (summa_s / totalt_man) + 0.8 * (summa_d / totalt_man) + 0.8 * (summa_tp / totalt_man)
    else:
        suger_per_kille = 0.0

    hander_per_kille = (2.0 * suger_per_kille) if hander_on else 0.0

    # ---- Älskar/Sover med (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # ---- Klockan ----
    try:
        if isinstance(rad_datum, datetime):
            base_dt = rad_datum.replace(hour=starttid.hour, minute=starttid.minute, second=0, microsecond=0)
        else:
            base_dt = datetime.combine(rad_datum, starttid)
        klockan_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan_str = klockan_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"
    try:
        klockan2_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan2_str = "-"

    # ---- Returnera alla fält appen läser ----
    out = {}

    # Bas
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Nyckeltal
    out["Totalt Män"] = totalt_man
    out["Känner"] = kanner
    out["Känner sammanlagt"] = kanner_sammanlagt

    # Tider/summor
    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)

    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"]       = _hhmm(summa_tid_sek)

    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    # Nya fält för din live
    out["Suger per kille (sek)"]  = float(suger_per_kille)
    out["Händer per kille (sek)"] = float(hander_per_kille)
    out["Händer aktiv"] = int(1 if hander_on else 0)

    # Behåll “Suger” total som kompatibilitet (används i liven som “Suger (totalt sek)”)
    out["Suger"] = int(summa_tid_sek)

    # Älskar + klockor
    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi – placeholders (sätts i app.py)
    out["Prenumeranter"]   = 0
    out["Hårdhet"]         = 0
    out["Intäkter"]        = 0.0
    out["Intäkt Känner"]   = 0.0
    out["Kostnad män"]     = 0.0
    out["Intäkt företag"]  = 0.0
    out["Lön Malin"]       = 0.0
    out["Vinst"]           = 0.0

    return out
