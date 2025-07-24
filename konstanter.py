from datetime import datetime, timedelta
import pandas as pd

# Kolumner i exakt den ordning du specificerat
COLUMNS = [
    "Datum", "Typ", "Antal vilodagar", "Nya män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
    "Tid enkel", "Tid dubbel", "Tid trippel",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man", "Antal varv", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille", "Vila"
]

def säkerställ_kolumner(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[COLUMNS]

def bestäm_datum(df, inst):
    """Returnerar rätt datum för nästa rad."""
    if df.empty:
        startdatum = inst.get("Startdatum")
        if isinstance(startdatum, str):
            try:
                return datetime.strptime(startdatum, "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                pass
        return datetime.today().strftime("%Y-%m-%d")
    else:
        senaste_datum = df["Datum"].iloc[-1]
        try:
            senaste = pd.to_datetime(senaste_datum, errors="coerce")
            if pd.isna(senaste):
                return datetime.today().strftime("%Y-%m-%d")
            nästa = senaste + timedelta(days=1)
            return nästa.strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")
