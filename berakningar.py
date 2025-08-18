from datetime import datetime, timedelta, date, time

def _safe_int(x, d=0):
    try:
        if x is None: return d
        if isinstance(x, str) and x.strip() == "": return d
        return int(float(x))
    except Exception:
        return d

def _safe_float(x, d=0.0):
    try:
        if x is None: return d
        if isinstance(x, str) and x.strip() == "": return d
        return float(x)
    except Exception:
        return d

def _hm_from_seconds(sec: int) -> str:
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _format_clock(start: time, add_seconds: int) -> str:
    # start + add_seconds → "HH:MM"
    dt = datetime.combine(date.today(), start) + timedelta(seconds=int(add_seconds))
    return dt.strftime("%H:%M")

def berakna_radvarden(grund: dict, rad_datum: date, fodelsedatum: date, starttid: time) -> dict:
    """
    Implementerar alla beräkningar enligt din specifikation.
    - Summa S = Tid S*(Fitta+Rumpa) + DT_tid * Totalt män
    - Summa D = Tid D*(DP+DPP+DAP)
    - Summa TP = Tid D*(TAP)     (3-faktorn används i 'Tid per kille', inte här)
    - Summa Vila = Vila*(Fitta+Rumpa+DP+DPP+DAP+TAP) + DT_vila*Totalt män
    - 'Summa tid' = S + D + TP + Vila  (sek)
    - 'Suger' = 60% av Summa tid (sek)
    - 'Tid per kille (sek)' = (S/tot)+(D/tot)*2+(TP/tot)*3 + (Suger/tot) + DT_tid
    - Hångel per kille = 3 timmar / Totalt Män
    - Älskar=20 min/st, Sover=20 min om 1; dessa **ingår ej** i Summa tid, men adderas till 'Klockan'
    - Hårdhet enligt dina regler
    - Prenumeranter = (Fitta+Rumpa+DP+DPP+DAP+TAP+Totalt Män) * Hårdhet
    - Intäkter = Prenumeranter * Avgift
    - Utgift män = (Män+Svarta+Bekanta+Eskilstuna killar+Bonus deltagit + PROD_STAFF) * (Summa tid h) * 15
                   (PROD_STAFF ersätter "Personal deltagit" i lönebasen)
    - Intäkt Känner = (Summa tid h) * 35 * Känner
    - Lön Malin = clamp(0.08 * max(Intäkter - Utgift män, 0), 150, 800)
    - Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    """
    g = lambda k, d=0: _safe_int(grund.get(k, d))
    gf = lambda k, d=0.0: _safe_float(grund.get(k, d))

    # Input
    man = g("Män")
    svarta = g("Svarta")
    fitta = g("Fitta")
    rumpa = g("Rumpa")
    dp  = g("DP")
    dpp = g("DPP")
    dap = g("DAP")
    tap = g("TAP")

    pappan = g("Pappans vänner")
    grannar = g("Grannar")
    nv = g("Nils vänner")
    nf = g("Nils familj")
    bek = g("Bekanta")
    esk = g("Eskilstuna killar")

    bonus_tot = g("Bonus killar")      # total tillgängliga (visning)
    bonus_deltagit = g("Bonus deltagit")

    personal_deltagit = g("Personal deltagit")  # OBS: ej i lönebas (ersätts av PROD_STAFF)
    prod_staff = g("PROD_STAFF", 0)             # hela personalstyrkan

    alskar = g("Älskar")
    sover  = g("Sover med")

    tid_s = g("Tid S", 60)
    tid_d = g("Tid D", 60)
    vila   = g("Vila", 7)
    dt_tid = g("DT tid (sek/kille)", 60)
    dt_vila = g("DT vila (sek/kille)", 3)

    avgift = gf("Avgift", 30.0)

    # Härledda
    känner = pappan + grannar + nv + nf

    # Totalt män (raden) – enligt din lista
    totalt_man = (
        man + känner + svarta + bek + esk + bonus_deltagit + personal_deltagit
    )

    # -------- Tider (sek) --------
    summa_s   = tid_s * (fitta + rumpa) + dt_tid * max(0, totalt_man)
    summa_d   = tid_d * (dp + dpp + dap)
    summa_tp  = tid_d * (tap)
    summa_vila= vila  * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * max(0, totalt_man)

    summa_tid_sec = int(summa_s + summa_d + summa_tp + summa_vila)

    # Suger (60% av scenens tid)
    suger_total_sec = int(round(summa_tid_sec * 0.60))
    suger_per_kille = int(suger_total_sec / totalt_man) if totalt_man > 0 else 0

    # Tid per kille (sek)
    if totalt_man > 0:
        tpk_sec = (
            (summa_s / totalt_man)
            + (summa_d / totalt_man) * 2
            + (summa_tp / totalt_man) * 3
            + (suger_total_sec / totalt_man)
            + dt_tid
        )
    else:
        tpk_sec = 0
    tpk_sec = int(round(tpk_sec))

    # Hångel (per kille)
    hangel_per_kille_sec = int(round( (3*3600) / totalt_man )) if totalt_man > 0 else 0

    # Älskar/Sover tider (sek)
    alskar_sec = int(alskar * 20 * 60)
    sover_sec  = int(sover * 20 * 60)

    # -------- Hårdhet --------
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    if svarta > 0: hardhet += 3

    # Trösklar för totalt män
    if totalt_man >= 1000: hardhet += 10
    elif totalt_man >= 500: hardhet += 6
    elif totalt_man >= 300: hardhet += 5
    elif totalt_man >= 200: hardhet += 3
    elif totalt_man >= 100: hardhet += 1

    # -------- Prenumeranter/Intäkter --------
    subs_base = fitta + rumpa + dp + dpp + dap + tap + totalt_man
    pren = int(max(0, subs_base) * max(0, hardhet))
    intakter = float(pren) * float(avgift)

    # -------- Ekonomi --------
    # Utgift män: (män-relaterade + full personalstyrka via PROD_STAFF) * tid(h) * 15
    tid_h = float(summa_tid_sec) / 3600.0
    lon_mansbas = (man + svarta + bek + esk + bonus_deltagit + prod_staff)
    utgift_man = float(lon_mansbas) * float(tid_h) * 15.0

    # Intäkt Känner: 35 USD per timme * Känner
    intakt_kanner = float(tid_h) * 35.0 * float(känner)

    # Lön Malin: 8% av max(Intäkter - Utgift män, 0), clamp 150..800
    kvar = max(0.0, float(intakter) - float(utgift_man))
    lon_malin_raw = 0.08 * kvar
    lon_malin = min(800.0, max(150.0, lon_malin_raw)) if lon_malin_raw > 0 else 150.0

    # Vinst
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # -------- Klockan (start + scenens tid + 3h + 1h + älskar + sover) --------
    add_sec_clock = int(summa_tid_sec + (3*3600) + (1*3600) + alskar_sec + sover_sec)
    klockan_str = _format_clock(starttid, add_sec_clock)

    # Formateringar
    result = {
        # metadata
        "Datum": rad_datum.isoformat() if isinstance(rad_datum, date) else str(rad_datum),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),

        # inmatning som speglas
        "Typ": grund.get("Typ", ""),
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Älskar": alskar, "Sover med": sover,
        "Pappans vänner": pappan, "Grannar": grannar, "Nils vänner": nv, "Nils familj": nf, "Bekanta": bek, "Eskilstuna killar": esk,
        "Bonus killar": bonus_tot, "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_deltagit,
        "Nils": grund.get("Nils", 0),
        "Avgift": avgift,
        "Känner": känner,

        # tidsblock (sek)
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": alskar_sec,
        "Tid Älskar": _ms_from_seconds(alskar_sec),
        "Tid Sover med (sek)": sover_sec,
        "Tid Sover med": _ms_from_seconds(sover_sec),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": _hm_from_seconds(int(summa_tid_sec)),

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille),

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": _ms_from_seconds(int(tpk_sec)),

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _ms_from_seconds(int(hangel_per_kille_sec)),

        "Totalt Män": int(totalt_man),

        # ekonomi
        "Hårdhet": int(hardhet),
        "Prenumeranter": int(pren),
        "Intäkter": float(intakter),
        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # klockan
        "Klockan": klockan_str,
    }
    return result
