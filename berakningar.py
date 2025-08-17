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
        if x is None:
            return default
        if isinstance(x, str):
            x = x.strip()
            if x == "":
                return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, str):
            x = x.strip()
            if x == "":
                return default
        return float(x)
    except Exception:
        return default

def berakna_radvarden(grund: dict, rad_datum, födelsedatum, starttid):
    man   = _safe_int(grund.get("Män", 0))
    svart = _safe_int(grund.get("Svarta", 0))
    fitta = _safe_int(grund.get("Fitta", 0))
    rumpa = _safe_int(grund.get("Rumpa", 0))
    dp    = _safe_int(grund.get("DP", 0))
    dpp   = _safe_int(grund.get("DPP", 0))
    dap   = _safe_int(grund.get("DAP", 0))
    tap   = _safe_int(grund.get("TAP", 0))

    tid_s = _safe_int(grund.get("Tid S", 0))
    tid_d = _safe_int(grund.get("Tid D", 0))
    vila  = _safe_int(grund.get("Vila", 0))

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 60))
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 3))

    alskar    = _safe_int(grund.get("Älskar", 0))
    sover_med = _safe_int(grund.get("Sover med", 0))

    pv = _safe_int(grund.get("Pappans vänner", 0))
    gr = _safe_int(grund.get("Grannar", 0))
    nv = _safe_int(grund.get("Nils vänner", 0))
    nf = _safe_int(grund.get("Nils familj", 0))
    bk = _safe_int(grund.get("Bekanta", 0))
    esk= _safe_int(grund.get("Eskilstuna killar", 0))

    nils = _safe_int(grund.get("Nils", 0))

    avgift = _safe_float(grund.get("Avgift", 30.0))

    total_man = max(0, man + svart + bk + esk + pv + gr + nv + nf)

    summa_s = fitta * tid_s * total_man
    summa_d = rumpa * tid_d * total_man
    summa_tp = (dp + dpp + dap + tap) * tid_d * total_man
    summa_vila = (vila * total_man) + (dt_vila * total_man)

    extra_dt_tid_total = dt_tid * total_man

    tid_alskar_sec = alskar * 30 * 60
    tid_sover_sec  = sover_med * 60 * 60

    summa_tid_sec = summa_s + 2*summa_d + 3*summa_tp + summa_vila + extra_dt_tid_total + tid_alskar_sec + tid_sover_sec
    def _hm_str_from_seconds(q_sec: int) -> str:
        h = q_sec // 3600
        m = round((q_sec % 3600) / 60)
        if m == 60:
            h += 1
            m = 0
        return f"{int(h)}h {int(m)} min"
    summa_tid_lbl = _hm_str_from_seconds(summa_tid_sec)

    if total_man > 0:
        tpk_sec = (summa_s/total_man) + 2*(summa_d/total_man) + 3*(summa_tp/total_man) + dt_tid
    else:
        tpk_sec = 0
    def _ms_str_from_seconds(sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{int(m)}m {int(s)}s"
    tpk_lbl = _ms_str_from_seconds(int(round(tpk_sec)))

    if total_man > 0:
        hangel_per_kille_sec = int(round((3*60*60) / total_man))
    else:
        hangel_per_kille_sec = 0

    suger_total_sec = int(round(0.60 * (summa_d + summa_tp)))
    suger_per_kille_sec = int(round(suger_total_sec / total_man)) if total_man > 0 else 0

    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svart > 0: hardhet += 3

    kanner_sammanlagt = pv + gr + nv + nf
    kanner = kanner_sammanlagt

    pren_bas = (man + bk + esk + (2*svart)
                + fitta + rumpa + dp + dpp + dap + tap
                + kanner)
    prenumeranter = int(max(0, pren_bas * hardhet))

    avgift = _safe_float(grund.get("Avgift", 30.0), 30.0)
    intakter = float(prenumeranter) * avgift

    intakt_man = 0.0
    intakt_kanner = 0.0
    lon_malin = 0.0
    intakt_foretaget = 0.0
    vinst = float(intakter)

    if isinstance(starttid, str):
        try:
            t = datetime.strptime(starttid, "%H:%M:%S").time()
        except Exception:
            t = datetime.strptime(starttid, "%H:%M").time()
    else:
        t = starttid
    start_dt = datetime.combine(rad_datum, t)
    sluttid = start_dt + timedelta(seconds=summa_tid_sec)
    klockan_str = sluttid.strftime("%H:%M")

    out = dict(grund)
    out.update({
        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),
        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _hm_str_from_seconds(int(tid_alskar_sec)),
        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _hm_str_from_seconds(int(tid_sover_sec)),
        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": summa_tid_lbl,
        "Tid per kille (sek)": int(round(tpk_sec)),
        "Tid per kille": tpk_lbl,
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _ms_str_from_seconds(int(hangel_per_kille_sec)),
        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),
        "Hårdhet": int(hardhet),
        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Intäkt Företaget": float(intakt_foretaget),
        "Vinst": float(vinst),
        "Känner Sammanlagt": int(kanner_sammanlagt),
        "Känner": int(kanner),
        "Totalt Män": int(total_man),
        "Klockan": klockan_str,
    })
    return out
