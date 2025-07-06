import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Inställningar
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit"
SHEET_NAME = "Blad1"

# Förväntade kolumner
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v",
    "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar", "Nils kom",
    "Pv", "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet",
    "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    data = worksheet.get_all_values()

    # Rensa dubbletter av rubriker
    if len(data) >= 2 and data[0] == data[1]:
        worksheet.delete_rows(2)

    # Återskapa rubrik om fel eller saknas
    if not data or data[0] != HEADERS:
        worksheet.clear()
        worksheet.append_row(HEADERS)
        return worksheet, pd.DataFrame(columns=HEADERS)

    df = pd.DataFrame(worksheet.get_all_records())
    df = df[[col for col in HEADERS if col in df.columns]]
    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(HEADERS)
    rows = df.fillna("").astype(str).values.tolist()
    worksheet.append_rows(rows)

def main():
    st.title("📊 Daglig Data – Malin")
    worksheet, df = load_data()

    today = (pd.to_datetime(df["Dag"], errors='coerce').max() + pd.Timedelta(days=1)).date() if not df.empty else datetime.date.today()

    with st.form("data_form"):
        st.subheader("➕ Ny post")

        ny_dag = st.date_input("Dag", today)
        ny_rad = {
            "Dag": ny_dag.strftime("%Y-%m-%d"),
            "Män": st.number_input("Män", step=1),
            "F": st.number_input("F", step=1),
            "R": st.number_input("R", step=1),
            "Dm": st.number_input("Dm", step=1),
            "Df": st.number_input("Df", step=1),
            "Dr": st.number_input("Dr", step=1),
            "3f": st.number_input("3f", step=1),
            "3r": st.number_input("3r", step=1),
            "3p": st.number_input("3p", step=1),
            "Tid s": st.number_input("Tid s", step=1),
            "Tid d": st.number_input("Tid d", step=1),
            "Tid t": st.number_input("Tid t", step=1),
            "Vila": st.number_input("Vila", step=1),
            "Älskar": st.number_input("Älskar", step=1),
            "Älsk tid": st.number_input("Älsk tid", step=1),
            "Sover med": st.number_input("Sover med", step=1),
            "Jobb": st.number_input("Jobb", step=1),
            "Grannar": st.number_input("Grannar", step=1),
            "Nils kom": st.number_input("Nils kom", step=1),
            "Pv": st.number_input("Pv", step=1),
            "Svarta": st.number_input("Svarta", step=1),
        }

        submitted = st.form_submit_button("Spara")

    if submitted:
        # Beräkningar
        ny_rad["Summa s"] = ny_rad["Tid s"] + ny_rad["Tid d"]
        ny_rad["Summa d"] = ny_rad["Tid t"]
        ny_rad["Summa t"] = ny_rad["Summa s"] + ny_rad["Summa d"]
        ny_rad["Summa v"] = ny_rad["Vila"]
        ny_rad["Klockan"] = "07:00"
        ny_rad["Känner"] = ny_rad["Jobb"] + ny_rad["Grannar"] + ny_rad["Nils kom"] + ny_rad["Pv"]
        ny_rad["Tid kille"] = ny_rad["Älsk tid"] + ny_rad["Sover med"]
        ny_rad["Filmer"] = ny_rad["Män"] + ny_rad["GB"]
        ny_rad["Pris"] = 19.99
        ny_rad["Intäkter"] = ny_rad["Filmer"] * ny_rad["Pris"]
        ny_rad["Malin"] = ny_rad["Älskar"] + ny_rad["Älsk tid"]
        ny_rad["Företag"] = ny_rad["Jobb"]
        ny_rad["Vänner"] = ny_rad["Känner"]
        ny_rad["Hårdhet"] = ny_rad["Män"] + ny_rad["F"] + ny_rad["R"]
        ny_rad["GB"] = ny_rad["Tid d"]

        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Ny rad sparad!")

    if not df.empty:
        st.subheader("📅 Senaste data")
        st.dataframe(df.tail(10), use_container_width=True)

if __name__ == "__main__":
    main()
