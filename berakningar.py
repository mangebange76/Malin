from datetime import datetime, timedelta

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def berakna_radvarden(inp: dict, rad_datum, foddatum, starttid):
    # Plocka värden
    man = _safe_int(inp.get("Män", 0))
    svart = _safe_int(inp.get("Svarta", 0))
    esk  = _safe_int(inp.get("Eskilstuna killar", 0))
    fitta = _safe_int(inp.get("Fitta", 0))
    rumpa = _safe_int(inp.get("Rumpa", 0))
    dp  = _safe_int(inp.get("DP", 0))
    dpp = _safe_int(inp.get("DPP", 0))
    dap = _safe_int(inp.get("DAP", 0))
    tap = _safe_int(inp.get("TAP", 0))

    tid_s = _safe_int(inp.get("Tid S", 0))
    tid_d = _safe_int(inp.get("Tid D", 0))
    vila  = _safe_int(inp.get("Vila", 0))

    dt_tid  = _safe_int(inp.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(inp.get("DT vila (sek/kille)", 0))

    alskar = _safe_int(inp.get("Älskar", 0))
    sover  = _safe_int(inp.get("Sover med", 0))
    kanner = _safe_int(inp.get("Känner", 0))

    pv = _safe_int(inp.get("Pappans vänner", 0))
    gr = _safe_int(inp.get("Grannar", 0))
    nv = _safe_int(inp.get("Nils vänner", 0))
    nf = _safe_int(inp.get("Nils familj", 0))
    bk = _safe_int(inp.get("Bekanta", 0))

    nils = _safe_int(inp.get("Nils", 0))

    avgift = float(inp.get("Avgift", 0))

    # Tot män-basis: Män + Svarta + Eskilstuna + (känner-källor & bekanta räknas som deltagande utan kostnad)
    # OBS: enligt dina senaste instruktioner: tot män ska inkludera bekanta & Eskilstuna; Svarta påverkar som män
    tot_man = man + svart + esk + pv + gr + nv + nf + bk

    # Summa S/D/TP/Vila
    summa_s = fitta * tid_s
    summa_d = (rumpa + dp + dpp + dap + tap) * tid_d
    summa_tp = 0  # om du har särskild TP, lägg här
    # Vila = radens egna + DT vila * tot_man
    summa_vila = vila + (dt_vila * tot_man)

    # Älskar/Sover med tider
    tid_alskar_sec = alskar * 3 * 3600  # ”hångel 3 timmar”
    tid_sover_sec  = sover * 1 * 3600   # ”1 timme vila”

    # Bas-tid + DT per kille
    bas_tid_sec = summa_s + summa_d + summa_tp + summa_vila
    dt_sec = dt_tid * tot_man
    total_tid_sec = bas_tid_sec + dt_sec + tid_alskar_sec + tid_sover_sec

    # Tid per kille = (total S+D+TP+Vila + DT tid)/tot_man  (ej inkl älskar/sover? – tidigare har vi visat total)
    tid_per_kille_sec = (summa_s + summa_d + summa_tp + summa_vila + dt_sec) // (tot_man if tot_man>0 else 1)

    # Hångel per kille (sek) – påverkas av Svarta & Bekanta & källor, använd tot_man
    hangel_per_kille_sec = 0
    if tot_man > 0:
        # placeholder: 5 sek per kille som baseline
        hangel_per_kille_sec = 5

    # Suger per kille (sek) – placeholder
    suger_per_kille_sec = 0
    if tot_man > 0:
        suger_per_kille_sec = 10

    # Prenumeranter (rad) – placeholder: pv+gr+nv+nf+bk + (svarta dubbelt)
    pren = pv + gr + nv + nf + bk + (svart * 2)

    # Ekonomi placeholders — oförändrat tills vi reviderar
    intakt_man = 0.0
    intakt_kanner = 0.0
    intakter = pren * avgift
    lon_malin = 0.0
    intakt_foretag = 0.0
    vinst = intakter - (intakt_man + intakt_kanner + intakt_foretag + lon_malin)

    # Klockan (enkel add)
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt = start_dt + timedelta(seconds=int(total_tid_sec))
    klockstr = slut_dt.strftime("%H:%M")

    out = dict(inp)
    out.update({
        "Summa S": summa_s,
        "Summa D": summa_d,
        "Summa TP": summa_tp,
        "Summa Vila": summa_vila,
        "Tid Älskar (sek)": tid_alskar_sec,
        "Tid Älskar": _hm_str_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": tid_sover_sec,
        "Tid Sover med": _hm_str_from_seconds(tid_sover_sec),
        "Summa tid (sek)": int(total_tid_sec),
        "Summa tid": _hm_str_from_seconds(int(total_tid_sec)),
        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": _ms_str_from_seconds(int(tid_per_kille_sec)),
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _ms_str_from_seconds(int(hangel_per_kille_sec)),
        "Suger per kille (sek)": int(suger_per_kille_sec),
        "Suger": _ms_str_from_seconds(int(suger_per_kille_sec)),
        "Totalt Män": int(tot_man),
        "Klockan": klockstr,
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
