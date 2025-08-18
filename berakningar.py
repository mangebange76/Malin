# berakningar.py

from datetime import datetime, timedelta

def _safe_int(x, default=0):
    try:
        if x is None: 
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: 
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default

def _ms_str_from_seconds(sec: int) -> str:
    # m:ss
    if sec is None or sec <= 0:
        return "0m 0s"
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}m {s}s"

def _hm_str_from_seconds(q_sec: int) -> str:
    # h + min
    if q_sec is None or q_sec <= 0:
        return "0h 0 min"
    h = int(q_sec // 3600)
    m = int(round((q_sec % 3600) / 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m} min"

def _fmt_clock(starttid, plus_seconds: int) -> str:
    # Returnerar klockslag HH:MM (24h) givet en starttid (datetime.time) + sekunder
    try:
        base_dt = datetime(2000,1,1, starttid.hour, starttid.minute, 0)
    except Exception:
        # fallback 07:00
        base_dt = datetime(2000,1,1, 7, 0, 0)
    end_dt = base_dt + timedelta(seconds=int(max(0, plus_seconds)))
    return end_dt.strftime("%H:%M")

def _hardhet(tot_men: int, dp: int, dpp: int, dap: int, tap: int, svarta: int) -> int:
    h = 0
    # enligt specifikationen
    if dp  > 0: h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9
    if tot_men > 100:  h += 1
    if tot_men > 200:  h += 3
    if tot_men >= 300: h += 5
    if tot_men >= 500: h += 6
    if tot_men >= 1000: h += 10
    if svarta > 0: h += 3
    return h

def berakna_radvarden(grund: dict, *, rad_datum, fodelsedatum, starttid, cfg) -> dict:
    """
    Beräknar alla radfält utifrån givna indata (utan Google-anrop).

    Viktigt:
      - Summa S = Tid S * (Fitta + Rumpa) + (DT tid per kille * Totalt Män)
      - Summa D = Tid D * (DP + DPP + DAP)
      - Summa TP = Tid S * TAP
      - Summa Vila = Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + (DT vila per kille * Totalt Män)
      - Summa tid (sek) = Summa S + Summa D + Summa TP + Summa Vila  (exkluderar Älskar/Sover med)
      - Suger (sek) = 60% av Summa tid (sek)
      - Tid per kille (sek) = (Summa S/tot) + (Summa D/tot)*2 + (Summa TP/tot)*3 + (Suger/tot) + (DT tid per kille)
      - Hångel (sek/kille) = (3 timmar) / tot
      - Klockan = starttid + Summa tid + 3h + 1h + tid_alskar + tid_sover
      - Prenumeranter = (Fitta + Rumpa + DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
      - Intäkter = Prenumeranter * Avgift
      - Utgift män = (Män + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + PROD_STAFF) * (Summa tid h) * 15
        (Obs: Känner ingår inte i lönebas)
      - Intäkt Känner = (Summa tid h) * 35 * Känner
      - Lön Malin = 8% av max(Intäkter - Utgift män, 0) med golv 150 och tak 800
      - Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    """

    # --- Indata ---
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))
    rumpa   = _safe_int(grund.get("Rumpa", 0))
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))
    tid_d   = _safe_int(grund.get("Tid D", 0))
    vila    = _safe_int(grund.get("Vila", 0))

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))

    alskar  = _safe_int(grund.get("Älskar", 0))
    sover   = _safe_int(grund.get("Sover med", 0))

    pv      = _safe_int(grund.get("Pappans vänner", 0))
    gr      = _safe_int(grund.get("Grannar", 0))
    nv      = _safe_int(grund.get("Nils vänner", 0))
    nf      = _safe_int(grund.get("Nils familj", 0))
    bk      = _safe_int(grund.get("Bekanta", 0))
    esk     = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_k = _safe_int(grund.get("Bonus killar", 0))
    bonus_d = _safe_int(grund.get("Bonus deltagit", 0))

    # "Personal deltagit" används i tot-män, men lönebasen ersätts av PROD_STAFF
    pers_d  = _safe_int(grund.get("Personal deltagit", 0))

    nils    = _safe_int(grund.get("Nils", 0))
    avgift  = _safe_float(grund.get("Avgift", _safe_float(cfg.get("avgift_usd", 30.0))))

    prod_staff_total = _safe_int(grund.get("PROD_STAFF", _safe_int(cfg.get("PROD_STAFF", 800))))

    # Härledda
    kanner = pv + gr + nv + nf

    # Totalt Män (rad): Män, Känner, Svarta, Bekanta, Eskilstuna killar, Bonus deltagit, Personal deltagit
    tot_man = (
        man + kanner + svarta + bk + esk + bonus_d + pers_d
    )

    # --- Del-summor (sekunder) ---
    # Summa S inkluderar DT tid per kille * Totalt Män
    summa_s = tid_s * (fitta + rumpa) + dt_tid * tot_man

    # Summa D
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP (TAP-bitar)
    summa_tp = tid_s * tap  # själva tiden per TAP-akt

    # Summa Vila inkluderar DT vila per kille * Totalt Män
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * tot_man

    # Älskar/Sover (sek) — dessa ska INTE ingå i Summa tid/arbete
    tid_alskar_sec = alskar * 20 * 60
    tid_sover_sec  = sover  * 20 * 60

    # Summa tid (sek) = arbetstid
    summa_tid_sec = int(summa_s + summa_d + summa_tp + summa_vila)

    # Suger = 60% av Summa tid (sek)
    suger_sec = int(round(summa_tid_sec * 0.60))

    # Tid per kille (sek)
    if tot_man > 0:
        tid_per_kille_sec = (
            (summa_s / tot_man)
            + (summa_d / tot_man) * 2
            + (summa_tp / tot_man) * 3
            + (suger_sec / tot_man)
            + dt_tid  # per kille direkt
        )
        tid_per_kille_sec = int(round(tid_per_kille_sec))
    else:
        tid_per_kille_sec = 0

    # Hångel (sek/kille) = 3 timmar / tot_man
    if tot_man > 0:
        hangel_sec_per = int(round((3 * 3600) / tot_man))
    else:
        hangel_sec_per = 0

    # Klockan = starttid + (summa tid) + 3h + 1h + älskar + sover
    clock_plus = int(summa_tid_sec + (3 * 3600) + (1 * 3600) + tid_alskar_sec + tid_sover_sec)
    klockan_label = _fmt_clock(starttid, clock_plus)

    # Hårdhet
    hardhet = _hardhet(tot_man, dp, dpp, dap, tap, svarta)

    # Prenumeranter = (Fitta + Rumpa + DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    pren = int((fitta + rumpa + dp + dpp + dap + tap + tot_man) * hardhet)

    # Intäkter
    intakter = float(pren) * float(avgift)

    # Utgift män:
    #  (Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + PROD_STAFF) * (summa_tid_h) * 15
    summa_tid_h = float(summa_tid_sec) / 3600.0
    lon_bas_count = man + svarta + bk + esk + bonus_d + prod_staff_total
    utgift_man = float(lon_bas_count) * summa_tid_h * 15.0

    # Intäkt Känner
    intakt_kanner = float(kanner) * summa_tid_h * 35.0

    # Lön Malin: 8% av max(Intäkter - Utgift män, 0) med golv 150 & tak 800
    kvar = max(0.0, float(intakter) - float(utgift_man))
    lon_malin = max(150.0, min(800.0, 0.08 * kvar))

    # Vinst
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # Presentabla strängar
    tid_per_kille_str = _ms_str_from_seconds(tid_per_kille_sec)
    hangel_str = _ms_str_from_seconds(hangel_sec_per)
    summa_tid_str = _hm_str_from_seconds(summa_tid_sec)
    tid_alskar_str = _hm_str_from_seconds(tid_alskar_sec)
    tid_sover_str  = _hm_str_from_seconds(tid_sover_sec)

    # Bygg resultat
    res = {
        # Inmatning som ev. saknas i grund fylls på, övrigt beräkningar
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),

        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": tid_alskar_str,

        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": tid_sover_str,

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": summa_tid_str,

        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": tid_per_kille_str,

        "Klockan": klockan_label,

        "Älskar": alskar,
        "Sover med": sover,

        "Känner": int(kanner),
        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,

        "Bonus killar": bonus_k,
        "Bonus deltagit": bonus_d,

        "Personal deltagit": pers_d,

        "Totalt Män": int(tot_man),
        "Tid kille": tid_per_kille_str,  # (legacy-titel)

        "Nils": nils,

        "Hångel (sek/kille)": int(hangel_sec_per),
        "Hångel (m:s/kille)": hangel_str,

        "Suger": int(suger_sec),
        "Suger per kille (sek)": int(round(suger_sec / tot_man)) if tot_man > 0 else 0,

        "Hårdhet": int(hardhet),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # “Känner Sammanlagt” – inte definierat som ack i denna funktion; returnera radens Känner
        "Känner Sammanlagt": int(kanner),
    }

    return res
