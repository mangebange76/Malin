import streamlit as st
import gspread
import pandas as pd
import datetime
import json
from oauth2client.service_account import ServiceAccountCredentials

# Autentisering med Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# Fil- och bladnamn
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Förväntade kolumnrubriker i rätt ordning
EXPECTED_COLUMNS = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR",
    "TPP", "TAP", "TPA", "Älskar med", "Sover med", "Känner", "Jobb", "Jobb 2",
    "Grannar", "Grannar 2", "Tjej PojkV", "Tjej PojkV 2", "Nils fam", "Nils fam 2",
    "Totalt män", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila",
    "Summa tid", "Klockan", "Tid kille", "Suger", "Filmer",
    "Pris", "Intäkter", "Malin lön", "Företag lön", "Vänner lön", "Hårdhet"
]

def load_sheet():
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet(WORKSHEET_NAME)

    # Läs befintliga data
    data = worksheet.get_all_records()

    # Om rubrikerna är fel eller saknas, skriv in dem korrekt
    if not data or list(data[0].keys()) != EXPECTED_COLUMNS:
        worksheet.clear()
        worksheet.append_row(EXPECTED_COLUMNS)
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    else:
        df = pd.DataFrame(data)

    return worksheet, df

def save_data(worksheet, df):
    # Konvertera alla värden till strängar för säker uppdatering
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    worksheet.update("A1", values)

def main():
    st.title("📝 Daglig inmatning – MalinData")

    worksheet, df = load_sheet()

    # Datum: första raden anges manuellt, andra raden föreslås +1 dag
    if df.empty:
        datum = st.date_input("Datum", datetime.date.today())
    else:
        senaste_datum = pd.to_datetime(df["Datum"], errors="coerce").max()
        datum = st.date_input("Datum", (senaste_datum + pd.Timedelta(days=1)).date())

    with st.form("inmatning_form"):
        ny_rad = {"Datum": str(datum)}

        heltalsfält = [
            "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
            "Älskar med", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam"
        ]

        for fält in heltalsfält:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1, value=0)

        sekunder_fält = ["Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila"]
        for fält in sekunder_fält:
            ny_rad[fält] = st.number_input(fält + " (sekunder)", min_value=0, step=1, value=0)

        submitted = st.form_submit_button("Spara")

    if submitted:
        # Fyll övriga kolumner med tomma värden för nu
        for kolumn in EXPECTED_COLUMNS:
            if kolumn not in ny_rad:
                ny_rad[kolumn] = ""

        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Data sparad!")

if __name__ == "__main__":
    main()
