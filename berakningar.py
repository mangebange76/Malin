from datetime import datetime, timedelta

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

def _safe_i(x):
    try:
        return int(float(x))
    except Exception:
        return 0

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med samtliga beräknade värden för en rad.
    Inga externa anrop. Håller sig till dina regler:
      - Summa S = Tid S*(Fitta+Rumpa) + (DT tid per kille)*Totalt män
      - Summa D = Tid D*(DP+DPP+DAP)
      - Summa TP = Tid S*(TAP)      (enligt tidigare 'du hade rätt på')
      - Summa Vila = Vila*(Fitta+Rumpa+DP+DPP+DAP+TAP) + (DT vila per kille)*Totalt män
      - Älskar/Sover: 20 min per styck (räknas inte i Summa tid)
      - Hångel = 3h / (Män+Svarta+Bekanta+Eskilstuna+Bonus deltagit+Personal deltagit)
      - Suger = 60% av Summa tid; Suger/kille = / Totalt män
      - Tid per kille = [Summa S / TM] + [Summa D / TM *2] + [Summa TP / TM *3] + [Suger/TM] + [DT tid/kille]
      - Klockan = start + Summa tid + 3h + 1h + älskar + sover
      - Prenumeranter = (Fitta+Rumpa+DP+DPP+DAP+TAP + Totalt Män) * Hårdhet
      - Hårdhet: DP>0:+3, DPP>0:+5, DAP>0:+7, TAP>0:+9,
                 TM>100:+1, >200:+3, >=300:+5, >=500:+6, >=1000:+10, Svarta>0:+3
      - Utgift män = (Summa tid timmar) * 15 USD * (Män+Svarta+Bekanta+Eskilstuna+Bonus deltagit + PROD_STAFF)
      - Intäkt Känner = (Summa tid timmar) * 35 USD * Känner
      - Lön Malin = clamp(8%*(Intäkter - Utgift män), 150..800)
      - Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    """

    gi = lambda k: _safe_i(grund.get(k, 0))

    man      = gi("Män")
    svarta   = gi("Svarta")
    fitta    = gi("Fitta")
    rumpa    = gi("Rumpa")
    dp       = gi("DP")
    dpp      = gi("DPP")
    dap      = gi("DAP")
    tap      = gi("TAP")
    pv       = gi("Pappans vänner")
    gr       = gi("Grannar")
    nv       = gi("Nils vänner")
    nf       = gi("Nils familj")
    bekanta  = gi("Bekanta")
    esk      = gi("Eskilstuna killar")
    bonus_d  = gi("Bonus deltagit")
    pers_d   = gi("Personal deltagit")
    alskar   = gi("Älskar")
    sover    = gi("Sover med")
    tid_s    = gi("Tid S")
    tid_d    = gi("Tid D")
    vila     = gi("Vila")
    dt_tid_k = gi("DT tid (sek/kille)")
    dt_vil_k = gi("DT vila (sek/kille)")
    nils     = gi("Nils")
    avgift   = float(grund.get("Avgift", 30.0) or 30.0)
    prod_staff = gi("PROD_STAFF")  # hela personalstyrkan

    # härledning
    känner = pv + gr + nv + nf
    totalt_man = man + svarta + bekanta + esk + bonus_d + pers_d + känner

    # tider (sek)
    summa_s   = tid_s * (fitta + rumpa) + dt_tid_k * totalt_man
    summa_d   = tid_d * (dp + dpp + dap)
    summa_tp  = tid_s * tap
    summa_vila= vila  * (fitta + rumpa + dp + dpp + dap + tap) + dt_vil_k * totalt_man

    summa_tid_sec = summa_s + summa_d + summa_tp + summa_vila  # utan älskar/sover
    summa_tid_txt = _hm_from_seconds(summa_tid_sec)

    # älskar/sover
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover * 20 * 60

    # hångel (ej inräknat i summa tid, bara visning)
    deltagare_hangel = max(1, man + svarta + bekanta + esk + bonus_d + pers_d)
    hangel_per_kille_sec = int(round(3*3600 / deltagare_hangel))
    hangel_per_kille_txt = _ms_from_seconds(hangel_per_kille_sec)

    # suger
    suger_total_sec = int(round(0.60 * summa_tid_sec))
    suger_per_kille_sec = int(round(suger_total_sec / max(1, totalt_man)))

    # tid per kille
    if totalt_man > 0:
        tpk_sec = (
            (summa_s / totalt_man) +
            (summa_d / totalt_man) * 2 +
            (summa_tp / totalt_man) * 3 +
            suger_per_kille_sec +
            dt_tid_k
        )
    else:
        tpk_sec = 0
    tpk_txt = _ms_from_seconds(int(tpk_sec))

    # klockan (start + summa tid + 3h + 1h + älskar + sover)
    start_dt = datetime.combine(rad_datum, starttid)
    klockan_dt = start_dt + timedelta(seconds=(summa_tid_sec + 4*3600 + alskar_sec + sover_sec))
    klockan_txt = klockan_dt.strftime("%H:%M")

    # hårdhet
    hard = 0
    if dp > 0:  hard += 3
    if dpp > 0: hard += 5
    if dap > 0: hard += 7
    if tap > 0: hard += 9
    if totalt_man > 100:  hard += 1
    if totalt_man > 200:  hard += 3
    if totalt_man >= 300: hard += 5
    if totalt_man >= 500: hard += 6
    if totalt_man >= 1000: hard += 10
    if svarta > 0: hard += 3

    pren = int((fitta + rumpa + dp + dpp + dap + tap + totalt_man) * hard)
    intakter = float(pren) * float(avgift)

    # utgift män: alla personal (PROD_STAFF) + män som inte är "känner"
    betalda = man + svarta + bekanta + esk + bonus_d + prod_staff
    timmar  = float(summa_tid_sec) / 3600.0
    utgift_man = timmar * 15.0 * float(betalda)

    # intäkt "känner"
    intakt_kanner = timmar * 35.0 * float(känner)

    # lön Malin = 8% av (intäkter - utgift män) clamp 150..800
    kvar = max(0.0, float(intakter) - float(utgift_man))
    lon_malin = max(150.0, min(800.0, 0.08 * kvar))

    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # bygg resultat
    res = {
        "Datum": rad_datum.isoformat(),
        "Veckodag": _weekday(rad_datum),
        "Scen": grund.get("Scen", ""),
        "Typ": grund.get("Typ", ""),

        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa,
        "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,

        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid_k, "DT vila (sek/kille)": dt_vil_k,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": _ms_from_seconds(int(alskar_sec)),

        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": _ms_from_seconds(int(sover_sec)),

        "Summa tid": summa_tid_txt,
        "Summa tid (sek)": int(summa_tid_sec),

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tpk_txt,

        "Klockan": klockan_txt,
        "Älskar": alskar, "Sover med": sover, "Känner": känner,

        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bekanta, "Eskilstuna killar": esk,

        "Bonus killar": int(grund.get("Bonus killar", 0)),
        "Bonus deltagit": bonus_d,
        "Personal deltagit": pers_d,
        "Totalt Män": int(totalt_man),
        "Nils": nils,

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_per_kille_txt,

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Hårdhet": int(hard),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),
    }
    return res

def _weekday(d):
    return ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][d.weekday()]
