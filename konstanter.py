from datetime import datetime, timedelta
import pandas as pd

# Kolumner i rätt ordning
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
    """Returnerar rätt datum för nästa rad."""
    # Om ingen data i df, använd startdatum från inställningar eller dagens datum
    if df.empty:
        startdatum = inst.get("Startdatum")
        if isinstance(startdatum, str):
            try:
                return datetime.strptime(startdatum, "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                pass
        return datetime.today().strftime("%Y-%m-%d")
    else:
        # Ta senaste datum och lägg till en dag
        senaste_datum = df["Datum"].iloc[-1]
        try:
            senaste = pd.to_datetime(senaste_datum, errors="coerce")
            if pd.isna(senaste):
                return datetime.today().strftime("%Y-%m-%d")
            nästa = senaste + timedelta(days=1)
            return nästa.strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")
