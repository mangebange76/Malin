# berakningar.py
from datetime import datetime, date, time, timedelta

# ---------------------------
# Hjälpformat
# ---------------------------
def _hm_str_from_seconds(q_sec: int) -> str:
    q = int(max(0, q_sec))
    h = q // 3600
    m = round((q % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    s = int(max(0, sec))
    m = s // 60
    r = s % 60
    return f"{int(m)}m {int(r)}s"

def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and not x.strip():
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and not x.strip():
            return default
        return float(x)
    except Exception:
        return default

# ---------------------------
# Huvudberäkning
# ---------------------------
def berakna_radvarden(grund: dict, rad_datum: date, fodelsedatum: date, starttid: time) -> dict:
    """
    Returnerar en dict med alla fält som ska visas/sparas.
    ALL logik är samlad här.

    Viktiga antaganden (från din spec):
      - Summa S = Tid S * (Fitta + Rumpa) + (Totalt Män * DT tid)
      - Summa D = Tid D * (DP + DPP + DAP)
      - Summa TP = Tid S * TAP   (du sa tidigare att jag hade rätt på denna)
      - Summa Vila = Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + (Totalt Män * DT vila)
      - Summa tid = Summa S + Summa D + Summa TP + Summa Vila   (sek)
      - Älskar-tid = Älskar * 20 min (sek) — ska INTE ingå i Summa tid
      - Sover-med-tid = (0/1) * 20 min (sek) — ska INTE ingå i Summa tid
      - Klockan = starttid + Summa tid + 3h + 1h + älskar-tid + sover-tid
      - Suger (sek) = 60% av Summa tid (sek)
      - Tid/kille(sek) = (Summa S / tot_män) + 2*(Summa D / tot_män) + 3*(Summa TP / tot_män)
                         + (Suger / tot_män) + DT tid (sek/kille)
      - Hångel (sek/kille) = (3h) / tot_män
      - Hårdhet = regler (se _hardhet)
      - Prenumeranter = (Fitta+Rumpa+DP+DPP+DAP+TAP+Totalt Män) * Hårdhet
      - Intäkter = Prenumeranter * Avgift
      - Känner = Pappans vänner + Grannar + Nils vänner + Nils familj
      - Intäkt Känner = (Summa tid i timmar) * 35 * Känner
      - Utgift män = ( (Män+Svarta+Bekanta+Eskilstuna killar+Bonus deltagit) + PROD_STAFF ) * (Summa tid i timmar) * 15
                     (PROD_STAFF = hela personalstyrkan får lön oavsett deltagit)
      - Lön Malin = 8% av (Intäkter - Utgift män), min $150, max $800
      - Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    """

    # -------- Inläsning (säker) --------
    man        = _safe_int(grund.get("Män", 0))
    svarta     = _safe_int(grund.get("Svarta", 0))
    fitta      = _safe_int(grund.get("Fitta", 0))
    rumpa      = _safe_int(grund.get("Rumpa", 0))
    dp         = _safe_int(grund.get("DP", 0))
    dpp        = _safe_int(grund.get("DPP", 0))
    dap        = _safe_int(grund.get("DAP", 0))
    tap        = _safe_int(grund.get("TAP", 0))

    pappan     = _safe_int(grund.get("Pappans vänner", 0))
    grannar    = _safe_int(grund.get("Grannar", 0))
    nvanner    = _safe_int(grund.get("Nils vänner", 0))
    nfamilj    = _safe_int(grund.get("Nils familj", 0))
    bekanta    = _safe_int(grund.get("Bekanta", 0))
    esk        = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_delt = _safe_int(grund.get("Bonus deltagit", 0))
    # bonus_total = _safe_int(grund.get("Bonus killar", 0))  # används för visning/extern logik, påverkar ej tiderna

    pers_delt  = _safe_int(grund.get("Personal deltagit", 0))  # påverkar ej lönen (PROD_STAFF används i stället)
    prod_staff = _safe_int(grund.get("PROD_STAFF", 0))

    alskar_cnt = _safe_int(grund.get("Älskar", 0))
    sover_med  = _safe_int(grund.get("Sover med", 0))

    tid_s      = _safe_int(grund.get("Tid S", 0))
    tid_d      = _safe_int(grund.get("Tid D", 0))
    vila       = _safe_int(grund.get("Vila", 0))
    dt_tid     = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila    = _safe_int(grund.get("DT vila (sek/kille)", 0))

    avgift     = _safe_float(grund.get("Avgift", 30.0))
    typ        = str(grund.get("Typ") or "")

    # -------- Härleder & totals --------
    kanner = pappan + grannar + nvanner + nfamilj
    totalt_man = (
        man + svarta + bekanta + esk + bonus_delt + prod_staff
        # OBS: du har tidigare sagt att "Totalt Män"-kolumnen finns; vi räknar on-the-fly här.
    )
    if totalt_man < 0:
        totalt_man = 0

    # -------- Tider (sek) --------
    # DT-bidrag läggs in i Summa S resp. Summa Vila enligt din spec
    summa_s   = tid_s * (fitta + rumpa) + (totalt_man * dt_tid)
    summa_d   = tid_d * (dp + dpp + dap)
    summa_tp  = tid_s * tap
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + (totalt_man * dt_vila)
    summa_tid_sec = int(max(0, summa_s + summa_d + summa_tp + summa_vila))

    # Älskar & Sover (utanför Summa tid)
    alskar_sec = alskar_cnt * 20 * 60
    sover_sec  = sover_med * 20 * 60

    # Suger = 60% av scenens aktiva tid (Summa tid)
    suger_sec = int(round(0.60 * summa_tid_sec))

    # Tid per kille (sek)
    if totalt_man > 0:
        tid_per_kille_sec = int(
            (summa_s / totalt_man)
            + 2 * (summa_d / totalt_man)
            + 3 * (summa_tp / totalt_man)
            + (suger_sec / totalt_man)
            + dt_tid
        )
        hångel_per_kille_sec = int((3 * 3600) / totalt_man)
        suger_per_kille_sec  = int(suger_sec / totalt_man)
    else:
        tid_per_kille_sec = 0
        hångel_per_kille_sec = 0
        suger_per_kille_sec = 0

    # Klockslag: start + Summa tid + 3h + 1h + älskar + sover
    base_dt = datetime.combine(rad_datum, starttid)
    slut_dt = base_dt + timedelta(
        seconds = int(summa_tid_sec + (3*3600) + (1*3600) + alskar_sec + sover_sec)
    )
    klockan_str = slut_dt.strftime("%H:%M")

    # -------- Hårdhet & Prenumeranter --------
    hårdhet = _hardhet(dp, dpp, dap, tap, totalt_man, svarta)
    pren = int(max(0, (fitta + rumpa + dp + dpp + dap + tap + totalt_man) * hårdhet))

    # -------- Ekonomi --------
    intakter = float(pren) * float(avgift)
    summa_tid_hr = (summa_tid_sec / 3600.0)

    intakt_kanner = 35.0 * summa_tid_hr * float(kanner)

    # Utgift män (alla män + HELA personalstyrkan) * tid * 15
    lonbas = (man + svarta + bekanta + esk + bonus_delt) + prod_staff
    utgift_man = 15.0 * summa_tid_hr * float(max(0, lonbas))

    # Lön Malin = 8% av (Intäkter - Utgift män), min 150 max 800
    bruttomarg = max(0.0, float(intakter) - float(utgift_man))
    lon_malin = max(150.0, min(800.0, 0.08 * bruttomarg))

    vinst = float(intakter) - float(utgift_man) - float(intakt_kanner) - float(lon_malin)

    # -------- Output --------
    out = {
        "Datum": rad_datum.isoformat(),
        "Veckodag": ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][rad_datum.weekday()],
        "Typ": typ,
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Pappans vänner": pappan, "Grannar": grannar, "Nils vänner": nvanner, "Nils familj": nfamilj,
        "Bekanta": bekanta, "Eskilstuna killar": esk,
        "Bonus deltagit": bonus_delt, "Personal deltagit": pers_delt,
        "Känner": kanner, "Totalt Män": totalt_man,

        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": _hm_str_from_seconds(summa_tid_sec),

        "Älskar": alskar_cnt,
        "Sover med": sover_med,
        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": _ms_str_from_seconds(alskar_sec),
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": _ms_str_from_seconds(sover_sec),

        "Suger": int(suger_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": _ms_str_from_seconds(tid_per_kille_sec),

        "Hångel (sek/kille)": int(hångel_per_kille_sec),
        "Hångel (m:s/kille)": _ms_str_from_seconds(hångel_per_kille_sec),

        "Klockan": klockan_str,

        "Hårdhet": int(hårdhet),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Intäkt Känner": float(intakt_kanner),
        "Utgift män": float(utgift_man),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),
    }
    return out

def _hardhet(dp, dpp, dap, tap, totalt_man, svarta) -> int:
    """
    Hårdhetssumma enligt dina regler:
      - DP>0 → +3, DPP>0 → +5, DAP>0 → +7, TAP>0 → +9
      - Totalt Män >100 → +1, >200 → +3, >=300 → +5, >=500 → +6, >=1000 → +10
      - Svarta>0 → +3
    Notera: thresholds staplas inte; vi tar största tillämpliga för Totalt Män.
    """
    h = 0
    if dp  > 0: h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9

    tm = int(max(0, totalt_man))
    if tm >= 1000: h += 10
    elif tm >= 500: h += 6
    elif tm >= 300: h += 5
    elif tm >  200: h += 3
    elif tm >  100: h += 1

    if int(svarta) > 0:
        h += 3

    return h

# (forts. berakningar.py)
# Inget mer behövs här – filen är komplett.
# Importera i app.py med:
#   from berakningar import berakna_radvarden as calc_row_values
