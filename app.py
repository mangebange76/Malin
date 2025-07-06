import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="MalinData", layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope)
client = gspread.authorize(credentials)

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

ALL_COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med",
    "Känner", "Jobb", "Grannar", "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()

    if not data:
        worksheet.append_row(ALL_COLUMNS)
        return worksheet, pd.DataFrame(columns=ALL_COLUMNS)

    df = pd.DataFrame(data)

    # Om rubriker saknas eller är fel: rensa blad och återskapa
    if list(df.columns) != ALL_COLUMNS:
        worksheet.clear()
        worksheet.append_row(ALL_COLUMNS)
        return worksheet, pd.DataFrame(columns=ALL_COLUMNS)

    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(ALL_COLUMNS)
    rows = df.fillna("").astype(str).values.tolist()
    worksheet.append_rows(rows)

def beräkna_fält(df):
    df["Summa s"] = pd.to_numeric(df["Tid s"], errors="coerce").fillna(0)
    df["Summa d"] = pd.to_numeric(df["Tid d"], errors="coerce").fillna(0)
    df["Summa t"] = pd.to_numeric(df["Tid t"], errors="coerce").fillna(0)
    df["Summa v"] = df["Summa s"] + df["Summa d"] + df["Summa t"]
    df["Klockan"] = "07:00"

    df["Känner"] = df[["Jobb", "Grannar", "Pv", "Nils kom"]].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    df["Tid kille"] = pd.to_numeric(df["Älsk tid"], errors="coerce").fillna(0) + pd.to_numeric(df["Sover med"], errors="coerce").fillna(0)
    df["Filmer"] = (pd.to_numeric(df["Män"], errors="coerce").fillna(0) > 0).astype(int)
    df["Pris"] = 19.99
    df["Intäkter"] = df["Pris"] * df["Filmer"]
    df["Malin"] = df["Älskar"] + df["Sover med"]
    df["Företag"] = df["Jobb"] + df["Grannar"]
    df["Vänner"] = df["Känner"]  # Tidigare "Känner 2"
    df["Hårdhet"] = df[["Män", "GB", "Svarta"]].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    df["GB"] = df[["F", "R"]].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)

    return df

def main():
    st.title("📊 MalinData App")

    worksheet, df = load_data()

    # Inmatning
    with st.form("data_form"):
        st.subheader("➕ Mata in ny rad")

        today = (pd.to_datetime(df["Dag"]).max() + pd.Timedelta(days=1)).date() if not df.empty else datetime.date.today()
        dag = st.date_input("Dag", value=today)

        kol_input = {}
        for kolumn in ALL_COLUMNS:
            if kolumn in ["Dag", "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Känner", "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet", "GB"]:
                continue
            kol_input[kolumn] = st.number_input(kolumn, min_value=0.0, format="%.2f")

        submitted = st.form_submit_button("Lägg till rad")
        if submitted:
            ny_rad = {k: kol_input.get(k, "") for k in ALL_COLUMNS}
            ny_rad["Dag"] = str(dag)

            new_df = pd.DataFrame([ny_rad])
            df = pd.concat([df, new_df], ignore_index=True)

            df = beräkna_fält(df)
            save_data(worksheet, df)
            st.success("✅ Ny rad tillagd och sparad!")

    # Presentation
    if not df.empty:
        df = beräkna_fält(df)
        st.subheader("📈 Senaste data")
        st.dataframe(df.tail(10), use_container_width=True)

        total_män = pd.to_numeric(df["Män"], errors="coerce").fillna(0).sum()
        total_gb = pd.to_numeric(df["GB"], errors="coerce").fillna(0).sum()
        total_svarta = pd.to_numeric(df["Svarta"], errors="coerce").fillna(0).sum()

        total_all = total_män + total_gb + total_svarta
        vita_procent = ((total_män + total_gb - total_svarta) / total_all) * 100 if total_all > 0 else 0
        svarta_procent = (total_svarta / total_all) * 100 if total_all > 0 else 0

        st.metric("Vita (%)", f"{vita_procent:.2f}%")
        st.metric("Svarta (%)", f"{svarta_procent:.2f}%")

if __name__ == "__main__":
    main()
