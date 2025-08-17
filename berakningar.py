# berakningar.py — kompatibel med appens basversion + tillägg
from datetime import timedelta, datetime, time as _time

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

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

def _calc_hardness(dp, dpp, dap, tap, svarta):
    hard = 0
    if dp  > 0: hard += 3
    if dpp > 0: hard += 4
    if dap > 0: hard += 6
    if tap > 0: hard += 8
    if svarta > 0: hard += 3
    return hard

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    # Grundfält
    man    = _safe_int(grund.get("Män", 0))
    svarta = _safe_int(grund.get("Svarta", 0))
    fitta  = _safe_int(grund.get("Fitta", 0))
    rumpa  = _safe_int(grund.get("Rumpa", 0))
    dp     = _safe_int(grund.get("DP", 0))
    dpp    = _safe_int(grund.get("DPP", 0))
    dap    = _safe_int(grund.get("DAP", 0))
    tap    = _safe_int(grund.get("TAP", 0))

    tid_s  = _safe_int(grund.get("Tid S", 60))
    tid_d  = _safe_int(grund.get("Tid D", 60))
    vila   = _safe_int(grund.get("Vila", 7))

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 60))
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 3))

    alskar    = _safe_int(grund.get("Älskar", 0))
    sover_med = _safe_int(grund.get("Sover med", 0))
    kanner    = _safe_int(grund.get("Känner", 0))

    pv = _safe_int(grund.get("Pappans vänner", 0))
    gr = _safe_int(grund.get("Grannar", 0))
    nv = _safe_int(grund.get("Nils vänner", 0))
    nf = _safe_int(grund.get("Nils familj", 0))
    bk = _safe_int(grund.get("Bekanta", 0))
    esk = _safe_int(grund.get("Eskilstuna killar", 0))

    nils = _safe_int(grund.get("Nils", 0))

    avgift = float(grund.get("Avgift", 30.0))

    # Totalt män = Män + Svarta + Eskilstuna + (känner-källor + bekanta påverkar tid/prenumeranter via män-logiken men inte kostnad)
    # OBS: i appens statistik tolkas "totalt män" som Män + Eskilstuna för scener. Här behåller vi beräkningsfältet
    totalt_man = max(0, man + esk + svarta + pv + gr + nv + nf + bk)

    # Summa S/D/TP/Vila
    summa_s = tid_s * (fitta + pv + gr + nv + nf + bk + man + esk + svarta)
    summa_d = tid_d * (rumpa + pv + gr + nv + nf + bk + man + esk + svarta)
    summa_tp = (dp + dpp + dap + tap) * 60  # 1 TP = 60s baseline (kan justeras)
    summa_vila = vila * (pv + gr + nv + nf + bk + man + esk + svarta)

    # DT-komponenter (per kille)
    dt_total = dt_tid * (man + esk + svarta + pv + gr + nv + nf + bk)
    dt_vila_total = dt_vila * (man + esk + svarta + pv + gr + nv + nf + bk)

    # Hångel (3h) i sek/kille för alla "män-lika" (inkl svarta, bekanta, eskilstuna)
    total_killar_for_hangel = max(1, man + esk + svarta + pv + gr + nv + nf + bk)
    hangel_per_kille_sec = int(round((3*3600) / total_killar_for_hangel))
    hangel_label = _ms_str_from_seconds(hangel_per_kille_sec)

    # Älskar & Sover med — tid som läggs direkt
    tid_alskar_sec = alskar * 30 * 60  # 30min per älskar
    tid_sover_sec = sover_med * 3600   # 1h om sover_med=1

    # Suger: 60% av (Summa D + Summa TP)
    suger_sec = int(round(0.60 * (summa_d + summa_tp)))
    # per kille
    suger_per_kille_sec = int(round(suger_sec / total_killar_for_hangel))

    # Hårdhet
    hard = _calc_hardness(dp, dpp, dap, tap, svarta)

    # Prenumeranter: (män + esk + svarta + pv + gr + nv + nf + bk + fitta + rumpa + dp + dpp + dap + tap + kanner) * hårdhet
    # + dubbelt för svarta
    pren_bas = (man + esk + svarta + pv + gr + nv + nf + bk + fitta + rumpa + dp + dpp + dap + tap + kanner)
    pren = pren_bas * hard + svarta * hard  # svarta dubbleras (extra *hard)

    # Tider
    summa_tid_sek = (
        summa_s + summa_d + summa_tp + summa_vila
        + dt_total + dt_vila_total
        + tid_alskar_sec + tid_sover_sec
        + suger_sec
    )
    summa_tid_label = _hm_str_from_seconds(summa_tid_sek)

    # Tid per kille: baserat på "män-lika"
    tpk_sec = int(round(summa_tid_sek / total_killar_for_hangel))
    tpk_label = _ms_str_from_seconds(tpk_sec)

    # Klockan (enkel: starttid + summa_tid)
    if isinstance(starttid, _time):
        start_dt = datetime.combine(rad_datum, starttid)
    else:
        # starttid kommer som time från appen, men fallback
        start_dt = datetime.combine(rad_datum, _time(7,0))
    slut_dt = start_dt + timedelta(seconds=summa_tid_sek)
    klockan_str = slut_dt.strftime("%H:%M")

    # Ekonomi (placeholder – lämna som i basen)
    intakt_man = 0.0
    intakt_kanner = 0.0
    lon_malin = 0.0
    intakt_foretag = pren * avgift
    intakter = intakt_foretag + intakt_kanner - intakt_man - lon_malin
    vinst = intakter

    out = dict(grund)
    out.update({
        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila + dt_vila_total),
        "Summa tid (sek)": int(summa_tid_sek),
        "Summa tid": summa_tid_label,
        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tpk_label,
        "Klockan": klockan_str,
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_label,
        "Suger": int(suger_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),
        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _hm_str_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _hm_str_from_seconds(tid_sover_sec),
        "Totalt Män": int(totalt_man),
        "Tid kille": tpk_label,
        "Hårdhet": int(hard),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Intäkt Företaget": float(intakt_foretag),
        "Vinst": float(vinst),
        "Känner Sammanlagt": int(kanner + pv + gr + nv + nf + bk),
    })
    return out
