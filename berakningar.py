import math

def process_lägg_till_rader(df, inst, f):
    # Beräkningar för olika scentyper
    ny_rad = {}

    # Hämta datum från inställning eller tidigare rad
    from konstanter import bestäm_datum
    ny_rad["Datum"] = bestäm_datum(df, inst)

    ny_rad["Typ"] = f["Typ"]
    ny_rad["Scenens längd (h)"] = f.get("Scenens längd (h)", 0)
    ny_rad["Antal vilodagar"] = f.get("Antal vilodagar", 0)
    ny_rad["Övriga män"] = f.get("Övriga män", 0)

    for nyckel in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"]:
        ny_rad[nyckel] = f.get(nyckel, 0)

    for nyckel in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
        ny_rad[nyckel] = f.get(nyckel, 0)

    ny_rad["DT tid per man (sek)"] = f.get("DT tid per man (sek)", 0)
    ny_rad["Älskar med"] = f.get("Älskar med", 0)
    ny_rad["Sover med"] = f.get("Sover med", 0)
    ny_rad["Nils sex"] = f.get("Nils sex", 0)

    ny_rad["Prenumeranter"] = f.get("Prenumeranter", 0)
    
    # Intäkt ($) beräknas senare
    ny_rad["Intäkt ($)"] = 0

    # Löner
    ny_rad["Kvinnans lön ($)"] = f.get("Kvinnans lön ($)", 0)
    ny_rad["Mäns lön ($)"] = f.get("Mäns lön ($)", 0)
    ny_rad["Kompisars lön ($)"] = f.get("Kompisars lön ($)", 0)

    # Tid per kille och total tid
    minuter_per_kille, total_tid_h = beräkna_tid_per_kille(f)
    ny_rad["Minuter per kille"] = round(minuter_per_kille, 2)
    ny_rad["Total tid (h)"] = round(total_tid_h, 2)
    ny_rad["Total tid (sek)"] = round(total_tid_h * 3600)
    ny_rad["DT total tid (sek)"] = f.get("DT tid per man (sek)", 0) * total_antal_killar(f)

    return df.append(ny_rad, ignore_index=True)

def total_antal_killar(f):
    return (
        f.get("Enkel vaginal", 0) +
        f.get("Enkel anal", 0) +
        2 * (f.get("DP", 0) + f.get("DPP", 0) + f.get("DAP", 0)) +
        3 * (f.get("TPP", 0) + f.get("TPA", 0) + f.get("TAP", 0)) +
        f.get("Övriga män", 0)
    )

def beräkna_tid_per_kille(f):
    dt_tid = f.get("DT tid per man (sek)", 0)
    älskar_tid = f.get("Älskar med", 0) * 30 * 60  # 30 minuter per älskare
    scen_tid = f.get("Scenens längd (h)", 0) * 3600

    killar = total_antal_killar(f)
    total_tid = scen_tid + älskar_tid + (dt_tid * killar)

    minuter_per_kille = (total_tid / 60 / killar) if killar > 0 else 0
    timmar_total = total_tid / 3600

    return minuter_per_kille, timmar_total
