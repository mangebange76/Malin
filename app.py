import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from berakningar import beräkna_radvärden

# Setup credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    dict(st.secrets["GOOGLE_CREDENTIALS"]), scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# Streamlit UI
st.title("Malin Produktionsapp")

with st.form("data_form"):
    aktivitet = st.selectbox("Typ av aktivitet", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
    antal_män = st.number_input("Antal män", min_value=0, value=1)
    hångel = st.number_input("Hångel (h)", min_value=0.0, value=3.0)
    summa_tid = st.number_input("Summa tid (h)", min_value=0.0, value=1.0)
    vila = st.number_input("Vila efter scen (h)", min_value=0.0, value=1.0)
    kvinnonamn = st.text_input("Kvinnans namn")
    födelsedatum = st.date_input("Födelsedatum")
    startdatum = st.date_input("Startdatum")

    submitted = st.form_submit_button("Spara")

    if submitted:
        data = {
            "Aktivitet": aktivitet,
            "Antal män": antal_män,
            "Hångel": hångel,
            "Summa tid": summa_tid,
            "Vila": vila,
            "Kvinnonamn": kvinnonamn,
            "Födelsedatum": str(födelsedatum),
            "Startdatum": str(startdatum)
        }
        beräknad_rad = beräkna_radvärden(data)
        sheet.append_row(list(beräknad_rad.values()))
        st.success("Rad sparad!")
