# -*- coding: utf-8 -*-
"""
Stub/kompatibilitetsversion av berakningar.py med samma gränssnitt.
Den här lämnar dina befintliga beräkningar orörda om du redan har en avancerad variant.
Fyll på med din fulla logik här om du vill ersätta.
"""

from datetime import datetime, timedelta, date, time

def berakna_radvarden(grund: dict, rad_datum, fodelsedatum, starttid):
    # Pass-through + minimala fält så appen inte kraschar.
    # Antagande: alla nycklar i `grund` finns.
    out = dict(grund)

    # Standardvärden om något saknas
    man     = int(float(grund.get("Män", 0) or 0))
    svarta  = int(float(grund.get("Svarta", 0) or 0))
    esk     = int(float(grund.get("Eskilstuna killar", 0) or 0))
    kanner  = int(float(grund.get("Känner", 0) or 0))
    pappan  = int(float(grund.get("Pappans vänner", 0) or 0))
    grannar = int(float(grund.get("Grannar", 0) or 0))
    nv      = int(float(grund.get("Nils vänner", 0) or 0))
    nf      = int(float(grund.get("Nils familj", 0) or 0))
    bk      = int(float(grund.get("Bekanta", 0) or 0))

    # Om "Känner" inte redan är satt, beräkna som summan av källorna inkl. Bekanta
    if ("Känner" not in grund) or (grund.get("Känner") in (None, "", 0)):
        kanner = pappan + grannar + nv + nf + bk
        out["Känner"] = kanner

    # Totalt Män: Män + Svarta + Eskilstuna + alla “känner”-källor
    totalt_man = man + svarta + esk + (pappan + grannar + nv + nf + bk)
    out["Totalt Män"] = totalt_man

    # Tider
    tid_s  = int(float(grund.get("Tid S", 0) or 0))
    tid_d  = int(float(grund.get("Tid D", 0) or 0))
    vila   = int(float(grund.get("Vila", 0) or 0))
    dt_tid  = int(float(grund.get("DT tid (sek/kille)", 0) or 0))
    dt_vila = int(float(grund.get("DT vila (sek/kille)", 0) or 0))

    summa_s = tid_s * totalt_man
    summa_d = tid_d * totalt_man
    summa_tp = summa_s + summa_d
    summa_vila = vila * totalt_man + dt_vila * totalt_man  # DT-vila adderas här enligt överenskommelse

    # Per kille (lägg på DT-tid)
    tid_per_kille_sek = tid_s + tid_d + dt_tid
    out["Tid per kille (sek)"] = tid_per_kille_sek
    out["Tid per kille"] = f"{tid_per_kille_sek//60}m {tid_per_kille_sek%60}s"

    # Summa tid (sek)
    alskar_sec = int(float(grund.get("Tid Älskar (sek)", 0) or 0))
    sover_sec  = int(float(grund.get("Tid Sover med (sek)", 0) or 0))
    summa_tid_sek = summa_tp + summa_vila + alskar_sec + sover_sec + (dt_tid * totalt_man)

    out["Summa S"] = summa_s
    out["Summa D"] = summa_d
    out["Summa TP"] = summa_tp
    out["Summa Vila"] = summa_vila
    out["Summa tid (sek)"] = summa_tid_sek
    out["Summa tid"] = f"{summa_tid_sek//3600}h {int((summa_tid_sek%3600)/60)} min"

    # Klockan (enkel framräkning från starttid)
    if isinstance(starttid, time):
        base_dt = datetime.combine(rad_datum, starttid)
    else:
        base_dt = datetime.combine(rad_datum, time(7,0))
    done_dt = base_dt + timedelta(seconds=summa_tid_sek)
    out["Klockan"] = done_dt.strftime("%H:%M")

    # Prenumeranter (förenklad – behåll din egen om du har en annan)
    hardhet = int(float(grund.get("Hårdhet", 0) or 0))
    if svarta > 0:
        hardhet += 3
    pren_base = (
        int(float(grund.get("Män", 0) or 0))
        + int(float(grund.get("Fitta", 0) or 0))
        + int(float(grund.get("Rumpa", 0) or 0))
        + int(float(grund.get("DP", 0) or 0))
        + int(float(grund.get("DPP", 0) or 0))
        + int(float(grund.get("DAP", 0) or 0))
        + int(float(grund.get("TAP", 0) or 0))
        + int(kanner)
    )
    pren_base += 2 * svarta  # svarta dubblas för prenumeranter
    pren = max(0, pren_base * max(1, hardhet))
    out["Hårdhet"] = hardhet
    out["Prenumeranter"] = pren

    fee = float(grund.get("Avgift", 0) or 0.0)
    out["Intäkter"] = float(pren) * fee

    # Ekonomi – placeholder (behåll/döp om efter ditt schema)
    out["Intäkt män"] = float(grund.get("Intäkt män", 0) or 0.0)
    out["Intäkt Känner"] = float(grund.get("Intäkt Känner", 0) or 0.0)
    out["Intäkt Företaget"] = float(grund.get("Intäkt Företaget", 0) or 0.0)
    out["Lön Malin"] = float(grund.get("Lön Malin", 0) or 0.0)
    out["Vinst"] = float(grund.get("Vinst", 0) or 0.0)

    # Hångel/Suger placeholders (om du har specifik logik, lägg in den här)
    out["Hångel (sek/kille)"] = int(float(grund.get("Hångel (sek/kille)", 0) or 0))
    out["Hångel (m:s/kille)"] = f"{out['Hångel (sek/kille)']//60}:{out['Hångel (sek/kille)']%60:02d}"
    out["Suger"] = int(float(grund.get("Suger", 0) or 0))
    out["Suger per kille (sek)"] = int(float(grund.get("Suger per kille (sek)", 0) or 0))

    # Typ – behåll värdet från grund, annars tomt
    out["Typ"] = grund.get("Typ", "") or ""

    return out
