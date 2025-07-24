from datetime import datetime
from konstanter import COLUMNS

def beräkna_tid_per_kille(f):
    multiplar = {
        "Enkel vaginal": 1,
        "Enkel anal": 1,
        "DP": 2,
        "DPP": 2,
        "DAP": 2,
        "TPP": 3,
        "TPA": 3,
        "TAP": 3
    }
    antal_killar = sum(f.get(k, 0) * v for k, v in multiplar.items()) + f.get("Övriga män", 0)
    dt_tid = f.get("DT tid per man (sek)", 0)
    total_dt_tid = antal_killar * dt_tid
    älskar_tid = f.get("Älskar med", 0) * 1800  # 30 min per tillfälle
    total_tid = total_dt_tid + älskar_tid
    total_tid_h = total_tid / 3600
    minuter_per_kille = (total_tid / antal_killar / 60) if antal_killar else 0
    return minuter_per_kille, total_tid_h

def process_lägg_till_rader(df, inst, f):
    ny_rad = {
        "Datum": datetime.today().strftime("%Y-%m-%d"),
        "Typ": f.get("Typ"),
        "Scenens längd (h)": f.get("Scenens längd (h)", 0),
        "Antal vilodagar": f.get("Antal vilodagar", 0),
        "Övriga män": f.get("Övriga män", 0),
        "Enkel vaginal": f.get("Enkel vaginal", 0),
        "Enkel anal": f.get("Enkel anal", 0),
        "DP": f.get("DP", 0),
        "DPP": f.get("DPP", 0),
        "DAP": f.get("DAP", 0),
        "TPP": f.get("TPP", 0),
        "TPA": f.get("TPA", 0),
        "TAP": f.get("TAP", 0),
        "Kompisar": f.get("Kompisar", 0),
        "Pappans vänner": f.get("Pappans vänner", 0),
        "Nils vänner": f.get("Nils vänner", 0),
        "Nils familj": f.get("Nils familj", 0),
        "DT tid per man (sek)": f.get("DT tid per man (sek)", 0),
        "Älskar med": f.get("Älskar med", 0),
        "Sover med": f.get("Sover med", 0),
        "Nils sex": f.get("Nils sex", 0),
        "Prenumeranter": 0,
        "Intäkt ($)": 0,
        "Kvinnans lön ($)": 0,
        "Mäns lön ($)": 0,
        "Kompisars lön ($)": 0,
        "DT total tid (sek)": 0,
        "Total tid (sek)": 0,
        "Total tid (h)": 0,
        "Minuter per kille": 0
    }

    minuter, timmar = beräkna_tid_per_kille(f)
    antal_killar = sum(f.get(k, 0) * v for k, v in {
        "Enkel vaginal": 1,
        "Enkel anal": 1,
        "DP": 2,
        "DPP": 2,
        "DAP": 2,
        "TPP": 3,
        "TPA": 3,
        "TAP": 3
    }.items()) + f.get("Övriga män", 0)

    ny_rad["DT total tid (sek)"] = f.get("DT tid per man (sek)", 0) * antal_killar
    ny_rad["Total tid (sek)"] = ny_rad["DT total tid (sek)"] + f.get("Älskar med", 0) * 1800
    ny_rad["Total tid (h)"] = ny_rad["Total tid (sek)"] / 3600
    ny_rad["Minuter per kille"] = minuter

    # Säkerställ rätt kolumnordning
    ny_rad = {col: ny_rad.get(col, 0) for col in COLUMNS}
    df.loc[len(df)] = ny_rad
    return df
