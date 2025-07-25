import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner

# Autentisering och Google Sheets-koppling
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)

# Initiera databladet
def initiera_dataark(sh, ark_namn="Data"):
    try:
        worksheet = sh.worksheet(ark_namn)
    except gspread.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=ark_namn, rows=1000, cols=len(COLUMNS))

    headers = worksheet.row_values(1)
    if headers != COLUMNS:
        worksheet.update("A1", [COLUMNS])
        worksheet.resize(rows=1000, cols=len(COLUMNS))
    return worksheet

worksheet = initiera_dataark(sh)

# Läser in data
@st.cache_data(ttl=60)
def läs_data():
    try:
        rows = worksheet.get_all_values()
        if not rows or rows == [[]]:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(rows[1:], columns=rows[0])
        df = säkerställ_kolumner(df)
        return df
    except Exception as e:
        st.error(f"Fel vid hämtning av data: {e}")
        return pd.DataFrame(columns=COLUMNS)

df = läs_data()

# Formulär för att lägga till en ny scenrad
with st.form("scenformulär", clear_on_submit=False):
    st.subheader("Lägg till scen")
    f = {}
    f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
    f["Datum"] = ""  # Sätts automatiskt senare
    f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, step=1)
    f["Nya män"] = st.number_input("Nya män", 0, step=1)
    f["Enkel vaginal"] = st.number_input("Enkel vaginal", 0, step=1)
    f["Enkel anal"] = st.number_input("Enkel anal", 0, step=1)
    f["DP"] = st.number_input("DP", 0, step=1)
    f["DPP"] = st.number_input("DPP", 0, step=1)
    f["DAP"] = st.number_input("DAP", 0, step=1)
    f["TPP"] = st.number_input("TPP", 0, step=1)
    f["TPA"] = st.number_input("TPA", 0, step=1)
    f["TAP"] = st.number_input("TAP", 0, step=1)
    f["Tid enkel"] = st.number_input("Tid enkel (sek)", 0, step=1)
    f["Tid dubbel"] = st.number_input("Tid dubbel (sek)", 0, step=1)
    f["Tid trippel"] = st.number_input("Tid trippel (sek)", 0, step=1)
    f["Vila"] = st.number_input("Vila mellan byten (sek)", 0, step=1)
    f["Kompisar"] = st.number_input("Kompisar", 0, step=1)
    f["Pappans vänner"] = st.number_input("Pappans vänner", 0, step=1)
    f["Nils vänner"] = st.number_input("Nils vänner", 0, step=1)
    f["Nils familj"] = st.number_input("Nils familj", 0, step=1)
    f["DT tid per man"] = st.number_input("DT tid per man", 0, step=1)
    f["Antal varv"] = st.number_input("Antal varv", 0, step=1)
    f["Älskar med"] = st.number_input("Älskar med", 0, step=1)
    f["Sover med"] = st.number_input("Sover med", 0, step=1)
    f["Nils sex"] = st.number_input("Nils sex", 0, step=1)
    f["Prenumeranter"] = st.number_input("Prenumeranter", 0, step=1)
    f["Intäkt ($)"] = st.number_input("Intäkt ($)", 0.0, step=0.1)
    f["Kvinnans lön ($)"] = st.number_input("Kvinnans lön ($)", 0.0, step=0.1)
    f["Mäns lön ($)"] = st.number_input("Mäns lön ($)", 0.0, step=0.1)
    f["Kompisars lön ($)"] = st.number_input("Kompisars lön ($)", 0.0, step=0.1)
    f["DT total tid (sek)"] = st.number_input("DT total tid (sek)", 0, step=1)
    f["Total tid (sek)"] = st.number_input("Total tid (sek)", 0, step=1)
    f["Total tid (h)"] = st.number_input("Total tid (h)", 0.0, step=0.1)
    f["Minuter per kille"] = st.number_input("Minuter per kille", 0.0, step=0.1)

    bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")
    skicka = st.form_submit_button("Lägg till")

# Spara ny rad
if skicka and bekräfta:
    import datetime

    f["Datum"] = datetime.date.today().strftime("%Y-%m-%d")
    ny_rad = [f.get(col, "") for col in COLUMNS]

    if len(ny_rad) != len(COLUMNS):
        st.error("Fel: Antalet fält matchar inte kolumnerna i databasen.")
    else:
        try:
            worksheet.append_row(ny_rad)
            st.success("Raden har lagts till.")
        except Exception as e:
            st.error(f"Kunde inte spara: {e}")
