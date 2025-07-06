import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# Autentisering mot Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Inställningar
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"

# Rubriker som ska finnas i arket
HEADERS = [
    "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "pv", "Nils kom", "Män", "Nils natt", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Känner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    # Kontrollera och skapa rubriker om de saknas
    try:
        current_headers = worksheet.row_values(1)
    except gspread.exceptions.APIError:
        worksheet.insert_row(HEADERS, 1)
        current_headers = HEADERS

    # Lägg till saknade kolumner
    for i, header in enumerate(HEADERS, start=1):
        if i > len(current_headers) or current_headers[i - 1] != header:
            worksheet.update_cell(1, i, header)

    # Läs data
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def save_row(worksheet, row_data):
    worksheet.append_row(row_data)

def main():
    st.title("Malin Appen")

    worksheet, df = load_data()

    # Ange startdatum
    if "start_datum" not in st.session_state:
        st.session_state.start_datum = datetime(2014, 5, 6)

    start_datum = st.date_input("Startdatum", value=st.session_state.start_datum)
    senaste_dag = start_datum + timedelta(days=len(df))

    st.markdown(f"### Datum för nästa rad: {senaste_dag.strftime('%Y-%m-%d')}")

    # Användarinput
    killar = st.number_input("Killar", 0)
    f = st.number_input("F", 0)
    r = st.number_input("R", 0)
    dm = st.number_input("Dm", 0)
    df_f = st.number_input("Df", 0)
    dr = st.number_input("Dr", 0)
    t3f = st.number_input("3f", 0)
    t3r = st.number_input("3r", 0)
    t3p = st.number_input("3p", 0)

    tid_s = st.number_input("Tid s (sek)", 0)
    tid_d = st.number_input("Tid d (sek)", 0)
    tid_t = st.number_input("Tid t (sek)", 0)
    vila = st.number_input("Vila (sek)", 0)

    älskar = st.number_input("Älskar", 0)
    älsk_tid = st.number_input("Älsk tid (min)", 0)
    sover_med = st.number_input("Sover med", 0)

    jobb = st.number_input("Jobb", 0)
    grannar = st.number_input("Grannar", 0)
    pv = st.number_input("pv", 0)
    nils_kom = st.number_input("Nils kom", 0)
    nils_natt = st.number_input("Nils natt", 0)

    filmer = st.number_input("Filmer", 0)
    pris = st.number_input("Pris", 0)
    svarta = st.number_input("Svarta", 0)

    # Beräkningar
    summa_s = (killar + f + r) * tid_s + vila
    summa_d = 2 * ((dm + df_f + dr) * tid_d + vila)
    summa_t = 3 * ((t3f + t3r + t3p) * tid_t + vila)
    summa_v = vila
    klockan = datetime.strptime("07:00", "%H:%M") + timedelta(seconds=(summa_s + summa_d + summa_t + älskar * älsk_tid * 60))
    klockan_str = klockan.strftime("%H:%M")

    män = killar + jobb + grannar + pv + nils_kom
    tid_kille = (summa_s + summa_d + summa_t) / män / 60 if män > 0 else 0
    intäkter = filmer * pris
    malin = intäkter * 0.01
    företag = intäkter * 0.40
    känner = intäkter * 0.59

    hårdhet = 0
    if r > 0: hårdhet = 1
    if dm > 0: hårdhet = 1
    if df_f > 0: hårdhet = 1
    if dr > 0: hårdhet = 2
    if t3f > 0: hårdhet = 3
    if t3r > 0: hårdhet = 5
    if t3p > 0: hårdhet = 4

    gb = jobb + grannar + pv + nils_kom

    # Spara ny rad
    if st.button("Spara rad"):
        new_row = [
            senaste_dag.strftime("%Y-%m-%d"), killar, f, r, dm, df_f, dr, t3f, t3r, t3p,
            tid_s, tid_d, tid_t, vila,
            summa_s, summa_d, summa_t, summa_v, klockan_str,
            älskar, älsk_tid, sover_med,
            jobb, grannar, pv, nils_kom, män, nils_natt, tid_kille, filmer, pris,
            intäkter, malin, företag, känner, hårdhet, svarta, gb
        ]
        save_row(worksheet, new_row)
        st.success("Rad sparad!")

    # Summeringar
    if not df.empty:
        max_jobb = df["Jobb"].max()
        max_grannar = df["Grannar"].max()
        max_pv = df["pv"].max()
        max_nils_kom = df["Nils kom"].max()
        total_malin = df["Malin"].sum()
        känner_total = max_jobb + max_grannar + max_pv + max_nils_kom
        känner_tjänat = total_malin / känner_total if känner_total > 0 else 0

        total_män = df["Killar"].sum() + df["GB"].sum()
        total_svarta = df["Svarta"].sum()
        vita_procent = ((total_män - total_svarta) / (total_män + total_svarta)) * 100 if (total_män + total_svarta) > 0 else 0
        svarta_procent = (total_svarta / (total_män + total_svarta)) * 100 if (total_män + total_svarta) > 0 else 0

        # Snitt film
        antal_filmerader = df[df["Killar"] > 0].shape[0]
        snitt_film = (df["Killar"].sum() + df["GB"].sum()) / antal_filmerader if antal_filmerader > 0 else 0

        # Malin tjänat
        malin_tjänat = df["Killar"].sum() + df["GB"].sum() + df["Älskar"].sum() + df["Sover med"].sum()

        st.markdown("### 🔢 Statistik")
        st.write(f"**Malin totalt tjänat:** {total_malin:.2f} kr")
        st.write(f"**Känner tjänat:** {känner_tjänat:.2f}")
        st.write(f"**Max Jobb/Grannar/pv/Nils kom:** {max_jobb}/{max_grannar}/{max_pv}/{max_nils_kom}")
        st.write(f"**Vita (%):** {vita_procent:.2f}%")
        st.write(f"**Svarta (%):** {svarta_procent:.2f}%")
        st.write(f"**Snitt film:** {snitt_film:.2f}")
        st.write(f"**Malin tjänat (snitt):** {malin_tjänat:.2f}")

if __name__ == "__main__":
    main()
