from datetime import datetime, timedelta

# --------------------------------------------------
# Hjälpare
# --------------------------------------------------
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

def _end_time_label(starttime, add_seconds: int) -> str:
    # starttime: datetime.time
    base = datetime(2000,1,1, starttime.hour, starttime.minute, starttime.second)
    endt = base + timedelta(seconds=int(add_seconds))
    return endt.strftime("%H:%M")

# --------------------------------------------------
# Huvudfunktion
# --------------------------------------------------
def berakna_radvarden(grund: dict, rad_datum, fodselsedatum, starttid):
    """
    Returnerar en dict med alla fält som app.py förväntar sig.
    Viktigt i denna version:
    - DT tid (sek/kille) läggs till i 'Tid per kille (sek)' (dvs + dt_tid direkt per kille).
    - DT vila (sek/kille) går ENDAST till 'Summa Vila' (inte till Tid per kille).
    - 'Vila på jobbet' / 'Vila i hemmet' ger inga prenumeranter eller intäkter/kostnader.
    - Svarta behandlas som män i tid/antal, dubblar pren.-bidrag och +3 hårdhet vid >0.
    - Bekanta beter sig som män/känner i tid/prenumeranter men ger ingen kostnad,
      och påverkar inte älskar/sover-med-beräkningarna (som tidigare).
    """

    # --- Hämta indata ---
    typ     = (grund.get("Typ") or "").strip()
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))
    rumpa   = _safe_int(grund.get("Rumpa", 0))
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))
    tid_d   = _safe_int(grund.get("Tid D", 0))
    vila    = _safe_int(grund.get("Vila", 0))

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))   # PER KILLE -> läggs till i Tid/kille
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # PER KILLE -> ENDAST till Summa Vila

    alskar  = _safe_int(grund.get("Älskar", 0))
    sover   = _safe_int(grund.get("Sover med", 0))

    pv      = _safe_int(grund.get("Pappans vänner", 0))
    gr      = _safe_int(grund.get("Grannar", 0))
    nv      = _safe_int(grund.get("Nils vänner", 0))
    nf      = _safe_int(grund.get("Nils familj", 0))
    bekanta = _safe_int(grund.get("Bekanta", 0))
    nils    = _safe_int(grund.get("Nils", 0))

    avgift  = _safe_float(grund.get("Avgift", 30.0))

    # --- Känner-sammanlagt (inkl. bekanta) ---
    kanner = pv + gr + nv + nf + bekanta

    # --- Totalt antal "killar" som ska räkna i tid-fördelning ---
    # Vi inkluderar män + svarta + "känner" + bekanta (bekanta redan med i kanner) = man + svarta + kanner
    total_killar = man + svarta + kanner

    # --- Summa-tider (sek) ---
    # S: "traditionell" (män + fitta + rumpa ...) – nu inkluderat svarta & känner (inkl. bekanta) i samma pott.
    summa_s = (man + svarta + fitta + rumpa + kanner) * tid_s

    # D: "dubbel/trippel" – behåller bas (dp+dpp+dap) * tid_d (acts-antal * per-act tid)
    summa_d = (dp + dpp + dap) * tid_d

    # TP: "triple anal" – tap * tid_d
    summa_tp = tap * tid_d

    # Vila: (alla killar * vila) + (alla killar * dt_vila)
    # DT-vila ska ENDAST hit, enligt din senaste korrigering.
    summa_vila = total_killar * (vila + dt_vila)

    # Extra tider
    alskar_sec = alskar * 1800         # 30 min per 'Älskar'
    sover_sec  = sover * 3600          # 1 h per 'Sover med'

    # DT tid (per kille) – TOTALT för scenen (till total tid), men per-kille läggs separat i tid/kille
    dt_total_sec = dt_tid * total_killar

    # --- Total tid (sek) ---
    total_tid_sec = (
        summa_s + summa_d + summa_tp + summa_vila +
        alskar_sec + sover_sec +
        dt_total_sec
    )

    # --- Hångel (sek/kille) = 3 h / killar (män + svarta + kanner) ---
    hangel_sek_per_kille = 0
    if total_killar > 0:
        hangel_sek_per_kille = int(round((3 * 3600) / total_killar))

    # --- Suger: 60% av (D + TP) ---
    suger_total_sec = int(round(0.60 * (summa_d + summa_tp)))
    suger_per_kille_sec = int(round(suger_total_sec / total_killar)) if total_killar > 0 else 0

    # --- Tid per kille (sek) ---
    # (S/alla) + 2*(D/alla) + 3*(TP/alla) + (Suger/alla) + DT_tid (per kille)
    if total_killar > 0:
        tid_per_kille_sec = int(round(
            (summa_s / total_killar)
            + 2 * (summa_d / total_killar)
            + 3 * (summa_tp / total_killar)
            + suger_per_kille_sec
            + dt_tid  # <-- VIKTIG: DT-TID PER KILLE läggs på direkt här
        ))
    else:
        tid_per_kille_sec = 0

    # --- Hårdhet ---
    hardhet = 0
    if dp  > 0: hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3  # extra om svarta finns

    # --- Prenumeranter ---
    # Bas: män + fitta + rumpa + dp + dpp + dap + tap + känner
    # Svarta dubblas i pren.-bidraget (→ +2*svarta)
    base_pren = (man + fitta + rumpa + dp + dpp + dap + tap + kanner) + (2 * svarta)
    prenumeranter = int(round(base_pren * hardhet))

    # "Vila…" rader ska inte ge prenumeranter eller intäkter
    if typ in ("Vila på jobbet", "Vila i hemmet"):
        prenumeranter = 0

    # --- Intäkter/kostnader ---
    intakter = prenumeranter * avgift

    # Kostnad män: gäller män + svarta (bekanta/känner ger ingen kostnad)
    kostnad_man = (man + svarta) * 120

    # Intäkt Känner: vi räknar den som 'avgift per pren.' * känner
    intakt_kanner = kanner * avgift

    # Lön Malin: 10% av intäkter, clamp 150–800
    lon_malin_raw = 0.10 * intakter
    lon_malin = max(150.0, min(800.0, lon_malin_raw)) if intakter > 0 else 0.0

    # Intäkt Företaget: 20% av intäkter
    intakt_foretaget = 0.20 * intakter

    # Vinst
    vinst = intakter - kostnad_man - intakt_kanner - lon_malin - intakt_foretaget

    # --- Formateringar & utdata ---
    out = {}

    # Kopiera tillbaka kända nycklar (bra för kolumnordningen i appen)
    for k in [
        "Typ","Veckodag","Scen","Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
        "Älskar","Sover med",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Nils","Avgift"
    ]:
        if k in grund:
            out[k] = grund[k]

    out["Känner"] = kanner
    out["Känner Sammanlagt"] = kanner

    out["Summa S"] = int(summa_s)
    out["Summa D"] = int(summa_d)
    out["Summa TP"] = int(summa_tp)
    out["Summa Vila"] = int(summa_vila)

    out["Tid Älskar (sek)"] = int(alskar_sec)
    out["Tid Älskar"] = _hm_str_from_seconds(int(alskar_sec))
    out["Tid Sover med (sek)"] = int(sover_sec)
    out["Tid Sover med"] = _hm_str_from_seconds(int(sover_sec))

    out["Summa tid (sek)"] = int(total_tid_sec)
    out["Summa tid"] = _hm_str_from_seconds(int(total_tid_sec))

    out["Hångel (sek/kille)"] = int(hangel_sek_per_kille)
    out["Hångel (m:s/kille)"] = _ms_str_from_seconds(int(hangel_sek_per_kille))

    out["Suger"] = int(suger_total_sec)
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Totalt Män"] = int(total_killar)

    out["Tid per kille (sek)"] = int(tid_per_kille_sec)
    out["Tid per kille"] = _ms_str_from_seconds(int(tid_per_kille_sec))

    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Intäkter"] = float(intakter)
    out["Intäkt män"] = float(kostnad_man)         # Kostnad
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Lön Malin"] = float(lon_malin)
    out["Intäkt Företaget"] = float(intakt_foretaget)
    out["Vinst"] = float(vinst)

    # Sluttid (klockslag)
    out["Klockan"] = _end_time_label(starttid, int(total_tid_sec))

    return out
