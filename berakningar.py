# berakningar.py
from datetime import datetime, timedelta

# ================= Hjälpfunktioner =================
def _si(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _hm(sec: int) -> str:
    h = int(sec // 3600)
    m = int(round((sec % 3600) / 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m} min"

def _ms(sec: int) -> str:
    sec = int(sec)
    m = sec // 60
    s = sec % 60
    return f"{m}m {s}s"

def _fmt_clock(start_time, plus_seconds: int) -> str:
    """start_time = datetime.time; return HH:MM efter att vi adderat sekunder."""
    dt0 = datetime(2000, 1, 1, start_time.hour, start_time.minute, start_time.second)
    dt1 = dt0 + timedelta(seconds=plus_seconds)
    return dt1.strftime("%H:%M")

# ============== Huvud: beräkna en rad =================
def berakna_radvarden(grund: dict, rad_datum, fodselsedatum, starttid):
    out = {}

    # -------- Inläsning av värden --------
    man    = _si(grund.get("Män", 0))
    svart  = _si(grund.get("Svarta", 0))
    fitta  = _si(grund.get("Fitta", 0))
    rumpa  = _si(grund.get("Rumpa", 0))
    dp     = _si(grund.get("DP", 0))
    dpp    = _si(grund.get("DPP", 0))
    dap    = _si(grund.get("DAP", 0))
    tap    = _si(grund.get("TAP", 0))

    tid_s  = _si(grund.get("Tid S", 60))   # sek
    tid_d  = _si(grund.get("Tid D", 60))   # sek
    vila   = _si(grund.get("Vila", 7))     # sek, bas (ej DT)
    dt_tid_per  = _si(grund.get("DT tid (sek/kille)", 60))
    dt_vila_per = _si(grund.get("DT vila (sek/kille)", 3))

    alskar    = _si(grund.get("Älskar", 0))
    sover_med = _si(grund.get("Sover med", 0))  # 0/1

    pv = _si(grund.get("Pappans vänner", 0))
    gr = _si(grund.get("Grannar", 0))
    nv = _si(grund.get("Nils vänner", 0))
    nf = _si(grund.get("Nils familj", 0))
    bk = _si(grund.get("Bekanta", 0))  # BETE SIG SOM MÄN (men ej i Känner Sammanlagt)
    esk = _si(grund.get("Eskilstuna killar", 0))  # BETE SIG SOM MÄN (ingen kostnad)

    nils = _si(grund.get("Nils", 0))

    avgift = float(grund.get("Avgift", 30.0) or 30.0)

    # -------- Känner Sammanlagt & Totalt Män --------
    # Bekanta ska *inte* räknas med i Känner Sammanlagt.
    kanner_sammanlagt = pv + gr + nv + nf
    out["Känner Sammanlagt"] = kanner_sammanlagt

    # Totalt-killar som påverkar tid, DT, hångel, suger, prenumeranter m.m.
    totalt_killar = man + svart + bk + esk + kanner_sammanlagt
    out["Totalt Män"] = totalt_killar

    # -------- SUMMOR (S/D/TP/Vila) --------
    # Viktigt: Känner ska räknas in i S/D/TP-summorna.
    # Vi låter S relatera till Fitta, D till Rumpa, TP till TAP (enligt tidigare resonemang).
    # (Modellen kan justeras senare om vi vill väga in dp/dpp/dap i S/D/TP)
    deltagare_s = (fitta + kanner_sammanlagt)
    deltagare_d = (rumpa + kanner_sammanlagt)
    deltagare_tp = (tap + kanner_sammanlagt)

    summa_s_sec  = max(0, tid_s * deltagare_s)
    summa_d_sec  = max(0, tid_d * deltagare_d)
    summa_tp_sec = max(0, tid_s * deltagare_tp)  # använder tid_s som bas även för TP (hållit så i tidigare versioner)

    # Vila: grund-vila + DT-vila
    dt_vila_total = dt_vila_per * totalt_killar
    summa_vila_sec = max(0, vila) + dt_vila_total

    # DT-tid som faktisk "aktiv tid"
    dt_tid_total = dt_tid_per * totalt_killar

    # Älskar/Sover med – tidsadditioner
    tid_alskar_sec = alskar * 1800      # 30 min per älskar
    tid_sover_sec  = sover_med * 3600   # 1h om 1, annars 0

    # Summa tid (sek)
    summa_tid_sec = (
        summa_s_sec
        + summa_d_sec
        + summa_tp_sec
        + dt_tid_total
        + tid_alskar_sec
        + tid_sover_sec
        + summa_vila_sec
    )
    out["Summa S"] = summa_s_sec
    out["Summa D"] = summa_d_sec
    out["Summa TP"] = summa_tp_sec
    out["Summa Vila"] = summa_vila_sec
    out["Summa tid (sek)"] = int(summa_tid_sec)
    out["Summa tid"] = _hm(summa_tid_sec)

    # -------- Klockan --------
    out["Klockan"] = _fmt_clock(starttid, int(summa_tid_sec))

    # -------- Hångel --------
    # 3 timmar som *per kille* (sek/kille) – svarta/bekanta/eskilstuna/känner ingår.
    hangel_per_kille_sec = int((3 * 3600) / totalt_killar) if totalt_killar > 0 else 0
    out["Hångel (sek/kille)"] = hangel_per_kille_sec
    out["Hångel (m:s/kille)"] = _ms(hangel_per_kille_sec)

    # -------- Suger --------
    # 60% av (Summa D + Summa TP); delas på alla killar → läggs på tid per kille.
    suger_total_sec = int(0.6 * (summa_d_sec + summa_tp_sec))
    suger_per_kille_sec = int(suger_total_sec / totalt_killar) if totalt_killar > 0 else 0
    out["Suger"] = suger_total_sec
    out["Suger per kille (sek)"] = suger_per_kille_sec

    # -------- Tid per kille --------
    # Tid per kille = (Summa S / killar) + 2*(Summa D / killar) + 3*(Summa TP / killar)
    # + (DT-tid / killar) + SUGER per kille.
    if totalt_killar > 0:
        tpk_sec = (
            (summa_s_sec / totalt_killar)
            + 2 * (summa_d_sec / totalt_killar)
            + 3 * (summa_tp_sec / totalt_killar)
            + (dt_tid_total / totalt_killar)
            + suger_per_kille_sec
        )
    else:
        tpk_sec = 0

    out["Tid per kille (sek)"] = int(tpk_sec)
    out["Tid per kille"] = _ms(int(tpk_sec))
    out["Tid kille"] = out["Tid per kille"]  # (visuell duplicering från din header)

    # -------- Älskar / Sover med – sparas både sek & label --------
    out["Tid Älskar (sek)"] = int(tid_alskar_sec)
    out["Tid Älskar"] = _hm(int(tid_alskar_sec))
    out["Tid Sover med (sek)"] = int(tid_sover_sec)
    out["Tid Sover med"] = _hm(int(tid_sover_sec))

    # -------- Hårdhet --------
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svart > 0: hardhet += 3  # +3 om svarta > 0
    out["Hårdhet"] = hardhet

    # -------- Prenumeranter --------
    # Pren = (män + (svarta * 2) + bekanta + eskilstuna + fitta + rumpa + dp + dpp + dap + tap + KÄNNER) * hårdhet
    pren_bas = (
        man
        + (svart * 2)      # svarta räknas dubbelt
        + bk               # bekanta beter sig som män
        + esk              # eskilstuna beter sig som män
        + fitta + rumpa + dp + dpp + dap + tap
        + kanner_sammanlagt
    )
    pren = int(pren_bas * hardhet)
    out["Prenumeranter"] = pren

    # -------- Intäkter / kostnader / vinst / lön --------
    intakter = float(pren) * float(avgift)
    out["Avgift"] = float(avgift)
    out["Intäkter"] = float(intakter)

    # Kostnad män (behåll fältet, men 0 tills vi har explicit pris)
    kostnad_man = 0.0
    out["Intäkt män"] = float(kostnad_man)

    # Intäkt Känner = intäkterna (som du använder i statistiken)
    out["Intäkt Känner"] = float(intakter)

    # Intäkt Företaget (0 tills annat beslut)
    out["Intäkt Företaget"] = 0.0

    # Lön Malin = 50% av intäkter (kan ändras enkelt sen)
    lon_malin = float(intakter) * 0.5
    out["Lön Malin"] = float(lon_malin)

    # Vinst = Intäkter - Lön Malin - Kostnad män - Intäkt Företaget
    vinst = float(intakter) - float(lon_malin) - float(kostnad_man) - 0.0
    out["Vinst"] = float(vinst)

    # -------- Återställ övriga fält direkt från indata --------
    out["Typ"] = (grund.get("Typ") or "").strip()
    out["Veckodag"] = grund.get("Veckodag", "")
    out["Scen"] = grund.get("Scen", "")
    out["Män"] = man
    out["Svarta"] = svart
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap
    out["Tid S"] = tid_s
    out["Tid D"] = tid_d
    out["Vila"] = vila
    out["DT tid (sek/kille)"] = dt_tid_per
    out["DT vila (sek/kille)"] = dt_vila_per
    out["Älskar"] = alskar
    out["Sover med"] = sover_med
    out["Känner"] = _si(grund.get("Känner", 0))  # om du matar det separat
    out["Pappans vänner"] = pv
    out["Grannar"] = gr
    out["Nils vänner"] = nv
    out["Nils familj"] = nf
    out["Bekanta"] = bk
    out["Eskilstuna killar"] = esk
    out["Nils"] = nils

    return out
