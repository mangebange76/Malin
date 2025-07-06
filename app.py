import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import numpy as np

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"
START_TIME = datetime.strptime("07:00", "%H:%M")

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Skapa rubriker om de saknas
def create_headers_if_missing(ws):
    headers = ["Datum", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA", "Tid singel", "Tid dubbel", "Tid trippel", "Vila",
               "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"]
    existing = ws.row_values(1)
    if existing != headers:
        ws.delete_rows(1, len(existing))  # Rensa om rubriker är fel
        ws.insert_row(headers, 1)

# Ladda data från Google Sheet
def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet(SHEET_NAME)
    create_headers_if_missing(ws)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    return ws, df

# Spara en ny rad i Google Sheet
def save_new_row(ws, new_row):
    ws.append_row(new_row, value_input_option="USER_ENTERED")

# Beräkna maxvärden
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df else 0,
    }

# Skapa vilodag
def generate_rest_day(mode, max_values):
    if mode == "jobb":
        return {
            "Jobb": round(max_values["Jobb 2"] * 0.5),
            "Grannar": round(max_values["Grannar 2"] * 0.5),
            "Tjej PojkV": round(max_values["Tjej PojkV 2"] * 0.5),
            "Nils Fam": round(max_values["Nils Fam 2"] * 0.5),
            "Älskar": 12,
            "Sover med": 1
        }
    elif mode == "hemma":
        return {
            "Jobb": 3,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils Fam": 3,
            "Älskar": 6,
            "Sover med": 0
        }

# Huvudpresentation
def show_summary(df, max_values):
    män_sum = df["Män"].sum()
    känner = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    känner_total = känner.sum()
    totalt_män = män_sum + känner_total
    rader_med_data = df[(df["Män"] > 0) | (känner > 0)].shape[0]
    snitt_män_känner = totalt_män / rader_med_data if rader_med_data else 0
    filmer = df["Män"].sum()
    pris = 19.99
    intäkter = filmer * pris
    malin = min(intäkter * 0.01, 1500)
    företag = intäkter * 0.4
    vänner = intäkter - malin - företag
    gangb = känner_total / sum(max_values.values()) if sum(max_values.values()) > 0 else 0
    älskat = df["Älskar"].sum() / känner_total if känner_total > 0 else 0
    svarta_total = df["Svarta"].sum()
    vita_proc = (män_sum - svarta_total) / män_sum * 100 if män_sum > 0 else 0
    svarta_proc = svarta_total / män_sum * 100 if män_sum > 0 else 0

    st.subheader("Huvudvy")
    st.markdown(f"**Totalt Män:** {män_sum}")
    st.markdown(f"**Snitt (Män + Känner):** {snitt_män_känner:.2f}")
    st.markdown(f"**Malin lön:** {malin:.2f} USD")
    st.markdown(f"**Vänner lön:** {vänner:.2f} USD")
    st.markdown(f"**GangB:** {gangb:.2f}")
    st.markdown(f"**Älskat:** {älskat:.2f}")
    st.markdown(f"**Vita (%):** {vita_proc:.1f}%")
    st.markdown(f"**Svarta (%):** {svarta_proc:.1f}%")

# Presentation av vald rad
def show_selected_row(df, index):
    rad = df.iloc[index]
    tid_kille = rad.get("Tid kille", None)
    filmer = rad.get("Filmer", None)
    intäkter = rad.get("Intäkter", None)
    klockan = rad.get("Klockan", None)

    st.subheader("Vald rad")
    if pd.notna(tid_kille):
        st.write(f"**Tid kille:** {round(tid_kille, 2)} min")
    if pd.notna(filmer):
        st.write(f"**Filmer:** {int(filmer)}")
    if pd.notna(intäkter):
        st.write(f"**Intäkter:** {round(intäkter, 2)} USD")
    if pd.notna(klockan):
        st.write(f"**Klockan:** {klockan}")

# -----------------------
# Huvudfunktion
# -----------------------
def main():
    st.title("MalinData App")
    worksheet, df = load_data()
    max_values = get_max_values(df)

    # Formulär för att lägga till rad
    with st.expander("➕ Lägg till ny rad"):
        with st.form("add_form"):
            today = datetime.today().strftime('%Y-%m-%d')
            datum = st.text_input("Datum", today)
            män = st.number_input("Män", 0)
            f = st.number_input("F", 0)
            r = st.number_input("R", 0)
            dm = st.number_input("Dm", 0)
            df_ = st.number_input("Df", 0)
            dr = st.number_input("Dr", 0)
            tpp = st.number_input("TPP", 0)
            tap = st.number_input("TAP", 0)
            tpa = st.number_input("TPA", 0)
            tid_singel = st.number_input("Tid singel (sekunder)", 0)
            tid_dubbel = st.number_input("Tid dubbel (sekunder)", 0)
            tid_trippel = st.number_input("Tid trippel (sekunder)", 0)
            vila = st.number_input("Vila (sekunder)", 0)
            älskar = st.number_input("Älskar", 0)
            älsk_tid = st.number_input("Älsk tid (minuter)", 0)
            sover_med = st.number_input("Sover med", 0)
            jobb = st.number_input("Jobb", 0)
            grannar = st.number_input("Grannar", 0)
            tjej_pojkv = st.number_input("Tjej PojkV", 0)
            nils_fam = st.number_input("Nils Fam", 0)
            svarta = st.number_input("Svarta", 0)

            submitted = st.form_submit_button("Spara rad")
            if submitted:
                new_row = [datum, män, f, r, dm, df_, dr, tpp, tap, tpa, tid_singel, tid_dubbel, tid_trippel, vila,
                           älskar, älsk_tid, sover_med, jobb, grannar, tjej_pojkv, nils_fam, svarta]
                save_new_row(worksheet, new_row)
                st.success("Raden har sparats. Ladda om appen för att se uppdatering.")

    # Knappar för vilodagar
    st.markdown("### 📅 Snabbinmatning")
    if st.button("➕ Vilodag jobb"):
        data = generate_rest_day("jobb", max_values)
        today = datetime.today().strftime('%Y-%m-%d')
        new_row = [today, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                   data["Älskar"], 0, data["Sover med"],
                   data["Jobb"], data["Grannar"], data["Tjej PojkV"], data["Nils Fam"], 0]
        save_new_row(worksheet, new_row)
        st.success("Vilodag (jobb) inlagd")

    if st.button("➕ Vilodag hemma"):
        data = generate_rest_day("hemma", max_values)
        today = datetime.today().strftime('%Y-%m-%d')
        new_row = [today, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                   data["Älskar"], 0, data["Sover med"],
                   data["Jobb"], data["Grannar"], data["Tjej PojkV"], data["Nils Fam"], 0]
        save_new_row(worksheet, new_row)
        st.success("Vilodag (hemma) inlagd")

    # Presentation
    st.divider()
    if not df.empty:
        show_summary(df, max_values)
        index = st.number_input("Välj radnummer", min_value=0, max_value=len(df) - 1, step=1)
        show_selected_row(df, index)

# Kör appen
if __name__ == "__main__":
    main()
