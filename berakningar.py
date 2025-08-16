# berakningar.py
from datetime import datetime, timedelta

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _safe_int(x, default=0):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _get(row, key, default=0):
    return _safe_int(row.get(key, default), default)

def berakna_radvarden(row: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en dict med alla nycklar som appen förväntar sig i DEFAULT_COLUMNS.
    row: indata från appen (enbart radens fält).
    rad_datum: date
    fodelsedatum: date
    starttid: datetime.time
    """

    # ---- Läs in fält (int) ----
    man      = _get(row, "Män", 0)
    svarta   = _get(row, "Svarta", 0)
    fitta    = _get(row, "Fitta", 0)
    rumpa    = _get(row, "Rumpa", 0)
    dp       = _get(row, "DP", 0)
    dpp      = _get(row, "DPP", 0)
    dap      = _get(row, "DAP", 0)
    tap      = _get(row, "TAP", 0)

    tid_s    = _get(row, "Tid S", 60)
    tid_d    = _get(row, "Tid D", 60)
    vila     = _get(row, "Vila", 7)

    dt_tid   = _get(row, "DT tid (sek/kille)", 60)
    dt_vila  = _get(row, "DT vila (sek/kille)", 3)

    alskar   = _get(row, "Älskar", 0)
    sover    = _get(row, "Sover med", 0)

    pv       = _get(row, "Pappans vänner", 0)
    gr       = _get(row, "Grannar", 0)
    nv       = _get(row, "Nils vänner", 0)
    nf       = _get(row, "Nils familj", 0)
    bekanta  = _get(row, "Bekanta", 0)

    nils     = _get(row, "Nils", 0)

    avgift   = float(row.get("Avgift", 30.0) or 0.0)

    # ---- Deriverade räknare ----
    kanner_total = pv + gr + nv + nf               # "Känner"
    total_killar_for_tid = man + svarta + bekanta + kanner_total  # alla killar som påverkar tid
    total_killar_for_hangel = man + svarta + bekanta              # hångel delar EJ på "känner"
    total_man_kolumn = man + svarta + kanner_total + bekanta      # visas i "Totalt Män"

    # ---- Summa-tider (sek) ----
    # S (singlar): räkna även in "känner" och "bekanta" samt svarta
    summa_s = (man + svarta + bekanta + kanner_total + fitta + rumpa) * tid_s

    # D (dubblar) – här är DP/DPP/DAP rena räkneord multiplicerat med Tid D
    summa_d = (dp + dpp + dap) * tid_d

    # TP (TAP = trippel) multiplicerat med Tid D (som i din bas)
    summa_tp = tap * tid_d

    # Vila: grundvila * alla killar
    summa_vila = vila * max(total_killar_for_tid, 0)

    # DT tillägg
    dt_tid_total  = dt_tid * max(total_killar_for_tid, 0)      # går in i total tid
    dt_vila_total = dt_vila * max(total_killar_for_tid, 0)     # ska in i Summa Vila (inte dubbelt)
    summa_vila += dt_vila_total

    # Extra-tid: älskar & sover med
    tid_alskar_sec = alskar * 30 * 60
    tid_sover_sec  = sover  * 60 * 60

    # Total scen-tid (sek)
    total_sec = (
        summa_s + summa_d + summa_tp + summa_vila +
        tid_alskar_sec + tid_sover_sec +
        dt_tid_total
    )

    # ---- Hångel (3 timmar / (män+svarta+bekanta)) ----
    hangel_tot_sec = 3 * 3600
    if total_killar_for_hangel > 0:
        hangel_per_kille_sec = hangel_tot_sec / total_killar_for_hangel
    else:
        hangel_per_kille_sec = 0
    hangel_label = _ms_str_from_seconds(int(round(hangel_per_kille_sec)))

    # ---- Suger: 60% av (summa_d + summa_tp). Per kille delas på alla killar (inkl. känner & bekanta & svarta). ----
    suger_total_sec = 0.60 * (summa_d + summa_tp)
    if total_killar_for_tid > 0:
        suger_per_kille_sec = suger_total_sec / total_killar_for_tid
    else:
        suger_per_kille_sec = 0

    # ---- Tid per kille (sek): (S+D+TP)/alla + suger_per_kille ----
    if total_killar_for_tid > 0:
        tid_per_kille_sec = ((summa_s + summa_d + summa_tp) / total_killar_for_tid) + suger_per_kille_sec
    else:
        tid_per_kille_sec = 0
    tid_per_kille_label = _ms_str_from_seconds(int(round(tid_per_kille_sec)))

    # ---- “Summa tid” (h:mm) + “Summa tid (sek)” ----
    summa_tid_label = _hm_str_from_seconds(int(round(total_sec)))
    summa_tid_sec   = int(round(total_sec))

    # ---- Klockan (starttid + total tid) ----
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt  = start_dt + timedelta(seconds=total_sec)
    klockan_str = slut_dt.strftime("%H:%M")

    # ---- Hårdhet ----
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3

    # ---- Prenumeranter ----
    pren_bas = (man + (svarta * 2) + fitta + rumpa + dp + dpp + dap + tap + kanner_total + bekanta)
    prenumeranter = int(round(pren_bas * hardhet))

    # ---- Ekonomi ----
    intakter = float(prenumeranter) * float(avgift)

    # Kostnad män: Män + Svarta (ej Känner/Bekanta)
    kostnad_man = (man + svarta) * 120.0

    # Företagets intäkt = 20% av intäkter
    intakt_foretaget = 0.20 * intakter

    # Lön Malin: 10% av intäkter, clampad 150..800
    lon_malin_raw = 0.10 * intakter
    lon_malin = max(150.0, min(800.0, lon_malin_raw))

    # Vinst
    vinst = intakter - kostnad_man - intakt_foretaget - lon_malin

    # ---- Sammanställ rad ----
    out = {}

    # Metadata
    out["Typ"] = row.get("Typ", "").strip()
    out["Veckodag"] = row.get("Veckodag", "")
    out["Scen"] = row.get("Scen", "")

    # Råvärden
    out["Män"] = man
    out["Svarta"] = svarta
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap

    out["Tid S"] = tid_s
    out["Tid D"] = tid_d
    out["Vila"]  = vila
    out["DT tid (sek/kille)"]  = dt_tid
    out["DT vila (sek/kille)"] = dt_vila

    # Tider (sek)
    out["Summa S"] = int(summa_s)
    out["Summa D"] = int(summa_d)
    out["Summa TP"] = int(summa_tp)
    out["Summa Vila"] = int(summa_vila)

    out["Tid Älskar (sek)"] = int(tid_alskar_sec)
    out["Tid Älskar"]       = _hm_str_from_seconds(int(tid_alskar_sec))

    out["Tid Sover med (sek)"] = int(tid_sover_sec)
    out["Tid Sover med"]       = _hm_str_from_seconds(int(tid_sover_sec))

    out["Summa tid"]      = summa_tid_label
    out["Summa tid (sek)"]= int(summa_tid_sec)

    out["Tid per kille (sek)"] = int(round(tid_per_kille_sec))
    out["Tid per kille"]       = tid_per_kille_label

    out["Klockan"] = klockan_str

    # Sociala
    out["Älskar"] = alskar
    out["Sover med"] = sover
    out["Känner"] = kanner_total
    out["Pappans vänner"] = pv
    out["Grannar"] = gr
    out["Nils vänner"] = nv
    out["Nils familj"] = nf
    out["Bekanta"] = bekanta

    out["Totalt Män"] = int(total_man_kolumn)  # män+svarta+känner+bekanta
    out["Tid kille"]  = tid_per_kille_label
    out["Nils"] = nils

    # Hångel
    out["Hångel (sek/kille)"]   = int(round(hangel_per_kille_sec))
    out["Hångel (m:s/kille)"]   = hangel_label

    # Suger
    out["Suger"]                   = int(round(suger_total_sec))
    out["Suger per kille (sek)"]   = int(round(suger_per_kille_sec))

    # Affär
    out["Hårdhet"]        = int(hardhet)
    out["Prenumeranter"]  = int(prenumeranter)
    out["Avgift"]         = float(avgift)
    out["Intäkter"]       = float(intakter)

    out["Intäkt män"]       = float(kostnad_man)         # kostnad
    out["Intäkt Känner"]    = float(0.0)                 # (behövs i statistik-summor; sätt 0 om ej separat modell)
    out["Lön Malin"]        = float(lon_malin)
    out["Intäkt Företaget"] = float(intakt_foretaget)
    out["Vinst"]            = float(vinst)

    out["Känner Sammanlagt"] = int(kanner_total)

    return out
