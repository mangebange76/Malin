# berakningar.py — DEL 1/3
from datetime import datetime, date, time, timedelta

# ====================== Småhjälpare ======================
def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default

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

def _time_add(base_t: time, seconds: int) -> time:
    # lägg sekunder på en klocktid (ingen datumspill över behövs här)
    dt = datetime.combine(date.today(), base_t) + timedelta(seconds=seconds)
    return dt.time()

# berakningar.py — DEL 2/3

def _rakna_hardhet(dp, dpp, dap, tap, tot_man, svarta):
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    # Mängd män (kumulativa trösklar enligt specifikationen)
    if tot_man > 100:  hardhet += 1
    if tot_man > 200:  hardhet += 3
    if tot_man >= 300: hardhet += 5
    if tot_man >= 500: hardhet += 6
    if tot_man >= 1000: hardhet += 10
    # Svarta > 0 ger +3
    if svarta > 0: hardhet += 3
    return hardhet

def _kanner_rad(pappan, grannar, nils_v, nils_f):
    return max(0, pappan) + max(0, grannar) + max(0, nils_v) + max(0, nils_f)

def _kanner_totalt_from_settings(cfg):
    # "Känner totalt" = summan från sidopanel (max) enligt instruktion
    # Om något saknas, anta 0
    keys = ["MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ"]
    return sum(int(float(cfg.get(k, 0) or 0)) for k in keys)

def _totalt_man(rad_kanner, man, svarta, bekanta, eskilstuna, bonus_deltagit, personal_deltagit):
    # Totalt Män (raden) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit
    return max(0, man) + max(0, rad_kanner) + max(0, svarta) + max(0, bekanta) + max(0, eskilstuna) + max(0, bonus_deltagit) + max(0, personal_deltagit)

def _summa_block(grund, tot_man):
    """
    Summa S = Tid S * (Fitta + Rumpa) + (DT tid per kille * Totalt män)
    Summa D = Tid D * (DP + DPP + DAP)
    Summa TP = Tid S * TAP
    Summa Vila = Vila * (Fitta+Rumpa+DP+DPP+DAP+TAP) + (DT vila per kille * Totalt män)
    (Alla tider i sekunder)
    """
    tid_s   = _safe_int(grund.get("Tid S", 0))
    tid_d   = _safe_int(grund.get("Tid D", 0))
    vila    = _safe_int(grund.get("Vila", 0))
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))

    fitta = _safe_int(grund.get("Fitta", 0))
    rumpa = _safe_int(grund.get("Rumpa", 0))
    dp    = _safe_int(grund.get("DP", 0))
    dpp   = _safe_int(grund.get("DPP", 0))
    dap   = _safe_int(grund.get("DAP", 0))
    tap   = _safe_int(grund.get("TAP", 0))

    summa_s   = tid_s * (fitta + rumpa) + (dt_tid * max(0, tot_man))
    summa_d   = tid_d * (dp + dpp + dap)
    summa_tp  = tid_s * tap
    summa_v   = vila  * (fitta + rumpa + dp + dpp + dap + tap) + (dt_vila * max(0, tot_man))

    return int(summa_s), int(summa_d), int(summa_tp), int(summa_v)

def _suger_secs(summa_tid_sec):
    # 60% av totala scensekunder
    return int(round(0.60 * max(0, summa_tid_sec)))

def _tid_per_kille_secs(summa_s, summa_d, summa_tp, tot_man, suger_total_secs):
    if tot_man <= 0:
        return 0
    # Enligt specifikationen för "Tid kille":
    #  (Summa S / tot) + (Summa D / tot) * 2 + (Summa TP / tot) * 3 + (Suger_total / tot)
    # (DT per kille ingår redan i Summa S/Vila och adderas alltså inte en gång till)
    base = (summa_s / tot_man) + (summa_d / tot_man) * 2 + (summa_tp / tot_man) * 3 + (suger_total_secs / tot_man)
    return int(round(base))

