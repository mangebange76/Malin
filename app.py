import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import math

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

def load_data():
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Säkerställ att alla kolumner finns
    expected_cols = [
        "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR",
        "TPP", "TAP", "TPA", "Älskar", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
        "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
        "Svarta"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0

    # Konvertera numeriska fält till tal
    for col in expected_cols[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return worksheet, df

def save_data(worksheet, df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def calculate_fields(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt Män"] = df["Män"] + df["Känner"]

    df["Summa singel"] = (df["Fi"] + df["Rö"]) * df["Tid Singel"]
    df["Summa dubbel"] = (df["DM"] + df["DF"] + df["DR"]) * df["Tid Dubbel"]
    df["Summa trippel"] = (df["TPP"] + df["TAP"] + df["TPA"]) * df["Tid Trippel"]

    df["Summa vila"] = (
        df["Totalt Män"] * df["Vila"] +
        (df["DM"] + df["DF"] + df["DR"]) * (df["Vila"] + 7) +
        (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)
    )

    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]
    df["Klockan"] = (pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(df["Summa tid"], unit='s')).dt.strftime("%H:%M")

    df["Tid kille"] = (
        df["Summa singel"] +
        df["Summa dubbel"] * 2 +
        df["Summa trippel"] * 3
    ) / df["Totalt Män"]
    df["Tid kille"] = df["Tid kille"].fillna(0).apply(lambda x: round(x / 60, 1))  # i minuter

    df["Filmer"] = (
        df["Män"] + df["Fi"] + df["Rö"] * 2 +
        df["DM"] * 2 + df["DF"] * 3 + df["DR"] * 4 +
        df["TPP"] * 5 + df["TAP"] * 7 + df["TPA"] * 6
    )
    df["Intäkter"] = df["Filmer"] * 19.99
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 1500))
    df["Företag lön"] = df["Intäkter"] * 0.40
    df["Vänner lön"] = df["Intäkter"] - df["Malin lön"] - df["Företag lön"]

    return df

def main():
    st.title("📊 MalinData - Översikt")

    worksheet, df = load_data()
    df = calculate_fields(df)

    if df.empty:
        st.warning("Inga data finns ännu.")
        return

    # Huvudvy
    st.header("🔹 Huvudvy")
    total_män = df["Män"].sum()
    total_känner = df["Känner"].sum()
    snitt = round((total_män + total_känner) / len(df), 1)

    total_intäkter = df["Intäkter"].sum()
    total_malin = df["Malin lön"].sum()
    total_vänner = df["Vänner lön"].sum()

    svart = df["Svarta"].sum()
    vita_pct = round((total_män - svart) / total_män * 100, 1) if total_män > 0 else 0
    svarta_pct = round(svart / total_män * 100, 1) if total_män > 0 else 0

    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils Fam"].max()

    gangB = round(total_känner / (jobb2 + grannar2 + tjej2 + fam2), 2) if (jobb2 + grannar2 + tjej2 + fam2) > 0 else 0
    älskar_total = df["Älskar"].sum()
    älskat = round(älskar_total / (jobb2 + grannar2 + tjej2 + fam2), 2) if (jobb2 + grannar2 + tjej2 + fam2) > 0 else 0

    st.markdown(f"""
    **Totalt Män:** {total_män}  
    **Snitt (Män + Känner):** {snitt}  
    **Malin lön (USD):** {total_malin:.2f}  
    **Vänner lön (USD):** {total_vänner:.2f}  
    **Intäkter (USD):** {total_intäkter:.2f}  
    **GangB:** {gangB}  
    **Älskat:** {älskat}  
    **Vita (%):** {vita_pct}%  
    **Svarta (%):** {svarta_pct}%  
    """)

    # Radvy
    st.header("🔹 Radvy")
    selected_index = st.selectbox("Välj rad", range(len(df)))
    row = df.iloc[selected_index]

    st.markdown(f"""
    **Datum:** {row['Datum']}  
    **Tid kille (min):** {row['Tid kille']}  
    **Filmer:** {row['Filmer']}  
    **Intäkter (USD):** {row['Intäkter']:.2f}  
    **Klockan:** {row['Klockan']}  
    """)

if __name__ == "__main__":
    main()
