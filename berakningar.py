# berakningar.py
from datetime import date, time, datetime, timedelta

def _safe_int(x, default=0):
    try:
        if x is None: 
            return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: 
            return default
        if isinstance(x, str) and x.strip()=="":
            return default
        return float(x)
    except Exception:
        return default

def _hm_from_seconds(sec: int) -> str:
    h = sec // 3600
    m = round((sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_from_seconds(sec: int) -> str:
    if sec <= 0:
        return "0m 0s"
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _clock_from(time_start: time, plus_seconds: int) -> str:
    base = datetime(2000,1,1, time_start.hour, time_start.minute, time_start.second)
    done = base + timedelta(seconds=plus_seconds)
    return done.strftime("%H:%M")

def _age_on(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))

def _hardhet(dp, dpp, dap, tap, tot_man, svarta):
    score = 0
    if dp  > 0: score += 3
    if dpp > 0: score += 5
    if dap > 0: score += 7
    if tap > 0: score += 9
    # Trösklar för Totalt Män (adderas kumulativt)
    if tot_man > 100:  score += 1
    if tot_man > 200:  score += 3
    if tot_man >= 300: score += 5
    if tot_man >= 500: score += 6
    if tot_man >= 1000: score += 10
    if svarta > 0: score += 3
    return score

def berakna_radvarden(grund: dict, rad_datum: date, foddatum: date, starttid: time) -> dict:
    """
    Beräknar samtliga fält för en rad utifrån specificerad logik.
    Inga sidoeffekter (ingen skrivning mot Sheets).

    Viktigt: Om du vill att hela personalstyrkan alltid ska räknas i lönekostnaden,
    skicka in nyckeln "PROD_STAFF" i `grund` (t.ex. 800). Då används detta antal i
    'Utgift män' istället för "Personal deltagit".
    """

    # --- Läs in basfält (int) ---
    man     = _safe_int(grund.get("Män"), 0)
    svarta  = _safe_int(grund.get("Svarta"), 0)
    fitta   = _safe_int(grund.get("Fitta"), 0)
    rumpa   = _safe_int(grund.get("Rumpa"), 0)
    dp      = _safe_int(grund.get("DP"), 0)
    dpp     = _safe_int(grund.get("DPP"), 0)
    dap     = _safe_int(grund.get("DAP"), 0)
    tap     = _safe_int(grund.get("TAP"), 0)

    tid_s   = _safe_int(grund.get("Tid S"), 0)               # sek
    tid_d   = _safe_int(grund.get("Tid D"), 0)               # sek
    vila    = _safe_int(grund.get("Vila"), 0)                # sek
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)"), 0)  # sek/kille
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)"), 0) # sek/kille

    alskar     = _safe_int(grund.get("Älskar"), 0)
    sover_med  = _safe_int(grund.get("Sover med"), 0)

    pappan = _safe_int(grund.get("Pappans vänner"), 0)
    grann  = _safe_int(grund.get("Grannar"), 0)
    nv     = _safe_int(grund.get("Nils vänner"), 0)
    nf     = _safe_int(grund.get("Nils familj"), 0)
    bek    = _safe_int(grund.get("Bekanta"), 0)
    esk    = _safe_int(grund.get("Eskilstuna killar"), 0)

    bonus_killar   = _safe_int(grund.get("Bonus killar"), 0)     # informativt
    bonus_deltagit = _safe_int(grund.get("Bonus deltagit"), 0)   # del av total, räknas som "svarta" i statistik (hanteras i Statistik)
    pers_deltagit  = _safe_int(grund.get("Personal deltagit"), 0)

    nils = _safe_int(grund.get("Nils"), 0)

    avgift = _safe_float(grund.get("Avgift"), 30.0)

    # Alternativ personalbas för lön (hela styrkan alltid med om PROD_STAFF finns)
    prod_staff_total = _safe_int(grund.get("PROD_STAFF"), 0)

    # --- Känner (radnivå) ---
    kanner = pappan + grann + nv + nf

    # --- Totalt män på radnivå (enligt spec) ---
    totalt_man = (
        man
        + kanner
        + svarta
        + bek
        + esk
        + bonus_deltagit
        + pers_deltagit
    )

    # --- Del-summor för scenens tid (sek) ---
    # Summa S: Tid S * (Fitta + Rumpa) + DT tid * (Totalt män)
    summa_s = tid_s * (fitta + rumpa) + dt_tid * totalt_man

    # Summa D: Tid D * (DP + DPP + DAP)
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP: TAP * 3 * (Tid S)
    summa_tp = tap * 3 * tid_s

    # Summa Vila: Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila * (Totalt män)
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * totalt_man

    # Älskar & Sover med (sek) — ska inte ingå i scenens tid, läggs endast på klockan
    tid_alskar_sec = alskar * 20 * 60
    tid_sover_sec  = sover_med * 20 * 60

    # Summa tid för scenen (sek) (exkl. älskar/sover)
    summa_tid_sec = summa_s + summa_d + summa_tp + summa_vila

    # Klockan = starttid + summa_tid_sec + 3h + 1h + tid_alskar_sec + tid_sover_sec
    klock_sec = summa_tid_sec + (4 * 3600) + tid_alskar_sec + tid_sover_sec
    klockan = _clock_from(starttid, klock_sec)

    # Hångel (sek/kille) = 3h / Totalt män (endast visning)
    hangel_per_kille_sec = 0
    if totalt_man > 0:
        hangel_per_kille_sec = int(round((3 * 3600) / totalt_man))

    # Suger = 60% av scenens tid (sek)
    suger_total_sec = int(round(summa_tid_sec * 0.60))
    suger_per_kille_sec = int(round(suger_total_sec / totalt_man)) if totalt_man > 0 else 0

    # Tid per kille (sek) =
    # (Summa S)/TotM + (Summa D)/TotM * 2 + (Summa TP)/TotM * 3 + (SugerTotal)/TotM + DT tid (sek/kille)
    if totalt_man > 0:
        tid_per_kille_sec = int(round(
            (summa_s / totalt_man)
            + (summa_d / totalt_man) * 2
            + (summa_tp / totalt_man) * 3
            + (suger_total_sec / totalt_man)
            + dt_tid
        ))
    else:
        tid_per_kille_sec = 0

    # Prenumeranter = (Fitta+Rumpa+DP+DPP+DAP+TAP+TotM) * Hårdhet
    hardhet = _hardhet(dp, dpp, dap, tap, totalt_man, svarta)
    prenumeranter = (fitta + rumpa + dp + dpp + dap + tap + totalt_man) * hardhet

    # Intäkter (rad) = Prenumeranter * Avgift
    intakter = prenumeranter * avgift

    # Intäkt Känner = (Summa tid i timmar) * 35 * (Känner)
    intakt_kanner = (summa_tid_sec / 3600.0) * 35.0 * kanner

    # Utgift män =
    # (Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + PROD_STAFF) * (Summa tid i timmar) * $15
    # Obs: PROD_STAFF skriver över "Personal deltagit" i lönebasen.
    lon_bas_personal = prod_staff_total if prod_staff_total > 0 else pers_deltagit
    lon_bas_tot = (man + svarta + bek + esk + bonus_deltagit + lon_bas_personal)
    utgift_man = lon_bas_tot * (summa_tid_sec / 3600.0) * 15.0

    # Lön Malin = 8% av (Intäkter - Utgift män), men minst 150 och max 800
    brutto_for_malin = max(0.0, intakter - utgift_man)
    lon_malin_raw = 0.08 * brutto_for_malin
    lon_malin = max(150.0, min(800.0, lon_malin_raw))

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # Ytterligare visningsfält
    hangel_label = _ms_from_seconds(hangel_per_kille_sec)
    tid_per_kille_label = _ms_from_seconds(tid_per_kille_sec)
    summa_tid_label = _hm_from_seconds(summa_tid_sec)

    # Ålder för visning (om appen vill)
    alder = _age_on(rad_datum, foddatum)

    # Känner Sammanlagt (inställningsnivå) brukar vara max-summan, men här returnerar vi radens Känner separat.
    # Appen kan skriva in "Känner Sammanlagt" om den vill; här lämnar vi tomt/0 så inte gissar fel.
    # Vill du ändå fylla det här från appen – skicka in t.ex. grund["KANNER_SAMMANLAGT_HINT"].
    kanner_sammanlagt = _safe_int(grund.get("KANNER_SAMMANLAGT_HINT"), 0)

    # ---------------- Returnera allt som databasen/appen förväntar sig ----------------
    out = {
        "Typ":         str(grund.get("Typ") or ""),
        "Veckodag":    grund.get("Veckodag", ""),
        "Scen":        _safe_int(grund.get("Scen"), 0),

        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,

        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _ms_from_seconds(tid_alskar_sec),
        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _ms_from_seconds(tid_sover_sec),

        "Summa tid": summa_tid_label,
        "Summa tid (sek)": int(summa_tid_sec),

        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": tid_per_kille_label,

        "Klockan": klockan,
        "Älskar": alskar,
        "Sover med": sover_med,

        "Känner": kanner,
        "Pappans vänner": pappan, "Grannar": grann, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bek, "Eskilstuna killar": esk,

        "Bonus killar": bonus_killar,
        "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": pers_deltagit,

        "Totalt Män": int(totalt_man),
        "Tid kille": tid_per_kille_label,   # (legacy-fält i databasen)

        "Nils": nils,

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_label,

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Hårdhet": int(hardhet),
        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        "Känner Sammanlagt": int(kanner_sammanlagt),

        # Extra som kan vara användbart i live:
        "Ålder": int(alder),
    }

    return out
