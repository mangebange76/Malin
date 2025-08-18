from datetime import datetime, timedelta, date, time

# -------------------- Små helpers --------------------
def _safe_int(x, default=0):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default

def _fmt_hms_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = (q_sec % 3600) // 60
    return f"{int(h)}h {int(m)} min"

def _fmt_ms_from_seconds(q_sec: int) -> str:
    m = q_sec // 60
    s = q_sec % 60
    return f"{int(m)}m {int(s)}s"

def _clock_from_start(start_t: time, add_seconds: int) -> str:
    zero = datetime.combine(date.today(), start_t)
    done = zero + timedelta(seconds=add_seconds)
    return done.strftime("%H:%M")

def _age_at(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


# =====================================================
# ===============  Huvudberäkning  ====================
# =====================================================
def berakna_radvarden(grund: dict, rad_datum: date, malin_fodelsedatum: date, starttid: time) -> dict:
    """
    Tar 'grund' med alla inmatningsfält (värden i sek/antal), samt radens datum,
    Malins födelsedatum och starttid. Returnerar en dict med alla kolumnvärden.
    Inga I/O eller sheets-anrop sker här.
    """

    # ----------- Läs in alla fält (säker konvertering) -----------
    man    = _safe_int(grund.get("Män", 0))
    svarta = _safe_int(grund.get("Svarta", 0))
    fitta  = _safe_int(grund.get("Fitta", 0))
    rumpa  = _safe_int(grund.get("Rumpa", 0))
    dp     = _safe_int(grund.get("DP", 0))
    dpp    = _safe_int(grund.get("DPP", 0))
    dap    = _safe_int(grund.get("DAP", 0))
    tap    = _safe_int(grund.get("TAP", 0))

    tid_s  = _safe_int(grund.get("Tid S", 0))             # sek
    tid_d  = _safe_int(grund.get("Tid D", 0))             # sek
    vila   = _safe_int(grund.get("Vila", 0))              # sek
    dt_tid = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila= _safe_int(grund.get("DT vila (sek/kille)", 0))

    alskar = _safe_int(grund.get("Älskar", 0))
    sover  = _safe_int(grund.get("Sover med", 0))

    pv  = _safe_int(grund.get("Pappans vänner", 0))
    gr  = _safe_int(grund.get("Grannar", 0))
    nv  = _safe_int(grund.get("Nils vänner", 0))
    nf  = _safe_int(grund.get("Nils familj", 0))
    bk  = _safe_int(grund.get("Bekanta", 0))
    esk = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_killar   = _safe_int(grund.get("Bonus killar", 0))
    bonus_deltagit = grund.get("Bonus deltagit", None)
    if bonus_deltagit is None or str(bonus_deltagit).strip() == "":
        # fallback: 40% av bonus-killar om inte angivet
        bonus_deltagit = int(round(bonus_killar * 0.40))
    else:
        bonus_deltagit = _safe_int(bonus_deltagit, 0)

    personal_deltagit = _safe_int(grund.get("Personal deltagit", 0))
    nils  = _safe_int(grund.get("Nils", 0))

    avgift = _safe_float(grund.get("Avgift", 30.0))
    typ    = str(grund.get("Typ") or "").strip()

    # Totala personalstyrkan för lönekostnad (fast)
    prod_staff_total = _safe_int(grund.get("_PROD_STAFF_TOTAL", 800))

    # ----------- Härleda "Känner" & Totalt män (raden) -----------
    kanner = pv + gr + nv + nf

    # Totalt män på radnivå – används i många delar
    tot_man = (
        man + kanner + svarta + bk + esk + bonus_deltagit + personal_deltagit
    )

    # ----------- Summa S / D / TP / Vila -------------------------
    # Summa S: Tid S * (Fitta + Rumpa) + DT tid * Totalt män
    summa_s = tid_s * (fitta + rumpa) + dt_tid * tot_man

    # Summa D: Tid D * (DP + DPP + DAP)
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP: Tid S * TAP
    summa_tp = tid_s * tap

    # Summa Vila: Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila * Totalt män
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * tot_man

    # ----------- Älskar / Sover — endast för klocka & egna kolumner --------
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover  * 20 * 60

    # ----------- Summa tid (sek) — exkl. älskar & sover -----------
    summa_tid_sec = int(summa_s + summa_d + summa_tp + summa_vila)
    summa_tid_lbl = _fmt_hms_from_seconds(summa_tid_sec)

    # ----------- Klockan: start + arbetstid + 4h buffert + älskar/sover ----
    # Spec: Klockan = summa tid + 3h + 1h + älskar tid + sover tid
    clock_total_sec = summa_tid_sec + (4 * 3600) + alskar_sec + sover_sec
    klockan = _clock_from_start(starttid, clock_total_sec)

    # ----------- Hångel (sek/kille & m:s/kille) -------------------
    denom_hangel = max(1, man + svarta + bk + esk + bonus_deltagit + personal_deltagit)
    hangel_per_kille_sec = int(round((3 * 3600) / denom_hangel))
    hangel_per_kille_lbl = _fmt_ms_from_seconds(hangel_per_kille_sec)

    # ----------- Suger (60% av scenens aktiva tid) ----------------
    suger_total_sec = int(round(summa_tid_sec * 0.60))
    suger_per_kille_sec = int(round(suger_total_sec / max(1, tot_man)))

    # ----------- Tid per kille (sek) -------------------------------
    # tpk = (S/men) + (D/men)*2 + (TP/men)*3 + (suger_total/men) + DT_tid_per_kille
    if tot_man > 0:
        tpk_sec = (
            (summa_s / tot_man)
            + (summa_d / tot_man) * 2
            + (summa_tp / tot_man) * 3
            + (suger_total_sec / tot_man)
            + dt_tid
        )
    else:
        tpk_sec = 0
    tpk_sec = int(round(tpk_sec))
    tpk_lbl = _fmt_ms_from_seconds(tpk_sec)

    # ----------- Hårdhet ------------------------------------------
    hardness = 0
    if dp  > 0: hardness += 3
    if dpp > 0: hardness += 5
    if dap > 0: hardness += 7
    if tap > 0: hardness += 9

    if tot_man > 1000:
        hardness += 10
    elif tot_man >= 500:
        hardness += 6
    elif tot_man >= 300:
        hardness += 5
    elif tot_man > 200:
        hardness += 3
    elif tot_man > 100:
        hardness += 1

    if svarta > 0:
        hardness += 3

    # ----------- Prenumeranter & Intäkter -------------------------
    pren = int(round((fitta + rumpa + dp + dpp + dap + tap + tot_man) * hardness))
    intakter = float(pren) * float(avgift)

    # ----------- Utgift män (ersätter "Intäkt män") ---------------
    # Lön för: Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + HELA personalstyrkan
    # * (arbetstid i timmar) * 15 USD
    person_count_for_wage = (man + svarta + bk + esk + bonus_deltagit + prod_staff_total)
    arbetstid_timmar = summa_tid_sec / 3600.0
    utgift_man = person_count_for_wage * arbetstid_timmar * 15.0

    # ----------- Lön Malin ---------------------------------------
    # 8% av (Intäkter - Utgift män), men minst 150 och max 800
    malin_base = (intakter - utgift_man) * 0.08
    lon_malin = max(150.0, min(800.0, malin_base))

    # ----------- Intäkt Känner -----------------------------------
    intakt_kanner = (summa_tid_sec / 3600.0) * 35.0 * kanner

    # ----------- Vinst -------------------------------------------
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # ----------- Datum/ålder -------------------------------------
    alder = _age_at(rad_datum, malin_fodelsedatum)

    # ----------- Returnera alla kolumners värden -----------------
    out = {
        # Bas
        "Typ": typ,
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),
        "Datum": rad_datum.isoformat(),

        # Inmatningar
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "DT tid (sek/kille)": dt_tid, "DT vila (sek/kille)": dt_vila,
        "Älskar": alskar, "Sover med": sover,

        "Pappans vänner": pv, "Grannar": gr, "Nils vänner": nv, "Nils familj": nf,
        "Bekanta": bk, "Eskilstuna killar": esk,
        "Bonus killar": bonus_killar, "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,
        "Nils": nils,

        # Härledda
        "Känner": kanner,
        "Totalt Män": tot_man,

        # Summeringar & tider
        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": _fmt_ms_from_seconds(int(alskar_sec)),

        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": _fmt_ms_from_seconds(int(sover_sec)),

        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": summa_tid_lbl,

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tpk_lbl,

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_per_kille_lbl,

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        # Ekonomi
        "Hårdhet": int(hardness),
        "Prenumeranter": int(pren),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # Övrigt
        "Klockan": klockan,
        "Ålder": int(alder),

        # Legacy-kolumn som ibland efterfrågas:
        "Tid kille": tpk_lbl,
        # Sammanlagt (om ni använder den senare)
        "Känner Sammanlagt": "",  # lämnas tom här; kan fyllas i statistik om ni behöver
    }

    return out
