from datetime import datetime, date, time, timedelta

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return int(float(x))
    except:
        return default

def _fmt_hms(total_seconds: int):
    h = total_seconds//3600
    m = (total_seconds%3600)//60
    s = total_seconds%60
    return f"{h}h {m} min" if s==0 else f"{h}h {m}m {s}s"

def _fmt_ms(sec:int):
    m = sec//60
    s = sec%60
    return f"{m}:{s:02d}"

def berakna_radvarden(grund: dict, rad_datum: date, fodelsedatum: date, starttid: time):
    # Läs in
    man    = _safe_int(grund.get("Män",0))
    svarta = _safe_int(grund.get("Svarta",0))
    fitta  = _safe_int(grund.get("Fitta",0))
    rumpa  = _safe_int(grund.get("Rumpa",0))
    dp     = _safe_int(grund.get("DP",0))
    dpp    = _safe_int(grund.get("DPP",0))
    dap    = _safe_int(grund.get("DAP",0))
    tap    = _safe_int(grund.get("TAP",0))

    tid_s  = _safe_int(grund.get("Tid S",60))
    tid_d  = _safe_int(grund.get("Tid D",60))
    vila   = _safe_int(grund.get("Vila",7))
    dt_tid = _safe_int(grund.get("DT tid (sek/kille)",60))
    dt_vila= _safe_int(grund.get("DT vila (sek/kille)",3))

    alskar = _safe_int(grund.get("Älskar",0))
    sover  = _safe_int(grund.get("Sover med",0))

    pv  = _safe_int(grund.get("Pappans vänner",0))
    gr  = _safe_int(grund.get("Grannar",0))
    nv  = _safe_int(grund.get("Nils vänner",0))
    nf  = _safe_int(grund.get("Nils familj",0))
    bk  = _safe_int(grund.get("Bekanta",0))
    esk = _safe_int(grund.get("Eskilstuna killar",0))

    bonus_total = _safe_int(grund.get("Bonus killar",0))
    bonus_d     = _safe_int(grund.get("Bonus deltagit",0))
    personal_d  = _safe_int(grund.get("Personal deltagit",0))

    avgift      = float(grund.get("Avgift",30.0))
    prod_staff  = _safe_int(grund.get("PROD_STAFF",800))

    # Känner
    kanner = pv + gr + nv + nf
    # Totalt män (explicit lista enligt din spec – utan personal_d)
    totalt_man = man + kanner + svarta + bk + esk + bonus_d

    # ---- Summa-tider ----
    summa_s   = tid_s * (fitta + rumpa) + dt_tid * totalt_man
    summa_d   = tid_d * (dp + dpp + dap)
    summa_tp  = (tid_s + tid_d) * tap  # själva TP-momentets “extra”
    summa_vila= vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * totalt_man

    # Älskar / Sover med – separat (påverkar klockan men inte “Summa tid”)
    tid_alskar_sec = alskar * 20 * 60
    tid_sover_sec  = sover  * 20 * 60

    # Summa tid (sek) för scen (exkl. älskar/sover; enligt dina instruktioner)
    total_sec = int(summa_s + summa_d + summa_tp + summa_vila)

    # Klockan = start + arbetstid + 3h + 1h + älskar + sover
    start_dt = datetime.combine(rad_datum, starttid)
    end_dt   = start_dt + timedelta(seconds=total_sec + 3*3600 + 1*3600 + tid_alskar_sec + tid_sover_sec)
    klockan_str = end_dt.strftime("%H:%M")

    # Suger = 60% av scenens totala arbetstid (sek)
    suger_tot = int(round(total_sec * 0.60))

    # Tid per kille (sek)
    if totalt_man > 0:
        tpk_sec = (
            (summa_s / totalt_man)
          + (summa_d / totalt_man) * 2
          + (summa_tp / totalt_man) * 3
          + (suger_tot / totalt_man)
          + dt_tid
        )
        tpk_sec = int(round(tpk_sec))
    else:
        tpk_sec = 0

    # Hångel: 3 timmar / (män + svarta + bekanta + esk + bonus + personal_d)
    denom_hangel = man + svarta + bk + esk + bonus_d + personal_d
    hangel_per_kille_sec = int(round((3*3600) / denom_hangel)) if denom_hangel > 0 else 0

    # Hårdhet
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 3
    if totalt_man >= 300: hardhet += 5
    if totalt_man >= 500: hardhet += 6
    if totalt_man >= 1000: hardhet += 10
    if svarta > 0: hardhet += 3

    # Prenumeranter
    pren_base = fitta + rumpa + dp + dpp + dap + tap + totalt_man
    pren = int(round(pren_base * hardhet))

    # Intäkter
    intakter = float(pren) * float(avgift)

    # Utgift män (alla “män” + ALL personal i lön, oavsett deltagit)
    # timmar = total_sec/3600
    timmar = total_sec / 3600.0
    utgift_man = (man + svarta + bk + esk + bonus_d + prod_staff) * timmar * 15.0

    # Intäkt Känner: timmar * 35 * Känner
    intakt_kanner = timmar * 35.0 * kanner

    # Lön Malin = 8% av (intäkter - utgift män - intäkt Känner), clamp 150..800
    kvar = max(0.0, float(intakter) - float(utgift_man) - float(intakt_kanner))
    lon_malin = max(150.0, min(800.0, 0.08 * kvar))

    # Vinst = Intäkter - (utgift män + intäkt Känner + lön)
    vinst = float(intakter) - float(utgift_man) - float(intakt_kanner) - float(lon_malin)

    # Format
    res = {
        "Typ": grund.get("Typ",""),
        "Veckodag": grund.get("Veckodag",""),
        "Scen": grund.get("Scen",""),
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": alskar, "Sover med": sover,
        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bk, "Eskilstuna killar": esk,
        "Bonus killar": bonus_total, "Bonus deltagit": bonus_d, "Personal deltagit": personal_d,
        "Känner": kanner,
        "Totalt Män": totalt_man,
        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),
        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _ms_str := _fmt_ms(int(tid_alskar_sec)),
        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _fmt_ms(int(tid_sover_sec)),
        "Summa tid (sek)": int(total_sec),
        "Summa tid": _fmt_hms(int(total_sec)),
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _fmt_ms(int(hangel_per_kille_sec)),
        "Suger": int(suger_tot),
        "Suger per kille (sek)": int(round(suger_tot / totalt_man)) if totalt_man>0 else 0,
        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": _fmt_ms(int(tpk_sec)),
        "Klockan": klockan_str,
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),
        "Känner Sammanlagt": kanner  # kan användas i statistik
    }
    return res
