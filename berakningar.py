# berakningar.py
from datetime import datetime, date, time, timedelta

# ----------------------------- Hjälpfunktioner -----------------------------
def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "": return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "": return default
        return float(x)
    except Exception:
        return default

def _fmt_hm_from_seconds(sec: int) -> str:
    if sec is None: return "-"
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _fmt_ms_from_seconds(sec: int) -> str:
    if sec is None: return "-"
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ----------------------------- Beräkningar -----------------------------
def berakna_radvarden(grund: dict, rad_datum: date, foddatum: date, starttid: time) -> dict:
    """
    Returnerar alla fält som appen behöver, inklusive:
    - Summa-fält (S/D/TP/Vila)
    - Summa tid (sek & label)
    - Klockan (sluttid)
    - Tid Älskar / Sover med (sek & label)
    - Hångel (sek/kille & m:s/kille) [visning]
    - Tid per kille (sek & label)
    - Prenumeranter, Intäkter
    - Känner (radnivå)
    - Utgift män, Intäkt Känner, Lön Malin, Vinst
    - Totalt Män (radnivå)
    Obs: Bonus-antal sätts i UI/flödena; här används värden som kommer in i `grund`.
    """

    # ----------- Läs in basvärden -----------
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))
    rumpa   = _safe_int(grund.get("Rumpa", 0))
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))                 # sek
    tid_d   = _safe_int(grund.get("Tid D", 0))                 # sek
    vila    = _safe_int(grund.get("Vila", 0))                  # sek
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))    # sek/kille
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))   # sek/kille

    alskar     = _safe_int(grund.get("Älskar", 0))
    sover_med  = _safe_int(grund.get("Sover med", 0))          # 0/1

    pappan = _safe_int(grund.get("Pappans vänner", 0))
    grann  = _safe_int(grund.get("Grannar", 0))
    nv     = _safe_int(grund.get("Nils vänner", 0))
    nf     = _safe_int(grund.get("Nils familj", 0))
    bek    = _safe_int(grund.get("Bekanta", 0))
    esk    = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_total    = _safe_int(grund.get("Bonus killar", 0))      # för visning/spar
    bonus_deltagit = _safe_int(grund.get("Bonus deltagit", 0))    # används i Totalt Män och i Svarta-tillägg (svart-scen-regel hanteras i UI)
    personal_delt  = _safe_int(grund.get("Personal deltagit", 0))

    nils = _safe_int(grund.get("Nils", 0))

    avgift = _safe_float(grund.get("Avgift", 30.0))  # USD per prenumerant (rad)

    # ----------- Härledda fält -----------
    # Känner (radnivå)
    kanner = pappan + grann + nv + nf

    # Totalt Män på raden
    totalt_man = (
        man + kanner + svarta + bek + esk + bonus_deltagit + personal_delt
    )

    # ----------- Summa-delar -----------
    # Summa S = Tid S * (Fitta + Rumpa) + DT tid * Totalt Män
    summa_s_sec = tid_s * (fitta + rumpa) + dt_tid * totalt_man

    # Summa D = Tid D * (DP + DPP + DAP)
    summa_d_sec = tid_d * (dp + dpp + dap)

    # Summa TP = TAP * Tid S  (enligt tidigare överenskommelse)
    summa_tp_sec = tap * tid_s

    # Summa Vila = Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila * Totalt Män
    summa_vila_sec = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * totalt_man

    # Summa tid (ARBETSTID – exkl. älskar/sover med, som läggs på klockan separat)
    summa_tid_sec = summa_s_sec + summa_d_sec + summa_tp_sec + summa_vila_sec

    # ----------- Extra-tider (påverkar klockan men ej Summa tid) -----------
    # Älskar/Sover med = antal * 20 minuter
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover_med * 20 * 60

    # ----------- Hångel (visning) -----------
    # 3 timmar totalt, fördelat på Totalt Män
    if totalt_man > 0:
        hangel_per_kille_sec = int(round((3 * 3600) / totalt_man))
    else:
        hangel_per_kille_sec = 0
    hangel_label = _fmt_ms_from_seconds(hangel_per_kille_sec)

    # ----------- Tid per kille -----------
    #  S_kille = Summa S / TotMän
    #  D_kille = (Summa D / TotMän) * 2    (två män)
    #  TP_kille = (Summa TP / TotMän) * 3  (tre män)
    #  Suger per kille = 60% av Summa tid / TotMän
    #  + DT tid per kille (redan separat)
    if totalt_man > 0:
        s_kille  = summa_s_sec  / totalt_man
        d_kille  = (summa_d_sec / totalt_man) * 2
        tp_kille = (summa_tp_sec / totalt_man) * 3
        suger_kille = 0.60 * (summa_tid_sec / totalt_man)
    else:
        s_kille = d_kille = tp_kille = suger_kille = 0.0

    tid_per_kille_sec = int(round(s_kille + d_kille + tp_kille + suger_kille + dt_tid))
    tid_per_kille_lbl = _fmt_ms_from_seconds(tid_per_kille_sec)

    # ----------- Klockan (sluttid) -----------
    # Klockan = starttid + Summa tid + 3h + 1h + älskar + sover
    # (3h + 1h = fasta tillägg enligt specifikationen)
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt = start_dt + timedelta(
        seconds = summa_tid_sec + (3 * 3600) + (1 * 3600) + alskar_sec + sover_sec
    )
    klockan_label = slut_dt.strftime("%H:%M")

    # ----------- Prenumeranter & Hårdhet -----------
    # Pren = (Fitta+Rumpa+DP+DPP+DAP+TAP+Totalt Män) * Hårdhet
    # Hårdhet = summa av villkor
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    # Totalt Män trösklar (högsta som gäller)
    if totalt_man >= 1000: hardhet += 10
    elif totalt_man >= 500: hardhet += 6
    elif totalt_man >= 300: hardhet += 5
    elif totalt_man >= 200: hardhet += 3
    elif totalt_man >= 100: hardhet += 1
    # Svarta > 0
    if svarta > 0: hardhet += 3

    pren_bas = fitta + rumpa + dp + dpp + dap + tap + totalt_man
    prenumeranter = int(round(pren_bas * hardhet))

    # Intäkter (rad) = Prenumeranter * Avgift
    intakter = float(prenumeranter) * float(avgift)

    # ----------- Ekonomi ----------- 
    # Utgift män (ersätter "Intäkt män"):
    # = (Män + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + HELA personalstyrkan) * (Summa tid i timmar * 15$)
    summa_tid_h = summa_tid_sec / 3600.0
    antal_betalas = man + svarta + bek + esk + bonus_deltagit + _safe_int(grund.get("PROD_STAFF", 800))
    utgift_man = float(antal_betalas) * (summa_tid_h * 15.0)

    # Intäkt Känner = (Summa tid i timmar * 35$) * Känner (radnivå)
    intakt_kanner = (summa_tid_h * 35.0) * float(kanner)

    # Lön Malin = 8% av max(intäkter - utgift män, 0), clamp [150, 800]
    kvar = max(0.0, float(intakter) - float(utgift_man))
    lon_malin = _clamp(kvar * 0.08, 150.0, 800.0)

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # ----------- Övrigt som ska sparas/visas -----------
    # Suger per kille (sek) för visning
    suger_per_kille_sec = int(round(suger_kille))

    # Tid Älskar / Sover med (sek + label)
    tid_alskar_label = _fmt_hm_from_seconds(alskar_sec)
    tid_sover_label  = _fmt_hm_from_seconds(sover_sec)

    # Summa tid label
    summa_tid_label = _fmt_hm_from_seconds(summa_tid_sec)

    # ----------- Bygg resultat -----------
    res = {
        # Input som kan behövas utåt
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),

        # Summeringar
        "Summa S": _fmt_hm_from_seconds(summa_s_sec),
        "Summa D": _fmt_hm_from_seconds(summa_d_sec),
        "Summa TP": _fmt_hm_from_seconds(summa_tp_sec),
        "Summa Vila": _fmt_hm_from_seconds(summa_vila_sec),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": summa_tid_label,

        # Extra tider
        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": tid_alskar_label,
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": tid_sover_label,

        # Hångel (visning)
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_label,

        # Per kille
        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": tid_per_kille_lbl,
        "Suger per kille (sek)": int(suger_per_kille_sec),

        # Tider/klocka
        "Klockan": klockan_label,

        # Känner (rad)
        "Känner": int(kanner),

        # Totalt Män
        "Totalt Män": int(totalt_man),

        # Prenumeranter & ekonomi
        "Hårdhet": int(hardhet),
        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # Pass-through (sparas)
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": alskar, "Sover med": sover_med,
        "Pappans vänner": pappan, "Grannar": grann, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bek, "Eskilstuna killar": esk,
        "Bonus killar": bonus_total, "Bonus deltagit": bonus_deltagit, "Personal deltagit": personal_delt,
        "Nils": nils,
    }

    return res
