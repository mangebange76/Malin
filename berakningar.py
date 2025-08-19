# berakningar.py
# v1.0 – grundberäkningar enligt senaste överenskommelse

from datetime import timedelta, datetime

def _sec_to_hm_str(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h:d}:{m:02d}"

def _time_to_str(t) -> str:
    # t är ett datetime.time; gör HH:MM
    return f"{t.hour:02d}:{t.minute:02d}"

def _add_seconds_to_time(t, secs: int):
    # t = datetime.time; return ny time efter +secs
    base = datetime(2000,1,1, t.hour, t.minute, t.second)
    new_dt = base + timedelta(seconds=max(0, int(secs)))
    return new_dt.time()

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Förväntar sig att app.py skickar in alla in-nycklar som redan finns i 'grund'.
    Viktigt: gör INGA externa anrop här.
    """

    # ---------- INPUTS ----------
    # Basfält (säkerställ int)
    get = lambda k, d=0: int(grund.get(k, d) or 0)

    man        = get("Män")
    svarta     = get("Svarta")
    fitta      = get("Fitta")
    rumpa      = get("Rumpa")
    dp         = get("DP")
    dpp        = get("DPP")
    dap        = get("DAP")
    tap        = get("TAP")

    tid_s      = get("Tid S")                # sek
    tid_d      = get("Tid D")                # sek
    dt_tid     = get("DT tid (sek/kille)")   # sek/kille

    alskar     = get("Älskar")
    sover_med  = get("Sover med")

    pappan     = get("Pappans vänner")
    grannar    = get("Grannar")
    nils_v     = get("Nils vänner")
    nils_f     = get("Nils familj")
    bekanta    = get("Bekanta")
    esk        = get("Eskilstuna killar")

    bonus_delt = get("Bonus deltagit")
    pers_delt  = get("Personal deltagit")
    nils       = get("Nils")

    avgift     = float(grund.get("Avgift", 0.0) or 0.0)
    prod_staff = int(grund.get("PROD_STAFF", 0) or 0)

    # ---------- KÄNNER ----------
    känner = pappan + grannar + nils_v + nils_f

    # ---------- TOTALT MÄN (radnivå) ----------
    total_man = (
        man + svarta + bekanta + esk + bonus_delt + pers_delt + känner
    )
    if total_man < 0: total_man = 0

    # ---------- SUMMA S / D / TP ----------
    # Summa S = Tid S * (Fitta + Rumpa) + DT_tid * Totalt män
    summa_s_sec  = tid_s * (fitta + rumpa) + dt_tid * total_man

    # Summa D = Tid D * (DP + DPP + DAP)
    summa_d_sec  = tid_d * (dp + dpp + dap)

    # Summa TP = Tid D * TAP
    summa_tp_sec = tid_d * tap

    # Summa tid (sek) = S + D + TP
    summa_tid_sec = summa_s_sec + summa_d_sec + summa_tp_sec
    summa_tid_str = _sec_to_hm_str(summa_tid_sec)

    # ---------- TID PER KILLE ----------
    # Särskild viktning: (S + 2*D + 3*TP) / totalt män
    if total_man > 0:
        tid_per_kille_sec = (summa_s_sec + 2*summa_d_sec + 3*summa_tp_sec) / total_man
        suger_per_kille_sec = summa_tid_sec / total_man
    else:
        tid_per_kille_sec = 0
        suger_per_kille_sec = 0
    tid_per_kille_str = _sec_to_hm_str(int(tid_per_kille_sec))

    # ---------- HÅNGEL ----------
    # 3 timmar totalt → per kille
    HANGEL_TOTAL_SEC = 3 * 3600
    hangel_per_kille_sec = (HANGEL_TOTAL_SEC / total_man) if total_man > 0 else 0
    hangel_per_kille_str = _sec_to_hm_str(int(hangel_per_kille_sec))

    # ---------- SUGER ----------
    suger_total_sec = summa_tid_sec  # enligt spec

    # ---------- KLOCKOR ----------
    # Klockan = starttid + 3h (hångel) + 1h vila + summa_tid
    KLOCKA_EXTRA_VILA_SEC = 3600
    klocka_time = _add_seconds_to_time(
        starttid,
        HANGEL_TOTAL_SEC + KLOCKA_EXTRA_VILA_SEC + int(summa_tid_sec)
    )
    klocka_str = _time_to_str(klocka_time)

    # Klockan inkl älskar & sover med (20 min per person)
    EXTRA_MS_PER_PERSON_SEC = 20 * 60
    extra_asm_sec = EXTRA_MS_PER_PERSON_SEC * (alskar + sover_med)
    klocka_ext_time = _add_seconds_to_time(
        klocka_time,
        int(extra_asm_sec)
    )
    klocka_ext_str = _time_to_str(klocka_ext_time)

    # ---------- ÅLDER ----------
    # Sätt datum/veckodag från grund om de finns
    datum_str   = grund.get("Datum", str(rad_datum))
    veckodag    = grund.get("Veckodag", "")
    fd = fodelsedatum
    _d = rad_datum
    alder = _d.year - fd.year - (( _d.month, _d.day) < (fd.month, fd.day))

    # ---------- OUTPUT ----------
    out = {}

    # meta
    out["Datum"]    = datum_str
    out["Veckodag"] = veckodag

    # summeringar
    out["Känner"]                 = int(känner)
    out["Totalt Män"]            = int(total_man)

    out["Summa S (sek)"]         = int(summa_s_sec)
    out["Summa D (sek)"]         = int(summa_d_sec)
    out["Summa TP (sek)"]        = int(summa_tp_sec)
    out["Summa tid (sek)"]       = int(summa_tid_sec)
    out["Summa tid"]             = summa_tid_str

    out["Tid per kille (sek)"]   = int(tid_per_kille_sec)
    out["Tid per kille"]         = tid_per_kille_str

    out["Hångel (sek/kille)"]    = int(hangel_per_kille_sec)
    out["Hångel (m:s/kille)"]    = hangel_per_kille_str

    out["Suger"]                 = int(suger_total_sec)
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Klockan"]               = klocka_str
    out["Klockan (inkl Älskar & Sover)"] = klocka_ext_str

    # ekonomi – placeholder (0) tills vi sätter formler
    out["Prenumeranter"]         = 0
    out["Intäkter"]              = 0.0
    out["Utgift män"]            = 0.0
    out["Intäkt Känner"]         = 0.0
    out["Lön Malin"]             = 0.0
    out["Intäkt Företaget"]      = 0.0
    out["Vinst"]                 = 0.0
    out["Hårdhet"]               = 0
    out["Känner sammanlagt"]     = 0

    # spegla tillbaka ev. indata som appen vill se i tabellen
    for k in [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","DT tid (sek/kille)","DT vila (sek/kille)",
        "Älskar","Sover med",
        "Pappans vänner","Grannar","Nils vänner","Nils familj",
        "Bekanta","Eskilstuna killar",
        "Bonus deltagit","Personal deltagit","Nils",
        "Avgift","PROD_STAFF"
    ]:
        if k in grund:
            out[k] = grund[k]

    return out
