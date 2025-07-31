import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
from berakningar import beräkna_radvärden

# === Autentisera mot Google Sheets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["GOOGLE_CREDENTIALS"], scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# === Sätt app-titel ===
st.title("Malin-produktionsapp")

# === Hämta tidigare data (för datum/vecka-synk) ===
existing_data = sheet.get_all_values()
header = existing_data[0] if existing_data else []
rows = existing_data[1:] if len(existing_data) > 1 else []

# === Startdatum och kvinnlig info (för ålder/beräkning) ===
startdatum = st.date_input("Startdatum", datetime.date.today())
namn = st.text_input("Kvinnans namn", "")
födelsedatum = st.date_input("Kvinnans födelsedatum", datetime.date(2000, 1, 1))

# === Formulär för att lägga till ny rad ===
with st.form("Lägg till ny rad"):
    män = st.number_input("Män", min_value=0, value=0)
    fitta = st.number_input("Fitta", min_value=0, value=0)
    rumpa = st.number_input("Rumpa", min_value=0, value=0)
    dp = st.number_input("DP", min_value=0, value=0)
    dpp = st.number_input("DPP", min_value=0, value=0)
    dap = st.number_input("DAP", min_value=0, value=0)
    tap = st.number_input("TAP", min_value=0, value=0)
    tid_s = st.number_input("Tid S (sekunder)", min_value=0, value=60)
    tid_d = st.number_input("Tid D (sekunder)", min_value=0, value=60)
    vila = st.number_input("Vila (sekunder)", min_value=0, value=7)
    älskar = st.number_input("Älskar", min_value=0, value=0)
    sover_med = st.number_input("Sover med", min_value=0, value=0)
    pappans_vänner = st.number_input("Pappans vänner", min_value=0, value=0)
    grannar = st.number_input("Grannar", min_value=0, value=0)
    nils_vänner = st.number_input("Nils vänner", min_value=0, value=0)
    nils_familj = st.number_input("Nils familj", min_value=0, value=0)
    nils = st.number_input("Nils", min_value=0, value=0)

    spara = st.form_submit_button("Spara")

# === Hantera sparning ===
if spara:
    # Veckodag & scennummer
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    scen_nummer = len(rows) + 1
    veckodag = veckodagar[(scen_nummer - 1) % 7]

    # Beräkna ålder
    ålder = (startdatum - födelsedatum).days // 365

    # Sätt upp rad för beräkning
    rad = {
        "Veckodag": veckodag,
        "Scen": scen_nummer,
        "Män": män,
        "Fitta": fitta,
        "Rumpa": rumpa,
        "DP": dp,
        "DPP": dpp,
        "DAP": dap,
        "TAP": tap,
        "Tid S": tid_s,
        "Tid D": tid_d,
        "Vila": vila,
        "Älskar": älskar,
        "Sover med": sover_med,
        "Pappans vänner": pappans_vänner,
        "Grannar": grannar,
        "Nils vänner": nils_vänner,
        "Nils familj": nils_familj,
        "Nils": nils,
        "Ålder": ålder
    }

    # === Beräkna alla automatiska kolumner ===
    beräknad_rad = beräkna_radvärden(rad)

    # === Spara till ark ===
    if not header:
        sheet.insert_row(list(beräknad_rad.keys()), 1)
    sheet.append_row(list(beräknad_rad.values()))
    st.success("Raden har sparats!")
