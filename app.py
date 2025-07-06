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

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Kolumner i rätt ordning
ALL_COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v",
    "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb", "Grannar",
    "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter", "Malin", "Företag",
    "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Säkerställ rubrikraden
    if worksheet.row_count == 0 or worksheet.row_values(1) != ALL_COLUMNS:
        worksheet.clear()
        worksheet.insert_row(ALL_COLUMNS, 1)
        df = pd.DataFrame(columns=ALL_COLUMNS)

    # Lägg till saknade kolumner
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[ALL_COLUMNS]
    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())

def calculate_fields(df, new_row):
    try:
        max_date = pd.to_datetime(df["Dag"], errors="coerce").max()
        today = (max_date + pd.Timedelta(days=1)).date() if not pd.isna(max_date) else datetime.date.today()
    except:
        today = datetime.date.today()

    # Automatisk beräkning
    new_row["Dag"] = today
    new_row["Summa s"] = sum([new_row.get("Tid s", 0) or 0])
    new_row["Summa d"] = sum([new_row.get("Tid d", 0) or 0])
    new_row["Summa t"] = sum([new_row.get("Tid t", 0) or 0])
    new_row["Summa v"] = sum([new_row.get("Vila", 0) or 0])
    new_row["Klockan"] = "07:00"
    new_row["Tid kille"] = new_row.get("Män", 0) or 0
    new_row["Filmer"] = 1 if (new_row.get("Män", 0) or 0) > 0 else 0
    new_row["Pris"] = 19.99
    new_row["Intäkter"] = new_row["Filmer"] * new_row["Pris"]
    new_row["Känner"] = (new_row.get("Jobb", 0) or 0) + (new_row.get("Grannar", 0) or 0) + (new_row.get("Pv", 0) or 0) + (new_row.get("Nils kom", 0) or 0)
    new_row["Malin"] = (new_row.get("Män", 0) or 0) + (new_row.get("GB", 0) or 0) + (new_row.get("Älskar", 0) or 0) + (new_row.get("Sover med", 0) or 0)
    new_row["Företag"] = new_row["Intäkter"]
    new_row["Vänner"] = new_row["Känner"]
    new_row["Hårdhet"] = new_row.get("Män", 0) + new_row.get("GB", 0)
    new_row["GB"] = new_row.get("Grannar", 0) or 0

    return new_row

def main():
    st.title("📊 MalinData-appen")

    worksheet, df = load_data()

    with st.form("data_form"):
        try:
            max_date = pd.to_datetime(df["Dag"], errors="coerce").max()
            today = (max_date + pd.Timedelta(days=1)).date() if not pd.isna(max_date) else datetime.date.today()
        except:
            today = datetime.date.today()

        st.write("### Mata in data:")
        ny_dag = st.date_input("Dag", today)
        ny_man = st.number_input("Män", 0)
        ny_f = st.number_input("F", 0)
        ny_r = st.number_input("R", 0)
        ny_dm = st.number_input("Dm", 0)
        ny_df = st.number_input("Df", 0)
        ny_dr = st.number_input("Dr", 0)
        ny_3f = st.number_input("3f", 0)
        ny_3r = st.number_input("3r", 0)
        ny_3p = st.number_input("3p", 0)
        ny_tids = st.number_input("Tid s", 0.0)
        ny_tidd = st.number_input("Tid d", 0.0)
        ny_tidt = st.number_input("Tid t", 0.0)
        ny_vila = st.number_input("Vila", 0.0)
        ny_alskar = st.number_input("Älskar", 0)
        ny_alsktid = st.number_input("Älsk tid", 0.0)
        ny_sovermed = st.number_input("Sover med", 0)
        ny_jobb = st.number_input("Jobb", 0)
        ny_grannar = st.number_input("Grannar", 0)
        ny_nils = st.number_input("Nils kom", 0)
        ny_pv = st.number_input("Pv", 0)
        ny_svarta = st.number_input("Svarta", 0)

        submitted = st.form_submit_button("Spara rad")

        if submitted:
            new_row = {
                "Dag": ny_dag, "Män": ny_man, "F": ny_f, "R": ny_r, "Dm": ny_dm, "Df": ny_df, "Dr": ny_dr,
                "3f": ny_3f, "3r": ny_3r, "3p": ny_3p, "Tid s": ny_tids, "Tid d": ny_tidd, "Tid t": ny_tidt,
                "Vila": ny_vila, "Älskar": ny_alskar, "Älsk tid": ny_alsktid, "Sover med": ny_sovermed,
                "Jobb": ny_jobb, "Grannar": ny_grannar, "Nils kom": ny_nils, "Pv": ny_pv, "Svarta": ny_svarta
            }
            new_row = calculate_fields(df, new_row)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(worksheet, df)
            st.success("✅ Raden har sparats!")

    # Visa summeringar
    if not df.empty:
        sum_man = df["Män"].fillna(0).sum()
        sum_gb = df["GB"].fillna(0).sum()
        sum_svarta = df["Svarta"].fillna(0).sum()
        vita = ((sum_man + sum_gb - sum_svarta) / (sum_man + sum_gb + sum_svarta)) * 100 if (sum_man + sum_gb + sum_svarta) > 0 else 0
        svarta = (sum_svarta / (sum_man + sum_gb + sum_svarta)) * 100 if (sum_man + sum_gb + sum_svarta) > 0 else 0

        st.write(f"### Sammanställning:")
        st.metric("Vita (%)", f"{vita:.1f}%")
        st.metric("Svarta (%)", f"{svarta:.1f}%")
        st.dataframe(df.tail(10))

if __name__ == "__main__":
    main()
