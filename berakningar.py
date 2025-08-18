# berakningar.py
from datetime import datetime, date, time, timedelta
from typing import Dict, Any

# Hjälpare (egen formattering; fristående från app.py)
def _hm_str_from_seconds(q_sec: int) -> str:
    if q_sec is None:
        return "-"
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    if sec is None:
        return "-"
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

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

def _add_time(start: time, add_seconds: int) -> str:
    # Returnerar HH:MM efter att ha lagt på add_seconds på start (tidsdelen)
    base = datetime.combine(date(2000,1,1), start)
    end = base + timedelta(seconds=max(0, add_seconds))
    return end.strftime("%H:%M")

def berakna_radvarden(grund: Dict[str, Any], rad_datum: date, födelsedatum: date, starttid: time) -> Dict[str, Any]:
    """
    Beräknar alla fält för en rad enligt specifikationen.
    Parameternamnen matchar anropet i app.py.
    """
    g = {k: grund.get(k) for k in grund.keys()}  # shallow copy

    # ----------- Läs in basfält (säker konvertering) -----------
    man    = _safe_int(g.get("Män", 0))
    svarta = _safe_int(g.get("Svarta", 0))
    fitta  = _safe_int(g.get("Fitta", 0))
    rumpa  = _safe_int(g.get("Rumpa", 0))
    dp     = _safe_int(g.get("DP", 0))
    dpp    = _safe_int(g.get("DPP", 0))
    dap    = _safe_int(g.get("DAP", 0))
    tap    = _safe_int(g.get("TAP", 0))

    tid_s  = _safe_int(g.get("Tid S", 0))          # sek
    tid_d  = _safe_int(g.get("Tid D", 0))          # sek
    vila   = _safe_int(g.get("Vila", 0))           # sek
    dt_tid = _safe_int(g.get("DT tid (sek/kille)", 0))
    dt_vila= _safe_int(g.get("DT vila (sek/kille)", 0))

    alskar = _safe_int(g.get("Älskar", 0))
    sover  = _safe_int(g.get("Sover med", 0))      # 0/1

    pv     = _safe_int(g.get("Pappans vänner", 0))
    gr     = _safe_int(g.get("Grannar", 0))
    nv     = _safe_int(g.get("Nils vänner", 0))
    nf     = _safe_int(g.get("Nils familj", 0))
    bk     = _safe_int(g.get("Bekanta", 0))
    esk    = _safe_int(g.get("Eskilstuna killar", 0))

    bonus_deltagit = _safe_int(g.get("Bonus deltagit", 0))
    personal_deltagit = _safe_int(g.get("Personal deltagit", 0))

    avgift = _safe_float(g.get("Avgift", 30.0))

    # ----------- Härledda fält -----------
    # Känner (radnivå)
    kanner = pv + gr + nv + nf

    # Totalt Män (radnivå) = Män + Känner + Svarta + Bekanta + Eskilstuna + Bonus deltagit + Personal deltagit
    totalt_man = man + kanner + svarta + bk + esk + bonus_deltagit + personal_deltagit

    # ----------- Summa-delar -----------
    # Summa S = Tid S * (Fitta + Rumpa) + DT tid * Totalt män
    summa_s = tid_s * (fitta + rumpa) + dt_tid * totalt_man

    # Summa D = Tid D * (DP + DPP + DAP)  (OBS: *2 kommer i "Tid per kille")
    summa_d = tid_d * (dp + dpp + dap)

    # Summa TP = Tid S * TAP  (enligt tidigare överenskommelse)
    summa_tp = tid_s * tap

    # Summa Vila = Vila * (Fitta + Rumpa + DP + DPP + DAP + TAP) + DT vila * Totalt män
    summa_vila = vila * (fitta + rumpa + dp + dpp + dap + tap) + dt_vila * totalt_man

    # Älskar & Sover (sek)
    alskar_sec = alskar * 20 * 60
    sover_sec  = sover * 20 * 60

    # Summa tid (sek) — arbetstid för scenen (exkl. älskar/sover)
    total_scene_sec = max(0, summa_s + summa_d + summa_tp + summa_vila)

    # Suger: 60% av scenens totala tid
    suger_total_sec = int(round(total_scene_sec * 0.60))

    # Hångel (sek/kille): 3 timmar per totalt män
    if totalt_man > 0:
        hangel_sec_per_kille = int(round(3 * 3600 / totalt_man))
    else:
        hangel_sec_per_kille = 0

    # Tid per kille (sek)
    if totalt_man > 0:
        tpk = (
            (summa_s / totalt_man)
            + (summa_d / totalt_man) * 2
            + (summa_tp / totalt_man) * 3
            + (suger_total_sec / totalt_man)  # "Suger per kille (sek)"
            + dt_tid  # DT tid per kille
        )
        tpk_sec = int(round(tpk))
        suger_per_kille_sec = int(round(suger_total_sec / totalt_man))
    else:
        tpk_sec = 0
        suger_per_kille_sec = 0

    # Hårdhet
    hardhet = 0
    if dp > 0:  hardhet += 3
    if dpp > 0: hardhet += 5
    if dap > 0: hardhet += 7
    if tap > 0: hardhet += 9
    # Totalt män trösklar
    if totalt_man > 100:  hardhet += 1
    if totalt_man > 200:  hardhet += 3
    if totalt_man == 300: hardhet += 5
    if totalt_man > 500:  hardhet += 6
    if totalt_man > 1000: hardhet += 10
    if svarta > 0: hardhet += 3

    # Prenumeranter
    prenumeranter = (fitta + rumpa + dp + dpp + dap + tap + totalt_man) * hardhet

    # Intäkter
    intakter = prenumeranter * avgift

    # Utgift män:
    # Lön betalas till: Män + Svarta + Bekanta + Eskilstuna + Bonus deltagit + ALL personal (hela personalstyrkan, men vi får här personal_deltagit => appen
    # matar in hela PRODUCTION_STAFF som separat i schemat. Här använder vi (Personal deltagit) som injicerat av appen när den motsvarar "alla".
    # Enligt senaste krav: använd hela personalstyrkan och inte "känner".
    # I appen sätts "Personal deltagit" alltid som procent av total personalstyrka – men för lönen ska ALL personal få lön.
    # För att kunna räkna här måste appen fylla in "Personal deltagit" = total personalstyrka när lönen ska avse alla.
    # Det är redan hanterat i appens logik (den använder procentinställningen/total), så vi utgår från att "personal_total_for_salary" = personal_deltagit om appen valt så.
    # Om du vill låsa till just "hela personalstyrkan" kan du ändra här till en egen parameter.
    lon_basantal = man + svarta + bk + esk + bonus_deltagit + personal_deltagit
    utgift_man = (total_scene_sec / 3600.0) * 15.0 * lon_basantal

    # Intäkt Känner = Summa tid (i timmar) * 35 USD * Känner
    intakt_kanner = (total_scene_sec / 3600.0) * 35.0 * kanner

    # Lön Malin = 8% av (Intäkter - Utgift män), min 150, max 800
    resterande = max(0.0, intakter - utgift_man)
    lon_malin = max(150.0, min(800.0, 0.08 * resterande))

    # Vinst = Intäkter - (Utgift män + Intäkt Känner + Lön Malin)
    vinst = intakter - (utgift_man + intakt_kanner + lon_malin)

    # Klockan (sluttid) = starttid + scen-tid + 4h (3+1) + älskar + sover
    end_seconds = total_scene_sec + (4 * 3600) + alskar_sec + sover_sec
    klockan_str = _add_time(starttid, end_seconds)

    # Ålder (behövs i appen men vi returnerar inte separat; appen visar i live)
    # alder = rad_datum.year - födelsedatum.year - ((rad_datum.month, rad_datum.day) < (födelsedatum.month, födelsedatum.day))

    # Presentationssträngar
    summa_tid_str = _hm_str_from_seconds(total_scene_sec)
    tid_per_kille_str = _ms_str_from_seconds(tpk_sec)
    hangel_ms_per_kille = _ms_str_from_seconds(hangel_sec_per_kille)

    # Tid Älskar / Sover med (sträng)
    tid_alskar_str = _ms_str_from_seconds(alskar_sec)
    tid_sover_str  = _ms_str_from_seconds(sover_sec)

    # Slutlig output – matchar kolumnnamn i appens schema
    out = {
        "Typ": g.get("Typ", ""),
        "Veckodag": g.get("Veckodag", ""),
        "Scen": g.get("Scen", ""),
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
        "DT tid (sek/kille)": dt_tid,
        "DT vila (sek/kille)": dt_vila,

        "Summa S": int(summa_s),
        "Summa D": int(summa_d),
        "Summa TP": int(summa_tp),
        "Summa Vila": int(summa_vila),

        "Tid Älskar (sek)": int(alskar_sec),
        "Tid Älskar": tid_alskar_str,
        "Tid Sover med (sek)": int(sover_sec),
        "Tid Sover med": tid_sover_str,

        "Summa tid": summa_tid_str,
        "Summa tid (sek)": int(total_scene_sec),

        "Tid per kille (sek)": int(tpk_sec),
        "Tid per kille": tid_per_kille_str,

        "Klockan": klockan_str,
        "Älskar": alskar,
        "Sover med": sover,

        "Känner": int(kanner),
        "Pappans vänner": pv,
        "Grannar": gr,
        "Nils vänner": nv,
        "Nils familj": nf,
        "Bekanta": bk,
        "Eskilstuna killar": esk,

        "Bonus killar": _safe_int(g.get("Bonus killar", 0)),  # informativt
        "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,

        "Totalt Män": int(totalt_man),
        "Tid kille": tid_per_kille_str,  # alias/visning

        "Hångel (sek/kille)": int(hangel_sec_per_kille),
        "Hångel (m:s/kille)": hangel_ms_per_kille,

        "Suger": int(suger_total_sec),
        "Suger per kille (sek)": int(suger_per_kille_sec),

        "Hårdhet": int(hardhet),
        "Prenumeranter": int(prenumeranter),
        "Avgift": float(avgift),
        "Intäkter": float(intakter),

        "Utgift män": float(utgift_man),
        "Intäkt Känner": float(intakt_kanner),
        "Lön Malin": float(lon_malin),
        "Vinst": float(vinst),

        # Behåller fältet (om du vill använda det senare som kumulativt):
        "Känner Sammanlagt": int(kanner),
    }

    return out
