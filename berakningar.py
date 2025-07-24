from datetime import datetime
from konstanter import COLUMNS, säkerställ_kolumner

def process_lägg_till_rader(df, inst, f):
    ny_rad = {k: f.get(k, 0) for k in COLUMNS}

    if not ny_rad.get("Datum"):
        ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")

    if "Minuter per kille" not in ny_rad or ny_rad["Minuter per kille"] in ["", None]:
        ny_rad["Minuter per kille"] = 0

    for kolumn in COLUMNS:
        if kolumn not in ny_rad:
            ny_rad[kolumn] = 0

    df = df.append(ny_rad, ignore_index=True)
    df = säkerställ_kolumner(df)
    return df

def beräkna_tid_per_kille(f):
    # Enkel beräkning (exempel): justera efter faktisk logik
    total_tid = float(f.get("Scenens längd (h)", 0)) * 3600
    dt_tid = int(f.get("DT tid per man (sek)", 0))
    män = sum([f.get(k, 0) for k in ["DP", "DPP", "DAP", "TPP", "TPA", "TAP"]]) * 2 + f.get("Övriga män", 0)

    män = max(1, män)
    total_tid_kille = total_tid + dt_tid * män
    minuter_per_kille = total_tid_kille / 60 / män
    timmar_total = total_tid_kille / 3600

    return minuter_per_kille, timmar_total
