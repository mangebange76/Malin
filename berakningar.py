from datetime import datetime, timedelta

# --- Hjälpare (egna, så beräkningen kan köras frikopplad från app.py) ---
def _safe_int(x, default=0):
    try:
        if x is None: return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
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

# ----------------------------- Huvudfunktion -----------------------------
def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    g = dict(grund or {})

    # Inmatningar
    man     = _safe_int(g.get("Män", 0))
    svarta  = _safe_int(g.get("Svarta", 0))
    esk     = _safe_int(g.get("Eskilstuna killar", 0))
    bek     = _safe_int(g.get("Bekanta", 0))
    fitta   = _safe_int(g.get("Fitta", 0))
    rumpa   = _safe_int(g.get("Rumpa", 0))
    dp      = _safe_int(g.get("DP", 0))
    dpp     = _safe_int(g.get("DPP", 0))
    dap     = _safe_int(g.get("DAP", 0))
    tap     = _safe_int(g.get("TAP", 0))

    tid_s   = _safe_int(g.get("Tid S", 0))
    tid_d   = _safe_int(g.get("Tid D", 0))
    vila    = _safe_int(g.get("Vila", 0))

    dt_tid  = _safe_int(g.get("DT tid (sek/kille)", 0))
    dt_vila = _safe_int(g.get("DT vila (sek/kille)", 0))

    alskar  = _safe_int(g.get("Älskar", 0))
    sover   = _safe_int(g.get("Sover med", 0))
    kanner  = _safe_int(g.get("Känner", 0))

    pv      = _safe_int(g.get("Pappans vänner", 0))
    gr      = _safe_int(g.get("Grannar", 0))
    nv      = _safe_int(g.get("Nils vänner", 0))
    nf      = _safe_int(g.get("Nils familj", 0))
    nils    = _safe_int(g.get("Nils", 0))

    avgift  = float(g.get("Avgift", 30.0) or 30.0)
    typ     = (g.get("Typ") or "").strip()

    # Total "killar" som påverkar tid/prenumeranter/suger/hångel
    total_killar = max(0, man + svarta + esk + bek)

    # --- Del-summor (enkla antaganden enligt senaste direktiv) ---
    summa_s  = fitta * tid_s                    # Sek totalt för S
    summa_d  = rumpa * tid_d                    # Sek totalt för D
    summa_tp = (dp + dpp + dap + tap) * tid_d   # Sek totalt för TP-block (multiplicerar på samma bas som D)
    summa_vila = vila + (dt_vila * total_killar)

    # Älskar/Sover med som tillägg på klockan (30 min per "älskar", 60 min per sover med)
    tid_alskar_sec = alskar * 30 * 60
    tid_sover_sec  = sover * 60 * 60

    # DT tid total (per kille)
    dt_tid_total = dt_tid * total_killar

    # Summa tid (sek) = S + D + TP + Vila + Älskar + Sover + DT_tid_total
    summa_tid_sec = max(0, summa_s + summa_d + summa_tp + summa_vila + tid_alskar_sec + tid_sover_sec + dt_tid_total)

    # Tid per kille (sek) = (S/killar) + (D/killar)*2 + (TP/killar)*3 + DT_tid (per kille)
    if total_killar > 0:
        tpk_sec = int(round((summa_s/total_killar) + (summa_d/total_killar)*2 + (summa_tp/total_killar)*3 + dt_tid))
    else:
        tpk_sec = 0

    # Hångel: 3 timmar / kille (svarta & bekanta & esk räknas in)
    hangel_per_kille_sec = int(round((3*3600) / total_killar)) if total_killar > 0 else 0

    # Suger: 60% av (D + TP) / kille
    suger_per_kille_sec = int(round(0.60 * (summa_d + summa_tp) / total_killar)) if total_killar > 0 else 0
    suger_total_label = "Ja" if (summa_d + summa_tp) > 0 else "Nej"

    # Hårdhet (DP>0=3, DPP>0=4, DAP>0=6, TAP>0=8) +3 om svarta>0
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3

    # Prenumeranter = (män + esk + bek + svarta*2 + fitta + rumpa + dp + dpp + dap + tap + känner) * hårdhet
    pren_bas = (man + esk + bek + (svarta * 2) + fitta + rumpa + dp + dpp + dap + tap + kanner)
    prenumeranter = max(0, pren_bas * hardhet)

    # Vila-poster ska inte generera prenumeranter/intäkter
    if typ in ("Vila på jobbet", "Vila i hemmet"):
        prenumeranter = 0

    # Intäkter och ekonomi (behåll minimalistiskt enligt senaste fokus)
    intakter = prenumeranter * avgift
    intakt_kanner = 0.0
    intakt_man_kostnad = 0.0  # kostnad hanteras ej nu
    lon_malin = 0.0
    intakt_foretaget = 0.0
    vinst = intakter - intakt_man_kostnad

    # Känner Sammanlagt (för kompatibilitet med kolumn)
    kanner_sammanlagt = pv + gr + nv + nf

    # Klockslag (enkel beräkning från starttid + summa_tid)
    try:
        dt_start = datetime.combine(rad_datum, starttid)
        dt_slut = dt_start + timedelta(seconds=summa_tid_sec)
        klockan_str = dt_slut.strftime("%H:%M")
    except Exception:
        klockan_str = ""

    # Format
    out = {}
    out.update(g)  # behåll originalfält (inkl. "Typ" osv)

    out["Summa S"] = int(summa_s)
    out["Summa D"] = int(summa_d)
    out["Summa TP"] = int(summa_tp)
    out["Summa Vila"] = int(summa_vila)

    out["Tid Älskar (sek)"] = int(tid_alskar_sec)
    out["Tid Älskar"] = _hm_str_from_seconds(int(tid_alskar_sec))

    out["Tid Sover med (sek)"] = int(tid_sover_sec)
    out["Tid Sover med"] = _hm_str_from_seconds(int(tid_sover_sec))

    out["Summa tid (sek)"] = int(summa_tid_sec)
    out["Summa tid"] = _hm_str_from_seconds(int(summa_tid_sec))

    out["Tid per kille (sek)"] = int(tpk_sec)
    out["Tid per kille"] = _ms_str_from_seconds(int(tpk_sec))

    out["Hångel (sek/kille)"] = int(hangel_per_kille_sec)
    out["Hångel (m:s/kille)"] = _ms_str_from_seconds(int(hangel_per_kille_sec))

    out["Suger"] = suger_total_label
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Avgift"] = float(avgift)
    out["Intäkter"] = float(intakter)

    out["Intäkt män"] = float(intakt_man_kostnad)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Lön Malin"] = float(lon_malin)
    out["Intäkt Företaget"] = float(intakt_foretaget)
    out["Vinst"] = float(vinst)

    out["Känner Sammanlagt"] = int(kanner_sammanlagt)

    out["Totalt Män"] = int(total_killar)
    out["Tid kille"] = out["Tid per kille"]

    out["Klockan"] = klockan_str

    return out
