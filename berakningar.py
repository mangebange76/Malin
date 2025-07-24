from datetime import timedelta
import random
from konstanter import COLUMNS

def process_lägg_till_rader(df, inst, f):
    ny_rad = {col: 0 for col in COLUMNS}

    ny_rad["Typ"] = f.get("Typ", "")
    ny_rad["Antal vilodagar"] = f.get("Antal vilodagar", 0)
    ny_rad["Scenens längd (h)"] = f.get("Scenens längd (h)", 0)
    ny_rad["Övriga män"] = f.get("Övriga män", 0)

    for nyckel in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
                   "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
                   "DT tid per man (sek)", "Älskar med", "Sover med"]:
        ny_rad[nyckel] = f.get(nyckel, 0)

    # Tid och beräkningar
    tid_per_kille_min, total_tid_h = beräkna_tid_per_kille(f)
    ny_rad["Minuter per kille"] = round(tid_per_kille_min, 2)
    ny_rad["Total tid (h)"] = round(total_tid_h, 2)
    ny_rad["Total tid (sek)"] = int(total_tid_h * 3600)
    ny_rad["DT total tid (sek)"] = ny_rad["DT tid per man (sek)"] * sum([
        ny_rad["Enkel vaginal"], ny_rad["Enkel anal"], ny_rad["DP"],
        ny_rad["DPP"], ny_rad["DAP"], ny_rad["TPP"], ny_rad["TPA"], ny_rad["TAP"]
    ])

    ny_rad["Datum"] = bestäm_datum(df, inst)

    return df.append(ny_rad, ignore_index=True)

def beräkna_tid_per_kille(f):
    base_tid_min = (
        f.get("Enkel vaginal", 0) +
        f.get("Enkel anal", 0) +
        f.get("DP", 0) * 2 +
        f.get("DPP", 0) * 2 +
        f.get("DAP", 0) * 2 +
        f.get("TPP", 0) * 3 +
        f.get("TPA", 0) * 3 +
        f.get("TAP", 0) * 3
    ) * 30

    dt_tid = f.get("DT tid per man (sek)", 0)
    antal_män = sum([
        f.get("Enkel vaginal", 0),
        f.get("Enkel anal", 0),
        f.get("DP", 0) * 2,
        f.get("DPP", 0) * 2,
        f.get("DAP", 0) * 2,
        f.get("TPP", 0) * 3,
        f.get("TPA", 0) * 3,
        f.get("TAP", 0) * 3,
    ])

    total_tid_min = base_tid_min + (antal_män * dt_tid / 60)
    tid_per_kille = total_tid_min / max(antal_män, 1)

    return tid_per_kille, total_tid_min / 60  # minuter, timmar

def bestäm_datum(df, inst):
    if df.empty:
        startdatum = inst.get("Startdatum")
        if isinstance(startdatum, str):
            try:
                return str(pd.to_datetime(startdatum).date())
            except:
                return str(pd.Timestamp.today().date())
        return str(pd.Timestamp.today().date())
    else:
        senaste = pd.to_datetime(df["Datum"], errors="coerce").dropna()
        if senaste.empty:
            return str(pd.Timestamp.today().date())
        return str((senaste.max() + timedelta(days=1)).date())
