import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import math

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"
RUBRIKER = [
    "Datum", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
]

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Ladda och säkerställ rubriker
def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()
    if not data or worksheet.row_values(1) != RUBRIKER:
        worksheet.clear()
        worksheet.append_row(RUBRIKER)
        data = []
    df = pd.DataFrame(data)
    return worksheet, df

# Spara rad
def spara_rad(worksheet, rad):
    worksheet.append_row([rad.get(k, "") for k in RUBRIKER])

# Räkna fram maxvärden
def get_max_values(df):
    maxvärden = {}
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]:
        if kolumn in df.columns and not df[kolumn].isna().all():
            maxvärden[kolumn + " 2"] = int(df[kolumn].max())
        else:
            maxvärden[kolumn + " 2"] = 0
    return maxvärden

# Lägga till vilodag jobb
def lägg_till_vilodag_jobbfält(df, worksheet):
    maxvärden = get_max_values(df)
    rad = {
        "Datum": datetime.today().strftime("%Y-%m-%d"),
        "Jobb": math.ceil(maxvärden["Jobb 2"] * 0.5),
        "Grannar": math.ceil(maxvärden["Grannar 2"] * 0.5),
        "Tjej PojkV": math.ceil(maxvärden["Tjej PojkV 2"] * 0.5),
        "Nils Fam": math.ceil(maxvärden["Nils Fam 2"] * 0.5),
        "Älskar": 12,
        "Sover med": 1,
    }
    for fält in RUBRIKER:
        if fält not in rad and fält != "Datum":
            rad[fält] = 0
    spara_rad(worksheet, rad)
    st.success("Vilodag jobb tillagd.")

# Lägga till vilodag hemma
def lägg_till_vilodag_hemma(df, worksheet):
    rad = {
        "Datum": datetime.today().strftime("%Y-%m-%d"),
        "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3,
        "Älskar": 6,
    }
    for fält in RUBRIKER:
        if fält not in rad and fält != "Datum":
            rad[fält] = 0
    spara_rad(worksheet, rad)
    st.success("Vilodag hemma tillagd.")

# Lägg till ny rad från formulär
def lägg_till_manuell_rad(worksheet):
    st.subheader("Lägg till ny rad")
    with st.form("ny_rad"):
        datum = st.date_input("Datum", datetime.today())
        fältvärden = {"Datum": datum.strftime("%Y-%m-%d")}
        for fält in RUBRIKER[1:]:
            if "Tid" in fält or fält == "Vila":
                fältvärden[fält] = st.number_input(fält, min_value=0, step=1, value=0)
            else:
                fältvärden[fält] = st.number_input(fält, min_value=0, step=1, value=0)
        submit = st.form_submit_button("Lägg till ny rad")
        if submit:
            spara_rad(worksheet, fältvärden)
            st.success("Ny rad tillagd.")

# Visa huvudpresentation
def presentera_huvudvy(df):
    st.subheader("Huvudvy")
    df = df.fillna(0)
    df[RUBRIKER[1:]] = df[RUBRIKER[1:]].astype(int)

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt Män"] = df["Män"] + df["Känner"]

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    totalt_svarta = df["Svarta"].sum()

    # Undvik division med noll
    try:
        snitt_män_känner = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])
    except ZeroDivisionError:
        snitt_män_känner = 0

    filmer = df["Män"].sum()  # Förenklad modell för demo
    pris = 19.99
    intäkter = filmer * pris
    malin_lön = min(intäkter * 0.01, 1500)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön

    maxvärden = get_max_values(df)
    gangb_nämnare = sum(maxvärden.values())
    gangb = totalt_känner / gangb_nämnare if gangb_nämnare else 0

    älskat_nämnare = df["Känner"].sum()
    älskat = df["Älskar"].sum() / älskat_nämnare if älskat_nämnare else 0

    vita_procent = ((totalt_män - totalt_svarta) / totalt_män) * 100 if totalt_män else 0
    svarta_procent = (totalt_svarta / totalt_män) * 100 if totalt_män else 0

    st.write(f"**Totalt Män:** {totalt_män}")
    st.write(f"**Snitt (Män + Känner):** {snitt_män_känner:.2f} per rad")
    st.write(f"**Intäkter:** {intäkter:.2f} USD")
    st.write(f"**Malin lön:** {malin_lön:.2f} USD")
    st.write(f"**Företag lön:** {företag_lön:.2f} USD")
    st.write(f"**Vänner lön:** {vänner_lön:.2f} USD")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Vita (%):** {vita_procent:.2f}%")
    st.write(f"**Svarta (%):** {svarta_procent:.2f}%")

# Visa rad för enskilt datum
def presentera_rad(df):
    st.subheader("Radvy")
    df = df.fillna(0)
    if not df.empty:
        datumlista = df["Datum"].tolist()
        vald = st.selectbox("Välj datum", datumlista)
        rad = df[df["Datum"] == vald].iloc[0]
        rad["Känner"] = rad["Jobb"] + rad["Grannar"] + rad["Tjej PojkV"] + rad["Nils Fam"]
        rad["Totalt Män"] = rad["Män"] + rad["Känner"]
        filmer = rad["Män"]
        pris = 19.99
        intäkter = filmer * pris
        st.write(f"**Filmer:** {filmer}")
        st.write(f"**Intäkter:** {intäkter:.2f} USD")
        st.write(f"**Tid kille:** visas i senare version")
        st.write(f"**Klockan:** visas i senare version")

# Huvudfunktion
def main():
    st.title("MalinData App")
    worksheet, df = load_data()

    # Lägg till rad manuellt
    lägg_till_manuell_rad(worksheet)

    # Knapp för vilodagar
    if st.button("Vilodag jobb"):
        lägg_till_vilodag_jobbfält(df, worksheet)
    if st.button("Vilodag hemma"):
        lägg_till_vilodag_hemma(df, worksheet)

    # Presentera
    presentera_huvudvy(df)
    presentera_rad(df)

if __name__ == "__main__":
    main()
