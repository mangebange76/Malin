import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="MalinApp", layout="wide")

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)

# Konfiguration
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"
HEADERS = [
    "Dag", "Killar", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner",
    "Jobb", "Grannar", "Pv", "Nils kom", "Män", "Nils natt", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Känner vänner", "Hårdhet", "GB", "Svarta"
]

# Hämta worksheet och kontrollera rubriker
def load_data():
    spreadsheet = client.open(SHEET_NAME)
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="50")

    sheet_data = worksheet.get_all_values()

    if not sheet_data:
        worksheet.append_row(HEADERS)
        return worksheet, pd.DataFrame(columns=HEADERS)

    current_headers = sheet_data[0]
    if current_headers != HEADERS:
        worksheet.update('A1', [HEADERS])
        data = sheet_data[1:]
    else:
        data = sheet_data[1:]

    df = pd.DataFrame(data, columns=HEADERS)
    return worksheet, df

# Skriv ny rad till kalkylarket
def append_row(worksheet, row_data):
    worksheet.append_row(row_data, value_input_option="USER_ENTERED")

# Töm hela databasen (ej rubriker)
def clear_data(worksheet):
    worksheet.resize(rows=1)
    worksheet.update('A1', [HEADERS])

# Konvertera till rätt typ
def safe_int(x):
    try:
        return int(float(x))
    except:
        return 0

def safe_float(x):
    try:
        return float(x)
    except:
        return 0.0

# Visa nyckeltal
def visa_nyckeltal(df):
    df_num = df.applymap(safe_float)

    total_malin = df_num["Malin"].sum()
    st.metric("💰 Malin tjänat", f"{total_malin:.2f} kr")

    max_jobb = df_num["Jobb"].max()
    max_grannar = df_num["Grannar"].max()
    max_pv = df_num["Pv"].max()
    max_nils_kom = df_num["Nils kom"].max()
    total_max = max_jobb + max_grannar + max_pv + max_nils_kom
    total_intäkter = df_num["Intäkter"].sum()

    känner_tjänat = total_intäkter / total_max if total_max > 0 else 0
    st.metric("🤝 Känner tjänat", f"{känner_tjänat:.2f} kr")

    film_rader = df_num[df_num["Killar"] > 0]
    antal_filmer = len(film_rader)
    snitt_film = (film_rader["Killar"].sum() + film_rader["GB"].sum()) / antal_filmer if antal_filmer > 0 else 0
    st.metric("🎥 Snitt film", f"{snitt_film:.2f}")

    malin_tjänst_snitt = (
        df_num["Killar"].sum()
        + df_num["GB"].sum()
        + df_num["Älskar"].sum()
        + df_num["Sover med"].sum()
    )
    st.metric("📊 Malin tjänst snitt", f"{malin_tjänst_snitt:.2f}")

    total_killar = df_num["Killar"].sum()
    total_gb = df_num["GB"].sum()
    total_svarta = df_num["Svarta"].sum()
    total_all = total_killar + total_gb + total_svarta
    vita_pct = ((total_killar + total_gb - total_svarta) / total_all * 100) if total_all > 0 else 0
    svarta_pct = (total_svarta / total_all * 100) if total_all > 0 else 0

    st.metric("⚪ Vita (%)", f"{vita_pct:.2f}%")
    st.metric("⚫ Svarta (%)", f"{svarta_pct:.2f}%")

    st.info(
        f"""📈 **Max per kategori**  
        Jobb: {max_jobb}, Grannar: {max_grannar}, Pv: {max_pv}, Nils kom: {max_nils_kom},  
        ➕ Totalt max känner: {total_max}
        """
    )

# Huvudgränssnitt
def main():
    st.title("📋 MalinData Inmatning")

    worksheet, df = load_data()
    visa_nyckeltal(df)

    st.divider()

    with st.form("data_form"):
        st.subheader("➕ Lägg till ny rad")

        startdatum = st.date_input("Startdatum", datetime.date(2014, 5, 6))
        antal_rader = len(df)
        nytt_datum = startdatum + datetime.timedelta(days=antal_rader)

        killar = st.number_input("Killar", 0)
        f = st.number_input("F", 0)
        r = st.number_input("R", 0)
        dm = st.number_input("Dm", 0)
        dfeld = st.number_input("Df", 0)
        dr = st.number_input("Dr", 0)
        tre_f = st.number_input("3f", 0)
        tre_r = st.number_input("3r", 0)
        tre_p = st.number_input("3p", 0)
        tid_s = st.number_input("Tid s (sek)", 0)
        tid_d = st.number_input("Tid d (sek)", 0)
        tid_t = st.number_input("Tid t (sek)", 0)
        vila = st.number_input("Vila (sek)", 0)
        älskar = st.number_input("Älskar", 0)
        älsk_tid = st.number_input("Älsk tid (min)", 0)
        sover_med = st.number_input("Sover med", 0)
        jobb = st.number_input("Jobb", 0)
        grannar = st.number_input("Grannar", 0)
        pv = st.number_input("Pv", 0)
        nils_kom = st.number_input("Nils kom", 0)
        nils_natt = st.selectbox("Nils natt", [0, 1])
        filmer = st.number_input("Filmer", 0)
        pris = st.number_input("Pris per film", 0)
        svarta = st.number_input("Svarta", 0)

        submitted = st.form_submit_button("✅ Lägg till")

        if submitted:
            summa_s = (killar + f + r) * tid_s + vila
            summa_d = (dm + dfeld + dr) * tid_d + vila
            summa_t = (tre_f + tre_r + tre_p) * tid_t + vila
            summa_d *= 2
            summa_t *= 3

            summa_v = vila
            klockan = datetime.datetime.combine(datetime.date.today(), datetime.time(7, 0)) + datetime.timedelta(
                seconds=(summa_s + summa_d + summa_t + älsk_tid * 60)
            )
            klockan_str = klockan.time().strftime("%H:%M")

            känner = jobb + grannar + pv + nils_kom
            män = killar + känner
            tid_kille = (summa_s + summa_d + summa_t) / män / 60 if män > 0 else 0

            intäkter = filmer * pris
            malin = intäkter * 0.01
            företag = intäkter * 0.4
            känner_vänner = intäkter * 0.59

            hårdhet = 0
            hårdhet += 1 if r > 0 else 0
            hårdhet += 1 if dm > 0 else 0
            hårdhet += 1 if dfeld > 0 else 0
            hårdhet += 2 if dr > 0 else 0
            hårdhet += 3 if tre_f > 0 else 0
            hårdhet += 5 if tre_r > 0 else 0
            hårdhet += 4 if tre_p > 0 else 0

            gb = jobb + grannar + pv + nils_kom

            ny_rad = [
                nytt_datum.strftime("%Y-%m-%d"), killar, f, r, dm, dfeld, dr, tre_f, tre_r, tre_p,
                tid_s, tid_d, tid_t, vila, summa_s, summa_d, summa_t, summa_v, klockan_str,
                älskar, älsk_tid, sover_med, känner, jobb, grannar, pv, nils_kom, män, nils_natt,
                tid_kille, filmer, pris, intäkter, malin, företag, känner_vänner, hårdhet, gb, svarta
            ]
            append_row(worksheet, ny_rad)
            st.success("Rad tillagd!")

    st.divider()

    if st.button("🗑️ Töm databasen"):
        clear_data(worksheet)
        st.warning("Databasen är nu tömd (rubrikerna kvarstår).")

if __name__ == "__main__":
    main()
