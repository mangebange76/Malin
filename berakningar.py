from datetime import datetime, timedelta

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def berakna_radvarden(rad: dict, rad_datum, fodelsedatum, starttid):
    # ----- Inputs (safe ints) -----
    man    = _safe_int(rad.get("Män", 0))
    svarta = _safe_int(rad.get("Svarta", 0))
    esk    = _safe_int(rad.get("Eskilstuna killar", 0))
    fitta  = _safe_int(rad.get("Fitta", 0))
    rumpa  = _safe_int(rad.get("Rumpa", 0))
    dp     = _safe_int(rad.get("DP", 0))
    dpp    = _safe_int(rad.get("DPP", 0))
    dap    = _safe_int(rad.get("DAP", 0))
    tap    = _safe_int(rad.get("TAP", 0))

    tid_s  = _safe_int(rad.get("Tid S", 0))
    tid_d  = _safe_int(rad.get("Tid D", 0))
    vila   = _safe_int(rad.get("Vila", 0))

    dt_tid  = _safe_int(rad.get("DT tid (sek/kille)", 60))
    dt_vila = _safe_int(rad.get("DT vila (sek/kille)", 3))

    alskar    = _safe_int(rad.get("Älskar", 0))
    sover_med = _safe_int(rad.get("Sover med", 0))

    pappan = _safe_int(rad.get("Pappans vänner", 0))
    grann  = _safe_int(rad.get("Grannar", 0))
    nvann  = _safe_int(rad.get("Nils vänner", 0))
    nfam   = _safe_int(rad.get("Nils familj", 0))
    bek    = _safe_int(rad.get("Bekanta", 0))
    nils   = _safe_int(rad.get("Nils", 0))

    avgift = float(rad.get("Avgift", 30.0) or 30.0)

    # ----- Härledda mängder -----
    kanner = pappan + grann + nvann + nfam + bek
    # "Totalt Män" ska nu inkludera allt "män-likt": Män + Svarta + Eskilstuna + alla känner-källor
    totalt_man = man + svarta + esk + pappan + grann + nvann + nfam + bek

    # Basen för tid S/D/TP och även Suger: "alla killar" = Män + Känner + Svarta + Eskilstuna
    alla_killar = max(0, man + kanner + svarta + esk)

    # ---- Tider S/D/TP/Vila ----
    # Dessa tider multipliceras med "alla killar" enligt dina regler
    summa_s   = tid_s * alla_killar
    summa_d   = tid_d * alla_killar
    summa_tp  = (fitta + rumpa + dp + dpp + dap + tap) * 60  # antag 60s/TP-enhet om inte annat angivits
    # DT delar
    summa_dt_tid  = dt_tid  * totalt_man
    summa_dt_vila = dt_vila * totalt_man

    # Summa vila = explicit vila + DT vila
    summa_vila = (vila * alla_killar) + summa_dt_vila

    # Älskar/Sover med tid (på klockan, separat)
    tid_alskar_sec = alskar * 1800  # 30 min per älskar
    tid_sover_sec  = sover_med * 3600  # 1h om 1

    # Suger = 60% av (Summa D + Summa TP)
    suger_total_sec = int(round(0.60 * (summa_d + summa_tp)))
    suger_per_kille_sec = int(suger_total_sec / alla_killar) if alla_killar > 0 else 0

    # Hångel: 3 timmar delas på (Män + Svarta + Bekanta + Eskilstuna)
    hongel_div = man + svarta + bek + esk
    hongel_total_sec = 3 * 3600
    hongel_per_kille_sec = int(hongel_total_sec / hongel_div) if hongel_div > 0 else 0

    # Summa tid (sek) = S + D + TP + Vila + DT_tid + Älskar + Sover med
    summa_tid_sec = summa_s + summa_d + summa_tp + summa_vila + summa_dt_tid + tid_alskar_sec + tid_sover_sec

    # Tid per kille (sek) = (S + D + TP)/alla_killar + DT_tid per kille + Suger per kille
    bas_per_kille = int((summa_s + summa_d + summa_tp) / alla_killar) if alla_killar > 0 else 0
    dt_per_kille  = int(summa_dt_tid / alla_killar) if alla_killar > 0 else 0
    tid_per_kille_sec = bas_per_kille + dt_per_kille + suger_per_kille_sec  # (hångel/älskar/sover påverkar ej per-kille)

    # Klockan: start + summa_tid
    if isinstance(starttid, str):
        # fallback om str (HH:MM:SS)
        h, m, s = map(int, starttid.split(":"))
        start_delta = timedelta(hours=h, minutes=m, seconds=s)
    else:
        start_delta = timedelta(hours=starttid.hour, minutes=starttid.minute, seconds=starttid.second)
    slut_tid = (datetime(2000,1,1) + start_delta + timedelta(seconds=summa_tid_sec)).time()
    klockan_str = slut_tid.strftime("%H:%M:%S")

    # Hårdhet: +3 (DP>0), +4 (DPP>0), +6 (DAP>0), +8 (TAP>0), +3 (Svarta>0)
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3

    # Prenumeranter = (Män + 2*Svarta + Eskilstuna + Fitta + Rumpa + DP + DPP + DAP + TAP + Känner) * Hårdhet
    pren_bas = man + (2 * svarta) + esk + fitta + rumpa + dp + dpp + dap + tap + kanner
    prenumeranter = int(pren_bas * max(0, hardhet))

    intakter = float(prenumeranter) * float(avgift)
    # Ekonomi placeholders (låter appens totalsummering vara som idag)
    intakt_man     = 0.0  # kostnad för män hanteras i appen senare
    intakt_kanner  = 0.0
    lon_malin      = 0.0
    intakt_foretag = float(intakter) - (intakt_man + intakt_kanner + lon_malin)
    vinst          = float(intakter) - (intakt_man + intakt_kanner + lon_malin)

    # Ålder (kan vara bra att returnera för info i appen)
    alder = rad_datum.year - fodelsedatum.year - ((rad_datum.month, rad_datum.day) < (fodelsedatum.month, fodelsedatum.day))

    # Utskrift (alla fält app.py kan tänkas läsa)
    out = {}

    out["Typ"] = rad.get("Typ", "")
    out["Veckodag"] = rad.get("Veckodag", "")
    out["Scen"] = rad.get("Scen", "")
    out["Män"] = man
    out["Svarta"] = svarta
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap

    out["Tid S"] = tid_s
    out["Tid D"] = tid_d
    out["Vila"]  = vila
    out["DT tid (sek/kille)"]  = dt_tid
    out["DT vila (sek/kille)"] = dt_vila

    out["Summa S"] = int(summa_s)
    out["Summa D"] = int(summa_d)
    out["Summa TP"] = int(summa_tp)
    out["Summa Vila"] = int(summa_vila)

    out["Tid Älskar (sek)"] = int(tid_alskar_sec)
    out["Tid Älskar"] = _hm_str_from_seconds(int(tid_alskar_sec))
    out["Tid Sover med (sek)"] = int(tid_sover_sec)
    out["Tid Sover med"] = _hm_str_from_seconds(int(tid_sover_sec))

    out["Summa tid (sek)"] = int(summa_tid_sec)
    out["Summa tid"] = _hm_str_from_seconds(int(summa_tid_sec))

    out["Tid per kille (sek)"] = int(tid_per_kille_sec)
    out["Tid per kille"] = _ms_str_from_seconds(int(tid_per_kille_sec))

    out["Klockan"] = klockan_str
    out["Älskar"] = alskar
    out["Sover med"] = sover_med

    out["Känner"] = int(kanner)
    out["Pappans vänner"] = pappan
    out["Grannar"] = grann
    out["Nils vänner"] = nvann
    out["Nils familj"] = nfam
    out["Bekanta"] = bek

    out["Eskilstuna killar"] = esk

    out["Totalt Män"] = int(totalt_man)
    out["Tid kille"] = out["Tid per kille"]  # behållen textlabel
    out["Nils"] = nils

    out["Hångel (sek/kille)"] = int(hongel_per_kille_sec)
    out["Hångel (m:s/kille)"] = _ms_str_from_seconds(int(hongel_per_kille_sec))

    out["Suger"] = int(suger_total_sec)
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Avgift"] = float(avgift)
    out["Intäkter"] = float(intakter)

    out["Intäkt män"] = float(intakt_man)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Lön Malin"] = float(lon_malin)
    out["Intäkt Företaget"] = float(intakt_foretag)
    out["Vinst"] = float(vinst)

    out["Känner Sammanlagt"] = int(kanner)

    return out
