import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Autentisering ---
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    return gspread.authorize(creds)

# --- Ladda data ---
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# --- Spara ny rad ---
def append_row(worksheet, row):
    worksheet.append_row(row)

# --- Hämta maxvärden för varje relevant kolumn ---
def get_max_values(df):
    return {
        "Jobb": df["Jobb"].max() if not df["Jobb"].isna().all() else 0,
        "Grannar": df["Grannar"].max() if not df["Grannar"].isna().all() else 0,
        "Tjej PojkV": df["Tjej PojkV"].max() if not df["Tjej PojkV"].isna().all() else 0,
        "Nils Fam": df["Nils Fam"].max() if not df["Nils Fam"].isna().all() else 0,
    }

# --- Funktion för slumpknapp ---
def generate_random_row(df):
    max_vals = {col: df[col].max() for col in df.columns if df[col].dtype != "O"}
    new_row = {
        col: random.randint(0, int(max_vals.get(col, 1))) for col in df.columns
        if col not in ["Älskar", "Sover med", "Vila", "Älsk tid", "Dag"]
    }
    new_row["Älskar"] = 8
    new_row["Sover med"] = 1
    new_row["Vila"] = 7
    new_row["Älsk tid"] = 30
    new_row["Dag"] = datetime.today().strftime("%Y-%m-%d")
    return [new_row.get(col, 0) for col in df.columns]

# --- UI och app-logik ---
def main():
    st.title("Malin-appen")

    worksheet, df = load_data()

    # Huvudvy: Visa nyckeldata och beräkningar
    st.header("📊 Huvudvy")
    if not df.empty:
        df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
        totalt_män = df["Män"].sum()
        totalt_känner = df["Känner"].sum()
        gangb = round(totalt_känner / max(get_max_values(df).values()), 2)
        älskat = round(df["Älskar"].sum() / totalt_känner, 2) if totalt_känner else 0
        snitt = round((totalt_män + totalt_känner) / df.shape[0], 2)
        kompisar = sum(get_max_values(df).values())
        sovermed_kvot = round(df["Sover med"].sum() / get_max_values(df)["Nils Fam"], 2) if get_max_values(df)["Nils Fam"] else 0

        st.write(f"Totalt Män: {totalt_män}")
        st.write(f"Totalt Känner: {totalt_känner}")
        st.write(f"Snitt (Män + Känner): {snitt}")
        st.write(f"GangB: {gangb}")
        st.write(f"Älskat: {älskat}")
        st.write(f"Kompisar: {kompisar}")
        st.write(f"Sover med/Nils Fam 2: {sovermed_kvot}")

    # Radvyn: Visa varje rad med tid kille
    st.header("📋 Rader")
    for i, rad in df.iterrows():
        st.subheader(f"Rad {i+1}")
        tid_kille = rad["Tid s"] + rad["Tid d"] + rad["Tid t"]
        st.write(f"Totalt Tid kille: {tid_kille:.2f} minuter")
        if tid_kille < 10:
            st.error("⚠️ Tid kille är under 10 minuter – bör ökas!")

    # Knappar för att lägga till ny rad
    st.header("➕ Lägg till ny data")
    if st.button("Slumpa ny rad"):
        new_row = generate_random_row(df)
        append_row(worksheet, new_row)
        st.success("Slumpmässig rad tillagd!")

if __name__ == "__main__":
    main()
