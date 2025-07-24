import pandas as pd
from datetime import datetime
from konstanter import COLUMNS, säkerställ_kolumner

def process_lägg_till_rader(df, inst, f):
    # Skapa ny rad med alla COLUMNS
    ny_rad = {k: f.get(k, 0) for k in COLUMNS}

    # Datum
    if not ny_rad.get("Datum"):
        ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")

    # Säkerställ att "Minuter per kille" finns
    if "Minuter per kille" not in ny_rad or ny_rad["Minuter per kille"] in ["", None]:
        ny_rad["Minuter per kille"] = 0

    # Komplettera alla saknade kolumner med 0
    for kolumn in COLUMNS:
        if kolumn not in ny_rad:
            ny_rad[kolumn] = 0

    # Lägg till raden på korrekt sätt (ersätter .append som är borttaget i Pandas >=2.0)
    ny_rad_df = pd.DataFrame([ny_rad])
    df = pd.concat([df, ny_rad_df], ignore_index=True)

    df = säkerställ_kolumner(df)
    return df

def beräkna_tid_per_kille(f):
    # En förenklad version som du gärna får anpassa
    total_tid = float(f.get("Scenens längd (h)", 0)) * 3600
    dt_tid = int(f.get("DT tid per man (sek)", 0))

    # Räkna antal män enligt dubbel- och trippel-logik
    antalscen = sum([
        f.get("Enkel vaginal", 0), f.get("Enkel anal", 0),
        f.get("DP", 0) * 2, f.get("DPP", 0) * 2, f.get("DAP", 0) * 2,
        f.get("TPP", 0) * 3, f.get("TPA", 0) * 3, f.get("TAP", 0) * 3,
        f.get("Övriga män", 0)
    ])
    antalscen = max(1, antalscen)

    total_tid_kille = total_tid + dt_tid * antalscen
    minuter_per_kille = total_tid_kille / 60 / antalscen
    timmar_total = total_tid_kille / 3600

    return minuter_per_kille, timmar_total
