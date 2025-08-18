# berakningar.py
from datetime import date, time, datetime, timedelta
import math
import random
from typing import Dict, Any

def _safe_int(x, default=0):
    try:
        if x is None: return default
        s = str(x).strip()
        if s == "": return default
        return int(float(s))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None: return default
        s = str(x).strip()
        if s == "": return default
        return float(s)
    except Exception:
        return default

def _hm_str_from_seconds(total_sec: int) -> str:
    h = total_sec // 3600
    m = round((total_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _klockan_str(starttid: time, extra_seconds: int) -> str:
    # Lägg på extra sekunder på starttid (utan datumrullning i strängen)
    dt = datetime.combine(date.today(), starttid) + timedelta(seconds=extra_seconds)
    return dt.strftime("%H:%M")

def _hardhet(dp, dpp, dap, tap, tot_man) -> int:
    score = 0
    if dp  > 0: score += 3
    if dpp > 0: score += 5
    if dap > 0: score += 7
    if tap > 0: score += 9
    # Män-trösklar: använd endast högsta tröskel som matchar
    if tot_man >= 1000:
        score += 10
    elif tot_man >= 500:
        score += 6
    elif tot_man >= 300:
        score += 5
    elif tot_man >= 200:
        score += 3
    elif tot_man >= 100:
        score += 1
    return score

def _bonus_from_subs(pren: int, seed_payload: str) -> int:
    """5% chans per prenumerant. Gör detta deterministiskt baserat på seed_payload."""
    if pren <= 0:
        return 0
    rnd = random.Random(hash(seed_payload) & 0xFFFFFFFF)
    # Binomial approx: summera Bernoulli(0.05)
    hits = 0
    for _ in range(pren):
        if rnd.random() < 0.05:
            hits += 1
    return hits

def berakna_radvarden(grund: Dict[str, Any], rad_datum: date, fodselsedatum: date, starttid: time) -> Dict[str, Any]:
    """
    Beräknar alla kolumnvärden för en rad, enligt senaste specifikationerna.
    OBS: 'PROD_STAFF' i grund (t.ex. 800) gör att hela personalstyrkan alltid
    räknas in i lönebasen (Utgift män), oavsett 'Personal deltagit'.
    """

    # ----------- Läs in värden (säkert) -----------
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))
    rumpa   = _safe_int(grund.get("Rumpa", 0))
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))                # sek
    tid_d   = _safe_int(grund.get("Tid D", 0))                # sek
    vila    = _safe_int(grund.get("Vila", 0))                 # sek
    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))   # sek/kille
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # sek/kille

    alskar  = _safe_int(grund.get("Älskar", 0))               # antal
    sover   = _safe_int(grund.get("Sover med", 0))            # 0/1

    pv      = _safe_int(grund.get("Pappans vänner", 0))
    gr      = _safe_int(grund.get("Grannar", 0))
    nv      = _safe_int(grund.get("Nils vänner", 0))
    nf      = _safe_int(grund.get("Nils familj", 0))
    bk      = _safe_int(grund.get("Bekanta", 0))
    esk     = _safe_int(grund.get("Eskilstuna killar", 0))

    bonus_k = _safe_int(grund.get("Bonus killar", 0))
    bonus_d = _safe_int(grund.get("Bonus deltagit", 0))
    personal_deltagit = _safe_int(grund.get("Personal deltagit", 0))
    prod_staff_total  = _safe_int(grund.get("PROD_STAFF", 0))  # total personalstyrka

    nils    = _safe_int(grund.get("Nils", 0))
    avgift  = _safe_float(grund.get("Avgift", 30.0))

    # ----------- Känner & Totalt Män -----------
    kanner = pv + gr + nv + nf
    # Totalt Män (rad) – enligt senaste: Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit
    tot_man = man + kanner + svarta + bk + esk + bonus_d

    # ----------- Summa-block (sek) -----------
    # Summa S = Tid S * (Fitta + Rumpa) + DT tid * Totalt Män
    summa_s_sec = tid_s * (fitta + rumpa) + dt_tid * max(tot_man, 0)

    # Summa D = Tid D * (DP + DPP + DAP)
    summa_d_sec = tid_d * (dp + dpp + dap)

    # Summa TP = Tid S * TAP  (enligt tidigare överenskommelse)
    summa_tp_sec = tid_s * tap

    # Summa Vila = Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila * Totalt Män
    summa_vila_sec = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * max(tot_man, 0)

    # Summa tid (sek) – exkl. Älskar/Sover (de går enbart på klockan)
    summa_tid_sec = int(summa_s_sec + summa_d_sec + summa_tp_sec + summa_vila_sec)

    # ----------- Älskar / Sover (sek) -----------
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover  * 20 * 60

    # ----------- Klockan -----------
    # Klockan = start + summa_tid + 3h + 1h + älskar + sover
    klockan_extra = summa_tid_sec + (3+1)*3600 + alskar_sec + sover_sec
    klockan_label = _klockan_str(starttid, klockan_extra)

    # ----------- Hårdhet & Prenumeranter & Bonus killar -----------
    hardhet = _hardhet(dp, dpp, dap, tap, tot_man)
    pren_base = fitta + rumpa + dp + dpp + dap + tap + max(tot_man, 0)
    prenumeranter = int(max(0, pren_base * hardhet))

    # Om Bonus killar inte skickats in, härled från prenumeranter (5% chans per prenumerant)
    if "Bonus killar" not in grund or bonus_k == 0:
        bonus_k = _bonus_from_subs(prenumeranter, f"{rad_datum.isoformat()}|{pren_base}|{hardhet}")

    # OBS: "Bonus deltagit" sätts i appen beroende på scenario (40%/fördelning). Vi rör INTE det här.
    # Men om inget finns och det inte är ett "vila"-case kan vi defaulta 0:
    if "Bonus deltagit" not in grund:
        bonus_d = 0

    # ----------- Suger (60% av Summan) -----------
    suger_total_sec = int(0.60 * summa_tid_sec)
    # Hångel: 3 timmar / (Män+Svarta+Bekanta+Eskilstuna+Bonus deltagit+Personal deltagit)
    hog_den = man + svarta + bk + esk + bonus_d + personal_deltagit
    hangel_per_kille_sec = int(round((3 * 3600) / hog_den)) if hog_den > 0 else 0

    # ----------- Tid per kille (sek) -----------
    denom_men = max(1, tot_man)  # undvik /0
    tpk_sec = int(round(
        (summa_s_sec / denom_men)
        + (summa_d_sec / denom_men) * 2
        + (summa_tp_sec / denom_men) * 3
        + (suger_total_sec / denom_men)
        # DT tid per kille är redan inbakad i Summa S
    ))

    # ----------- Ekonomi -----------
    # Intäkter = Prenumeranter * Avgift
    intakter = float(prenumeranter) * float(avgift)

    # Utgift män: (Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + HELA personalstyrkan)
    #   * (Summa tid i timmar) * $15
    wage_count = man + svarta + bk + esk + bonus_d + prod_staff_total
    utgift_man = float(wage_count) * (summa_tid_sec / 3600.0) * 15.0

    # Intäkt Känner = (Summa tid i timmar) * $35 * Känner
    intakt_kanner = float(kanner) * (summa_tid_sec / 3600.0) * 35.0

    # Lön Malin = 8% av max(Intäkter - Utgift män, 0), min $150, max $800
    malin_lone_bas = max(0.0, intakter - utgift_man)
    lon_malin = max(150.0, min(800.0, 0.08 * malin_lone_bas))

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = float(intakter) - (float(utgift_man) + float(intakt_kanner) + float(lon_malin))

    # ----------- Ålder (för live-visning i appen om den vill) -----------
    alder = rad_datum.year - fodselsedatum.year - (
        (rad_datum.month, rad_datum.day) < (fodselsedatum.month, fodselsedatum.day)
    )

    # ----------- Packa resultat -----------
    out: Dict[str, Any] = {}

    # Tidsblock
    out["Summa S"] = int(summa_s_sec)
    out["Summa D"] = int(summa_d_sec)
    out["Summa TP"] = int(summa_tp_sec)
    out["Summa Vila"] = int(summa_vila_sec)

    out["Tid Älskar (sek)"] = int(alskar_sec)
    out["Tid Älskar"] = _ms_str_from_seconds(int(alskar_sec))

    out["Tid Sover med (sek)"] = int(sover_sec)
    out["Tid Sover med"] = _ms_str_from_seconds(int(sover_sec))

    out["Summa tid (sek)"] = int(summa_tid_sec)
    out["Summa tid"] = _hm_str_from_seconds(int(summa_tid_sec))

    out["Tid per kille (sek)"] = int(tpk_sec)
    out["Tid per kille"] = _ms_str_from_seconds(int(tpk_sec))

    out["Hångel (sek/kille)"] = int(hangel_per_kille_sec)
    out["Hångel (m:s/kille)"] = _ms_str_from_seconds(int(hangel_per_kille_sec))

    out["Suger"] = int(suger_total_sec)
    out["Suger per kille (sek)"] = int(round(suger_total_sec / max(1, tot_man)))

    # Övrigt
    out["Klockan"] = klockan_label
    out["Älskar"] = alskar
    out["Sover med"] = sover
    out["Känner"] = int(kanner)

    out["Totalt Män"] = int(tot_man)
    out["Tid kille"] = out["Tid per kille"]  # alias som finns i schemat
    out["Nils"] = int(nils)

    # Ekonomi
    out["Hårdhet"] = int(hardhet)
    out["Prenumeranter"] = int(prenumeranter)
    out["Avgift"] = float(avgift)
    out["Intäkter"] = float(intakter)

    out["Utgift män"] = float(utgift_man)
    out["Intäkt Känner"] = float(intakt_kanner)
    out["Lön Malin"] = float(lon_malin)
    out["Vinst"] = float(vinst)

    # Känner Sammanlagt – på radsnivå samma som Känner (totalsummeras i statistik)
    out["Känner Sammanlagt"] = int(kanner)

    # Bonus
    out["Bonus killar"] = int(bonus_k)
    out["Bonus deltagit"] = int(bonus_d)  # tas från appens scenario (40% osv.)

    # Meta
    out["Veckodag"] = grund.get("Veckodag", "")
    out["Scen"] = grund.get("Scen", "")
    out["Typ"] = grund.get("Typ", "")

    # För ev. livevisning
    out["_Ålder"] = int(alder)

    return out
