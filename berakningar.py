# berakningar.py
from datetime import datetime, timedelta, date, time as _time

def _sec_to_hm(sec: int) -> str:
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _sec_to_ms(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return float(x)
    except Exception:
        return default

def _hardhet(dp, dpp, dap, tap, totman, svarta):
    h = 0
    if dp > 0:  h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9
    # Totalt män – ta högsta matchande nivå (inte kumulativt mellan nivåerna)
    if totman >= 1000: lvl = 10
    elif totman >= 500: lvl = 6
    elif totman >= 300: lvl = 5
    elif totman >= 200: lvl = 3
    elif totman > 100:  lvl = 1
    else: lvl = 0
    h += lvl
    if svarta > 0: h += 3
    return h

def _bonus_from_subscribers(subs: int, p: float = 0.05) -> int:
    # Binomial subs,p  (utan numpy)
    if subs <= 0: return 0
    import random
    c = 0
    for _ in range(int(subs)):
        if random.random() < p:
            c += 1
    return c

def _add_seconds(t: _time, seconds: int) -> _time:
    dt = datetime.combine(date.today(), t) + timedelta(seconds=seconds)
    return dt.time()

def berakna_radvarden(grund: dict, rad_datum: date, foddag: date, starttid: _time) -> dict:
    """
    Beräknar alla fält för en rad. Läser endast 'grund' (inputs) och returnerar en mapping
    för alla kolumnnamn appen använder. Ingen IO här inne.
    """

    # ------- Läs in värden -------
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

    alskar     = _safe_int(grund.get("Älskar", 0))
    sover_med  = _safe_int(grund.get("Sover med", 0))

    pv   = _safe_int(grund.get("Pappans vänner", 0))
    gr   = _safe_int(grund.get("Grannar", 0))
    nv   = _safe_int(grund.get("Nils vänner", 0))
    nf   = _safe_int(grund.get("Nils familj", 0))
    bk   = _safe_int(grund.get("Bekanta", 0))
    esk  = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_killar   = _safe_int(grund.get("Bonus killar", 0))
    bonus_deltagit = _safe_int(grund.get("Bonus deltagit", 0))
    personal_delt  = _safe_int(grund.get("Personal deltagit", 0))

    nils = _safe_int(grund.get("Nils", 0))
    avgift = _safe_float(grund.get("Avgift", 30.0))

    # ------- Härledda basfält -------
    kanner = pv + gr + nv + nf

    # Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit + Personal deltagit
    tot_man = man + kanner + svarta + bk + esk + bonus_deltagit + personal_delt

    # ------- Summa-delar -------
    # Summa S: Tid S * (Fitta + Rumpa)  +  (DT tid * Totalt män)
    summa_s_base = tid_s * (fitta + rumpa)
    summa_s = summa_s_base + dt_tid * tot_man

    # Summa D: Tid D * (DP + DPP + DAP)
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP: (TAP använder samma tidslängd som D-akt, enligt “du hade rätt”)
    summa_tp = tid_d * tap

    # Summa Vila: Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP)  +  (DT vila * Totalt män)
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * tot_man

    # Summa tid (sek) – OBS: älskar/sover ingår INTE
    summa_tid_sek = int(summa_s + summa_d + summa_tp + summa_vila)
    summa_tid_lbl = _sec_to_hm(summa_tid_sek)

    # Älskar/Sover med – 20 min per tillfälle, adderas direkt på klockan (ej i summa tid)
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover_med * 20 * 60

    # Klockan: starttid + summa tid + 3h + 1h + älskar + sover
    clock_add = summa_tid_sek + (3*3600) + (1*3600) + alskar_sec + sover_sec
    sluttid = _add_seconds(starttid, clock_add)
    klockan_str = sluttid.strftime("%H:%M")

    # Hångel (sek/kille): 3h / Totalt Män (endast visning)
    hangel_sec_per_kille = 0
    if tot_man > 0:
        hangel_sec_per_kille = int(round((3*3600) / tot_man))
    hangel_ms_per_kille = _sec_to_ms(hangel_sec_per_kille)

    # Suger: 60% av scenens tid (Summa tid) – per kille
    suger_total_sec = int(round(0.60 * summa_tid_sek))
    suger_per_kille_sec = int(round(suger_total_sec / tot_man)) if tot_man > 0 else 0

    # Tid per kille (sek):
    #   = (Summa S_base / tot) + 2*(Summa D / tot) + 3*(Summa TP / tot)
    #     + (Suger_total / tot) + DT tid (per kille)
    tpk_sec = 0
    if tot_man > 0:
        tpk_sec = (
            (summa_s_base / tot_man)
            + 2.0 * (summa_d / tot_man)
            + 3.0 * (summa_tp / tot_man)
            + (suger_total_sec / tot_man)
            + dt_tid
        )
    tpk_sec = int(round(tpk_sec))
    tpk_lbl = _sec_to_ms(tpk_sec)

    # Hårdhet
    hard = _hardhet(dp, dpp, dap, tap, tot_man, svarta)

    # Prenumeranter: (Fitta+Rumpa+DP+DPP+DAP+TAP+Totalt Män) * Hårdhet
    pren = (fitta + rumpa + dp + dpp + dap + tap + tot_man) * hard

    # Bonus killar: om fältet inte givits, avled från prenumeranter (5% chans per pren)
    if bonus_killar == 0 and pren > 0:
        bonus_killar = _bonus_from_subscribers(pren, 0.05)

    # Om Bonus deltagit inte angivet – 40% av bonus_killar som default
    if bonus_deltagit == 0 and bonus_killar > 0:
        bonus_deltagit = int(round(bonus_killar * 0.40))

    # Ekonomi
    intakter = pren * avgift
    # Utgift män = (män + svarta + bekanta + eskilstuna + bonus_deltagit + ALL personal) * (summa_tid (h)) * 15
    # OBS: personal = hela styrkan (fast), inte "personal deltagit"
    # (Den fasta personalstyrkan levereras via grund["PROD_STAFF_TOTAL"] av appen vid spar/live)
    prod_staff_total = _safe_int(grund.get("PROD_STAFF_TOTAL", 0))
    betalande_cnt = man + svarta + bk + esk + bonus_deltagit + prod_staff_total
    utgift_man = (summa_tid_sek / 3600.0) * 15.0 * betalande_cnt

    # Lön Malin = 8% av max(0, intäkter - utgift män)  men minst 150 och max 800
    lon_malin_raw = max(0.0, intakter - utgift_man) * 0.08
    lon_malin = max(150.0, min(800.0, lon_malin_raw))

    # Intäkt Känner = (summa tid (h) * 35) * Känner
    intakt_kanner = (summa_tid_sek / 3600.0) * 35.0 * kanner

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # Tid älskar/sover (visning)
    tid_alskar_lbl = _sec_to_hm(alskar_sec)
    tid_sover_lbl  = _sec_to_hm(sover_sec)

    # Ålder för visning i live
    alder = rad_datum.year - foddag.year - ((rad_datum.month, rad_datum.day) < (foddag.month, foddag.day))

    # Return-mapp: matchar kolumnnamn i arket
    out = {
        "Typ": str(grund.get("Typ", "") or ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),
        "Män": man,
        "Svarta": svarta,
        "Fitta": fitta,
        "Rumpa": rumpa,
        "DP": dp,
        "DPP": dpp,
        "DAP": dap,
        "TAP": tap,
        "Tid S": tid_s,
        "Tid D": tid_d,
        "Vila": vila,
        "DT tid (sek/kille)": dt_tid,
        "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": tid_alskar_lbl,
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": tid_sover_lbl,

        "Summa tid": summa_tid_lbl,
        "Summa tid (sek)": int(summa_tid_sek),

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tpk_lbl,

        "Klockan": klockan_str,
        "Älskar": alskar,
        "Sover med": sover_med,

        "Känner": kanner,
        "Pappans vänner": pv,
        "Grannar": gr,
        "Nils vänner": nv,
        "Nils familj": nf,
        "Bekanta": bk,
        "Eskilstuna killar": esk,

        "Bonus killar": int(bonus_killar),
        "Bonus deltagit": int(bonus_deltagit),
        "Personal deltagit": personal_delt,

        "Totalt Män": int(tot_man),
        "Tid kille": tpk_lbl,  # legacy/visning

        "Hångel (sek/kille)": int(hangel_sec_per_kille),
        "Hångel (m:s/kille)": hangel_ms_per_kille,

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

        "Känner Sammanlagt": kanner,  # kvar för kompatibilitet
        "Malins ålder": int(alder),   # för livevisning
    }
    return out
