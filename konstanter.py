from datetime import datetime, timedelta
import pandas as pd

COLUMNS = [
    "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
]

def säkerställ_kolumner(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[COLUMNS]

def bestäm_datum(df, inst):
    if df.empty:
        start = inst.get("Startdatum", datetime.today().strftime("%Y-%m-%d"))
        try:
            return datetime.strptime(start, "%Y-%m-%d").strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")
    senaste = pd.to_datetime(df["Datum"].iloc[-1], errors="coerce")
    if pd.isna(senaste):
        return datetime.today().strftime("%Y-%m-%d")
    return (senaste + timedelta(days=1)).strftime("%Y-%m-%d")
