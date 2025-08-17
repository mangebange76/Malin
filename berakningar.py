# berakningar.py — Del 1/3
from datetime import datetime, date, time, timedelta

# -------- Hjälpfunktioner ----------
def _safe_int(x, default=0):
    try:
        if x is None:
            return default
        s = str(x).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def _fmt_hm_from_seconds(total_sec: int) -> str:
    h = total_sec // 3600
    m = round((total_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _fmt_ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _add_time_of_day(d: date, t: time, add_seconds: int) -> str:
    # Returnera klockslag (HH:MM) efter att ha lagt till add_seconds
    dt = datetime.combine(d, t) + timedelta(seconds=add_seconds)
    return dt.strftime("%H:%M")

# -------- Huvudfunktion ----------
def berakna_radvarden(rad: dict, rad_datum: date, fodseldatum: date, starttid: time) -> dict:
    """
    Tar in inmatade fält för en rad och räknar ut alla derivat.
    - Summa S/D/TP/Vila
    - Summa tid (sek) och HM-format
    - Hångel/Suger per kille
    - Tid Älskar/Sover med (sek + format)
    - Klockan (starttid + buffert + extra-tider)
    - Prenumeranter/Hårdhet/Intäkter
    - Utgift män, Intäkt Känner, Lön Malin, Vinst
    - Känner, Totalt Män
    Allt utan läs/skriv mot Sheets.
    """

    # --- Råinmatning (säker-parsa) ---
    man     = _safe_int(rad.get("Män", 0))
    svarta  = _safe_int(rad.get("Svarta", 0))
    fitta   = _safe_int(rad.get("Fitta", 0))
    rumpa   = _safe_int(rad.get("Rumpa", 0))
    dp      = _safe_int(rad.get("DP", 0))
    dpp     = _safe_int(rad.get("DPP", 0))
    dap     = _safe_int(rad.get("DAP", 0))
    tap     = _safe_int(rad.get("TAP", 0))

    tid_s   = _safe_int(rad.get("Tid S", 0))             # sek
    tid_d   = _safe_int(rad.get("Tid D", 0))             # sek
    vila    = _safe_int(rad.get("Vila", 0))              # sek
    dt_tid  = _safe_int(rad.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(rad.get("DT vila (sek/kille)", 0))

    alskar  = _safe_int(rad.get("Älskar", 0))
    sover   = _safe_int(rad.get("Sover med", 0))

    pv      = _safe_int(rad.get("Pappans vänner", 0))
    gr      = _safe_int(rad.get("Grannar", 0))
    nv      = _safe_int(rad.get("Nils vänner", 0))
    nf      = _safe_int(rad.get("Nils familj", 0))
    bk      = _safe_int(rad.get("Bekanta", 0))
    esk     = _safe_int(rad.get("Eskilstuna killar", 0))

    bonus_k = _safe_int(rad.get("Bonus killar", 0))
    bonus_d = _safe_int(rad.get("Bonus deltagit", 0))
    # Om Bonus deltagit inte matats in: defaulta till 40% av bonus_k (avrundat nedåt)
    if rad.get("Bonus deltagit", None) is None:
        bonus_d = (bonus_k * 40) // 100

    personal = _safe_int(rad.get("Personal deltagit", 0))
    nils     = _safe_int(rad.get("Nils", 0))

    avgift   = float(rad.get("Avgift", 30.0))

    # --- Känner & Totalt män ---
    kanner = pv + gr + nv + nf
    # Totalt Män på radnivå: Män, Känner, Svarta, Bekanta, Eskilstuna, Bonus deltagit, Personal deltagit
    tot_man = man + kanner + svarta + bk + esk + bonus_d + personal

    # --- Tider (sek) för scenen (exklusive Älskar/Sover) ---
    # Summa S = Tid S × (Fitta + Rumpa) + DT tid × Totalt män
    summa_s = tid_s * (fitta + rumpa) + dt_tid * max(tot_man, 0)

    # Summa D = Tid D × (DP + DPP + DAP)
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP (bekräftat tidigare): TAP × Tid S
    summa_tp = tap * tid_s

    # Summa Vila = Vila × (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila × Totalt män
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * max(tot_man, 0)

    # Totala scensekunder (utan älskar/sover)
    scene_total_sec = summa_s + summa_d + summa_tp + summa_vila

# berakningar.py — Del 2/3 (forts.)

    # ---------------- Tider för extra moment ----------------
    # Älskar: 20 min per tillfälle, Sover med: 20 min om 0/1
    tid_alskar_sec = alskar * 20 * 60
    tid_sover_sec  = sover * 20 * 60

    # Hångel: 3 timmar / (män + svarta + bekanta + eskilstuna + bonus_deltagit + personal)
    # (Visas bara i liven, ingår inte i scenernas tid)
    hog_den = man + svarta + bk + esk + bonus_d + personal
    hangel_per_kille_sec = 0 if hog_den <= 0 else int(round(3 * 3600 / hog_den))
    hangel_per_kille_str = _fmt_ms_from_seconds(hangel_per_kille_sec)

    # Suger: 60% av scensumman
    suger_total_sec = int(round(scene_total_sec * 0.60))
    suger_per_kille_sec = 0 if tot_man <= 0 else int(round(suger_total_sec / tot_man))

    # ---------------- Summa tid & Klockan ----------------
    # Summa tid (sek) för scenen (utan älskar/sover) – som arbetstid
    summa_tid_sec = int(scene_total_sec)
    summa_tid_hm  = _fmt_hm_from_seconds(summa_tid_sec)

    # Klockan = starttid + scensek + 3h + 1h + tid_alskar + tid_sover
    # (lägger älskar/sover och 3+1 h direkt på klockan, inte i Summa tid)
    extra_buffer_sec = (3 + 1) * 3600
    klockan_str = _add_time_of_day(rad_datum, starttid, summa_tid_sec + extra_buffer_sec + tid_alskar_sec + tid_sover_sec)

    # ---------------- Tid per kille ----------------
    # per spec:
    #  - Summa S / tot_män
    #  - (Summa D / tot_män) * 2 (två män)
    #  - (Summa TP / tot_män) * 3 (tre män)
    #  - Suger_total / tot_män (60% av totaltiden)
    #  - + DT tid (sek/kille) (utöver att DT redan ingår i Summa S)
    if tot_man > 0:
        tid_per_kille_sec = int(round(
            (summa_s / tot_man)
            + 2 * (summa_d / tot_man)
            + 3 * (summa_tp / tot_man)
            + (suger_total_sec / tot_man)
            + dt_tid
        ))
    else:
        tid_per_kille_sec = 0
    tid_per_kille_str = _fmt_ms_from_seconds(tid_per_kille_sec)

    # ---------------- Prenumeranter & Hårdhet ----------------
    # Hårdhet = summering av villkor
    hardhet = 0
    if dp   > 0: hardhet += 3
    if dpp  > 0: hardhet += 5
    if dap  > 0: hardhet += 7
    if tap  > 0: hardhet += 9
    if tot_man > 100:  hardhet += 1
    if tot_man > 200:  hardhet += 3
    if tot_man == 300: hardhet += 5
    if tot_man > 500:  hardhet += 6
    if tot_man > 1000: hardhet += 10
    if svarta > 0:     hardhet += 3

    pren_bas = fitta + rumpa + dp + dpp + dap + tap + tot_man
    prenumeranter = int(max(0, pren_bas * hardhet))

    # ---------------- Ekonomi ----------------
    # Intäkter = prenumeranter * avgift
    intakter = float(prenumeranter) * float(avgift)

    # Utgift män:
    #  (män + svarta + bekanta + eskilstuna + bonus_deltagit + ALL PERSONAL (fast)) * (summa_tid_i_timmar) * $15
    prod_staff_total = _safe_int(rad.get("PROD_STAFF", 800))
    utg_mann_count = man + svarta + bk + esk + bonus_d + prod_staff_total
    summa_tid_hours = summa_tid_sec / 3600.0
    utgift_man = float(utg_mann_count) * summa_tid_hours * 15.0

    # Intäkt Känner = (summa tid i timmar) * $35 * (Känner på raden)
    intakt_kanner = summa_tid_hours * 35.0 * float(kanner)

    # Lön Malin = 8% av (Intäkter - Utgift män), min $150, max $800 (ej negativ)
    lon_malin_raw = max(0.0, (intakter - utgift_man) * 0.08)
    lon_malin = min(800.0, max(150.0, lon_malin_raw))

    # Vinst = Intäkter − (Utgift män + Intäkt Känner + Lön Malin)
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # ---------------- Ålder (för live) ----------------
    alder = rad_datum.year - fodseldatum.year - (
        (rad_datum.month, rad_datum.day) < (fodseldatum.month, fodseldatum.day)
    )

# berakningar.py — Del 3/3 (slut)

    # ---------------- Bygg retur-rad ----------------
    beraknad_rad = {
        # Tider
        "Summa tid (sek)"       : summa_tid_sec,
        "Summa tid (h:m)"       : summa_tid_hm,
        "Tid älskar (sek)"      : tid_alskar_sec,
        "Tid sover med (sek)"   : tid_sover_sec,
        "Hångel (sek/kille)"    : hangel_per_kille_sec,
        "Hångel (m:s/kille)"    : hangel_per_kille_str,
        "Suger (sek)"           : suger_total_sec,
        "Tid per kille (sek)"   : tid_per_kille_sec,
        "Tid per kille"         : tid_per_kille_str,
        "DT tid (sek/kille)"    : dt_tid,
        "DT vila (sek/kille)"   : dt_vila,
        "Klockan"               : klockan_str,

        # Ekonomi
        "Prenumeranter"         : prenumeranter,
        "Hårdhet"               : hardhet,
        "Intäkter"              : round(intakter, 2),
        "Utgift män"            : round(utgift_man, 2),
        "Intäkt Känner"         : round(intakt_kanner, 2),
        "Lön Malin"             : round(lon_malin, 2),
        "Vinst"                 : round(vinst, 2),

        # Deltagande
        "Totalt män"            : tot_man,
        "Bonus deltagit"        : bonus_d,
        "Personal deltagit"     : personal,
        "Känner (rad)"          : kanner,
        "Känner totalt"         : kanner_totalt,

        # Metadata
        "Datum"                 : rad_datum,
        "Typ"                   : typ,
        "Ålder Malin"           : alder
    }

    return beraknad_rad
