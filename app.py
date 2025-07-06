import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Kalkylark och blad
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Alla fält vi förväntar oss i rätt ordning
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v", "Klockan",
    "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar", "Nils kom", "Pv",
    "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet",
    "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    # Om tomt ark: skapa rubriker
    if worksheet.cell(1, 1).value != "Dag":
        worksheet.clear()
        worksheet.append_row(HEADERS)

    # Ladda data
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Säkerställ att alla kolumner finns
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""

    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(HEADERS)
    rows = df[HEADERS].values.tolist()
    for row in rows:
        worksheet.append_row(row)

def next_day(last_day_str):
    last_day = datetime.datetime.strptime(last_day_str, "%Y-%m-%d")
    return (last_day + datetime.timedelta(days=1)).date().isoformat()

def main():
    st.title("📘 MalinApp - Daglig logg och analys")

    worksheet, df = load_data()

    # Förifyllt nästa dag
    today = next_day(df["Dag"].iloc[-1]) if not df.empty else datetime.date.today().isoformat()

    with st.form("data_entry_form"):
        st.subheader("📥 Mata in dagens värden")

        input_data = {
            "Dag": st.date_input("Dag", value=pd.to_datetime(today)).isoformat(),
            "Män": st.number_input("Män", value=0),
            "F": st.number_input("F", value=0),
            "R": st.number_input("R", value=0),
            "Dm": st.number_input("Dm", value=0),
            "Df": st.number_input("Df", value=0),
            "Dr": st.number_input("Dr", value=0),
            "3f": st.number_input("3f", value=0),
            "3r": st.number_input("3r", value=0),
            "3p": st.number_input("3p", value=0),
            "Tid s": st.number_input("Tid s", value=0.0),
            "Tid d": st.number_input("Tid d", value=0.0),
            "Tid t": st.number_input("Tid t", value=0.0),
            "Vila": st.number_input("Vila", value=0.0),
            "Älskar": st.number_input("Älskar", value=0),
            "Älsk tid": st.number_input("Älsk tid", value=0.0),
            "Sover med": st.number_input("Sover med", value=0),
            "Jobb": st.number_input("Jobb", value=0),
            "Grannar": st.number_input("Grannar", value=0),
            "Nils kom": st.number_input("Nils kom", value=0),
            "Pv": st.number_input("Pv", value=0),
            "Svarta": st.number_input("Svarta", value=0),
        }

        submitted = st.form_submit_button("Spara rad")

        if submitted:
            row = input_data.copy()
            row["Summa s"] = row["Tid s"]
            row["Summa d"] = row["Tid d"]
            row["Summa t"] = row["Tid t"]
            row["Summa v"] = row["Vila"]
            row["Klockan"] = "07:00"
            row["Känner"] = row["Jobb"] + row["Grannar"] + row["Pv"] + row["Nils kom"]
            row["Tid kille"] = row["Tid s"] + row["Tid d"]
            row["Filmer"] = 1 if row["Män"] > 0 else 0
            row["Pris"] = 19.99
            row["Intäkter"] = row["Filmer"] * row["Pris"]
            row["Malin"] = row["Älskar"]
            row["Företag"] = row["Jobb"]
            row["Vänner"] = row["Känner"]
            row["Hårdhet"] = row["Män"] + row["F"]
            row["GB"] = row["Jobb"] + row["Grannar"] + row["Pv"] + row["Nils kom"]

            df = df.append(row, ignore_index=True)
            save_data(worksheet, df)
            st.success("Raden har sparats!")

    # Nyckeltal
    st.subheader("📊 Nyckeltal")

    if not df.empty:
        total_filmer = df[df["Män"] > 0].shape[0]
        snitt_film = (df["Män"].sum() + df["GB"].sum()) / total_filmer if total_filmer > 0 else 0

        max_jobb = df["Jobb"].max()
        max_grannar = df["Grannar"].max()
        max_pv = df["Pv"].max()
        max_nils = df["Nils kom"].max()
        total_känner = max_jobb + max_grannar + max_pv + max_nils

        malin_tjänat = df["Intäkter"].sum() / total_känner if total_känner > 0 else 0
        gb_snitt = df["GB"].sum() / total_känner if total_känner > 0 else 0

        vita_n = df["Män"].sum() + df["GB"].sum()
        svarta_n = df["Svarta"].sum()
        vita_proc = ((vita_n - svarta_n) / (vita_n + svarta_n)) * 100 if (vita_n + svarta_n) > 0 else 0
        svarta_proc = (svarta_n / (vita_n + svarta_n)) * 100 if (vita_n + svarta_n) > 0 else 0

        st.metric("🎬 Snitt film", f"{snitt_film:.2f}")
        st.metric("💰 Malin tjänat", f"{malin_tjänat:.2f} kr")
        st.metric("📦 GB snitt", f"{gb_snitt:.2f}")
        st.metric("⚪ Vita (%)", f"{vita_proc:.2f}%")
        st.metric("⚫ Svarta (%)", f"{svarta_proc:.2f}%")
        st.caption(f"Max Jobb: {max_jobb}, Grannar: {max_grannar}, Pv: {max_pv}, Nils kom: {max_nils}")

if __name__ == "__main__":
    main()
