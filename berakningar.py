# berakningar.py
from datetime import datetime, timedelta

# -------- Hjälpare --------
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


# -------- Huvudberäkning --------
def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med:
      1) alla råa inmatningsfält (för tabell/Sheets)
      2) alla beräknade nyckeltal vi använder i liven
    Viktigt: vi stödjer omdöpta etiketter (LBL_*) från appens CFG.
    """

    # Etiketter (så att omdöpningar slår igenom även här)
    lbl_pappan  = grund.get("LBL_PAPPAN", "Pappans vänner")
    lbl_grannar = grund.get("LBL_GRANNAR", "Grannar")
    lbl_nv      = grund.get("LBL_NILS_VANNER", "Nils vänner")
    lbl_nf      = grund.get("LBL_NILS_FAMILJ", "Nils familj")
    lbl_bek     = grund.get("LBL_BEKANTA", "Bekanta")
    lbl_esk     = grund.get("LBL_ESK", "Eskilstuna killar")

    # ---- Rå indata ----
    scen       = _safe_int(grund.get("Scen", 0))
    man        = _safe_int(grund.get("Män", 0))
    svarta     = _safe_int(grund.get("Svarta", 0))
    fitta      = _safe_int(grund.get("Fitta", 0))
    rumpa      = _safe_int(grund.get("Rumpa", 0))
    dp         = _safe_int(grund.get("DP", 0))
    dpp        = _safe_int(grund.get("DPP", 0))
    dap        = _safe_int(grund.get("DAP", 0))
    tap        = _safe_int(grund.get("TAP", 0))

    # källor (stöd både standardnamn och ev. redan-mappade etiketter)
    pappan     = _safe_int(grund.get(lbl_pappan, grund.get("Pappans vänner", 0)))
    grannar    = _safe_int(grund.get(lbl_grannar, grund.get("Grannar", 0)))
    n_vanner   = _safe_int(grund.get(lbl_nv,      grund.get("Nils vänner", 0)))
    n_familj   = _safe_int(grund.get(lbl_nf,      grund.get("Nils familj", 0)))
    bekanta    = _safe_int(grund.get(lbl_bek,     grund.get("Bekanta", 0)))
    esk        = _safe_int(grund.get(lbl_esk,     grund.get("Eskilstuna killar", 0)))

    bonus_d    = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d     = _safe_int(grund.get("Personal deltagit", 0))

    alskar     = _safe_int(grund.get("Älskar", 0))
    sover      = _safe_int(grund.get("Sover med", 0))
    hander_on  = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))  # 1=Ja, 0=Nej

    # tider
    tid_s      = _safe_int(grund.get("Tid S", 0))
    tid_d      = _safe_int(grund.get("Tid D", 0))
    dt_tid     = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej använd nu

    # metadata/ekonomi
    avgift     = _safe_float(grund.get("Avgift", 0.0))
    prod_staff = _safe_int(grund.get("PROD_STAFF", 0))

    datum_str  = grund.get("Datum")  # kan vara redan formaterad av appen
    veckodag   = grund.get("Veckodag", "")
    typ_scen   = str(grund.get("Typ", "") or "")

    # ---- Känner ----
    kanner = pappan + grannar + n_vanner + n_familj

    # Känner sammanlagt från max (om skickat med)
    max_p = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_g = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_nv = _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_nf = _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_p + max_g + max_nv + max_nf

    # ---- Totalt män (rad) ----
    totalt_man = man + kanner + svarta + bekanta + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # ---- Summa S/D/TP ----
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # ---- Hångel ----
    total_for_hang = man + svarta + bekanta + esk + bonus_d + pers_d  # Känner ingår inte
    hang_per_kille_sek = 0.0 if total_for_hang <= 0 else 10800.0 / total_for_hang  # 3h = 10800s

    # ---- Tid per kille ----
    if totalt_man > 0:
        tid_per_kille_sek = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
    else:
        tid_per_kille_sek = 0.0

    # ---- Suger/Händer per kille (nya regler) ----
    if totalt_man > 0:
        suger_per_kille_sek = 0.8 * (summa_s / totalt_man) + 0.8 * (summa_d / totalt_man) + 0.8 * (summa_tp / totalt_man)
    else:
        suger_per_kille_sek = 0.0

    hander_per_kille_sek = 2.0 * suger_per_kille_sek if hander_on else 0.0

    # ---- Älskar/Sover med (sek) ----
    tid_alskar_sek = (alskar + sover) * 20 * 60

    # ---- Klocka ----
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

    # ---- Ekonomi (placeholder/vila-regel) ----
    # Här räknar vi bara enkla defaultar. Appen kan skriva över om ni har
    # mer logik i UI. Vid *Vila*-scener blir allt 0 enligt din regel.
    hardhet = _safe_int(grund.get("Hårdhet", 0))
    pren = _safe_int(grund.get("Prenumeranter", hardhet * (dp + dpp + dap + tap + totalt_man)))
    intakter = avgift * pren
    kostnad_man = (summa_tid_sek / 3600.0) * (man + svarta + bekanta + esk + prod_staff) * 15.0
    intakt_kanner = kanner_sammanlagt * 30.0
    intakt_foretag = intakter - kostnad_man - intakt_kanner

    # Ålder → lönefaktor
    try:
        if hasattr(rad_datum, "year"):
            rd = rad_datum
        else:
            rd = datetime.fromisoformat(grund.get("Datum")).date()
        fd = fodelsedatum
        alder = rd.year - fd.year - ((rd.month, rd.day) < (fd.month, fd.day))
    except Exception:
        alder = 30

    bas_lon = max(150.0, min(800.0, 0.08 * max(0.0, intakt_foretag)))
    if alder <= 18:
        lon = bas_lon
    elif 19 <= alder <= 23:
        lon = bas_lon * 0.90
    elif 24 <= alder <= 27:
        lon = bas_lon * 0.85
    elif 28 <= alder <= 30:
        lon = bas_lon * 0.80
    elif 31 <= alder <= 32:
        lon = bas_lon * 0.75
    elif 33 <= alder <= 35:
        lon = bas_lon * 0.70
    else:
        lon = bas_lon * 0.60

    vinst = intakt_foretag - lon

    # Vila-regel
    if typ_scen.lower().startswith("vila"):
        pren = 0
        intakter = 0.0
        kostnad_man = 0.0
        lon = 0.0
        vinst = intakt_foretag  # borde bli 0 om ovan sätts 0

    # ---- Svara med ALLT vi behöver (inkl. råfält) ----
    out = {}

    # Bas/metadata
    out["Datum"] = datum_str if datum_str else (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    out["Veckodag"] = veckodag
    out["Scen"] = scen
    out["Typ"]  = typ_scen

    # Rå indata
    out["Män"] = man
    out["Svarta"] = svarta
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap

    # Källor under aktiva etiketter
    out[lbl_pappan]  = pappan
    out[lbl_grannar] = grannar
    out[lbl_nv]      = n_vanner
    out[lbl_nf]      = n_familj
    out[lbl_bek]     = bekanta
    out[lbl_esk]     = esk

    out["Bonus deltagit"] = bonus_d
    out["Personal deltagit"] = pers_d

    out["Älskar"] = alskar
    out["Sover med"] = sover
    out["Händer aktiv"] = int(1 if hander_on else 0)

    # Nyckeltal – volymer/tider
    out["Känner"] = kanner
    out["Känner sammanlagt"] = kanner_sammanlagt
    out["Totalt Män"] = totalt_man

    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"]       = _hhmm(summa_tid_sek)

    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    # Nya fält
    out["Suger per kille (sek)"]  = float(suger_per_kille_sek)
    out["Händer per kille (sek)"] = float(hander_per_kille_sek)
    out["Tid/kille inkl händer (sek)"] = float(tid_per_kille_sek + hander_per_kille_sek)
    out["Tid/kille inkl händer"]       = _mmss(tid_per_kille_sek + hander_per_kille_sek)

    out["Hångel (sek/kille)"]  = float(hang_per_kille_sek)
    out["Hångel (m:s/kille)"]  = _mmss(hang_per_kille_sek)

    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi
    out["Hårdhet"]       = hardhet
    out["Prenumeranter"] = int(pren)
    out["Intäkter"]      = float(intakter)
    out["Kostnad män"]   = float(kostnad_man)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Intäkt företag"]= float(intakt_foretag)
    out["Lön Malin"]     = float(lon)
    out["Vinst"]         = float(vinst)

    return out
