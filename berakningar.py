from datetime import datetime, timedelta

# ---------- Hjälpformattering ----------
def _hm_str_from_seconds(sec: float) -> str:
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h {m} min"

def _ms_from_seconds(sec: int) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}m {s}s"

# ---------- Huvudberäkning för en rad ----------
def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Basversion + Svarta + DT-fält:
      - DT tid (sek/kille) multipliceras med (Män + Svarta + Känner)
        -> adderas till 'Summa tid (sek)' och +dt_tid_per i 'Tid per kille (sek)'.
      - DT vila (sek/kille) multipliceras med (Män + Svarta + Känner)
        -> adderas till 'Summa Vila' (och därmed indirekt i totalen), INTE en gång till i totalen.
    """

    # ---- Indata (säkra typer) ----
    man     = int(float(grund.get("Män", 0) or 0))
    svarta  = int(float(grund.get("Svarta", 0) or 0))
    fitta   = int(float(grund.get("Fitta", 0) or 0))
    rumpa   = int(float(grund.get("Rumpa", 0) or 0))
    dp      = int(float(grund.get("DP", 0) or 0))
    dpp     = int(float(grund.get("DPP", 0) or 0))
    dap     = int(float(grund.get("DAP", 0) or 0))
    tap     = int(float(grund.get("TAP", 0) or 0))

    tid_s   = int(float(grund.get("Tid S", 0) or 0))
    tid_d   = int(float(grund.get("Tid D", 0) or 0))
    vila    = int(float(grund.get("Vila", 0) or 0))

    dt_tid_per   = int(float(grund.get("DT tid (sek/kille)", 60) or 0))
    dt_vila_per  = int(float(grund.get("DT vila (sek/kille)", 3) or 0))

    alskar  = int(float(grund.get("Älskar", 0) or 0))
    sover   = int(float(grund.get("Sover med", 0) or 0))

    pv = int(float(grund.get("Pappans vänner", 0) or 0))
    gr = int(float(grund.get("Grannar", 0) or 0))
    nv = int(float(grund.get("Nils vänner", 0) or 0))
    nf = int(float(grund.get("Nils familj", 0) or 0))

    nils   = int(float(grund.get("Nils", 0) or 0))
    avgift = float(grund.get("Avgift", 30.0) or 0.0)

    # ---- Härledda grundvärden ----
    kanner     = pv + gr + nv + nf
    man_total  = man + svarta            # Män + Svarta
    alla_killar = max(1, man_total + kanner)

    # ---- Del-summor S/D/TP ----
    s_count = fitta + rumpa + man_total + kanner
    m_sum = s_count * tid_s  # Summa S (sek)

    d_count = dp + dpp + dap + kanner
    n_sum = d_count * tid_d  # Summa D (sek)

    o_sum = (tap + kanner) * tid_d  # Summa TP (sek)

    # ---- Vila (inkl DT vila) ----
    total_inter = (fitta + rumpa + dp + dpp + dap + tap + man_total + kanner)
    p_sum_base = total_inter * vila
    dt_vila_total_sec = dt_vila_per * alla_killar
    p_sum = p_sum_base + dt_vila_total_sec   # Summa Vila (sek)

    # ---- Älskar & Sover med (tid i sek) ----
    tid_alskar_sec = alskar * 1800   # 30 min per älskar
    tid_sover_sec  = sover * 3600    # 60 min per sover med

    # ---- Hångel 3h per kille (delas på kolumnen Män, ej Svarta) ----
    hangel_sek_per_kille = 10800 // max(man, 1)
    hangel_ms_per_kille  = _ms_from_seconds(hangel_sek_per_kille)

    # ---- Suger = 60% av (Summa D + Summa TP) ----
    suger_total = 0.60 * (n_sum + o_sum)
    suger_per_kille_sec = int(round(suger_total / alla_killar))

    # ---- DT tid (arbetsdel) ----
    dt_tid_total_sec = dt_tid_per * alla_killar

    # ---- Total tid (sek) ----
    # OBS: DT tid läggs till i totalen här; DT vila ingår redan i p_sum.
    total_tid_sec = m_sum + n_sum + o_sum + p_sum + tid_alskar_sec + tid_sover_sec + dt_tid_total_sec

    # ---- Tid per kille (sek) ----
    # (m/z) + (n/z)*2 + (o/z)*3 + suger_per_kille + DT_tid_per
    tid_per_kille_sec = int(round(
        (m_sum / alla_killar) + (n_sum / alla_killar) * 2 + (o_sum / alla_killar) * 3 + suger_per_kille_sec + dt_tid_per
    ))
    tid_per_kille_label = _ms_from_seconds(tid_per_kille_sec)

    # ---- Prenumeranter & Hårdhet ----
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3

    pren_bas = (man + 2*svarta) + fitta + rumpa + dp + dpp + dap + tap + kanner
    prenumeranter = pren_bas * hardhet

    # ---- Ekonomi ----
    intakter       = prenumeranter * avgift
    intakt_man     = man_total * 120.0                 # "Kostnad män" i UI
    lon_malin_rad  = max(150.0, min(800.0, prenumeranter * 0.10))
    intakt_kanner  = (lon_malin_rad + 120.0) * kanner
    intakt_foretag = intakter * 0.20
    vinst          = intakter - intakt_man - intakt_kanner - lon_malin_rad - intakt_foretag

    # ---- Summa tid (h) + Klockan ----
    total_tid_h = total_tid_sec / 3600.0
    klockan = 7 + 3 + total_tid_h + 1
    klockan_label = f"{klockan:.2f}"

    # ---- Presentationstexter ----
    tid_alskar_label = _hm_str_from_seconds(tid_alskar_sec)
    tid_sover_label  = _hm_str_from_seconds(tid_sover_sec)

    # ---- Returnera full rad ----
    return {
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),

        "Män": man, "Svarta": svarta,
        "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid_per,
        "DT vila (sek/kille)": dt_vila_per,

        "Summa S": m_sum,
        "Summa D": n_sum,
        "Summa TP": o_sum,
        "Summa Vila": p_sum,

        "Tid Älskar (sek)": tid_alskar_sec,
        "Tid Älskar": tid_alskar_label,
        "Tid Sover med (sek)": tid_sover_sec,
        "Tid Sover med": tid_sover_label,

        "Summa tid (sek)": int(round(total_tid_sec)),
        "Summa tid": _hm_str_from_seconds(total_tid_sec),

        "Tid per kille (sek)": tid_per_kille_sec,
        "Tid per kille": tid_per_kille_label,

        "Klockan": klockan_label,
        "Älskar": alskar,
        "Sover med": sover,
        "Känner": kanner,
        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Totalt Män": man_total,
        "Tid kille": tid_per_kille_label,
        "Nils": nils,

        "Hångel (sek/kille)": hangel_sek_per_kille,
        "Hångel (m:s/kille)": hangel_ms_per_kille,

        "Suger": int(round(suger_total)),
        "Suger per kille (sek)": int(round(suger_per_kille_sec)),

        "Hårdhet": hardhet,
        "Prenumeranter": int(round(prenumeranter)),
        "Avgift": avgift,
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin_rad),
        "Intäkt Företaget": float(intakt_foretag),
        "Vinst": float(vinst),

        "Känner Sammanlagt": kanner,
    }
