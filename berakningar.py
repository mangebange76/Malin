from datetime import datetime, timedelta, date, time

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and (x.strip() == "" or x.strip().lower() == "none"):
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

def berakna_radvarden(inp: dict, rad_datum: date, fod: date, starttid: time) -> dict:
    """Returnerar en komplett rad med alla beräknade fält.
       Inkluderar 'Bonus tilldelade' i Totalt Män och tidsberäkningar.
    """
    d = dict(inp)

    man    = _safe_int(d.get("Män", 0), 0)
    svarta = _safe_int(d.get("Svarta", 0), 0)
    fitta  = _safe_int(d.get("Fitta", 0), 0)
    rumpa  = _safe_int(d.get("Rumpa", 0), 0)
    dp     = _safe_int(d.get("DP", 0), 0)
    dpp    = _safe_int(d.get("DPP", 0), 0)
    dap    = _safe_int(d.get("DAP", 0), 0)
    tap    = _safe_int(d.get("TAP", 0), 0)

    tid_s = _safe_int(d.get("Tid S", 0), 0)
    tid_d = _safe_int(d.get("Tid D", 0), 0)
    vila  = _safe_int(d.get("Vila", 0), 0)

    dt_tid  = _safe_int(d.get("DT tid (sek/kille)", 60), 60)
    dt_vila = _safe_int(d.get("DT vila (sek/kille)", 3), 3)

    alskar = _safe_int(d.get("Älskar", 0), 0)
    sover  = _safe_int(d.get("Sover med", 0), 0)

    p = _safe_int(d.get("Pappans vänner", 0), 0)
    g = _safe_int(d.get("Grannar", 0), 0)
    nv = _safe_int(d.get("Nils vänner", 0), 0)
    nf = _safe_int(d.get("Nils familj", 0), 0)
    bk = _safe_int(d.get("Bekanta", 0), 0)
    esk= _safe_int(d.get("Eskilstuna killar", 0), 0)

    bonus = _safe_int(d.get("Bonus tilldelade", 0), 0)

    # Summeringar
    sum_s = tid_s * (fitta + rumpa) if (fitta + rumpa) > 0 else tid_s * (fitta + rumpa)  # enkelt placeholder
    sum_d = tid_d * (dp + dpp + dap + tap)

    tot_penetration = fitta + rumpa + dp + dpp + dap + tap

    # Totalt antal "män" som påverkar tider och per-kille: inkludera alla samt BONUS
    totalt_men = max(0, man + esk + bk + p + g + nv + nf + bonus)

    # DT
    dt_tid_total  = dt_tid  * totalt_men
    dt_vila_total = dt_vila * totalt_men

    # Summa vila = vila + DT vila
    sum_vila = vila + dt_vila_total

    # Summa tid (sek) = S + D + vila + extra tider för Älskar/Sover (sekfält)
    tid_alskar_sec = _safe_int(d.get("Tid Älskar (sek)", 0), 0)
    tid_sover_sec  = _safe_int(d.get("Tid Sover med (sek)", 0), 0)

    summa_tid_sek = sum_s + sum_d + sum_vila + tid_alskar_sec + tid_sover_sec + dt_tid_total
    summa_tid_lbl = _hm_str_from_seconds(summa_tid_sek)

    # Tid per kille – baserat på totalt_men (inkl bonus)
    if totalt_men > 0:
        tid_per_kille_sec = int(round(summa_tid_sek / totalt_men))
    else:
        tid_per_kille_sec = 0

    # Hångel/Suger – placeholders, låt samma logik som tidigare
    hangel_per_kille_sec = max(0, 30)  # statiskt exempel
    hangel_per_kille_lbl = _ms_str_from_seconds(hangel_per_kille_sec)

    suger_total = 0
    suger_per_kille = tid_per_kille_sec // 2 if totalt_men > 0 else 0

    # Prenumeranter & ekonomi – lämnas som de var i appen; här returnerar vi bara genom inp
    avgift = float(d.get("Avgift", 30.0) or 30.0)
    pren   = int(float(d.get("Prenumeranter", 0) or 0))
    intakter = pren * avgift

    # Klockan – enkel framräkning: lägg på summa_tid_sek på starttid
    dt_start = datetime.combine(rad_datum, starttid)
    dt_end   = dt_start + timedelta(seconds=summa_tid_sek)
    klockan  = dt_end.strftime("%H:%M")

    out = {
        "Typ": d.get("Typ",""),
        "Veckodag": d.get("Veckodag",""),
        "Scen": d.get("Scen",""),
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Summa S": sum_s, "Summa D": sum_d, "Summa TP": tot_penetration, "Summa Vila": sum_vila,
        "Tid Älskar (sek)": tid_alskar_sec, "Tid Älskar": _ms_str_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": tid_sover_sec, "Tid Sover med": _ms_str_from_seconds(tid_sover_sec),
        "Summa tid": summa_tid_lbl, "Summa tid (sek)": int(summa_tid_sek),
        "Tid per kille (sek)": int(tid_per_kille_sec), "Tid per kille": _ms_str_from_seconds(tid_per_kille_sec),
        "Klockan": klockan, "Älskar": alskar, "Sover med": sover, "Känner": _safe_int(d.get("Känner",0),0),
        "Pappans vänner": p, "Grannar": g, "Nils vänner": nv, "Nils familj": nf, "Bekanta": bk, "Eskilstuna killar": esk,
        "Bonus tilldelade": bonus,
        "Totalt Män": int(totalt_men),
        "Tid kille": _ms_str_from_seconds(tid_per_kille_sec),
        "Hångel (sek/kille)": hangel_per_kille_sec, "Hångel (m:s/kille)": hangel_per_kille_lbl,
        "Suger": suger_total, "Suger per kille (sek)": int(suger_per_kille),
        "Hårdhet": _safe_int(d.get("Hårdhet", 0), 0),
        "Prenumeranter": pren, "Avgift": avgift, "Intäkter": float(intakter),
        "Intäkt män": 0.0, "Intäkt Känner": 0.0, "Lön Malin": 0.0, "Intäkt Företaget": 0.0, "Vinst": 0.0,
        "Känner Sammanlagt": _safe_int(d.get("Känner Sammanlagt", 0), 0),
        "Nils": _safe_int(d.get("Nils", 0), 0),
    }
    return out
