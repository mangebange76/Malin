import numpy as np
from konstanter import COLUMNS

def process_lägg_till_rader(df, inst, f):
    """Bearbetar en ny rad som användaren fyllt i och lägger till den i DataFrame."""

    ny_rad = {col: 0 for col in COLUMNS}

    ny_rad.update({
        "Datum": f["Datum"],
        "Typ": f["Typ"],
        "Scenens längd (h)": f["Scenens längd (h)"],
        "Antal vilodagar": f.get("Antal vilodagar", 0),
        "Övriga män": f["Övriga män"],
        "Enkel vaginal": f["Enkel vaginal"],
        "Enkel anal": f["Enkel anal"],
        "DP": f["DP"],
        "DPP": f["DPP"],
        "DAP": f["DAP"],
        "TPP": f["TPP"],
        "TPA": f["TPA"],
        "TAP": f["TAP"],
        "Kompisar": f["Kompisar"],
        "Pappans vänner": f["Pappans vänner"],
        "Nils vänner": f["Nils vänner"],
        "Nils familj": f["Nils familj"],
        "DT tid per man (sek)": f["DT tid per man (sek)"],
        "Älskar med": f["Älskar med"],
        "Sover med": f["Sover med"],
        "Nils sex": f["Nils sex"],
        "Prenumeranter": f["Prenumeranter"],
        "Kvinnans lön ($)": f["Kvinnans lön ($)"],
        "Mäns lön ($)": f["Mäns lön ($)"],
        "Kompisars lön ($)": f["Kompisars lön ($)"],
        "Minuter per kille": f["Minuter per kille"],
    })

    # Beräkningar
    dt_total_tid = ny_rad["DT tid per man (sek)"] * ny_rad["Älskar med"]
    total_tid = dt_total_tid + ny_rad["Minuter per kille"] * 60
    total_tid_h = total_tid / 3600

    ny_rad["DT total tid (sek)"] = dt_total_tid
    ny_rad["Total tid (sek)"] = total_tid
    ny_rad["Total tid (h)"] = total_tid_h

    df = df._append(ny_rad, ignore_index=True)
    return df

def konvertera_typer(df):
    """Konverterar kolumner till rätt datatyper."""
    float_cols = [
        "Scenens längd (h)", "DT tid per man (sek)", "DT total tid (sek)",
        "Total tid (sek)", "Total tid (h)", "Minuter per kille",
        "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)", "Intäkt ($)"
    ]
    int_cols = [col for col in df.columns if col not in float_cols and col != "Datum" and col != "Typ"]

    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)
    for col in float_cols:
        df[col] = df[col].fillna(0).astype(float)

    return df
