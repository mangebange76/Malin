import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import random
from datetime import datetime, timedelta

# Våra egna beräkningar
import berakningar

st.set_page_config(page_title="Malin-produktionsapp", layout="wide")

# Google Sheets setup
SHEET_URL = st.secrets["SHEET_URL"]
SHEET_NAME = "Blad1"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

def skapa_koppling():
    return client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)

def hamta_data():
    sheet = skapa_koppling()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def spara_data(df):
    sheet = skapa_koppling()
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

# Initiera session_state
def init_state():
    if "df" not in st.session_state:
        try:
            st.session_state.df = hamta_data()
        except Exception:
            st.session_state.df = pd.DataFrame()

    # Defaults för alla inputs
    keys = [
        "in_man", "in_svarta", "in_fitta", "in_rumpa", "in_dp", "in_dpp", "in_dap", "in_tap",
        "in_pappan", "in_grannar", "in_nils_vanner", "in_nils_familj", "in_bekanta",
        "in_eskilstuna", "in_bonus_deltagit", "in_personal_deltagit",
        "in_alskar", "in_sover", "in_tid_s", "in_tid_d", "in_vila",
        "in_dt_tid", "in_dt_vila"
    ]
    for k in keys:
        st.session_state.setdefault(k, 0)

    # extra: Nils slumpas av scenarion
    st.session_state.setdefault("in_nils", 0)

init_state()

# ======== UI – Inmatningsraden (exakt ordning) ========
st.subheader("Input")

with st.container():
    st.number_input("Män",                 min_value=0, step=1, key="in_man")
    st.number_input("Svarta",              min_value=0, step=1, key="in_svarta")
    st.number_input("Fitta",               min_value=0, step=1, key="in_fitta")
    st.number_input("Rumpa",               min_value=0, step=1, key="in_rumpa")
    st.number_input("DP",                  min_value=0, step=1, key="in_dp")
    st.number_input("DPP",                 min_value=0, step=1, key="in_dpp")
    st.number_input("DAP",                 min_value=0, step=1, key="in_dap")
    st.number_input("TAP",                 min_value=0, step=1, key="in_tap")
    st.number_input("Pappans vänner",      min_value=0, step=1, key="in_pappan")
    st.number_input("Grannar",             min_value=0, step=1, key="in_grannar")
    st.number_input("Nils vänner",         min_value=0, step=1, key="in_nils_vanner")
    st.number_input("Nils familj",         min_value=0, step=1, key="in_nils_familj")
    st.number_input("Bekanta",             min_value=0, step=1, key="in_bekanta")
    st.number_input("Eskilstuna killar",   min_value=0, step=1, key="in_eskilstuna")
    st.number_input("Bonus deltagit",      min_value=0, step=1, key="in_bonus_deltagit")
    st.number_input("Personal deltagit",   min_value=0, step=1, key="in_personal_deltagit")
    st.number_input("Älskar",              min_value=0, step=1, key="in_alskar")
    st.number_input("Sover med (0/1)",     min_value=0, max_value=1, step=1, key="in_sover")
    st.number_input("Tid S (sek)",         min_value=0, step=1, key="in_tid_s")
    st.number_input("Tid D (sek)",         min_value=0, step=1, key="in_tid_d")
    st.number_input("Vila (sek)",          min_value=0, step=1, key="in_vila")
    st.number_input("DT tid (sek/kille)",  min_value=0, step=1, key="in_dt_tid")
    st.number_input("DT vila (sek/kille)", min_value=0, step=1, key="in_dt_vila")

# ======== Scenarion ========
st.subheader("Scenarier")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Slumpa scen vit"):
        berakningar.scenario_vit()
with col2:
    if st.button("Slumpa scen svart"):
        berakningar.scenario_svarta()
with col3:
    if st.button("Vila i hemmet"):
        berakningar.scenario_vila_hemma()

# ======== Spara rad ========
if st.button("Spara rad"):
    # Hämta inputvärden
    rad = {k: st.session_state[k] for k in st.session_state if k.startswith("in_")}

    df = st.session_state.df.copy()
    ny_rad = pd.DataFrame([rad])
    df = pd.concat([df, ny_rad], ignore_index=True)

    # Beräkna allt via berakningar
    df = berakningar.beräkna_rader(df)

    # Spara tillbaka
    st.session_state.df = df
    spara_data(df)
    st.success("Rad sparad och beräknad!")

# ======== Visa tabell ========
st.subheader("Databas")
if not st.session_state.df.empty:
    st.dataframe(st.session_state.df)
else:
    st.write("Ingen data sparad ännu.")
