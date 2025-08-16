# berakningar.py
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

def _safe(v):
    try:
        if v is None: return 0
        s = str(v).strip()
        if s == "": return 0
        return int(float(s))
    except Exception:
        return 0

def _hardness(dp, dpp, dap, tap):
    # Hårdhet: DP>0 => +3, DPP>0 => +4, DAP>0 => +6, TAP>0 => +8
    return (3 if dp>0 else 0) + (4 if dpp>0 else 0) + (6 if dap>0 else 0) + (8 if tap>0 else 0)

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    # --- Inputs ---
    c = _safe(grund.get("Män", 0))
    d = _safe(grund.get("Fitta", 0))
    e = _safe(grund.get("Rumpa", 0))
    f = _safe(grund.get("DP", 0))
    g = _safe(grund.get("DPP", 0))
    h = _safe(grund.get("DAP", 0))
    i = _safe(grund.get("TAP", 0))

    j = _safe(grund.get("Tid S", 60))
    k = _safe(grund.get("Tid D", 60))
    l = _safe(grund.get("Vila", 7))

    alskar = _safe(grund.get("Älskar", 0))
    sover  = _safe(grund.get("Sover med", 0))

    pv = _safe(grund.get("Pappans vänner", 0))
    gr = _safe(grund.get("Grannar", 0))
    nv = _safe(grund.get("Nils vänner", 0))
    nf = _safe(grund.get("Nils familj", 0))
    nils = _safe(grund.get("Nils", 0))

    avgift = float(grund.get("Avgift", 30.0) or 30.0)
    typ = (grund.get("Typ") or "").strip()

    # --- Känner & alla killar (raden) ---
    kanner = pv + gr + nv + nf
    alla_killar = max(c + kanner, 1)  # undvik 0-division
    totalt_man = c + kanner

    # --- Summor S/D/TP (sekunder) ---
    m_sum = (c + d + e) * j                  # Summa S
    n_sum = (f + g + h) * k                  # Summa D
    o_sum = i * k                            # Summa TP

    # --- Vila-tid ---
    p_sum = (c + d + e + f + g + h + i) * l  # Summa Vila

    # --- Älskar & Sover med (tidsadderingar) ---
    tid_alskar_sec = alskar * 30 * 60        # 30 min per styck
    tid_sover_sec  = sover * 60 * 60         # 60 min per styck

    # --- Total tid ---
    total_sec = m_sum + n_sum + o_sum + p_sum + tid_alskar_sec + tid_sover_sec
    total_h = total_sec / 3600.0

    # --- Klockan ---
    klockan_dt = datetime.combine(rad_datum, starttid) + timedelta(hours=(3 + total_h + 1))
    klockan_label = klockan_dt.strftime("%H:%M")

    # --- Hångel (3h / män) per kille ---
    hangel_per_kille_sec = int(round((3 * 3600) / c)) if c > 0 else 0
    hangel_label = _ms_str_from_seconds(hangel_per_kille_sec)

    # --- Suger = 60% av (Summa D + Summa TP) ---
    suger_total_sec = int(round(0.60 * (n_sum + o_sum)))

    # --- Tid per kille (sek) ---
    # (S/alla) + 2*(D/alla) + 3*(TP/alla) + (Suger/alla)
    tpk_sec = int(round((m_sum / alla_killar) + 2*(n_sum / alla_killar) + 3*(o_sum / alla_killar) + (suger_total_sec / alla_killar)))
    tpk_label = _ms_str_from_seconds(tpk_sec)

    # --- Suger per kille (sek) ---
    suger_per_kille_sec = int(round(suger_total_sec / alla_killar))

    # --- Prenumeranter & ekonomi (exkludera vila-rader) ---
    hardhet = _hardness(f, g, h, i)
    pren = 0
    intakter = 0
    lon_malin = 0
    intakt_man = 0
    intakt_kanner = 0
    intakt_foretag = 0
    vinst = 0

    if typ not in ("Vila på jobbet", "Vila i hemmet"):
        pren = (c + d + e + f + g + h + i + kanner) * hardhet
        intakter = pren * avgift
        intakt_man = c * 120
        lon_malin = max(150, min(800, pren * 0.10))
        intakt_kanner = (lon_malin + 120) * kanner
        intakt_foretag = intakter * 0.20
        vinst = intakter - intakt_man - intakt_kanner - lon_malin - intakt_foretag

    return {
        "Typ": typ,
        "Veckodag": grund.get("Veckodag"),
        "Scen": grund.get("Scen"),
        "Män": c, "Fitta": d, "Rumpa": e, "DP": f, "DPP": g, "DAP": h, "TAP": i,
        "Tid S": j, "Tid D": k, "Vila": l,
        "Summa S": m_sum, "Summa D": n_sum, "Summa TP": o_sum, "Summa Vila": p_sum,
        "Tid Älskar (sek)": tid_alskar_sec, "Tid Älskar": _hm_str_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": tid_sover_sec, "Tid Sover med": _hm_str_from_seconds(tid_sover_sec),
        "Summa tid (sek)": total_sec, "Summa tid": _hm_str_from_seconds(total_sec),
        "Tid per kille (sek)": tpk_sec, "Tid per kille": tpk_label,
        "Klockan": klockan_label,
        "Älskar": alskar, "Sover med": sover,
        "Känner": kanner, "Pappans vänner": pv, "Grannar": gr,
        "Nils vänner": nv, "Nils familj": nf, "Totalt Män": totalt_man,
        "Tid kille": tpk_label, "Nils": nils,
        "Hångel (sek/kille)": hangel_per_kille_sec, "Hångel (m:s/kille)": hangel_label,
        "Suger": suger_total_sec, "Suger per kille (sek)": suger_per_kille_sec,
        "Hårdhet": hardhet, "Prenumeranter": pren, "Avgift": avgift, "Intäkter": intakter,
        "Intäkt män": intakt_man, "Intäkt Känner": intakt_kanner, "Lön Malin": lon_malin,
        "Intäkt Företaget": intakt_foretag, "Vinst": vinst,
        "Känner Sammanlagt": kanner
    }
