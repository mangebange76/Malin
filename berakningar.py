import pandas as pd
from datetime import datetime, timedelta
from konstanter import COLUMNS, säkerställ_kolumner, bestäm_datum

def beräkna_tid_per_kille(f):
    totala_män = (
        f.get("Övriga män", 0)
        + f.get("Enkel vaginal", 0)
        + f.get("Enkel anal", 0)
        + f.get("DP", 0) * 2
        + f.get("DPP", 0) * 2
        + f.get("DAP", 0) * 2
        + f.get("TPP", 0) * 3
        + f.get("TPA", 0) * 3
        + f.get("TAP", 0) * 3
        + f.get("Kompisar", 0)
        + f.get("Pappans vänner", 0)
        + f.get("Nils vänner", 0)
        + f.get("Nils familj", 0)
    )

    dt_tid_per_man = f.get("DT tid per man (sek)", 0)
    dt_total_tid = totala_män * dt_tid_per_man
    älskar_tid = f.get("Älskar med", 0) * 1800  # 30 minuter i sekunder
    total_tid = dt_total_tid + älskar_tid

    minuter_per_kille = (dt_tid_per_man / 60) if totala_män else 0
    total_tid_h = total_tid / 3600

    return minuter_per_kille, total_tid_h

def process_lägg_till_rader(df, inst, f):
    f = f.copy()

    # Beräkningar
    minuter_per_kille, total_tid_h = beräkna_tid_per_kille(f)
    dt_total_tid = f.get("DT tid per man (sek)", 0) * (
        f.get("Övriga män", 0)
        + f.get("Enkel vaginal", 0)
        + f.get("Enkel anal", 0)
        + f.get("DP", 0) * 2
        + f.get("DPP", 0) * 2
        + f.get("DAP", 0) * 2
        + f.get("TPP", 0) * 3
        + f.get("TPA", 0) * 3
        + f.get("TAP", 0) * 3
        + f.get("Kompisar", 0)
        + f.get("Pappans vänner", 0)
        + f.get("Nils vänner", 0)
        + f.get("Nils familj", 0)
    )
    total_tid = dt_total_tid + f.get("Älskar med", 0) * 1800

    ny_rad = {
        "Datum": bestäm_datum(df, inst),
        "Typ": f.get("Typ", ""),
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
        "Prenumeranter": f.get("Prenumeranter", 0),
        "Intäkt ($)": f.get("Intäkt ($)", 0),
        "Kvinnans lön ($)": f.get("Kvinnans lön ($)", 0),
        "Mäns lön ($)": f.get("Mäns lön ($)", 0),
        "Kompisars lön ($)": f.get("Kompisars lön ($)", 0),
        "DT total tid (sek)": dt_total_tid,
        "Total tid (sek)": total_tid,
        "Total tid (h)": total_tid / 3600,
        "Minuter per kille": minuter_per_kille,
    }

    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    df = säkerställ_kolumner(df)
    return df
