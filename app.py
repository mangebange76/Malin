import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta
from berakningar import beräkna_radvärden

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    dict(st.secrets["GOOGLE_CREDENTIALS"]), scope)
client = gspread.authorize(credentials)

# Öppna ark
sheet_url = st.secrets["SHEET_URL"]
sheet = client.open_by_url(sheet_url).sheet1

# Kolumnrubriker enligt struktur
KOLUMNER = [
    "Veckodag", "Scen", "Män", "Fitta", "Rumpa", "DP", "DPP", "DAP", "TAP",
    "Tid S", "Tid D", "Vila", "Summa S", "Summa D", "Summa TP", "Summa Vila", "Summa tid",
    "Klockan", "Älskar", "Sover med", "Känner", "Pappans vänner", "Grannar",
    "Nils vänner", "Nils familj", "Totalt Män", "Tid kille", "Nils",
    "Hångel", "Suger", "Prenumeranter", "Avgift", "Intäkter", "Intäkt män",
    "Intäkt Känner", "Lön Malin", "Intäkt Företaget", "Vinst", "Känner Sammanlagt", "Hårdhet"
]

# Säkerställ att arket har rätt kolumner
def säkerställ_kolumner():
    befintliga = sheet.row_values(1)
    if befintliga != KOLUMNER:
        sheet.resize(rows=1)
        sheet.insert_row(KOLUMNER, 1)

säkerställ_kolumner()

# Funktion för att hämta nästa veckodag
def nästa_veckodag(föregående):
    dagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    idx = (dagar.index(föregående) + 1) % 7
    return dagar[idx]

# Hämta senaste rad (om någon finns)
data = sheet.get_all_records()
senaste_rad = data[-1] if data else {}
senaste_veckodag = senaste_rad.get("Veckodag", "Lördag")
senaste_scen = int(senaste_rad.get("Scen", 0)) if senaste_rad else 0

st.title("Malin-produktionsapp")

with st.form("ny_rad"):
    st.subheader("Lägg till ny händelse")

    män = st.number_input("Män", min_value=0, step=1)
    fitta = st.number_input("Fitta", min_value=0, step=1)
    rumpa = st.number_input("Rumpa", min_value=0, step=1)
    dp = st.number_input("DP", min_value=0, step=1)
    dpp = st.number_input("DPP", min_value=0, step=1)
    dap = st.number_input("DAP", min_value=0, step=1)
    tap = st.number_input("TAP", min_value=0, step=1)
    tid_s = st.number_input("Tid S (sek)", value=60, step=1)
    tid_d = st.number_input("Tid D (sek)", value=60, step=1)
    vila = st.number_input("Vila (sek)", value=7, step=1)
    älskar = st.number_input("Älskar", min_value=0, step=1)
    sover_med = st.number_input("Sover med", min_value=0, step=1)
    pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1)
    grannar = st.number_input("Grannar", min_value=0, step=1)
    nils_vänner = st.number_input("Nils vänner", min_value=0, step=1)
    nils_familj = st.number_input("Nils familj", min_value=0, step=1)
    nils = st.number_input("Nils (antal gånger)", min_value=0, step=1)

    submitted = st.form_submit_button("Spara händelse")

    if submitted:
        # Grunddata
        ny_rad = {
            "Veckodag": nästa_veckodag(senaste_veckodag),
            "Scen": senaste_scen + 1,
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
            "Nils": nils
        }

        # Beräkna övriga kolumner
        beräknad_rad = beräkna_radvärden(ny_rad)

        # Lägg till som rad i samma ordning som KOLUMNER
        rad_lista = [beräknad_rad.get(k, "") for k in KOLUMNER]
        sheet.append_row(rad_lista)

        st.success("Händelse tillagd!")