def _alder_for_datum(rad_datum: date, fodelse: date) -> int:
    return rad_datum.year - fodelse.year - ((rad_datum.month, rad_datum.day) < (fodelse.month, fodelse.day))

def _klockan_str(starttid: time, summa_tid_sec: int, alskar_sec: int, sover_sec: int):
    # Klockan = start + summa_tid + 3h + 1h + älskar tid + sover tid
    extra = (3 + 1) * 3600  # 3h + 1h
    tot_secs = max(0, summa_tid_sec) + extra + max(0, alskar_sec) + max(0, sover_sec)
    t = _time_add(starttid, tot_secs)
    return t.strftime("%H:%M")

# berakningar.py — DEL 3/3

def berakna_radvarden(grund: dict, rad_datum: date, fodelsedatum: date, starttid: time, cfg: dict|None=None):
    """
    Returnerar en dict med ALLA uträknade fält för en rad.
    - grund: indatafält (i samma namn som appen skickar)
    - rad_datum: datum för raden
    - fodelsedatum: Malins födelsedatum
    - starttid: starttid (time)
    - cfg: valfritt settings-objekt (för "PROD_STAFF" mm). Kan vara None.
    """
    cfg = cfg or {}
    # --------------- Läs in värden ---------------
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    bekanta = _safe_int(grund.get("Bekanta", 0))
    esk     = _safe_int(grund.get("Eskilstuna killar", 0))
    bonus_deltagit = _safe_int(grund.get("Bonus deltagit", 0))
    personal_deltagit = _safe_int(grund.get("Personal deltagit", 0))
    avgift  = _safe_float(grund.get("Avgift", 30.0))

    # Känner (radvärde) och "Känner Sammanlagt" (från sidopanel)
    pappan = _safe_int(grund.get("Pappans vänner", 0))
    grann  = _safe_int(grund.get("Grannar", 0))
    nilsv  = _safe_int(grund.get("Nils vänner", 0))
    nilsf  = _safe_int(grund.get("Nils familj", 0))
    kanner_rad = _kanner_rad(pappan, grann, nilsv, nilsf)
    kanner_totalt = _kanner_totalt_from_settings(cfg)

    # --------------- Totalt män ---------------
    tot_man = _totalt_man(kanner_rad, man, svarta, bekanta, esk, bonus_deltagit, personal_deltagit)

    # --------------- Summa block + total scen-tid (sek) ---------------
    summa_s, summa_d, summa_tp, summa_v = _summa_block(grund, tot_man)
    summa_tid_sec = max(0, summa_s + summa_d + summa_tp + summa_v)

    # --------------- Älskar / Sover med — sek & visning ---------------
    alskar_cnt = _safe_int(grund.get("Älskar", 0))
    sover_cnt  = _safe_int(grund.get("Sover med", 0))
    alskar_sec = alskar_cnt * 20 * 60
    sover_sec  = sover_cnt  * 20 * 60

    # --------------- Suger ---------------
    suger_total = _suger_secs(summa_tid_sec)
    suger_per_kille = int(round(suger_total / tot_man)) if tot_man > 0 else 0

    # --------------- Tid per kille ---------------
    tid_per_kille_sec = _tid_per_kille_secs(summa_s, summa_d, summa_tp, tot_man, suger_total)

    # --------------- Hångel (3h / tot_man) – bara visning ---------------
    hangel_per_kille_sec = int(round((3 * 3600) / tot_man)) if tot_man > 0 else 0

    # --------------- Hårdhet & Prenumeranter ---------------
    dp  = _safe_int(grund.get("DP", 0))
    dpp = _safe_int(grund.get("DPP", 0))
    dap = _safe_int(grund.get("DAP", 0))
    tap = _safe_int(grund.get("TAP", 0))
    fitta = _safe_int(grund.get("Fitta", 0))
    rumpa = _safe_int(grund.get("Rumpa", 0))

    hardhet = _rakna_hardhet(dp, dpp, dap, tap, tot_man, svarta)
    pren_bas = fitta + rumpa + dp + dpp + dap + tap + tot_man
    prenumeranter = int(max(0, pren_bas * hardhet))

    # --------------- Intäkter / Kostnader / Vinst ---------------
    # Intäkter = Prenumeranter * Avgift
    intakter = float(prenumeranter) * float(avgift)

    # Utgift män = (Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + ALL PERSONAL) * (Summa tid i timmar) * $15
    prod_staff_all = _safe_int(cfg.get("PROD_STAFF", 0))
    antal_betalda = max(0, man) + max(0, svarta) + max(0, bekanta) + max(0, esk) + max(0, bonus_deltagit) + max(0, prod_staff_all)
    timmar = summa_tid_sec / 3600.0
    utgift_man = float(antal_betalda) * float(timmar) * 15.0

    # Intäkt Känner = summa tid (timmar) * $35 * antal känner (rad)
    intakt_kanner = float(timmar) * 35.0 * float(kanner_rad)

    # Lön Malin = 8% av (Intäkter - Utgift män), min $150, max $800
    lon_malin = max(150.0, min(800.0, 0.08 * max(0.0, (intakter - utgift_man))))

    # Vinst = Intäkter - (utgift män + intäkt Känner + lön Malin)
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # --------------- Klockan & ålder ---------------
    alder = _alder_for_datum(rad_datum, fodelsedatum)
    klockan = _klockan_str(starttid, summa_tid_sec, alskar_sec, sover_sec)

    # --------------- Returnera alla fält ---------------
    out = {
        # metadata
        "Typ": grund.get("Typ", ""),
        "Veckodag": grund.get("Veckodag", ""),
        "Scen": grund.get("Scen", ""),
        # indata (normaliserade)
        "Män": man, "Svarta": svarta, "Fitta": fitta, "Rumpa": rumpa, "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": _safe_int(grund.get("Tid S", 0)),
        "Tid D": _safe_int(grund.get("Tid D", 0)),
        "Vila": _safe_int(grund.get("Vila", 0)),
        "DT tid (sek/kille)": _safe_int(grund.get("DT tid (sek/kille)", 0)),
        "DT vila (sek/kille)": _safe_int(grund.get("DT vila (sek/kille)", 0)),
        "Älskar": alskar_cnt, "Sover med": sover_cnt,
        "Pappans vänner": pappan, "Grannar": grann, "Nils vänner": nilsv, "Nils familj": nilsf,
        "Bekanta": bekanta, "Eskilstuna killar": esk,
        "Bonus killar": _safe_int(grund.get("Bonus killar", 0)),
        "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,
        "Nils": _safe_int(grund.get("Nils", 0)),
        # summerat
        "Känner": kanner_rad,
        "Känner Sammanlagt": kanner_totalt,
        "Totalt Män": tot_man,
        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_v),
        "Summa tid (sek)": int(summa_tid_sec),
        "Summa tid": _hm_str_from_seconds(int(summa_tid_sec)),
        # älskar/sover visning
        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": _ms_str_from_seconds(int(alskar_sec)),
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": _ms_str_from_seconds(int(sover_sec)),
        # kille-nivå
        "Tid per kille (sek)": int(tid_per_kille_sec),
        "Tid per kille": _ms_str_from_seconds(int(tid_per_kille_sec)),
        "Tid kille": _ms_str_from_seconds(int(tid_per_kille_sec)),
        # suger
        "Suger per kille (sek)": int(suger_per_kille),
        "Suger": _ms_str_from_seconds(int(suger_total)),
        # hångel — visning
        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": _ms_str_from_seconds(int(hangel_per_kille_sec)),
        # ekonomi
        "Hårdhet": int(hardhet),
        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),
        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),
        # tid/klocka
        "Klockan": klockan,
        # datum sätts i appen vid spar: "Datum": rad_datum.isoformat()
    }
    return out
