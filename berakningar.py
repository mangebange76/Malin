# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

def _mmss(sec: float) -> str:
    try:
        s = max(0, int(round(float(sec))))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "-"

def _hhmm(dt: datetime) -> str:
    try:
        return dt.strftime("%H:%M")
    except Exception:
        return "-"

def calc_row_values(base: dict, rad_datum, fodelsedatum, starttid):
    """
    Returnerar en preview-dict med alla fält som app.py visar.
    Följer dina specifikationer för tider/summor/hångel/suger/händer/Klocka.
    """

    # Hämta label-namn för källor (numeriska värden ligger under etikettnamnen)
    lbl_p = base.get("LBL_PAPPAN", "Pappans vänner")
    lbl_g = base.get("LBL_GRANNAR", "Grannar")
    lbl_nv = base.get("LBL_NILS_VANNER", "Nils vänner")
    lbl_nf = base.get("LBL_NILS_FAMILJ", "Nils familj")
    lbl_bek = base.get("LBL_BEKANTA", "Bekanta")
    lbl_esk = base.get("LBL_ESK", "Eskilstuna killar")

    # Inmatningar
    man      = int(base.get("Män", 0))
    svarta   = int(base.get("Svarta", 0))
    fitta    = int(base.get("Fitta", 0))
    rumpa    = int(base.get("Rumpa", 0))
    dp       = int(base.get("DP", 0))
    dpp      = int(base.get("DPP", 0))
    dap      = int(base.get("DAP", 0))
    tap      = int(base.get("TAP", 0))
    tid_s    = int(base.get("Tid S", 0))  # sek
    tid_d    = int(base.get("Tid D", 0))  # sek
    vila     = int(base.get("Vila", 0))   # sek
    dt_tid_k = int(base.get("DT tid (sek/kille)", 0))
    dt_vil_k = int(base.get("DT vila (sek/kille)", 0))
    alskar   = int(base.get("Älskar", 0))
    sover    = int(base.get("Sover med", 0))

    pappan   = int(base.get(lbl_p, 0))
    grannar  = int(base.get(lbl_g, 0))
    nvanner  = int(base.get(lbl_nv, 0))
    nfamilj  = int(base.get(lbl_nf, 0))
    bekanta  = int(base.get(lbl_bek, 0))
    esk      = int(base.get(lbl_esk, 0))

    bonus    = int(base.get("Bonus deltagit", 0))
    personal = int(base.get("Personal deltagit", 0))

    # Totalt män på raden (DIN definition för rad-nivå)
    tot_man_rad = (man + svarta + pappan + grannar + nvanner + nfamilj +
                   bekanta + esk + bonus + personal)

    # ---- Summor ----
    summa_s   = (fitta + rumpa) * tid_s
    summa_d   = (dp + dpp + dap) * tid_d
    summa_tp  = (tap) * tid_d

    # DT tid och DT vila separata
    dt_tid_sum  = tot_man_rad * dt_tid_k
    dt_vila_sum = tot_man_rad * dt_vil_k

    # Summa vila (inkl DT vila)
    summa_vila = (fitta + rumpa + dp + dpp + dap + tap) * vila + dt_vila_sum

    # Summa tid (sek) = S + D + TP + DT tid + Summa vila
    summa_tid_sek = summa_s + summa_d + summa_tp + dt_tid_sum + summa_vila

    # Hångel: 3 timmar totalt, per kille delas på (män + bekanta + esk + bonus + personal)
    hangel_total_sek = 3 * 3600
    hangel_denom = (man + bekanta + esk + bonus + personal)
    hangel_per_kille = (hangel_total_sek / hangel_denom) if hangel_denom > 0 else 0

    # Suger: 75% av (summa S + summa D + summa TP) – utan DT tid
    suger_total = 0.75 * (summa_s + summa_d + summa_tp)
    suger_per_kille = (suger_total / tot_man_rad) if tot_man_rad > 0 else 0

    # Händer per kille = 2 × suger/kille
    hander_per_kille = 2.0 * suger_per_kille
    hander_total = hander_per_kille * tot_man_rad  # = 2 × suger_total

    # Tid per kille (sek) — enligt viktning du angav
    if tot_man_rad > 0:
        tid_per_kille_sek = (
            summa_s + summa_d + summa_d +        # D två gånger
            summa_tp + summa_tp + summa_tp +     # TP tre gånger
            dt_tid_sum + suger_total + hander_total
        ) / tot_man_rad
    else:
        tid_per_kille_sek = 0.0

    # Älskar/Sover – endast för visning/statistik, ej in i summor
    tid_alskar_sek = alskar * 20 * 60
    tid_sover_sek  = sover  * 20 * 60

    # Klockan: start + (summa tid) + 1h vila + 3h hångel
    if isinstance(rad_datum, datetime):
        base_dt = rad_datum
    else:
        # rad_datum är oftast date; kombinera med starttid
        base_dt = datetime.combine(rad_datum, starttid)
    klockan_dt = base_dt + timedelta(seconds=summa_tid_sek + 1*3600 + hangel_total_sek)
    klockan_str = _hhmm(klockan_dt)

    # Klockan inkl älskar/sover (+ 20 min per enhet)
    extra_as = tid_alskar_sek + tid_sover_sek
    klockan_as_dt = klockan_dt + timedelta(seconds=extra_as)
    klockan_as_str = _hhmm(klockan_as_dt)

    # Känner sammanlagt (statistik-nivå) = maxvärden från raden (inställningarna)
    kanner_sammanlagt = (
        int(base.get("MAX_PAPPAN", 0)) +
        int(base.get("MAX_GRANNAR", 0)) +
        int(base.get("MAX_NILS_VANNER", 0)) +
        int(base.get("MAX_NILS_FAMILJ", 0))
    )

    # Packa resultat
    out = {
        "Datum": base.get("Datum"),
        "Veckodag": base.get("Veckodag"),
        "Typ": base.get("Typ"),
        "Känner": int(base.get("Känner", 0)),
        "Känner sammanlagt": int(kanner_sammanlagt),

        "Totalt Män": int(tot_man_rad),

        "Summa tid (sek)": int(summa_tid_sek),
        "Summa tid": _mmss(summa_tid_sek),

        "Hångel (sek/kille)": int(round(hangel_per_kille)),
        "Hångel (m:s/kille)": _mmss(hangel_per_kille),

        "Suger per kille (sek)": int(round(suger_per_kille)),
        "Händer per kille (sek)": int(round(hander_per_kille)),

        "Tid per kille (sek)": float(tid_per_kille_sek),
        "Tid per kille": _mmss(tid_per_kille_sek),

        "Tid Älskar (sek)": int(tid_alskar_sek),
        # (Tid Sover om du vill visa/spara separat)
        # "Tid Sover (sek)": int(tid_sover_sek),

        "Klockan": klockan_str,
        "Klockan inkl älskar/sover": klockan_as_str,
    }
    return out
