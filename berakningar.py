# berakningar.py
from datetime import datetime, timedelta

def _safe_int(x, default=0):
    try:
        if x is None:
            return default
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

def _klockan_label(starttid, total_seconds_plus_rest_and_hang):
    """Returnera HH:MM utifrån starttid + (3h hångel) + (summa tid) + (1h vila efter scen)."""
    # starttid är datetime.time
    base = datetime(2000,1,1, starttid.hour, starttid.minute, 0)
    t = base + timedelta(seconds=total_seconds_plus_rest_and_hang)
    return t.strftime("%H:%M")

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Beräknar alla kolumnvärden för en rad.
    - Svarta behandlas som Män i alla beräkningar (totalt_män = män + svarta)
    - Prenumeranter: Svarta räknas dubbelt (1 Svart => +2 i prenumerantbas)
    - Hårdhet: +3 om Svarta > 0
    - Summa S/D/TP inkluderar också 'Känner' (Pappans vänner + Grannar + Nils vänner + Nils familj)
    - Älskar adderar 30 min per styck, Sover med adderar 60 min per styck till total tid
    - Suger = 60% av (Summa D + Summa TP). Suger per kille = Suger / totalt_män
    - Tid per kille = (S/alla) + (D/alla)*2 + (TP/alla)*3 + (Suger/alla)  (i sekunder)
      (Obs: Hångel ingår inte i “Tid per kille”)
    - Hångel = 3h / totalt_män (sparas både sek/kille och "m:s/kille")
    - Ekonomi: Intäkter = Prenumeranter * Avgift; Intäkt män = (män + svarta)*120 (kostnad),
      Intäkt Känner = (Lön Malin + 120) * Känner; Intäkt Företaget = 20% av Intäkter (kostnad);
      Vinst = Intäkter - Intäkt män - Intäkt Känner - Lön Malin - Intäkt Företaget
    - Typ "Vila på jobbet" / "Vila i hemmet" ger 0 i Prenumeranter & intäkter/kostnader.
    """
    # ---- Läs in värden, säkra int ----
    typ = (grund.get("Typ") or "").strip()

    man     = _safe_int(grund.get("Män", 0), 0)
    svarta  = _safe_int(grund.get("Svarta", 0), 0)
    fitta   = _safe_int(grund.get("Fitta", 0), 0)
    rumpa   = _safe_int(grund.get("Rumpa", 0), 0)
    dp      = _safe_int(grund.get("DP", 0), 0)
    dpp     = _safe_int(grund.get("DPP", 0), 0)
    dap     = _safe_int(grund.get("DAP", 0), 0)
    tap     = _safe_int(grund.get("TAP", 0), 0)

    tid_s   = _safe_int(grund.get("Tid S", 0), 0)
    tid_d   = _safe_int(grund.get("Tid D", 0), 0)
    vila    = _safe_int(grund.get("Vila", 0), 0)

    alskar  = _safe_int(grund.get("Älskar", 0), 0)
    sover   = _safe_int(grund.get("Sover med", 0), 0)

    pv      = _safe_int(grund.get("Pappans vänner", 0), 0)
    gr      = _safe_int(grund.get("Grannar", 0), 0)
    nv      = _safe_int(grund.get("Nils vänner", 0), 0)
    nf      = _safe_int(grund.get("Nils familj", 0), 0)
    nils    = _safe_int(grund.get("Nils", 0), 0)

    avgift  = float(grund.get("Avgift", 30.0))

    veckodag = grund.get("Veckodag", "")
    scen     = grund.get("Scen", "")

    # ---- Känner och totalt antal "män" (alla deltagare av "män-typ") ----
    kanner_sum = pv + gr + nv + nf
    totalt_man = man + svarta + kanner_sum  # Totalt Män = U + Män (+Svarta)
    # Men "alla killar" för tid per kille ska vara "män + svarta" (inte inkluderar Känner)
    alla_killar = max(1, man + svarta)

    # ---- Summa S / D / TP / Vila (sek) — inkluderar Känner i respektive kategori ----
    # S-kategori: (Män + Fitta + Rumpa + Känner) * Tid S
    summa_s = (man + svarta + fitta + rumpa + kanner_sum) * tid_s
    # D-kategori: (DP + DPP + DAP + Känner) * Tid D
    summa_d = (dp + dpp + dap + kanner_sum) * tid_d
    # TP-kategori: (TAP + Känner) * Tid D  (enligt tidigare logik använde TP också Tid D)
    summa_tp = (tap + kanner_sum) * tid_d
    # Vila: (alla "aktivitetsdeltagare") * vila
    vila_sec = (man + svarta + fitta + rumpa + dp + dpp + dap + tap + kanner_sum) * vila

    # ---- Extra tid: Älskar (30 min vardera) och Sover med (60 min vardera) ----
    tid_alskar_sec = alskar * 30 * 60
    tid_sover_sec  = sover  * 60 * 60

    # ---- Total tid (sek) ----
    total_tid_sec = summa_s + summa_d + summa_tp + vila_sec + tid_alskar_sec + tid_sover_sec

    # ---- Hångel: 3h / (män + svarta)  (ingår inte i "tid per kille") ----
    hangel_total_sec = 3 * 60 * 60  # 10800
    hangel_per_kille_sec = int(round(hangel_total_sec / max(1, man + svarta)))
    hangel_label_ms = _ms_str_from_seconds(hangel_per_kille_sec)

    # ---- Suger: 60% av (Summa D + Summa TP) ----
    suger_sec = int(round(0.60 * (summa_d + summa_tp)))
    suger_per_kille_sec = int(round(suger_sec / max(1, man + svarta)))

    # ---- Tid per kille (sek) enligt reglerna ----
    # (S/alla) + (D/alla)*2 + (TP/alla)*3 + (Suger/alla)
    tpk_sec = 0
    if man + svarta > 0:
        tpk_sec = int(round(
            (summa_s / (man + svarta))
            + (summa_d / (man + svarta)) * 2
            + (summa_tp / (man + svarta)) * 3
            + (suger_sec / (man + svarta))
        ))
    tpk_label = _ms_str_from_seconds(tpk_sec)

    # ---- Summa tid som timmar/minuter-sträng ----
    summa_tid_label = _hm_str_from_seconds(total_tid_sec)

    # ---- Klockan (starttid + 3h hångel + total tid + 1h vila efter scen) ----
    plus_allt_sec = hangel_total_sec + total_tid_sec + 3600
    klockan_label = _klockan_label(starttid, plus_allt_sec)

    # ---- Hårdhet ----
    hardhet = 0
    if dp > 0:  hardhet += 3
    if dpp > 0: hardhet += 4
    if dap > 0: hardhet += 6
    if tap > 0: hardhet += 8
    if svarta > 0: hardhet += 3  # +3 om Svarta > 0

    # ---- Prenumeranter ----
    # Bas = (Män + Fitta + Rumpa + DP + DPP + DAP + TAP + Känner) 
    # MEN: Svarta räknas dubbelt (läggs på utöver Män).
    pren_bas = (man + fitta + rumpa + dp + dpp + dap + tap + kanner_sum)
    pren_bas += (svarta * 2)  # svarta dubblas
    prenumeranter = pren_bas * hardhet

    # Exkludera vila-typer från pren & ekonomi
    if typ in ("Vila på jobbet", "Vila i hemmet"):
        prenumeranter = 0

    # ---- Ekonomi ----
    # Intäkter = Prenumeranter * Avgift
    intakter = float(prenumeranter) * float(avgift)

    # Intäkt män (kostnad): (män + svarta) * 120
    intakt_man = (man + svarta) * 120.0

    # Lön Malin: 10% av prenumeranter med min 150 max 800
    lon_malin = float(prenumeranter) * 0.10
    if lon_malin < 150:
        lon_malin = 150.0
    if lon_malin > 800:
        lon_malin = 800.0

    # Intäkt Känner (kostnad): (Lön Malin + 120) * Känner
    intakt_kanner = (lon_malin + 120.0) * kanner_sum

    # Intäkt Företaget (kostnad): 20% av Intäkter
    intakt_foretaget = intakter * 0.20

    # För vila-typer nollställ ekonomin:
    if typ in ("Vila på jobbet", "Vila i hemmet"):
        intakter = 0.0
        intakt_man = 0.0
        intakt_kanner = 0.0
        lon_malin = 0.0
        intakt_foretaget = 0.0

    # Vinst = Intäkter - Intäkt män - Intäkt Känner - Lön Malin - Intäkt Företaget
    vinst = float(intakter) - float(intakt_man) - float(intakt_kanner) - float(lon_malin) - float(intakt_foretaget)

    # ---- Ålder / Känner Sammanlagt ----
    # (Ålder används bara i notisen i appen, inget fält)
    kannersammanlagt = kanner_sum

    # ---- Returnera dictionary i samma nyckelstruktur som appen förväntar sig ----
    out = {
        "Datum": rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else str(rad_datum),
        "Typ": typ,
        "Veckodag": veckodag,
        "Scen": grund.get("Scen", ""),
        "Män": man,
        "Svarta": svarta,
        "Fitta": fitta,
        "Rumpa": rumpa,
        "DP": dp,
        "DPP": dpp,
        "DAP": dap,
        "TAP": tap,

        "Tid S": tid_s,
        "Tid D": tid_d,
        "Vila": vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(vila_sec),

        "Tid Älskar (sek)": int(tid_alskar_sec),
        "Tid Älskar": _hm_str_from_seconds(tid_alskar_sec),

        "Tid Sover med (sek)": int(tid_sover_sec),
        "Tid Sover med": _hm_str_from_seconds(tid_sover_sec),

        "Summa tid (sek)": int(total_tid_sec),
        "Summa tid": summa_tid_label,

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tpk_label,

        "Klockan": klockan_label,

        "Älskar": alskar,
        "Sover med": sover,
        "Känner": kanner_sum,

        "Pappans vänner": pv,
        "Grannar": gr,
        "Nils vänner": nv,
        "Nils familj": nf,

        "Totalt Män": int(totalt_man),  # U + Män + Svarta

        # Historiskt fält i basen; behåller kompatibilitet genom att spegla "Tid per kille"
        "Tid kille": tpk_label,

        "Nils": nils,

        "Hångel (sek/kille)": int(hangel_per_kille_sec),
        "Hångel (m:s/kille)": hangel_label_ms,

        "Suger": int(suger_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Hårdhet": int(hardhet),

        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Intäkt män": float(intakt_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Intäkt Företaget": float(intakt_foretaget),
        "Vinst": float(vinst),

        "Känner Sammanlagt": int(kannersammanlagt),
    }

    return out
