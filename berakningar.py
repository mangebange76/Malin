# berakningar.py
from datetime import datetime, date, time, timedelta

# -----------------------------
# Hjälpfunktioner
# -----------------------------

def _mmss(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds)))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(total_seconds: float) -> str:
    try:
        s = max(0, int(round(total_seconds)))
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _as_date(d):
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d).date()
        except Exception:
            return date.today()
    return date.today()

def _as_time(t):
    if isinstance(t, time):
        return t
    if isinstance(t, str):
        try:
            hh, mm = [int(x) for x in t.split(":")[:2]]
            return time(hh, mm)
        except Exception:
            return time(7, 0)
    return time(7, 0)

# -----------------------------
# Huvudberäkning
# -----------------------------

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar alla beräknade fält för liven och sparraden.

    Nyckelpunkter:
    - Känner (rad) = Pappans vänner + Grannar + Nils vänner + Nils familj
      (accepterar både standardnamn och dina LBL_etiketter som kolumnnamn).
    - Totalt Män (rad) = Män + Känner + Svarta + Bekanta + Eskilstuna killar + Bonus deltagit + Personal deltagit
    - Summa S (sek)  = Tid S * (Fitta + Rumpa) + (DT tid * Totalt Män)
    - Summa D (sek)  = Tid D * (DP + DPP + DAP)
    - Summa TP (sek) = Tid D * TAP
    - Summa tid (sek) = S + D + TP
    - Hångel per kille: 10800 / (Män + Svarta + Bekanta + Eskilstuna + Bonus + Personal)  (Känner ingår inte)
    - Suger per kille (sek) = 0.8*(S/tot) + 0.8*(D/tot) + 0.8*(TP/tot)
    - Händer per kille (sek) = 2 * Suger per kille om "Händer aktiv" = 1, annars 0
    - Tid per kille (sek) = (S + 2*D + 3*TP)/tot  **+ Händer per kille (sek)**  (inkluderad)
    - Hårdhet = (DP>0)*3 + (DPP>0)*5 + (DAP>0)*7 + (TAP>0)*9
                + T(Män>100)*1 + T(>200)*2 + T(>400)*4 + T(>700)*7 + T(>1000)*10
                + (Svarta>0)*3
      (Men sätts till 0 om scenariot är "Vila ...")
    - Prenumeranter = (DP + DPP + DAP + TAP + Totalt Män) * Hårdhet
    - Intäkter       = Prenumeranter * Avgift (USD)
    - Kostnad män    = (Summa tid i timmar) * ((Män + Svarta + Bekanta + Eskilstuna killar) + PROD_STAFF) * 15 USD
                       (OBS: Exkluderar Känner/Bonus deltagit/Personal deltagit)
    - Intäkt Känner  = Känner (rad) * 30 USD
    - Intäkt företag = Intäkter - Kostnad män - Intäkt Känner
    - Lön Malin      = clamp(0.08 * Intäkt företag, 150, 800) * åldersfaktor
      Åldersfaktor: 18:100%, 19–23:90%, 24–27:85%, 28–30:80%, 31–32:75%, 33–35:70%, 36–:60%
    - Vinst          = Intäkt företag - Lön Malin
    - Klockan        = start + 3h + 1h + Summa tid (sek)
      Klockan inkl   = ovan + (Älskar + Sover med) * 20 min * 60
    """

    # --- Hämta siffror ---
    # Grundantal
    man    = _safe_int(grund.get("Män", 0))
    svarta = _safe_int(grund.get("Svarta", 0))
    fitta  = _safe_int(grund.get("Fitta", 0))
    rumpa  = _safe_int(grund.get("Rumpa", 0))
    dp     = _safe_int(grund.get("DP", 0))
    dpp    = _safe_int(grund.get("DPP", 0))
    dap    = _safe_int(grund.get("DAP", 0))
    tap    = _safe_int(grund.get("TAP", 0))

    # Etikettstöd (tillåt kolumnnamn via LBL_*), fall tillbaka till standardnamn
    pappan = _safe_int(grund.get("Pappans vänner", grund.get(grund.get("LBL_PAPPAN","Pappans vänner"), 0)))
    grann  = _safe_int(grund.get("Grannar",        grund.get(grund.get("LBL_GRANNAR","Grannar"), 0)))
    nv     = _safe_int(grund.get("Nils vänner",    grund.get(grund.get("LBL_NILS_VANNER","Nils vänner"), 0)))
    nf     = _safe_int(grund.get("Nils familj",    grund.get(grund.get("LBL_NILS_FAMILJ","Nils familj"), 0)))
    bek    = _safe_int(grund.get("Bekanta",        grund.get(grund.get("LBL_BEKANTA","Bekanta"), 0)))
    esk    = _safe_int(grund.get("Eskilstuna killar", grund.get(grund.get("LBL_ESK","Eskilstuna killar"), 0)))

    bonus_d = _safe_int(grund.get("Bonus deltagit", 0))
    pers_d  = _safe_int(grund.get("Personal deltagit", 0))

    alskar  = _safe_int(grund.get("Älskar", 0))
    sover   = _safe_int(grund.get("Sover med", 0))

    hander_on = _safe_int(grund.get("Händer aktiv", grund.get("Hander aktiv", 1)))

    # Tider (sek)
    tid_s  = _safe_int(grund.get("Tid S", 0))
    tid_d  = _safe_int(grund.get("Tid D", 0))
    dt_tid = _safe_int(grund.get("DT tid (sek/kille)", 0))
    # dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # ej i bruk just nu

    # Metadata
    avgift      = _safe_float(grund.get("Avgift", 0.0))
    prod_staff  = _safe_int(grund.get("PROD_STAFF", 0))
    scenario    = str(grund.get("Typ", "")).strip()

    datum_str = grund.get("Datum", "")
    veckodag  = grund.get("Veckodag", "")

    # Känner sammanlagt för statistik (om MAX_ kommer med)
    max_p = _safe_int(grund.get("MAX_PAPPAN", 0))
    max_g = _safe_int(grund.get("MAX_GRANNAR", 0))
    max_nv= _safe_int(grund.get("MAX_NILS_VANNER", 0))
    max_nf= _safe_int(grund.get("MAX_NILS_FAMILJ", 0))
    kanner_sammanlagt = max_p + max_g + max_nv + max_nf

    # --- Beräkna Känner & Totalt Män ---
    kanner = pappan + grann + nv + nf

    totalt_man = man + kanner + svarta + bek + esk + bonus_d + pers_d
    if totalt_man < 0:
        totalt_man = 0

    # --- Summa S/D/TP/Total ---
    summa_s  = tid_s * (fitta + rumpa) + (dt_tid * totalt_man)
    summa_d  = tid_d * (dp + dpp + dap)
    summa_tp = tid_d * tap
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp)

    # --- Hångel per kille ---
    tot_for_hang = man + svarta + bek + esk + bonus_d + pers_d  # Känner ingår inte
    hang_pk = 0.0 if tot_for_hang <= 0 else 10800.0 / float(tot_for_hang)  # 3h = 10800s

    # --- Suger/Händer per kille enligt nya regler ---
    if totalt_man > 0:
        suger_pk = 0.8 * (summa_s / totalt_man) + 0.8 * (summa_d / totalt_man) + 0.8 * (summa_tp / totalt_man)
    else:
        suger_pk = 0.0
    hander_pk = 2.0 * suger_pk if hander_on else 0.0

    # --- Tid per kille (sek) inkl. händer ---
    if totalt_man > 0:
        tpk_base = (summa_s + 2 * summa_d + 3 * summa_tp) / float(totalt_man)
    else:
        tpk_base = 0.0
    tid_per_kille_sek = tpk_base + hander_pk

    # --- Älskar/Sover med (sek) ---
    tid_alskar_sek = (alskar + sover) * 20 * 60  # 20 min per person

    # --- Klockan ---
    try:
        rd = _as_date(rad_datum)
        stt = _as_time(starttid)
        base_dt = datetime.combine(rd, stt)
        klockan_dt  = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek)
        klockan2_dt = base_dt + timedelta(hours=3) + timedelta(hours=1) + timedelta(seconds=summa_tid_sek + tid_alskar_sek)
        klockan_str  = klockan_dt.strftime("%H:%M")
        klockan2_str = klockan2_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"
        klockan2_str = "-"

    # --- Hårdhet ---
    hardhet = 0
    if dp   > 0: hardhet += 3
    if dpp  > 0: hardhet += 5
    if dap  > 0: hardhet += 7
    if tap  > 0: hardhet += 9
    if svarta > 0: hardhet += 3
    for thr, add in [(100,1),(200,2),(400,4),(700,7),(1000,10)]:
        if totalt_man > thr:
            hardhet += add

    # 'Vila' ska inte generera ekonomi/hårdhet
    is_vila = scenario.startswith("Vila")
    if is_vila:
        hardhet = 0

    # --- Prenumeranter ---
    pren = int((dp + dpp + dap + tap + totalt_man) * hardhet) if hardhet > 0 else 0
    if is_vila:
        pren = 0

    # --- Intäkter ---
    intakter = float(pren) * float(avgift)
    if is_vila:
        intakter = 0.0

    # --- Kostnad män ---
    timmar = float(summa_tid_sek) / 3600.0
    kostnad_man = timmar * ((man + svarta + bek + esk) + prod_staff) * 15.0
    if is_vila:
        kostnad_man = 0.0

    # --- Intäkt Känner ---
    intakt_kanner = float(kanner) * 30.0
    if is_vila:
        intakt_kanner = 0.0

    # --- Intäkt företag ---
    intakt_foretag = float(intakter) - float(kostnad_man) - float(intakt_kanner)
    if is_vila:
        intakt_foretag = 0.0

    # --- Lön Malin ---
    # Bas = 8% av intäkt företag, clamp 150..800, därefter åldersfaktor
    fd = _as_date(fodelsedatum)
    alder = rd.year - fd.year - ((rd.month, rd.day) < (fd.month, fd.day))
    base_lon = 0.08 * float(intakt_foretag)
    if base_lon < 150.0: base_lon = 150.0
    if base_lon > 800.0: base_lon = 800.0

    if alder <= 18:
        faktor = 1.00
    elif 19 <= alder <= 23:
        faktor = 0.90
    elif 24 <= alder <= 27:
        faktor = 0.85
    elif 28 <= alder <= 30:
        faktor = 0.80
    elif 31 <= alder <= 32:
        faktor = 0.75
    elif 33 <= alder <= 35:
        faktor = 0.70
    else:
        faktor = 0.60

    lon_malin = base_lon * faktor
    if is_vila:
        lon_malin = 0.0

    # --- Vinst ---
    vinst = float(intakt_foretag) - float(lon_malin)
    if is_vila:
        vinst = 0.0

    # -----------------------------
    #   Packa resultat
    # -----------------------------
    out = {}

    # Bas-info
    out["Datum"] = datum_str if datum_str else (rd.isoformat() if hasattr(rd, "isoformat") else "")
    out["Veckodag"] = veckodag

    # Volymer
    out["Totalt Män"] = int(totalt_man)
    out["Känner"] = int(kanner)
    out["Känner sammanlagt"] = int(kanner_sammanlagt)

    # Tider (sek)
    out["Summa S (sek)"]  = int(summa_s)
    out["Summa D (sek)"]  = int(summa_d)
    out["Summa TP (sek)"] = int(summa_tp)
    out["Summa tid (sek)"] = int(summa_tid_sek)
    out["Summa tid"]       = _hhmm(summa_tid_sek)

    # Per-kille (inkl händer)
    out["Tid per kille (sek)"] = float(tid_per_kille_sek)
    out["Tid per kille"]       = _mmss(tid_per_kille_sek)

    # Hångel / Suger / Händer
    out["Hångel (sek/kille)"]  = float(hang_pk)
    out["Hångel (m:s/kille)"]  = _mmss(hang_pk)
    out["Suger per kille (sek)"]  = float(suger_pk)
    out["Händer per kille (sek)"] = float(hander_pk)
    out["Händer aktiv"] = int(1 if hander_on else 0)

    # Behåll kompatibelt totalfält ”Suger” som summa tid i sek
    out["Suger"] = int(summa_tid_sek)

    # Älskar / Klocka
    out["Tid Älskar (sek)"] = int(tid_alskar_sek)
    out["Klockan"] = klockan_str
    out["Klockan inkl älskar/sover"] = klockan2_str

    # Ekonomi
    out["Prenumeranter"]   = int(pren)
    out["Hårdhet"]         = int(hardhet)
    out["Intäkter"]        = float(intakter)
    out["Intäkt Känner"]   = float(intakt_kanner)
    out["Kostnad män"]     = float(kostnad_man)
    out["Intäkt företag"]  = float(intakt_foretag)
    out["Lön Malin"]       = float(lon_malin)
    out["Vinst"]           = float(vinst)

    return out
