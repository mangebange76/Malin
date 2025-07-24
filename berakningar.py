from konstanter import COLUMNS
import pandas as pd

def beräkna_tid_per_kille(f):
    antal_män = (
        f.get("Övriga män", 0)
        + sum(f.get(k, 0) for k in ["Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP"])
    )
    dt_tid = f.get("DT tid per man (sek)", 0)
    dt_total = antal_män * dt_tid
    annan_tid = f.get("Scenens längd (h)", 0) * 3600
    total_tid = dt_total + annan_tid
    minuter_per_kille = (total_tid / 60) / max(antal_män, 1)
    return minuter_per_kille, total_tid / 3600

def process_lägg_till_rader(df, inst, f):
    ny_rad = {k: f.get(k, 0) for k in COLUMNS}
    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    return df
