from datetime import datetime, timedelta
import math

def _sec_to_hm_str(sec: float) -> str:
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h {m} min"

def _ms_from_seconds(sec: int) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}m {s}s"

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Beräknar alla fält för en rad. Anpassad till basversionen + 'Svarta' + DT-fälten.
    Viktigt: 'DT tid (sek/kille)' och 'DT vila (sek/kille)' multipliceras med (Män + Svarta + Känner).
             DT tid läggs till 'Tid per kille (sek)', medan (DT tid + DT vila) läggs till 'Summa tid (sek)'.
    """

    # ---- Indata (säker avläsning) ----
    man     = int(float(grund.get("Män", 0) or 0))
    svarta  = int(float(grund.get("Svarta", 0) or 0))
    fitta   = int(float(grund.get("Fitta", 0) or 0))
    rumpa   = int(float(grund.get("Rumpa", 0) or 0))
    dp      = int(float(grund.get("DP", 0) or 0))
    dpp     = int(float(grund.get("DPP", 0) or 0))
    dap     = int(float(grund.get("DAP", 0) or 0))
    tap     = int(float(grund.get("TAP", 0) or 0))

    tid_s   = int(float(grund.get("Tid S", 0) or 0))  # sek per (fitta+rumpa+människor) del S
    tid_d   = int(float(grund.get("Tid D", 0) or 0))  # sek för DP/DPP/DAP del D
    vila    = int(float(grund.get("Vila", 0) or 0))   # vila per interaktion (räknas med i total vila)

    dt_tid_per = int(float(grund.get("DT tid (sek/kille)", 60) or 0))   # NYTT
    dt_vila_per= int(float(grund.get("DT vila (sek/kille)", 3) or 0))   # NYTT

    alskar  = int(float(grund.get("Älskar", 0) or 0))
    sover   = int(float(grund.get("Sover med", 0) or 0))

    pv = int(float(grund.get("Pappans vänner", 0) or 0))
    gr = int(float(grund.get("Grannar", 0) or 0))
    nv = int(float(grund.get("Nils vänner", 0) or 0))
    nf = int(float(grund.get("Nils familj", 0) or 0))

    nils = int(float(grund.get("Nils", 0) or 0))

    avgift = float(grund.get("Avgift", 30.0) or 0.0)

    # ---- Härledda fält ----
    # Känner = Pappans vänner + Grannar + Nils vänner + Nils familj
    kanner = pv + gr + nv + nf

    # Totalt män på raden (för scener och tid): Män + Svarta
    man_total = man + svarta

    # ---- SUMMA S / D / TP ----
    # Summa S = (Fitta + Rumpa + Män_total + Känner?) * Tid S
    # Du har tidigare valt att S, D, TP ska INKLUDERA Känner i räknaren:
    s_count = fitta + rumpa + man_total + kanner
    m_sum = s_count * tid_s  # sek

    # Summa D = (DP + DPP + DAP + Känner) * Tid D
    d_count = dp + dpp + dap + kanner
    n_sum = d_count * tid_d  # sek

    # Summa TP = (TAP + Känner) * Tid D  (TP använder även Tid D i din bas)
    o_sum = (tap + kanner) * tid_d      # sek

    # Summa vila (grund): (alla interaktioner) * vila
    total_inter = (fitta + rumpa + dp + dpp + dap + tap + man_total + kanner)
    p_sum = total_inter * vila  # sek

    # ---- Älskar & Sover med → tidstillägg i sekunder (läggs på total tid) ----
    # Älskar: 30 minuter per älskar → 1800 sek * älskar
    tid_alskar_sec = alskar * 1800
    # Sover med: 1 timme per sover med → 3600 sek * sover
    tid_sover_sec  = sover * 3600

    # ---- Hångel (3h) per kille → per-kille sek (för statistik)
    # 3 timmar = 10800 sek. Delas på MÄN (ej svarta separat; “Män” i din tidigare logik).
    # Basen delade på Män (ej man_total). Vi behåller det.
    hangel_sek_per_kille = 10800 // max(man, 1)
    hangel_ms_per_kille  = _ms_from_seconds(hangel_sek_per_kille)

    # ---- “Suger” = 60% av (Summa D + Summa TP)
    suger_total = 0.60 * (n_sum + o_sum)
    # per kille delas på totala killar (Män + Svarta + Känner) enligt din uppdaterade logik
    alla_killar = max(1, man_total + kanner)
    suger_per_kille_sec = int(round(suger_total / alla_killar))

    # ---- Prenumeranter ----
    # Prenumeranter = (Män + Fitta + Rumpa + DP + DPP + DAP + TAP + Känner) * Hårdhet,
    # med svarta som dubblas i prenumerant-skörden: män + 2*svarta + ...
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3   # dina senaste regler

    pren_bas = (man + 2*svarta) + fitta + rumpa + dp + dpp + dap + tap + kanner
    prenumeranter = pren_bas * hardhet

    # ---- Intäkter/Kostnader/Vinst ----
    intakter = prenumeranter * avgift
    intakt_man = man_total * 120.0            # “Kostnad män” i UI
    # “Intäkt Känner” = (Lön Malin + 120) * Känner — enligt din bas
    lon_malin_rad = max(150.0, min(800.0, prenumeranter * 0.10))
    intakt_kanner = (lon_malin_rad + 120.0) * kanner
    intakt_foretag = intakter * 0.20          # företagsandel 20%
    vinst = intakter - intakt_man - intakt_kanner - lon_malin_rad - intakt_foretag

    # ---- DT-tider (NYTT) ----
    # “Totalt antal män” för DT = Män + Svarta + Känner (dina ord: “totalt antal män” i logiken för tid/kille)
    tot_for_dt = man_total + kanner
    dt_tid_total_sec  = dt_tid_per  * tot_for_dt
    dt_vila_total_sec = dt_vila_per * tot_for_dt

    # ---- Total tid (sek) ----
    total_tid_sec = m_sum + n_sum + o_sum + p_sum + tid_alskar_sec + tid_sover_sec
    # Lägg på båda DT-delarna i totalen:
    total_tid_sec += (dt_tid_total_sec + dt_vila_total_sec)

    # ---- Tid per kille (sek) ----
    # Bas: ((m_sum/z) + (n_sum/z)*2 + (o_sum/z)*3 + suger_per_kille_sec)  (z = alla killar = Män + Svarta + Känner)
    # + DT tid per kille (men INTE DT vila)
    z = max(1, man_total + kanner)
    tid_per_kille_sec = int(round(
        (m_sum / z) + (n_sum / z) * 2 + (o_sum / z) * 3 + suger_per_kille_sec + dt_tid_per
    ))
    tid_per_kille_label = _ms_from_seconds(tid_per_kille_sec)

    # ---- Summa tid (h) + Klockan ----
    total_tid_h = total_tid_sec / 3600.0
    # Klockan = 7 + 3 + SummaTid(h) + 1  (enligt din bas)
    klockan = 7 + 3 + total_tid_h + 1
    klockan_label = f"{klockan:.2f}"

    # ---- Älskar/Sover med – visa som formaterad tid också ----
    tid_alskar_label = _hm_str_from_seconds(tid_alskar_sec)
    tid_sover_label  = _hm_str_from_seconds(tid_sover_sec)

    # Paketera resultat i return-dict (alla kolumner som appen förväntar sig)
    return {
        # Input/meta
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),

        "Män": man, "Svarta": svarta,
        "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid_per,            # sparas för spårbarhet
        "DT vila (sek/kille)": dt_vila_per,          # sparas för spårbarhet

        # Del-summor
        "Summa S": m_sum,
        "Summa D": n_sum,
        "Summa TP": o_sum,
        "Summa Vila": p_sum,

        # Älskar/Sover med tider
        "Tid Älskar (sek)": tid_alskar_sec,
        "Tid Älskar": tid_alskar_label,
        "Tid Sover med (sek)": tid_sover_sec,
        "Tid Sover med": tid_sover_label,

        # Total tid
        "Summa tid (sek)": int(round(total_tid_sec)),
        "Summa tid": _hm_str_from_seconds(total_tid_sec),

        # Per kille
        "Tid per kille (sek)": tid_per_kille_sec,
        "Tid per kille": tid_per_kille_label,

        # Övrigt
        "Klockan": klockan_label,
        "Älskar": alskar,
        "Sover med": sover,
        "Känner": kanner,
        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Totalt Män": man_total,   # (Män + Svarta)
        "Tid kille": tid_per_kille_label,
        "Nils": nils,

        # Hångel (för statistik)
        "Hångel (sek/kille)": hangel_sek_per_kille,
        "Hångel (m:s/kille)": hangel_ms_per_kille,

        # Suger
        "Suger": int(round(suger_total)),
        "Suger per kille (sek)": int(round(suger_per_kille_sec)),

        # Hårdhet/ekonomi
        "Hårdhet": hardhet,
        "Prenumeranter": int(round(prenumeranter)),
        "Avgift": avgift,
        "Intäkter": float(intakter),
        "Intäkt män": float(intakt_man),         # visas som kostnad i UI
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin_rad),
        "Intäkt Företaget": float(intakt_foretag),
        "Vinst": float(vinst),

        "Känner Sammanlagt": kanner,
    }
