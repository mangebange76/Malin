import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# Autentisering
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(credentials, scopes=scopes)
gc = gspread.authorize(creds)

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Rubriker
COLUMNS = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Älskar med",
    "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2", "Tjej PojkV", "Tjej PojkV 2",
    "Nils fam", "Nils fam 2", "Totalt män", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid", "Klockan",
    "Tid kille", "Suger", "Filmer", "Pris", "Intäkter", "Malin lön", "Företag lön", "Vänner lön", "Hårdhet"
]

# Ladda data
def load_data():
    try:
        sh = gc.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(SHEET_NAME)
    try:
        worksheet = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Om fel rubriker – skapa nya
    if df.empty or list(df.columns) != COLUMNS:
        worksheet.clear()
        worksheet.append_row(COLUMNS)
        df = pd.DataFrame(columns=COLUMNS)

    return worksheet, df

# Spara data
def save_data(worksheet, df):
    worksheet.clear()
    worksheet.update([df.columns.tolist()] + df.values.tolist())

def main():
    st.title("📊 Malin Analysapp – Daglig Logg")

    worksheet, df = load_data()

    with st.form("data_input_form"):
        today = datetime.date.today()
        ny_rad = {}

        ny_rad["Datum"] = st.date_input("Datum", today)
        ny_rad["Män"] = st.number_input("Män", min_value=0, step=1)
        ny_rad["Fi"] = st.number_input("Fi", min_value=0, step=1)
        ny_rad["Rö"] = st.number_input("Rö", min_value=0, step=1)
        ny_rad["DM"] = st.number_input("DM", min_value=0, step=1)
        ny_rad["DF"] = st.number_input("DF", min_value=0, step=1)
        ny_rad["DR"] = st.number_input("DR", min_value=0, step=1)
        ny_rad["TPP"] = st.number_input("TPP", min_value=0, step=1)
        ny_rad["TAP"] = st.number_input("TAP", min_value=0, step=1)
        ny_rad["TPA"] = st.number_input("TPA", min_value=0, step=1)
        ny_rad["Älskar med"] = st.number_input("Älskar med", min_value=0, step=1)
        ny_rad["Sover med"] = st.number_input("Sover med", min_value=0, step=1)
        ny_rad["Jobb"] = st.number_input("Jobb", min_value=0, step=1)
        ny_rad["Grannar"] = st.number_input("Grannar", min_value=0, step=1)
        ny_rad["Tjej PojkV"] = st.number_input("Tjej PojkV", min_value=0, step=1)
        ny_rad["Nils fam"] = st.number_input("Nils fam", min_value=0, step=1)
        ny_rad["Tid Singel"] = st.number_input("Tid Singel (sek)", min_value=0, step=1)
        ny_rad["Tid Dubbel"] = st.number_input("Tid Dubbel (sek)", min_value=0, step=1)
        ny_rad["Tid Trippel"] = st.number_input("Tid Trippel (sek)", min_value=0, step=1)
        ny_rad["Vila"] = st.number_input("Vila (sek)", min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")

    if submitted:
        # Beräkningar
        ny_rad["Känner"] = ny_rad["Jobb"] + ny_rad["Grannar"] + ny_rad["Tjej PojkV"] + ny_rad["Nils fam"]
        ny_rad["Totalt män"] = ny_rad["Män"] + ny_rad["Känner"]

        ny_rad["Summa singel"] = ny_rad["Tid Singel"] * ny_rad["Totalt män"]
        ny_rad["Summa dubbel"] = ny_rad["Tid Dubbel"] * ny_rad["Totalt män"]
        ny_rad["Summa trippel"] = ny_rad["Tid Trippel"] * ny_rad["Totalt män"]

        ny_rad["Summa vila"] = (
            ny_rad["Vila"] * ny_rad["Totalt män"] +
            ny_rad["DM"] * (ny_rad["Vila"] + 10) +
            ny_rad["DF"] * (ny_rad["Vila"] + 15) +
            ny_rad["DR"] * (ny_rad["Vila"] + 15) +
            ny_rad["TPP"] * (ny_rad["Vila"] + 15) +
            ny_rad["TAP"] * (ny_rad["Vila"] + 15) +
            ny_rad["TPA"] * (ny_rad["Vila"] + 15)
        )

        ny_rad["Summa tid"] = ny_rad["Summa singel"] + ny_rad["Summa dubbel"] + ny_rad["Summa trippel"] + ny_rad["Summa vila"]

        klockslag = (datetime.datetime.combine(datetime.date.today(), datetime.time(7, 0)) + datetime.timedelta(seconds=ny_rad["Summa tid"])).time()
        ny_rad["Klockan"] = klockslag.strftime("%H:%M")

        tid_kille = (
            ny_rad["Summa singel"] +
            ny_rad["Summa dubbel"] * 2 +
            ny_rad["Summa trippel"] * 3
        ) / ny_rad["Totalt män"]
        ny_rad["Tid kille"] = round(tid_kille / 60, 2)

        suger = 0.6 * (ny_rad["Summa singel"] + ny_rad["Summa dubbel"] + ny_rad["Summa trippel"]) / ny_rad["Totalt män"]
        ny_rad["Suger"] = round(suger, 2)
        ny_rad["Tid kille"] += round(suger / 60, 2)

        filmer = (
            ny_rad["Män"] + ny_rad["Fi"] + ny_rad["Rö"] * 2 + ny_rad["DM"] * 2 +
            ny_rad["DF"] * 3 + ny_rad["DR"] * 4 + ny_rad["TPP"] * 5 +
            ny_rad["TAP"] * 7 + ny_rad["TPA"] * 6
        )
        ny_rad["Filmer"] = filmer

        ny_rad["Hårdhet"] = filmer  # kan justeras senare
        ny_rad["Pris"] = 19.99
        ny_rad["Intäkter"] = round(filmer * ny_rad["Pris"], 2)
        ny_rad["Malin lön"] = min(ny_rad["Intäkter"] * 0.01, 1500)
        ny_rad["Företag lön"] = ny_rad["Intäkter"] * 0.4
        ny_rad["Vänner lön"] = ny_rad["Intäkter"] - ny_rad["Malin lön"] - ny_rad["Företag lön"]

        # Högsta värden
        ny_rad["Jobb 2"] = max(ny_rad["Jobb"], df["Jobb"].max() if not df.empty else 0)
        ny_rad["Grannar 2"] = max(ny_rad["Grannar"], df["Grannar"].max() if not df.empty else 0)
        ny_rad["Tjej PojkV 2"] = max(ny_rad["Tjej PojkV"], df["Tjej PojkV"].max() if not df.empty else 0)
        ny_rad["Nils fam 2"] = max(ny_rad["Nils fam"], df["Nils fam"].max() if not df.empty else 0)
        ny_rad["Känner 2"] = max(ny_rad["Känner"], df["Känner"].max() if not df.empty else 0)

        # Lägg till ny rad
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Raden sparades!")

    # Visa nyckeltal
    if not df.empty:
        st.subheader("📈 Maxvärden:")
        st.metric("Jobb 2", df["Jobb 2"].max())
        st.metric("Grannar 2", df["Grannar 2"].max())
        st.metric("Tjej PojkV 2", df["Tjej PojkV 2"].max())
        st.metric("Nils fam 2", df["Nils fam 2"].max())
        st.metric("Känner 2", df["Känner 2"].max())

if __name__ == "__main__":
    main()
