# berakningar.py
from datetime import datetime, date, time, timedelta

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def berakna_radvarden(grund: dict, rad_datum, fod: date, starttid: time) -> dict:
    # Läs in
    man   = int(float(grund.get("Män", 0) or 0))
    svarta= int(float(grund.get("Svarta", 0) or 0))
    fitta = int(float(grund.get("Fitta", 0) or 0))
    rumpa = int(float(grund.get("Rumpa", 0) or 0))
    dp    = int(float(grund.get("DP", 0) or 0))
    dpp   = int(float(grund.get("DPP", 0) or 0))
    dap   = int(float(grund.get("DAP", 0) or 0))
    tap   = int(float(grund.get("TAP", 0) or 0))

    tid_s = int(float(grund.get("Tid S", 0) or 0))
    tid_d = int(float(grund.get("Tid D", 0) or 0))
    vila  = int(float(grund.get("Vila", 0) or 0))

    dt_tid  = int(float(grund.get("DT tid (sek/kille)", 0) or 0))
    dt_vila = int(float(grund.get("DT vila (sek/kille)", 0) or 0))

    alskar = int(float(grund.get("Älskar", 0) or 0))
    sover  = int(float(grund.get("Sover med", 0) or 0))
    kanner = int(float(grund.get("Känner", 0) or 0))

    pv     = int(float(grund.get("Pappans vänner", 0) or 0))
    gr     = int(float(grund.get("Grannar", 0) or 0))
    nv     = int(float(grund.get("Nils vänner", 0) or 0))
    nf     = int(float(grund.get("Nils familj", 0) or 0))
    bk     = int(float(grund.get("Bekanta", 0) or 0))
    esk    = int(float(grund.get("Eskilstuna killar", 0) or 0))

    bonus_killar   = int(float(grund.get("Bonus killar", 0) or 0))
    bonus_deltagit = int(float(grund.get("Bonus deltagit", 0) or 0))
    personal_deltagit = int(float(grund.get("Personal deltagit", 0) or 0))

    nils   = int(float(grund.get("Nils", 0) or 0))

    avgift = float(grund.get("Avgift", 0.0) or 0.0)

    # ----- Tider -----
    summa_s = tid_s * (fitta + rumpa)
    summa_d = tid_d * (dp + dpp + dap + tap)
    summa_tp = 0  # reserv
    # DT-vila adderas EN gång per kille till Summa Vila (inte dubbelräknas)
    # Killar som påverkar DT: Totalt_Män (se nedan)
    # Summa vila bas (vila * antal punkter?) – tidigare låg vila som egen post, vi behåller ursprunglig och adderar DT-vila nedan.
    summa_vila_bas = vila

    # ----- Totalt Män (rad) -----
    totalt_man = max(0, man + kanner + svarta + bk + esk + bonus_deltagit + personal_deltagit)

    # DT-tid: per kille
    dt_tid_total = dt_tid * totalt_man
    dt_vila_total = dt_vila * totalt_man

    # Summa tid (sek)
    summa_tid_sek = max(0, summa_s + summa_d + summa_tp + summa_vila_bas + dt_tid_total + dt_vila_total)

    # Tid per kille
    tid_per_kille_sek = (summa_tid_sek // totalt_man) if totalt_man > 0 else 0
    tid_per_kille_lbl = _ms_str_from_seconds(tid_per_kille_sek)

    # Hångel & Suger – förenklad placeholder, men inkluderar Bekanta och Svarta
    hangel_per_kille = 30  # sek per kille, placeholder
    hangel_per_kille_lbl = _ms_str_from_seconds(hangel_per_kille)
    suger_per_kille = 20  # sek per kille, placeholder

    # Hårdhet – +3 om svarta > 0
    hardhet = 5 + (3 if svarta > 0 else 0)

    # Prenumeranter – svarta ger dubbel vikt + bonus killar ingår ej i prenumeranter
    pren = (man + bk + esk + kanner) + (svarta * 2)
    # Bonus killar påverkar inte prenumeranter
    intakter = pren * avgift

    # Intäkt män / känner / lön / företag / vinst – lämnas som tidigare stubb tills omräkning senare
    intakt_man = 0.0
    intakt_kanner = 0.0
    lon_malin = 0.0
    intakt_foretaget = 0.0
    vinst = 0.0

    # Summa tid i H:M
    summa_tid_lbl = f"{summa_tid_sek//3600}h { (summa_tid_sek%3600)//60 } min"

    # Klockan
    if isinstance(rad_datum, date) and isinstance(starttid, time):
        dt_start = datetime.combine(rad_datum, starttid)
        dt_end = dt_start + timedelta(seconds=summa_tid_sek)
        klockan = dt_end.strftime("%H:%M")
    else:
        klockan = ""

    out = dict(grund)
    out.update({
        "Summa S": summa_s,
        "Summa D": summa_d,
        "Summa TP": summa_tp,
        "Summa Vila": summa_vila_bas + dt_vila_total,
        "Tid Älskar (sek)": alskar * 60,
        "Tid Älskar": _ms_str_from_seconds(alskar * 60),
        "Tid Sover med (sek)": sover * 300,
        "Tid Sover med": _ms_str_from_seconds(sover * 300),
        "Summa tid (sek)": summa_tid_sek,
        "Summa tid": summa_tid_lbl,
        "Tid per kille (sek)": tid_per_kille_sek,
        "Tid per kille": tid_per_kille_lbl,
        "Klockan": klockan,
        "Totalt Män": totalt_man,
        "Tid kille": tid_per_kille_lbl,
        "Hångel (sek/kille)": hangel_per_kille,
        "Hångel (m:s/kille)": hangel_per_kille_lbl,
        "Suger": suger_per_kille * totalt_man,
        "Suger per kille (sek)": suger_per_kille,
        "Hårdhet": hardhet,
        "Prenumeranter": pren,
        "Avgift": avgift,
        "Intäkter": intakter,
        "Intäkt män": intakt_man,
        "Intäkt Känner": intakt_kanner,
        "Lön Malin": lon_malin,
        "Intäkt Företaget": intakt_foretaget,
        "Vinst": vinst,
        "Känner Sammanlagt": kanner,  # placeholder
    })
    return out
