COLUMNS = [
    "Datum", "Typ", "Antal vilodagar", "Nya män", "Enkel vaginal", "Enkel anal",
    "DP", "DPP", "DAP", "TPP", "TPA", "TAP", "Tid enkel", "Tid dubbel",
    "Tid trippel", "Vila",  # ← "Vila" flyttad hit
    "Kompisar", "Pappans vänner", "Nils vänner", "Nils familj",
    "DT tid per man", "Antal varv", "Älskar med", "Sover med", "Nils sex",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "DT total tid (sek)", "Total tid (sek)", "Total tid (h)", "Minuter per kille"
]

def säkerställ_kolumner(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS]
