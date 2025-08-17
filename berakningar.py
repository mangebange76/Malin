from datetime import datetime, timedelta

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

def _sec_to_hm_str(sec: int) -> str:
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _sec_to_ms_str(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _safe_int(x, default=0):
    try:
        if x is None: return default
        return int(float(x))
    except Exception:
        return default

def _hardhet(dp, dpp, dap, tap, totman, svarta):
    h = 0
    if dp  > 0: h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9
    # trösklar för totalt män
    if totman >= 1000: h += 10
    elif totman >= 500: h += 6
    elif totman >= 300: h += 5
    elif totman > 200:  h += 3
    elif totman > 100:  h += 1
    if svarta > 0: h += 3
    return h

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    # Plocka ut
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

    pv = _safe_int(grund.get("Pappans vänner", 0))
    gr = _safe_int(grund.get("Grannar", 0))
    nv = _safe_int(grund.get("Nils vänner", 0))
    nf = _safe_int(grund.get("Nils familj", 0))
    bk = _safe_int(grund.get("Bekanta", 0))
    esk = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_deltagit = _safe_int(grund.get("Bonus deltagit", 0))
    personal_deltagit = _safe_int(grund.get("Personal deltagit", 80))
    avgift = float(grund.get("Avgift", 30.0) or 30.0)
    prod_staff = _safe_int(grund.get("PROD_STAFF", 800))

    # Känner
    kanner = pv + gr + nv + nf

    # Totalt män (OBS: personal ingår inte)
    tot_man = man + kanner + svarta + bk + esk + bonus_deltagit

    # Summa S: Tid S*(Fitta+Rumpa) + DT tid * Totalt män
    summa_s = tid_s * (fitta + rumpa) + dt_tid * tot_man

    # Summa D: Tid D*(DP + DPP + DAP)
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP: TAP * Tid D (enligt specifikationen)
    summa_tp = tap * tid_d

    # Summa Vila: Vila*(Fitta+Rumpa+DP+DPP+DAP+TAP) + DT vila * Totalt män
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * tot_man

    # Tid Älskar / Sover med (sek) – läggs på klockan, inte i Summa tid
    tid_alskar_sec = alskar * 20 * 60
    tid_sover_sec  = sover * 20 * 60

    # Summa tid (sek) – scenens arbetstid (exkl. älskar/sover)
    summa_tid_sec = int(summa_s + summa_d + summa_tp + summa_vila)

    # Suger = 60% av scenens tid
    suger_total_sec = int(round(summa_tid_sec * 0.60))
    suger_per_kille_sec = int(suger_total_sec / tot_man) if tot_man > 0 else 0

    # Tid per kille (sek)
    if tot_man > 0:
        tpk_sec = (
            (summa_s / tot_man)
            + 2 * (summa_d / tot_man)
            + 3 * (summa_tp / tot_man)
            + (suger_total_sec / tot_man)
            + dt_tid  # explicit enligt specifikation, även om dt redan ingår i summa_s
        )
        tpk_sec = int(round(tpk_sec))
    else:
        tpk_sec = 0

    # Hångel (sek/kille) = 3h / (män+svarta+bekanta+esk+bonus+personal_deltagit)
    denom_hang = man + svarta + bk + esk + bonus_deltagit + personal_deltagit
    hangel_per_kille_sec = int(10800 / denom_hang) if denom_hang > 0 else 0

    # Klockan: start + summa_tid_sec + 3h + 1h + älskar + sover
    if isinstance(starttid, str):
        st_h, st_m = [int(x) for x in starttid.split(":")]
        start_dt = datetime(rad_datum.year, rad_datum.month, rad_datum.day, st_h, st_m)
    else:
        start_dt = datetime(rad_datum.year, rad_datum.month, rad_datum.day, starttid.hour, starttid.minute)
    extra_sec = (3+1)*3600 + tid_alskar_sec + tid_sover_sec
    end_dt = start_dt + timedelta(seconds=summa_tid_sec + extra_sec)
    klockan_str = end_dt.strftime("%H:%M")

    # Hårdhet
    hard = _hardhet(dp, dpp, dap, tap, tot_man, svarta)

    # Prenumeranter
    pren = (fitta + rumpa + dp + dpp + dap + tap + tot_man) * hard
    pren = int(pren)

    # Intäkter
    intakter = float(pren) * float(avgift)

    # Utgift män = (män + svarta + bekanta + esk + bonus + ALL PERSONAL) * (summa tid i timmar) * 15
    timmar = float(summa_tid_sec) / 3600.0
    utgift_man = (man + svarta + bk + esk + bonus_deltagit + prod_staff) * timmar * 15.0

    # Intäkt Känner = Känner * timmar * 35
    intakt_kanner = kanner * timmar * 35.0

    # Lön Malin = 8% av (intäkter - utgift män), clamp 150..800
    grund_lonebas = intakter - utgift_man
    lon_malin = _clamp(grund_lonebas * 0.08, 150.0, 800.0)

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # Bonus killar (från pren) – förhandsvärde (5% sannolikhet per prenumerant)
    # För live kör vi en deterministisk uppskattning: 5% av pren.
    bonus_killar_from_pren = int(round(pren * 0.05))

    # Malins ålder (visas i app, men returnerar inte explicit som kolumn)
    age = rad_datum.year - fodelsedatum.year - ((rad_datum.month, rad_datum.day) < (fodelsedatum.month, fodelsedatum.day))

    # Retur
    return {
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag",""),
        "Scen": grund.get("Scen",""),
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": alskar, "Sover med": sover,

        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bk, "Eskilstuna killar": esk,

        "Känner": kanner,
        "Bonus killar": bonus_killar_from_pren,
        "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,

        "Totalt Män": tot_man,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _sec_to_hm_str(int(tid_alskar_sec)),
        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _sec_to_hm_str(int(tid_sover_sec)),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": _sec_to_hm_str(int(summa_tid_sec)),

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": _sec_to_ms_str(int(tpk_sec)),

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _sec_to_ms_str(int(hangel_per_kille_sec)),

        "Hårdhet": int(hard),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        "Klockan": klockan_str
    }

# (inget mer behövs här – filen slutar efter berakna_radvarden)
