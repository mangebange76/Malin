# berakningar.py
from datetime import datetime, timedelta, date, time

def _safe_int(x, default=0):
    try:
        if x is None: return default
        return int(float(x))
    except Exception:
        return default

def _ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _hm_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def berakna_radvarden(grund: dict, rad_datum: date, fod: date, starttid: time) -> dict:
    # Inputs
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

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))

    alskar = _safe_int(grund.get("Älskar", 0))
    sover  = _safe_int(grund.get("Sover med", 0))
    kanner = _safe_int(grund.get("Känner", 0))

    pv = _safe_int(grund.get("Pappans vänner", 0))
    gr = _safe_int(grund.get("Grannar", 0))
    nv = _safe_int(grund.get("Nils vänner", 0))
    nf = _safe_int(grund.get("Nils familj", 0))
    bk = _safe_int(grund.get("Bekanta", 0))

    esk = _safe_int(grund.get("Eskilstuna killar", 0))
    nils = _safe_int(grund.get("Nils", 0))

    bonus_deltagit = _safe_int(grund.get("Bonus deltagit", 0))

    # Totalt man-lika som påverkar tider m.m.
    totalt_man = man + svart + dp*0 + dpp*0 + dap*0 + tap*0 \
                 + pv + gr + nv + nf + bk + esk + bonus_deltagit

    # Summa tider (sek)
    summa_s = tid_s * totalt_man
    summa_d = tid_d * totalt_man
    summa_tp = 0  # placeholder om TP särskilda
    summa_vila = (vila + dt_vila) * totalt_man  # DT vila inkluderas här (inte dubbelräknas)
    # Älskar/Sover med extra tider (sek) – som tidigare logik (3h hångel, 1h vila typ)
    tid_alskar_sec = alskar * 3 * 3600
    tid_sover_sec  = sover * 1 * 3600

    # DT tid läggs till i totala tiden (sek/kille * antal)
    dt_tid_total = dt_tid * totalt_man

    summa_tid_sek = summa_s + summa_d + summa_tp + summa_vila + tid_alskar_sec + tid_sover_sec + dt_tid_total
    tid_per_kille_sek = int(summa_tid_sek / totalt_man) if totalt_man > 0 else 0

    # Hårdhet (+3 om svarta > 0)
    hardhet = 3 if svart > 0 else 0

    # Hångel (sek/kille) – enkel proportional, inkluderar svarta & bekanta
    hangel_sec_per = int((svart + man + esk + pv + gr + nv + nf + bk + bonus_deltagit) * 0)  # placeholder 0; behåll kolumnen

    # Prenumeranter – dubblas andelen som är Svarta (bas: män+esk+pv+gr+nv+nf+bk)
    base_sub_pool = man + esk + pv + gr + nv + nf + bk
    pren = base_sub_pool + svart*2
    avgift = float(grund.get("Avgift", 30.0) or 0.0)
    intakter = pren * avgift

    # Kostnader/intäkter placeholders (enl. tidigare överenskommelse, lämnar som fanns)
    intakt_man = 0
    intakt_kanner = 0
    lon_malin = 0
    intakt_foretag = 0
    vinst = intakter - intakt_man - lon_malin  # placeholder

    # Klockan
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt = start_dt + timedelta(seconds=summa_tid_sek)
    klockan_str = slut_dt.strftime("%H:%M")

    out = dict(grund)
    out.update({
        "Veckodag": grund.get("Veckodag",""),
        "Scen": grund.get("Scen",""),
        "Summa S": summa_s,
        "Summa D": summa_d,
        "Summa TP": summa_tp,
        "Summa Vila": summa_vila,
        "Tid Älskar (sek)": tid_alskar_sec,
        "Tid Älskar": _hm_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": tid_sover_sec,
        "Tid Sover med": _hm_from_seconds(tid_sover_sec),
        "Summa tid (sek)": int(summa_tid_sek),
        "Summa tid": _hm_from_seconds(int(summa_tid_sek)),
        "Tid per kille (sek)": int(tid_per_kille_sek),
        "Tid per kille": _ms_from_seconds(int(tid_per_kille_sek)),
        "Totalt Män": int(totalt_man),
        "Tid kille": _ms_from_seconds(int(tid_per_kille_sek)),
        "Hångel (sek/kille)": int(hangel_sec_per),
        "Hångel (m:s/kille)": _ms_from_seconds(int(hangel_sec_per)),
        "Hårdhet": hardhet,
        "Prenumeranter": int(pren),
        "Avgift": avgift,
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Intäkt Företaget": float(intakt_foretag),
        "Vinst": float(vinst),
        "Känner Sammanlagt": int(kanner + pv + gr + nv + nf + bk),
        "Klockan": klockan_str,
    })
    return out
