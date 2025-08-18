# berakningar.py
from datetime import date, time, datetime, timedelta

SEC_PER_MIN = 60
SEC_PER_HOUR = 3600

def _safe_int(x, d=0):
    try:
        if x is None: return d
        s = str(x).strip()
        if s == "": return d
        return int(float(s))
    except Exception:
        return d

def _safe_float(x, d=0.0):
    try:
        if x is None: return d
        s = str(x).strip()
        if s == "": return d
        return float(s)
    except Exception:
        return d

def _fmt_hms_from_seconds(q_sec: int) -> str:
    h = q_sec // SEC_PER_HOUR
    m = round((q_sec % SEC_PER_HOUR) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _fmt_ms_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _clock_string(start_tid: time, add_seconds: int) -> str:
    dt0 = datetime.combine(date.today(), start_tid)
    dt1 = dt0 + timedelta(seconds=max(0, int(add_seconds)))
    return dt1.strftime("%H:%M")

def _hardhet(dp, dpp, dap, tap, tot_man, svarta):
    h = 0
    # penetration-flaggor
    if dp  > 0: h += 3
    if dpp > 0: h += 5
    if dap > 0: h += 7
    if tap > 0: h += 9
    # totals – adderas kumulativt enligt specen
    if tot_man > 100:  h += 1
    if tot_man > 200:  h += 3
    if tot_man >= 300: h += 5
    if tot_man >= 500: h += 6
    if tot_man >= 1000:h += 10
    # svarta
    if svarta > 0: h += 3
    return max(0, h)

def berakna_radvarden(base: dict, rad_datum: date, fod_datum: date, starttid: time) -> dict:
    """
    Returnerar en dict med alla beräknade fält för en rad.
    - Skriver ingenting externt.
    - Använder exakt de definitioner vi har fastslagit.
    """
    # --------- Läs invärden ---------
    man     = _safe_int(base.get("Män", 0))
    svarta  = _safe_int(base.get("Svarta", 0))
    fitta   = _safe_int(base.get("Fitta", 0))
    rumpa   = _safe_int(base.get("Rumpa", 0))
    dp      = _safe_int(base.get("DP", 0))
    dpp     = _safe_int(base.get("DPP", 0))
    dap     = _safe_int(base.get("DAP", 0))
    tap     = _safe_int(base.get("TAP", 0))

    pv      = _safe_int(base.get("Pappans vänner", 0))
    gr      = _safe_int(base.get("Grannar", 0))
    nv      = _safe_int(base.get("Nils vänner", 0))
    nf      = _safe_int(base.get("Nils familj", 0))
    bek     = _safe_int(base.get("Bekanta", 0))
    esk     = _safe_int(base.get("Eskilstuna killar", 0))

    bonus_k = _safe_int(base.get("Bonus killar", 0))
    bonus_d = _safe_int(base.get("Bonus deltagit", 0))
    pers_d  = _safe_int(base.get("Personal deltagit", 0))
    nils    = _safe_int(base.get("Nils", 0))

    tid_s   = _safe_int(base.get("Tid S", 0))
    tid_d   = _safe_int(base.get("Tid D", 0))
    vila    = _safe_int(base.get("Vila", 0))
    dt_tid  = _safe_int(base.get("DT tid (sek/kille)", 60))
    dt_vila = _safe_int(base.get("DT vila (sek/kille)", 3))

    alskar  = _safe_int(base.get("Älskar", 0))
    sover   = _safe_int(base.get("Sover med", 0))
    avgift  = _safe_float(base.get("Avgift", 30.0))

    veckodag = base.get("Veckodag", "")
    scen     = base.get("Scen", "")

    # --------- Härledda basfält ---------
    # Känner (radnivå)
    kanner = pv + gr + nv + nf

    # Totalt Män (rad): Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit + Personal deltagit
    tot_man = (
        man + kanner + svarta + bek + esk + bonus_d + pers_d
    )

    # --------- Summa-block ---------
    # Summa S = Tid S * (Fitta + Rumpa) + DT tid * Totalt män
    summa_s_sec = (tid_s * (fitta + rumpa)) + (dt_tid * tot_man)

    # Summa D = Tid D * (DP + DPP + DAP)
    summa_d_sec = tid_d * (dp + dpp + dap)

    # Summa TP = Tid S * TAP (multipliceras med 3 i "tid per kille"-steget)
    summa_tp_sec = tid_s * tap

    # Summa Vila = Vila * (Fitta+Rumpa+DP+DPP+DAP+TAP) + DT vila * Totalt män
    summa_vila_sec = (vila * (fitta + rumpa + dp + dpp + dap + tap)) + (dt_vila * tot_man)

    # Älskar/Sover – separat, ingår inte i "Summa tid"
    tid_alskar_sec = alskar * 20 * SEC_PER_MIN
    tid_sover_sec  = sover * 20 * SEC_PER_MIN

    # Summa tid (endast scenens "arbetstid", exkl. älskar/sover)
    total_scen_sec = summa_s_sec + summa_d_sec + summa_tp_sec + summa_vila_sec

    # --------- Suger & Hångel ---------
    # Suger = 60% av totala scensekunder
    suger_total_sec = int(round(0.60 * total_scen_sec))
    # Hångel 3 timmar / Totalt män (per kille) — används bara för visning men vi räknar ändå ut kolumnerna
    hangel_per_kille_sec = 0
    if tot_man > 0:
        hangel_per_kille_sec = int(round((3 * SEC_PER_HOUR) / tot_man))

    # --------- Tid per kille ---------
    # (Summa S/tot_man) + (Summa D/tot_man *2) + (Summa TP/tot_man *3) + (Suger/tot_man)
    # OBS: DT tid ligger redan i Summa S; lägg INTE till separat här för att undvika dubbelräkning.
    if tot_man > 0:
        tpk_sec = (
            (summa_s_sec / tot_man)
            + (summa_d_sec / tot_man) * 2
            + (summa_tp_sec / tot_man) * 3
            + (suger_total_sec / tot_man)
        )
    else:
        tpk_sec = 0.0
    tpk_sec_int = int(round(tpk_sec))

    # Suger per kille (sek)
    suger_per_kille_sec = int(round(suger_total_sec / tot_man)) if tot_man > 0 else 0

    # --------- Hårdhet, Prenumeranter, Ekonomi ---------
    h = _hardhet(dp, dpp, dap, tap, tot_man, svarta)

    # Prenumeranter = (Fitta+Rumpa+DP+DPP+DAP+TAP+TotaltMän) * Hårdhet
    pren = int(round((fitta + rumpa + dp + dpp + dap + tap + tot_man) * h))

    # Intäkter (rad) = Prenumeranter * Avgift
    intakter = pren * avgift

    # Utgift män = (Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + PROD_STAFF)
    #               * (Summa tid i timmar) * 15 USD
    # PROD_STAFF matas inte hit – summan "Personal deltagit" ska INTE ingå, utan hela personalstyrkan (PROD_STAFF)
    # hanteras i appen när den kallar hit (via CFG). För att slippa extern beroende tar vi bara det som finns i raden:
    # => här använder vi *inte* pers_d utan förväntar oss att appen lägger till PROD_STAFF i base["PROD_STAFF_COUNT"].
    prod_staff_count = _safe_int(base.get("PROD_STAFF_COUNT", 0))
    tim_scen = total_scen_sec / SEC_PER_HOUR
    utgift_man = (man + svarta + bek + esk + bonus_d + prod_staff_count) * tim_scen * 15.0

    # Intäkt Känner = (Summa tid i timmar) * 35 USD * Känner (rad)
    intakt_kanner = tim_scen * 35.0 * kanner

    # Lön Malin = 8% av (Intäkter - Utgift män), med min 150, max 800
    lon_malin_raw = 0.08 * max(0.0, (intakter - utgift_man))
    lon_malin = max(150.0, min(800.0, lon_malin_raw))

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # --------- Klockan ---------
    # Klockan = starttid + Summa tid + 3h + 1h + tid_alskar + tid_sover
    # (dvs +4 timmar buffert)
    clock_sec_add = total_scen_sec + (4 * SEC_PER_HOUR) + tid_alskar_sec + tid_sover_sec
    klockan = _clock_string(starttid, clock_sec_add)

    # --------- Ålder (för ev. visning/spar) ---------
    alder = rad_datum.year - fod_datum.year - ((rad_datum.month, rad_datum.day) < (fod_datum.month, fod_datum.day))

    # --------- Bygg resultatdict ---------
    out = {}

    # Identity/meta
    out["Datum"] = rad_datum.isoformat()
    out["Veckodag"] = veckodag
    out["Scen"] = scen if scen != "" else base.get("Scen", "")

    # Originalfält (återexponera så appen kan mappa rätt)
    out["Män"] = man
    out["Svarta"] = svarta
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap

    out["Pappans vänner"] = pv
    out["Grannar"] = gr
    out["Nils vänner"] = nv
    out["Nils familj"] = nf
    out["Bekanta"] = bek
    out["Eskilstuna killar"] = esk

    out["Bonus killar"] = bonus_k
    out["Bonus deltagit"] = bonus_d
    out["Personal deltagit"] = pers_d

    out["Älskar"] = alskar
    out["Sover med"] = sover

    out["Tid S"] = tid_s
    out["Tid D"] = tid_d
    out["Vila"]  = vila
    out["DT tid (sek/kille)"]  = dt_tid
    out["DT vila (sek/kille)"] = dt_vila

    out["Avgift"] = avgift
    out["Nils"]   = nils

    # Härledda/summerade
    out["Känner"] = kanner

    out["Summa S"] = int(summa_s_sec)
    out["Summa D"] = int(summa_d_sec)
    out["Summa TP"] = int(summa_tp_sec)
    out["Summa Vila"] = int(summa_vila_sec)

    out["Tid Älskar (sek)"] = int(tid_alskar_sec)
    out["Tid Sover med (sek)"] = int(tid_sover_sec)

    out["Summa tid (sek)"] = int(total_scen_sec)
    out["Summa tid"] = _fmt_hms_from_seconds(int(total_scen_sec))

    out["Totalt Män"] = int(tot_man)

    out["Tid per kille (sek)"] = int(tpk_sec_int)
    out["Tid per kille"] = _fmt_ms_from_seconds(int(tpk_sec_int))

    out["Suger"] = int(suger_total_sec)
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Hångel (sek/kille)"] = int(hangel_per_kille_sec)
    out["Hångel (m:s/kille)"] = _fmt_ms_from_seconds(int(hangel_per_kille_sec)) if hangel_per_kille_sec > 0 else "-"

    out["Hårdhet"] = int(h)

    out["Prenumeranter"] = int(pren)
    out["Intäkter"] = float(intakter)
    out["Utgift män"] = float(utgift_man)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Lön Malin"] = float(lon_malin)
    out["Vinst"] = float(vinst)

    out["Klockan"] = klockan

    # Extra: för live kan det vara trevligt att ha ålder lättåtkomligt
    out["Ålder"] = int(alder)

    # Fält som appens schema kan vilja se (även om ej använda för beräkning)
    out["Tid Älskar"] = _fmt_hms_from_seconds(int(tid_alskar_sec))
    out["Tid Sover med"] = _fmt_hms_from_seconds(int(tid_sover_sec))
    out["Tid kille"] = out["Tid per kille"]  # alias om appen läser detta fält

    return out
