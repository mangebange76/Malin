import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from berakningar import beräkna_radvärden

# --- Kolumnrubriker ---
KOLUMN_RUBRIKER = [
    "Datum", "Veckodag", "Scen", "Män", "Fitta", "Rumpa", "DP", "DPP", "DAP", "TAP",
    "Tid S", "Tid D", "Vila", "Summa S", "Summa D", "Summa TP", "Summa Vila", 
    "Summa tid", "Klockan", "Älskar", "Sover med", "Känner", "Pappans vänner", 
    "Grannar", "Nils vänner", "Nils familj", "Totalt Män", "Tid kille", "Nils", 
    "Hångel", "Suger", "Prenumeranter", "Avgift", "Intäkter", "Intäkt män", 
    "Intäkt Känner", "Lön Malin", "Intäkt Företaget", "Vinst", "Känner Sammanlagt", 
    "Hårdhet"
]

# --- Google Sheets Setup ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["GOOGLE_CREDENTIALS"]), scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

def läs_data():
    rows = sheet.get_all_records()
    return pd.DataFrame(rows)

def säkerställ_kolumner():
    data = sheet.get_all_values()
    if not data or data[0] != KOLUMN_RUBRIKER:
        sheet.clear()
        sheet.append_row(KOLUMN_RUBRIKER)

# --- App Start ---
st.title("Malin-produktionsapp")

# Sidopanel: inställningar
st.sidebar.header("Inställningar")
startdatum = st.sidebar.date_input("Startdatum", value=datetime.today())
födelsedatum = st.sidebar.date_input("Kvinnans födelsedatum", value=datetime(2000, 1, 1))
kvinnans_namn = st.sidebar.text_input("Kvinnans namn", value="Malin")

# Läs existerande data
säkerställ_kolumner()
df = läs_data()

# Nästa radens metadata
nästa_datum = startdatum + timedelta(days=len(df))
veckodagar = ["lördag", "söndag", "måndag", "tisdag", "onsdag", "torsdag", "fredag"]
nästa_veckodag = veckodagar[len(df) % 7]
nästa_scen = len(df) + 1
ålder = (nästa_datum - födelsedatum).days // 365

# Formulär
with st.form("scenformulär"):
    st.subheader(f"Ny rad för {kvinnans_namn} ({ålder} år) – {nästa_datum.strftime('%Y-%m-%d')} ({nästa_veckodag})")
    c = st.number_input("Män", min_value=0, step=1)
    d = st.number_input("Fitta", min_value=0, step=1)
    e = st.number_input("Rumpa", min_value=0, step=1)
    f = st.number_input("DP", min_value=0, step=1)
    g = st.number_input("DPP", min_value=0, step=1)
    h = st.number_input("DAP", min_value=0, step=1)
    i = st.number_input("TAP", min_value=0, step=1)
    j = st.number_input("Tid S (sek)", min_value=0, step=1, value=60)
    k = st.number_input("Tid D (sek)", min_value=0, step=1, value=60)
    l = st.number_input("Vila (sek)", min_value=0, step=1, value=7)
    s = st.number_input("Älskar", min_value=0, step=1)
    t = st.number_input("Sover med", min_value=0, step=1)
    v = st.number_input("Pappans vänner", min_value=0, step=1)
    w = st.number_input("Grannar", min_value=0, step=1)
    x = st.number_input("Nils vänner", min_value=0, step=1)
    y = st.number_input("Nils familj", min_value=0, step=1)
    ab = st.number_input("Nils", min_value=0, step=1)
    an = st.number_input("Nya prenumeranter", min_value=0, step=1)
    af = st.number_input("Avgift (USD)", value=15)

    spara = st.form_submit_button("Bekräfta och spara")

# Om bekräfta
if spara:
    fält = {
        "Män": c, "Fitta": d, "Rumpa": e, "DP": f, "DPP": g, "DAP": h, "TAP": i,
        "Tid S": j, "Tid D": k, "Vila": l, "Älskar": s, "Sover med": t,
        "Pappans vänner": v, "Grannar": w, "Nils vänner": x, "Nils familj": y,
        "Nils": ab, "Prenumeranter": an, "Avgift": af
    }
    ny_rad = beräkna_radvärden(
        fält, 
        datum=nästa_datum.strftime("%Y-%m-%d"), 
        veckodag=nästa_veckodag, 
        scenummer=nästa_scen, 
        ålder=ålder
    )
    sheet.append_row(ny_rad)
    st.success("✅ Raden har sparats!")
