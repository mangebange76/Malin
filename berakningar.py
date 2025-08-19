from datetime import datetime, time, timedelta

def _hm_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _safe_int(x, d=0):
    try: return int(float(x))
    except: return d

def _safe_float(x, d=0.0):
    try: return float(x)
    except: return d

def _time_add(start: time, add_seconds: int) -> str:
    dt = datetime.combine(datetime.today().date(), start) + timedelta(seconds=add_seconds)
    return dt.strftime("%H:%M")

def _hardhet(grund: dict, tot_men: int) -> int:
    h = 0
    if _safe_int(grund.get("DP",0))  > 0: h += 3
    if _safe_int(grund.get("DPP",0)) > 0: h += 5
    if _safe_int(grund.get("DAP",0)) > 0: h += 7
    if _safe_int(grund.get("TAP",0)) > 0: h += 9
    if _safe_int(grund.get("Svarta",0)) > 0: h += 3
    # trösklar på tot_men
    if tot_men > 100: h += 1
    if tot_men > 200: h += 3
    if tot_men == 300: h += 5
    if tot_men == 500: h += 6
    if tot_men == 1000: h += 10
    return h

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    # ------- läsa in -------
    man   = _safe_int(grund.get("Män",0))
    sv    = _safe_int(grund.get("Svarta",0))
    fitta = _safe_int(grund.get("Fitta",0))
    rumpa = _safe_int(grund.get("Rumpa",0))
    DP    = _safe_int(grund.get("DP",0))
    DPP   = _safe_int(grund.get("DPP",0))
    DAP   = _safe_int(grund.get("DAP",0))
    TAP   = _safe_int(grund.get("TAP",0))

    papp  = _safe_int(grund.get("Pappans vänner",0))
    gran  = _safe_int(grund.get("Grannar",0))
    nv    = _safe_int(grund.get("Nils vänner",0))
    nf    = _safe_int(grund.get("Nils familj",0))
    bek   = _safe_int(grund.get("Bekanta",0))
    esk   = _safe_int(grund.get("Eskilstuna killar",0))

    bonus_delt = _safe_int(grund.get("Bonus deltagit",0))
    pers_delt  = _safe_int(grund.get("Personal deltagit",0))

    alskar = _safe_int(grund.get("Älskar",0))
    sover  = _safe_int(grund.get("Sover med",0))

    tidS   = _safe_int(grund.get("Tid S",0))
    tidD   = _safe_int(grund.get("Tid D",0))
    vila   = _safe_int(grund.get("Vila",0))
    dt_tid = _safe_int(grund.get("DT tid (sek/kille)",0))
    dt_vila= _safe_int(grund.get("DT vila (sek/kille)",0))

    avgift = _safe_float(grund.get("Avgift",30.0))
    prod_staff = _safe_int(grund.get("PROD_STAFF",0))

    kanner = _safe_int(grund.get("Känner",0))

    # ------- totals -------
    tot_man = (
        man + kanner + sv + bek + esk + bonus_delt + pers_delt
    )

    # ------- tider (sek) -------
    summaS  = tidS * (fitta + rumpa) + dt_tid * max(tot_man, 0)  # DT tid in i S
    summaD  = tidD * (DP + DPP + DAP)
    summaTP = tidS * TAP
    summaV  = vila * (fitta + rumpa + DP + DPP + DAP + TAP) + dt_vila * max(tot_man, 0)

    summa_tid_sec = summaS + summaD + summaTP + summaV
    summa_tid_txt = _hm_from_seconds(summa_tid_sec)

    # älskar/sover (ej med i summa tid)
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover  * 20 * 60

    # tid per kille
    if tot_man > 0:
        per_s  = summaS  / tot_man
        per_d  = (summaD / tot_man) * 2
        per_tp = (summaTP/ tot_man) * 3
        per_tot = per_s + per_d + per_tp + (summaV / tot_man)
    else:
        per_tot = 0

    # suger = 60% av scenens (summa tid), per kille:
    suger_tot = 0.60 * summa_tid_sec
    suger_pk  = (suger_tot / tot_man) if tot_man > 0 else 0

    # klockan (lägg på 3 + 1 min + alskar+sover)
    extra_sec = (3+1)*60 + alskar_sec + sover_sec
    klockan = _time_add(starttid, int(summa_tid_sec + extra_sec))

    # hångel: 3h / (män+svarta+bekanta+eskilstuna+bonus_delt+personal_delt)
    denom_h = man + sv + bek + esk + bonus_delt + pers_delt
    hangel_pk_sec = int((3*3600) / denom_h) if denom_h > 0 else 0
    hangel_pk_txt = _ms_from_seconds(hangel_pk_sec)

    # hårdhet & prenumeranter
    h = _hardhet(grund, tot_man)
    pren = (fitta + rumpa + DP + DPP + DAP + TAP + tot_man) * h

    # ekonomi
    intakter = pren * avgift
    # Utgift män = (män + svarta + bekanta + esk + bonus_delt + HELA personalstyrkan) * (summa_tid_timmar*15)
    timmar = summa_tid_sec / 3600.0
    utgift_man = (man + sv + bek + esk + bonus_delt + prod_staff) * (timmar * 15.0)

    # Intäkt Känner (sparas också)
    intakt_kanner = kanner * (timmar * 35.0)

    # Lön Malin = 8% av (intäkter - utgift män), minst 150, max 800
    malin = max(150.0, min(800.0, 0.08 * (intakter - utgift_man)))

    # Vinst = Intäkter - (utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + malin)

    # Ålder vid datum
    fd = fodelsedatum
    alder = rad_datum.year - fd.year - ((rad_datum.month, rad_datum.day) < (fd.month, fd.day))

    # svar-dict (alla kolumnnamn som i databasen)
    out = dict(grund)  # behåll originalfält
    out.update({
        "Datum": rad_datum.isoformat(),
        "Veckodag": grund.get("Veckodag",""),
        "Scen": grund.get("Scen",""),
        "Totalt Män": tot_man,

        "Summa S": int(summaS),
        "Summa D": int(summaD),
        "Summa TP": int(summaTP),
        "Summa Vila": int(summaV),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": summa_tid_txt,

        "Tid per kille (sek)": int(per_tot),
        "Tid per kille": _ms_from_seconds(int(per_tot)),

        "Suger": int(suger_tot),
        "Suger per kille (sek)": int(suger_pk),

        "Hångel (sek/kille)": int(hangel_pk_sec),
        "Hångel (m:s/kille)": hangel_pk_txt,

        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": _ms_from_seconds(int(alskar_sec)),
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": _ms_from_seconds(int(sover_sec)),

        "Klockan": klockan,
        "Hårdhet": int(h),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(malin),
        "Vinst": float(vinst),

        "Känner Sammanlagt": int(kanner),
        "Ålder": int(alder),
    })
    return out
