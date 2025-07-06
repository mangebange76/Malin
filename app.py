import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope)
client = gspread.authorize(credentials)

SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Ladda Google Sheet
def load_data():
    try:
        spreadsheet = client.open(SHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except Exception as e:
        st.error(f"Kunde inte öppna arket: {e}")
        st.stop()

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Om inga rubriker, skapa dem
    required_columns = [
        "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
        "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "pv", "Nils kom", "Nils natt", "Pris", "Svarta"
    ]
    derived_columns = [
        "Summa s", "Summa d", "Summa t", "Klockan", "Känner", "Män", "Tid kille",
        "Filmer", "Intäkter", "Malin", "Företag", "Känner (heta vänner)", "Hårdhet", "GB"
    ]
    all_columns = required_columns + derived_columns

    if df.empty or set(all_columns).difference(df.columns):
        df = pd.DataFrame(columns=all_columns)
        worksheet.clear()
        worksheet.append_row(all_columns)

    return worksheet, df

# Spara ny rad
def append_row(worksheet, row_dict):
    existing_data = worksheet.get_all_records()
    df = pd.DataFrame(existing_data)
    next_row = []

    for col in worksheet.row_values(1):
        next_row.append(row_dict.get(col, ""))

    worksheet.append_row(next_row)

# Beräkningar per rad
def calculate_fields(row):
    try:
        killar = int(row.get("Killar", 0))
        f = int(row.get("F", 0))
        r = int(row.get("R", 0))
        dm = int(row.get("Dm", 0))
        df_f = int(row.get("Df", 0))
        dr = int(row.get("Dr", 0))
        t3f = int(row.get("3f", 0))
        t3r = int(row.get("3r", 0))
        t3p = int(row.get("3p", 0))
        tid_s = int(row.get("Tid s", 0))
        tid_d = int(row.get("Tid d", 0))
        tid_t = int(row.get("Tid t", 0))
        vila = int(row.get("Vila", 0))
        älsk_tid = int(row.get("Älsk tid", 0))
        älskar = int(row.get("Älskar", 0))
        sover_med = int(row.get("Sover med", 0))
        jobb = int(row.get("Jobb", 0))
        grannar = int(row.get("Grannar", 0))
        pv = int(row.get("pv", 0))
        nils_kom = int(row.get("Nils kom", 0))
        pris = float(row.get("Pris", 0))
        svarta = int(row.get("Svarta", 0))

        summa_s = (killar + f + r) * tid_s + vila
        summa_d = ((dm + df_f + dr) * tid_d + vila) * 2
        summa_t = ((t3f + t3r + t3p) * tid_t + vila) * 3
        känner = jobb + grannar + pv + nils_kom
        män = killar + känner
        tid_kille = (summa_s + summa_d + summa_t) / män / 60 if män else 0
        filmer = 1 if killar > 0 else 0
        intäkter = filmer * pris
        malin = intäkter * 0.01
        företag = intäkter * 0.40
        heta_vänner = intäkter * 0.59

        hårdhet = 0
        if r > 0: hårdhet += 1
        if dm > 0: hårdhet += 1
        if df_f > 0: hårdhet += 1
        if dr > 0: hårdhet += 2
        if t3f > 0: hårdhet += 3
        if t3r > 0: hårdhet += 5
        if t3p > 0: hårdhet += 4

        gb = jobb + grannar + pv + nils_kom

        klockan_tid = timedelta(seconds=(summa_s + summa_d + summa_t + (älsk_tid * älskar)))
        klockan = (datetime.strptime("07:00", "%H:%M") + klockan_tid).strftime("%H:%M")

        return {
            "Summa s": summa_s,
            "Summa d": summa_d,
            "Summa t": summa_t,
            "Klockan": klockan,
            "Känner": känner,
            "Män": män,
            "Tid kille": round(tid_kille, 2),
            "Filmer": filmer,
            "Intäkter": round(intäkter, 2),
            "Malin": round(malin, 2),
            "Företag": round(företag, 2),
            "Känner (heta vänner)": round(heta_vänner, 2),
            "Hårdhet": hårdhet,
            "GB": gb
        }
    except Exception as e:
        st.error(f"Fel i beräkningar: {e}")
        return {}

# Sammanställ nyckeltal
def calculate_summary(df):
    total_malin = df["Malin"].sum()
    max_jobb = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_pv = df["pv"].max()
    max_nils = df["Nils kom"].max()
    känner_total = max_jobb + max_grannar + max_pv + max_nils
    känner_tjänat = df["Intäkter"].sum() / känner_total if känner_total else 0

    filmer_antal = (df["Killar"] > 0).sum()
    snitt_film = (df["Killar"].sum() + df["GB"].sum()) / filmer_antal if filmer_antal else 0
    malin_tjänat = df["Killar"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

    total_svarta = df["Svarta"].sum()
    vita_andel = (df["Killar"].sum() + df["GB"].sum() - total_svarta) / (df["Killar"].sum() + df["GB"].sum() + total_svarta) * 100 if (df["Killar"].sum() + df["GB"].sum() + total_svarta) else 0
    svarta_andel = total_svarta / (df["Killar"].sum() + df["GB"].sum() + total_svarta) * 100 if (df["Killar"].sum() + df["GB"].sum() + total_svarta) else 0

    st.metric("💰 Malin totalt", f"{total_malin:.2f} kr")
    st.metric("👥 Känner tjänat", f"{känner_tjänat:.2f} kr/person")
    st.metric("🎬 Snitt film", f"{snitt_film:.2f}")
    st.metric("🧮 Malin tjänat", f"{malin_tjänat}")
    st.metric("⚪ Vita (%)", f"{vita_andel:.1f}%")
    st.metric("⚫ Svarta (%)", f"{svarta_andel:.1f}%")

# Streamlit-gränssnitt
def main():
    st.title("📊 MalinApp – Daglig inmatning och analys")

    worksheet, df = load_data()
    calculate_summary(df)

    with st.form("dataform"):
        start_datum = st.date_input("Startdatum", value=datetime.today())
        rader = st.number_input("Antal dagar att lägga till", min_value=1, step=1)

        inputs = {}
        for fält in [
            "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
            "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "pv", "Nils kom", "Nils natt", "Pris", "Svarta"
        ]:
            inputs[fält] = st.number_input(fält, value=0, step=1, format="%d")

        submitted = st.form_submit_button("➕ Lägg till")
        if submitted:
            for i in range(rader):
                dag = (start_datum + timedelta(days=i)).strftime("%Y-%m-%d")
                row = {"Dag": dag, **inputs}
                beräkningar = calculate_fields(row)
                full_row = {**row, **beräkningar}
                append_row(worksheet, full_row)
            st.success(f"{rader} rader har lagts till.")

    if st.button("🧹 Töm databasen"):
        worksheet.clear()
        worksheet.append_row(df.columns.tolist())
        st.success("Databasen har tömts.")

if __name__ == "__main__":
    main()
