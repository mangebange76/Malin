import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

# Konstanter
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"
STARTTID = datetime.strptime("07:00", "%H:%M")

# Google Sheets-autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# Läs data från Google Sheet
def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Skapa rubriker om de saknas
    expected_headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
    ]
    if df.empty or list(df.columns) != expected_headers:
        worksheet.clear()
        worksheet.append_row(expected_headers)
        df = pd.DataFrame(columns=expected_headers)

    return worksheet, df

# Spara ny rad till Google Sheet
def append_row(worksheet, new_row):
    worksheet.append_row(new_row)

# Funktion för maxvärden
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if not df["Jobb"].isna().all() else 0,
        "Grannar 2": df["Grannar"].max() if not df["Grannar"].isna().all() else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if not df["Tjej PojkV"].isna().all() else 0,
        "Nils Fam 2": df["Nils Fam"].max() if not df["Nils Fam"].isna().all() else 0,
        "Känner 2": (df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]).max()
    }

# Summera tid
def summera_tid(row):
    män = row["Män"]
    känner = row["Jobb"] + row["Grannar"] + row["Tjej PojkV"] + row["Nils Fam"]
    totalt_män = män + känner

    tid_singel = row["Tid s"]
    tid_dubbel = row["Tid d"]
    tid_trippel = row["Tid t"]
    vila = row["Vila"]

    dm = row["Dm"]
    df = row["Df"]
    dr = row["Dr"]
    tpp = row["TPP"]
    tap = row["TAP"]
    tpa = row["TPA"]

    summa_singel = tid_singel * män
    summa_dubbel = tid_dubbel * (dm + df + dr)
    summa_trippel = tid_trippel * (tpp + tap + tpa)
    summa_vila = (totalt_män * vila) + ((dm + df + dr) * (vila + 7)) + ((tpp + tap + tpa) * (vila + 15))
    summa_tid = summa_singel + summa_dubbel + summa_trippel + summa_vila

    klockan = (STARTTID + timedelta(seconds=summa_tid)).strftime("%H:%M")

    return {
        "Totalt män": totalt_män,
        "Känner": känner,
        "Summa singel": summa_singel,
        "Summa dubbel": summa_dubbel,
        "Summa trippel": summa_trippel,
        "Summa vila": summa_vila,
        "Summa tid": summa_tid,
        "Klockan": klockan
    }

# Presentera huvudvy
def presentera_huvudvy(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])

    filmer = df["Män"].sum() + df["TPP"].sum()*5 + df["TAP"].sum()*7 + df["TPA"].sum()*6
    intäkter = filmer * 19.99
    malin_lön = min(1500, intäkter * 0.01)
    företag_lön = intäkter * 0.40
    vänner_lön = intäkter - malin_lön - företag_lön

    maxvärden = get_max_values(df)
    gangb = totalt_känner / sum([maxvärden["Jobb 2"], maxvärden["Grannar 2"], maxvärden["Tjej PojkV 2"], maxvärden["Nils Fam 2"]])
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner else 0

    svarta = df["Svarta"].sum()
    vita = totalt_män - svarta
    vita_pct = (vita / totalt_män) * 100 if totalt_män else 0
    svarta_pct = (svarta / totalt_män) * 100 if totalt_män else 0

    st.subheader("🔹 Huvudvy")
    st.markdown(f"""
    - **Totalt Män:** {int(totalt_män)}
    - **Snitt (Män + Känner):** {snitt:.1f}
    - **Malin lön:** {malin_lön:.2f} USD
    - **Företag lön:** {företag_lön:.2f} USD
    - **Vänner lön:** {vänner_lön:.2f} USD
    - **GangB:** {gangb:.2f}
    - **Älskat:** {älskat:.2f}
    - **Vita (%):** {vita_pct:.1f}%
    - **Svarta (%):** {svarta_pct:.1f}%
    """)

# Huvudfunktion
def main():
    st.title("📊 MalinData App")

    worksheet, df = load_data()

    presentera_huvudvy(df)

    if not df.empty:
        radval = st.selectbox("Välj rad", df.index + 1)
        rad = df.iloc[radval - 1]
        tiddata = summera_tid(rad)

        st.subheader("🔸 Radvy")
        st.write(f"**Tid kille:** {round(tiddata['Summa tid'] / tiddata['Totalt män'] / 60, 1)} minuter")
        st.write(f"**Filmer:** {int(rad['Män'])}")
        st.write(f"**Intäkter:** {int(rad['Män']) * 19.99:.2f} USD")
        st.write(f"**Klockan:** {tiddata['Klockan']}")

if __name__ == "__main__":
    main()
