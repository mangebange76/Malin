# berakningar.py
from datetime import datetime, timedelta

def _safe_int(x, default=0):
    try:
        if x is None:
            return default
        sx = str(x).strip()
        if sx == "":
            return default
        return int(float(sx))
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

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med alla beräknade fält för raden.
    OBS: Prenumeranter beräknas här som tidigare i din logik (förenklad placeholder om inget fanns),
    BONUS hanteras i app.py efter att antalet prenumeranter är bestämt.
    """
    d = dict(grund)

    man      = _safe_int(d.get("Män", 0))
    svarta   = _safe_int(d.get("Svarta", 0))
    fitta    = _safe_int(d.get("Fitta", 0))
    rumpa    = _safe_int(d.get("Rumpa", 0))
    dp       = _safe_int(d.get("DP", 0))
    dpp      = _safe_int(d.get("DPP", 0))
    dap      = _safe_int(d.get("DAP", 0))
    tap      = _safe_int(d.get("TAP", 0))

    tid_s    = _safe_int(d.get("Tid S", 0))
    tid_d    = _safe_int(d.get("Tid D", 0))
    vila     = _safe_int(d.get("Vila", 0))

    dt_tid   = _safe_int(d.get("DT tid (sek/kille)", 0))
    dt_vila  = _safe_int(d.get("DT vila (sek/kille)", 0))

    alskar   = _safe_int(d.get("Älskar", 0))
    sover    = _safe_int(d.get("Sover med", 0))
    kanner   = _safe_int(d.get("Känner", 0))

    pv       = _safe_int(d.get("Pappans vänner", 0))
    gr       = _safe_int(d.get("Grannar", 0))
    nv       = _safe_int(d.get("Nils vänner", 0))
    nf       = _safe_int(d.get("Nils familj", 0))
    bk       = _safe_int(d.get("Bekanta", 0))
    esk      = _safe_int(d.get("Eskilstuna killar", 0))

    nils     = _safe_int(d.get("Nils", 0))

    # Totalt "män-lika" är män + eskilstuna, men svarta påverkar vissa delar separat
    total_man_like = man + esk

    # Bas-summor
    summa_s = tid_s * (fitta + pv + gr + nv + nf + bk + total_man_like + svarta)
    summa_d = tid_d * (rumpa + pv + gr + nv + nf + bk + total_man_like + svarta)

    # TP är en enkel viktad summa
    summa_tp = (dp + 2*dpp + 3*dap + 4*tap)

    # DT-komponenter (tid och vila) multipliceras med totala man-like
    dt_total_tid  = dt_tid  * total_man_like
    dt_total_vila = dt_vila * total_man_like

    # Vila-komponent
    summa_vila = vila + dt_total_vila

    # Älskar / Sover med tid (sek)
    tid_alskar_sec = alskar * 60  # ex. 1 älskar = 60s (justeras vid behov)
    tid_sover_sec  = sover * 3600  # 1 sover med = 1h

    # Summa tid (sek): S + D + (TP som sekundvikt?) + vila + DT + älskar/sover
    # Här behåller vi tidigare anda: TP i sek gissas som 0 för enkelhet (din tidigare kod styr)
    summa_tid_sek = (summa_s + summa_d + summa_vila + dt_total_tid + tid_alskar_sec + tid_sover_sec)
    d["Summa tid (sek)"] = int(summa_tid_sek)
    d["Summa tid"] = _hm_str_from_seconds(int(summa_tid_sek))

    # Tid per kille (inkl DT-tid) — per total_man_like + svarta (de beter sig som män i tid)
    total_for_tid = total_man_like + svarta if (total_man_like + svarta) > 0 else 1
    tid_per_kille_sek = int(summa_tid_sek // total_for_tid) if total_for_tid > 0 else 0
    d["Tid per kille (sek)"] = int(tid_per_kille_sek)
    d["Tid per kille"] = _ms_str_from_seconds(int(tid_per_kille_sek))

    d["Tid Älskar (sek)"] = int(tid_alskar_sec)
    d["Tid Älskar"] = _ms_str_from_seconds(int(tid_alskar_sec))
    d["Tid Sover med (sek)"] = int(tid_sover_sec)
    d["Tid Sover med"] = _ms_str_from_seconds(int(tid_sover_sec))

    # Totalt Män (på raden): män + svarta + eskilstuna + källa-grupper
    total_man_raden = total_man_like + svarta + pv + gr + nv + nf + bk
    d["Totalt Män"] = int(total_man_raden)

    # Hårdhet — tidigare logik +3 om svarta>0
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3
    d["Hårdhet"] = int(hardhet)

    # Prenumeranter (behåll tidigare "anda"): män + bekanta + källor + fitta + rumpa + dp-vikter
    # Svarta räknas dubbelt i pren (enligt din regel)
    pren_base = (man + pv + gr + nv + nf + bk + esk) + fitta + rumpa + (dp + 2*dpp + 3*dap + 4*tap)
    pren = pren_base + 2*svarta + kanner
    d["Prenumeranter"] = int(max(0, pren))

    # Avgift och intäkter (oförändrat mönster)
    avgift = float(d.get("Avgift", 30.0) or 30.0)
    intakter = float(d["Prenumeranter"]) * avgift
    d["Intäkter"] = round(intakter, 2)

    # Ekonomi-kolumnerna behålls som i din bas (kan omräknas senare)
    d["Intäkt män"] = 0.0
    d["Intäkt Känner"] = 0.0
    d["Lön Malin"] = 0.0
    d["Intäkt Företaget"] = 0.0
    d["Vinst"] = float(d["Intäkter"])

    # Suger — 60% av (Summa D + Summa TP), per kille
    suger_sum = 0.6 * (summa_d + summa_tp)
    d["Suger"] = int(suger_sum)
    d["Suger per kille (sek)"] = int(suger_sum // total_for_tid) if total_for_tid > 0 else 0

    # Hångel: 3h / (män-lika + svarta) i sek/kille
    denom_hangel = total_for_tid
    hangel_per_kille = int((3*3600) // denom_hangel) if denom_hangel > 0 else 0
    d["Hångel (sek/kille)"] = int(hangel_per_kille)
    d["Hångel (m:s/kille)"] = _ms_str_from_seconds(int(hangel_per_kille))

    # Klockan (start + summa tid)
    try:
        dt_start = datetime.combine(rad_datum, starttid)
        dt_end = dt_start + timedelta(seconds=int(summa_tid_sek))
        d["Klockan"] = dt_end.strftime("%H:%M")
    except Exception:
        d["Klockan"] = ""

    # Summeringar
    d["Summa S"] = int(summa_s)
    d["Summa D"] = int(summa_d)
    d["Summa TP"] = int(summa_tp)
    d["Summa Vila"] = int(summa_vila)

    # Sammanlagt "känner"
    d["Känner Sammanlagt"] = int(kanner)

    # Bonus killar sätts i app.py vid preview & spar — men initiera till 0 här
    d["Bonus killar"] = 0

    return d
