COLUMNS = [
    "Datum", "Typ", "Scenens längd (h)", "Antal vilodagar", "Övriga män",
    "Enkel vaginal", "Enkel anal", "DP", "DPP", "DAP", "TPP", "TPA", "TAP",
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man (sek)", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
]

def säkerställ_kolumner(df):
    for kolumn in COLUMNS:
        if kolumn not in df.columns:
            df[kolumn] = 0
    return df
