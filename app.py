import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from berakningar import beräkna_radvärden

st.set_page_config(page_title="Malin", layout="centered")

# === Steg 1: Autentisera mot Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# === Steg 2: Säkerställ att kolumnerna finns ===
kolumnnamn = [
    "Veckodag", "Scen", "Män", "Fitta", "Rumpa", "DP", "DPP", "DAP", "TAP",
    "Tid S", "Tid D", "Vila", "Summa S", "Summa D", "Summa TP", "Summa Vila",
    "Summa tid", "Klockan", "Älskar", "Sover med", "Känner", "Pappans vänner",
    "Grannar", "Nils vänner", "Nils familj", "Totalt Män", "Tid kille", "Nils",
    "Hångel", "Suger", "Prenumeranter", "Avgift", "Intäkter", "Intäkt män",
    "Intäkt Känner", "Lön Malin", "Intäkt Företaget", "Vinst", "Känner Sammanlagt",
    "Hårdhet"
]
if sheet.row_count == 0 or sheet.row_values(1) != kolumnnamn:
    sheet.clear()
    sheet.insert_row(kolumnnamn, index=1)

# === Steg 3: Formulär för inmatning ===
st.header("Lägg till ny rad")

with st.form("data_form"):
    män = st.number_input("Antal män", min_value=0)
    fitta = st.number_input("Fitta", min_value=0)
    rumpa = st.number_input("Rumpa", min_value=0)
    dp = st.number_input("DP", min_value=0)
    dpp = st.number_input("DPP", min_value=0)
    dap = st.number_input("DAP", min_value=0)
    tap = st.number_input("TAP", min_value=0)
    tid_s = st.number_input("Tid S (sek)", value=60, min_value=0)
    tid_d = st.number_input("Tid D (sek)", value=60, min_value=0)
    vila = st.number_input("Vila (sek)", value=7, min_value=0)
    älskar = st.number_input("Älskar", min_value=0)
    sover_med = st.number_input("Sover med", min_value=0)
    nils = st.number_input("Nils", min_value=0)
    pappans_vänner = st.number_input("Pappans vänner", min_value=0)
    grannar = st.number_input("Grannar", min_value=0)
    nils_vänner = st.number_input("Nils vänner", min_value=0)
    nils_familj = st.number_input("Nils familj", min_value=0)

    submitted = st.form_submit_button("Spara")

# === Steg 4: Spara rad ===
if submitted:
    data = {
        "Män": män, "Fitta": fitta, "Rumpa": rumpa,
        "DP": dp, "DPP": dpp, "DAP": dap, "TAP": tap,
        "Tid S": tid_s, "Tid D": tid_d, "Vila": vila,
        "Älskar": älskar, "Sover med": sover_med,
        "Nils": nils,
        "Pappans vänner": pappans_vänner,
        "Grannar": grannar,
        "Nils vänner": nils_vänner,
        "Nils familj": nils_familj,
    }

    # Lägg till automatiskt veckodag, scen etc
    befintliga_rader = sheet.get_all_values()
    ny_rad = beräkna_radvärden(befintliga_rader, data)

    sheet.append_row(ny_rad)
    st.success("Rad tillagd!")
