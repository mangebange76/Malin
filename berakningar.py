from datetime import datetime, timedelta, time

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

def berakna_radvarden(row: dict, rad_datum, fodelsedatum, starttid: time):
    # Input
    man   = _safe_int(row.get("Män", 0))
    svart = _safe_int(row.get("Svarta", 0))
    fitta = _safe_int(row.get("Fitta", 0))
    rumpa = _safe_int(row.get("Rumpa", 0))
    dp    = _safe_int(row.get("DP", 0))
    dpp   = _safe_int(row.get("DPP", 0))
    dap   = _safe_int(row.get("DAP", 0))
    tap   = _safe_int(row.get("TAP", 0))

    tid_s = _safe_int(row.get("Tid S", 0))
    tid_d = _safe_int(row.get("Tid D", 0))
    vila  = _safe_int(row.get("Vila", 0))

    dt_tid  = _safe_int(row.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(row.get("DT vila (sek/kille)", 0))

    alskar    = _safe_int(row.get("Älskar", 0))
    sover_med = _safe_int(row.get("Sover med", 0))

    kanner = _safe_int(row.get("Känner", 0))

    pappan = _safe_int(row.get("Pappans vänner", 0))
    grann  = _safe_int(row.get("Grannar", 0))
    nilsv  = _safe_int(row.get("Nils vänner", 0))
    nilsf  = _safe_int(row.get("Nils familj", 0))
    bek    = _safe_int(row.get("Bekanta", 0))
    esk    = _safe_int(row.get("Eskilstuna killar", 0))
    nils   = _safe_int(row.get("Nils", 0))

    bonus_deltagit = _safe_int(row.get("Bonus deltagit", 0))

    avgift = float(row.get("Avgift", 0.0))

    # ---- Totalt "män-lika" deltagare denna rad ----
    # Regler enligt appdiskussionen:
    # - "Män" + "Eskilstuna killar" räknas i totals, "Svarta" är alternativa män som påverkar tid/hårdhet etc
    #   och ska ge samma effekt som Män (och egen andel i statistik). Vi lägger dem i samma pott tidsmässigt.
    # - Bekanta påverkar tid/hångel/suger osv, men inte kostnader/intäkter och inte älskar/sover med.
    # - Bonus deltagit ska påverka som män (inte prenumeranter).
    total_killar_for_time = man + esk + svart + bek + bonus_deltagit
    total_killar_for_cost = man + esk + svart  # bekanta och bonus ingår ej i kostnader/intäkter
    total_man_for_stats   = man + esk          # används i vissa stat-avsnitt i appen

    # ---- Summera tekniska delar ----
    sum_s = fitta * tid_s
    sum_d = (rumpa + dp + dpp + dap + tap) * tid_d
    sum_tp = sum_s + sum_d  # teknisk penetrationstid

    # DT extra tid och vila multiplicerat med totalt antal "män-lika" för tid
    dt_sum_tid  = total_killar_for_time * dt_tid
    dt_sum_vila = total_killar_for_time * dt_vila

    # "Vila" kolumnen i indata är basvila (per rad), DT_vila adderas per kille
    sum_vila = vila + dt_sum_vila

    # Älskar & Sover med tider (sek) — antag tidigare standard: hångel 3h och vila 1h läggs på klockan separat i appens statistik,
    # men här behåller vi befintliga kolumner.
    tid_alskar_sec = alskar * 3 * 3600  # 3 timmar per älskar (enligt tidigare överenskommelse)
    tid_sover_sec  = sover_med * 1 * 3600  # 1 timme

    # Total tid (sek)
    summa_tid_sek = sum_tp + sum_vila + dt_sum_tid + tid_alskar_sec + tid_sover_sec
    summa_tid_lbl = _hm_str_from_seconds(summa_tid_sek)

    # Tid per kille (sek) – ska inkludera DT tid
    tpk_sek = int(summa_tid_sek / total_killar_for_time) if total_killar_for_time > 0 else 0
    tpk_lbl = _ms_str_from_seconds(tpk_sek)

    # Hångel per kille: använd alla "män-lika" som påverkar hångel = män + svart + bekanta + esk + bonus_deltagit
    # (följ tidigare riktlinje att Svarta & Bekanta påverkar hångel)
    # Sätt enkel modell: hångel = 180 sek per kille.
    hangel_per_kille = 180 if total_killar_for_time > 0 else 0
    suger_per_kille  = 60  if total_killar_for_time > 0 else 0

    # Hårdhet: +3 om svarta > 0 (tidigare regel)
    hardhet = 3 if svart > 0 else 0

    # Prenumeranter: tidigare regel "svarta dubblerar per svart" – implementera enkelt som:
    pren = pappan + grann + nilsv + nilsf + bek  # baseline från källor (exempel – behåll befintlig logik i appen)
    if svart > 0:
        pren += svart  # enkel extra boost – detaljerna kan justeras senare
    intakter = pren * avgift

    # Kostnader/intäkter/lön – lämnas i stort som placeholders tills vi räknar om ekonomin
    intakt_man    = total_killar_for_cost * 0.0
    intakt_kanner = kanner * 0.0
    lon_malin     = 0.0
    intakt_fore   = 0.0
    vinst         = intakter - (intakt_man + intakt_fore + lon_malin)

    # Klockan – enkel summering på starttid + summa_tid_sek
    try:
        dt = datetime.combine(rad_datum, starttid) + timedelta(seconds=summa_tid_sek)
        klockan = dt.strftime("%H:%M")
    except Exception:
        klockan = "-"

    # Känner Sammanlagt (placeholder = Känner, kan vara annat i din bas)
    kanner_sum = kanner

    out = dict(row)
    out.update({
        "Summa S": sum_s,
        "Summa D": sum_d,
        "Summa TP": sum_tp,
        "Summa Vila": sum_vila,
        "Tid Älskar (sek)": tid_alskar_sec,
        "Tid Älskar": _hm_str_from_seconds(tid_alskar_sec) if tid_alskar_sec > 0 else "0h 0 min",
        "Tid Sover med (sek)": tid_sover_sec,
        "Tid Sover med": _hm_str_from_seconds(tid_sover_sec) if tid_sover_sec > 0 else "0h 0 min",
        "Summa tid": summa_tid_lbl,
        "Summa tid (sek)": int(summa_tid_sek),
        "Tid per kille (sek)": int(tpk_sek),
        "Tid per kille": tpk_lbl,
        "Hångel (sek/kille)": int(hangel_per_kille),
        "Hångel (m:s/kille)": _ms_str_from_seconds(hangel_per_kille) if hangel_per_kille else "0m 0s",
        "Suger": total_killar_for_time,
        "Suger per kille (sek)": int(suger_per_kille),
        "Hårdhet": int(hardhet),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Intäkt Företaget": float(intakt_fore),
        "Vinst": float(vinst),
        "Klockan": klockan,
        "Totalt Män": int(total_man_for_stats),
        "Tid kille": tpk_lbl,
        "Känner Sammanlagt": int(kanner_sum),
        # säkerställ att bonus-kolumner finns om de inte sattes innan
        "Bonus killar": _safe_int(row.get("Bonus killar", 0)),
        "Bonus deltagit": _safe_int(row.get("Bonus deltagit", 0)),
    })
    return out
