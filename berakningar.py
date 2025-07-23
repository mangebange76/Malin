from datetime import datetime, timedelta
import random
import pandas as pd

def beräkna_tid_per_kille(f):
    scen_tid = f.get("Scenens längd (h)", 0) * 3600
    dt_tid = f.get("DT tid per man (sek)", 0)
    totalt_dt = dt_tid * total_män(f)
    total_tid = scen_tid + totalt_dt
    per_kille_min = total_tid / 60 / max(1, total_män(f))
    return per_kille_min, total_tid / 3600

def total_män(f):
    enkel = f.get("Enkel vaginal", 0) + f.get("Enkel anal", 0)
    dubbel = 2 * (f.get("DP", 0) + f.get("DPP", 0) + f.get("DAP", 0))
    trippel = 3 * (f.get("TPA", 0) + f.get("TPP", 0) + f.get("TAP", 0))
    övriga = f.get("Övriga män", 0)
    return enkel + dubbel + trippel + övriga

def process_lägg_till_rader(df, inst, f):
    startdatum = inst.get("Startdatum", "2014-03-26")
    if df.empty:
        nytt_datum = datetime.strptime(startdatum, "%Y-%m-%d")
    else:
        senaste = max(pd.to_datetime(df["Datum"], errors="coerce").dropna())
        nytt_datum = senaste + timedelta(days=1)

    nya_rader = []

    if f["Typ"] == "Scen":
        nya_rader.append(skapa_rad(f.copy(), nytt_datum, inst))

    elif f["Typ"] == "Vila inspelningsplats":
        for _ in range(f["Antal vilodagar"]):
            rad = skapa_rad(f.copy(), nytt_datum, inst)
            rad["Typ"] = "Vila inspelningsplats"
            rad["Älskar med"] = 12
            rad["Sover med"] = 1
            rad["Kompisar"] = slumpa_andel(inst.get("Kompisar", 0), 0.25, 0.5)
            rad["Pappans vänner"] = slumpa_andel(inst.get("Pappans vänner", 0), 0.25, 0.5)
            rad["Nils vänner"] = slumpa_andel(inst.get("Nils vänner", 0), 0.25, 0.5)
            rad["Nils familj"] = slumpa_andel(inst.get("Nils familj", 0), 0.25, 0.5)
            nya_rader.append(rad)
            nytt_datum += timedelta(days=1)

    elif f["Typ"] == "Vilovecka hemma":
        dagar = 7
        multiplikator = 1.5
        for grupp in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
            tot = round(inst.get(grupp, 0) * multiplikator)
            fördelat = fördela_heltal(tot, dagar)
            for i in range(dagar):
                if len(nya_rader) <= i:
                    rad = skapa_rad(f.copy(), nytt_datum + timedelta(days=i), inst)
                    rad["Typ"] = "Vilovecka hemma"
                    rad["Älskar med"] = 8
                    rad["Sover med"] = 0
                    nya_rader.append(rad)
                nya_rader[i][grupp] = fördelat[i]

        # Slumpa 0–2 tillfällen med Nils
        antal = random.randint(0, 2)
        dagar_med_nils = random.sample(range(dagar), antal)
        for i in dagar_med_nils:
            nya_rader[i]["Nils sex"] = 1

    return pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)

def skapa_rad(f, datum, inst):
    rad = {k: f.get(k, 0) for k in f}
    rad["Datum"] = datum.strftime("%Y-%m-%d")
    rad["Nils sex"] = 0
    rad["Prenumeranter"] = räkna_prenumeranter(f)
    rad["Intäkt ($)"] = rad["Prenumeranter"] * 15
    rad["Kvinnans lön ($)"] = 100
    män = total_män(f)
    rad["Mäns lön ($)"] = män * 200
    komp = inst.get("Kompisar", 1)
    kvar = max(0, rad["Intäkt ($)"] - rad["Kvinnans lön ($)"] - rad["Mäns lön ($)"])
    rad["Kompisars lön ($)"] = kvar / komp if komp > 0 else 0
    dt_total = f.get("DT tid per man (sek)", 0) * män
    rad["DT total tid (sek)"] = dt_total
    total_tid = f.get("Scenens längd (h)", 0) * 3600 + dt_total
    rad["Total tid (sek)"] = total_tid
    rad["Total tid (h)"] = round(total_tid / 3600, 2)
    rad["Minuter per kille"] = round(total_tid / max(1, män) / 60, 2)
    return rad

def slumpa_andel(antal, min_andel, max_andel):
    return random.randint(round(antal * min_andel), round(antal * max_andel))

def fördela_heltal(totalt, dagar):
    bas = totalt // dagar
    rester = totalt % dagar
    lst = [bas] * dagar
    for i in random.sample(range(dagar), rester):
        lst[i] += 1
    return lst

def räkna_prenumeranter(f):
    enkel = f.get("Enkel vaginal", 0) + f.get("Enkel anal", 0)
    dubbel = f.get("DP", 0) + f.get("DPP", 0) + f.get("DAP", 0)
    trippel = f.get("TPA", 0) + f.get("TPP", 0) + f.get("TAP", 0)
    return enkel * 1 + dubbel * 5 + trippel * 8
