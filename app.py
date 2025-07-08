import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import random

# Google Sheets autentisering
def auth_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Säkerställ rubriker i sheet, skapa om de saknas eller ändra ordning
def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.resize(1)
        worksheet.update("A1", [headers])

# Ladda data från Google Sheet
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Dag","Män","Fi","Rö","DM","DF","DR","TPP","TAP","TPA",
        "Älskar","Sover med","Känner","Jobb","Jobb 2","Grannar","Grannar 2",
        "Tjej PojkV","Tjej PojkV 2","Nils fam","Nils fam 2","Totalt män",
        "Tid Singel","Tid Dubbel","Tid Trippel","Vila",
        "Summa singel","Summa dubbel","Summa trippel","Summa vila","Summa tid",
        "Klockan","Tid kille","Suger","Filmer","Pris","Intäkter",
        "Malin lön","Företag lön","Vänner lön","Hårdhet",
        "DeepT","Grabbar","Snitt","Sekunder","Varv","Total tid","Tid kille DT","Runk",
        "Svarta"
    ]

    ensure_headers(worksheet, headers)

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

    # Säkerställ att alla kolumner finns i df, annars lägg till med 0 som default
    for col in headers:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

# Spara eller uppdatera rad i sheet (append eller update)
def append_row(worksheet, row_dict):
    values = [row_dict.get(col, 0) for col in worksheet.row_values(1)]
    worksheet.append_row(values)

def update_row(worksheet, index, row_dict):
    col_names = worksheet.row_values(1)
    values = [row_dict.get(col, 0) for col in col_names]
    range_str = f"A{index+2}:{chr(ord('A')+len(col_names)-1)}{index+2}"
    worksheet.update(range_str, [values])

# Hämta nästa dag som ett heltal (dag 1, 2, 3...)
def nästa_dag(df):
    if df.empty or df["Dag"].isnull().all():
        return 1
    else:
        return int(df["Dag"].max()) + 1

# Uppdatera alla beräkningar i df
def update_calculations(df):
    # Maxvärden för "känner 2"
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()

    df["Jobb 2"] = jobb_2
    df["Grannar 2"] = grannar_2
    df["Tjej PojkV 2"] = tjej_2
    df["Nils fam 2"] = nils_2

    känner2 = jobb_2 + grannar_2 + tjej_2 + nils_2
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)

    # Totalt män
    df["Totalt män"] = df["Män"] + känner2

    # Grabbar (radnivå män + känner)
    df["Grabbar"] = df["Män"] + df["Känner"]

    # Summa singel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DR"])

    # Summa trippel
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa vila
    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + \
                       (df["DM"] + df["DF"] + df["DR"]) * (df["Vila"] + 7) + \
                       (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT och Runk
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    # Suger
    df["Suger"] = 0
    mask = df["Totalt män"] > 0
    df.loc[mask, "Suger"] = (df.loc[mask, "Summa tid"] * 0.6) / df.loc[mask, "Totalt män"]

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + 2*df["Tid Dubbel"] + 3*df["Tid Trippel"] + \
                      df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Klockan (baserat på 07:00)
    def calc_klockan(row):
        total_min = row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Total tid"]
        start = datetime.strptime("07:00", "%H:%M")
        sluttid = start + timedelta(minutes=total_min)
        return sluttid.strftime("%H:%M")

    df["Klockan"] = df.apply(calc_klockan, axis=1)

    # Pris, intäkter, Malin lön, företagets lön, vänner lön
    df["Pris per film"] = 39.99
    df["Filmer"] = df["Totalt män"]
    df["Intäkter"] = df["Filmer"] * df["Pris per film"]

    df["Malin lön"] = (df["Intäkter"] * 0.01).clip(upper=800)
    df["Företagets lön"] = 10000
    df["Vänner lön"] = (df["Intäkter"] - df["Malin lön"] - df["Företagets lön"]) / känner2 if känner2 > 0 else 0

    return df

# ------------- PRESENTATION I HUVUDVYN -------------

def huvudvy(df):
    st.title("💖 MalinApp – Översikt")

    # Känner 2 = maxvärden av Jobb, Grannar, Tjej PojkV, Nils fam
    känner2 = df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2"]].iloc[0].sum()

    antal_filmer = df[df["Män"] > 0].shape[0]
    privat_gb = df[(df["Män"] == 0) & (df["Känner"] > 0)].shape[0]

    st.write(f"**Totalt antal män:** {df['Totalt män'].sum()}")
    st.write(f"**Känner (kompisar):** {känner2}")
    st.write(f"**Jobb:** {df['Jobb'].sum()}")
    st.write(f"**Grannar:** {df['Grannar'].sum()}")
    st.write(f"**Tjej PojkV:** {df['Tjej PojkV'].sum()}")
    st.write(f"**Nils fam:** {df['Nils fam'].sum()}")
    st.write(f"**Snitt film:** {(df['Män'].sum() + känner2) / max(1, df[df['Män'] > 0].shape[0]):.2f}")
    st.write(f"**GangB:** {df['DM'].sum() + df['DF'].sum() + df['DR'].sum()}")
    st.write(f"**Älskat:** {df['Älskar'].sum() / max(1, känner2):.2f}")
    st.write(f"**Sover med:** {df['Sover med'].sum()}")
    st.write(f"**Filmer:** {df['Filmer'].sum()}")
    st.write(f"**Intäkter:** ${df['Intäkter'].sum():,.0f}")
    st.write(f"**Malins lön:** ${df['Malin lön'].sum():,.0f}")
    st.write(f"**Företagets lön:** ${df['Företagets lön'].sum():,.0f}")
    st.write(f"**Vänner lön (per kompis):** ${df['Vänner lön'].sum():,.2f}")
    st.write(f"**Antal filmer:** {antal_filmer}")
    st.write(f"**PrivatGB:** {privat_gb}")
    st.write(f"**Antal dagar:** {df.shape[0]}")

# ------------- RADVY -------------

def radvy(df, worksheet):
    st.subheader("🧾 Senaste rad – detaljer")

    if df.empty:
        st.warning("Ingen data tillgänglig.")
        return

    rad = df.iloc[-1]
    index = df.index[-1]

    st.write(f"**Dag:** {rad['Dag']}")
    st.write(f"**Totalt män:** {rad['Totalt män']}")
    st.write(f"**Klockan:** {rad['Klockan']}")
    st.write(f"**Tid kille:** {rad['Tid kille']:.2f} min")
    st.write(f"**Filmer:** {rad['Filmer']}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")

    st.markdown("### ✏️ Justera tider")
    with st.form("form_justera"):
        tid_s = st.number_input("Tid Singel", value=int(rad["Tid Singel"]), step=1)
        tid_d = st.number_input("Tid Dubbel", value=int(rad["Tid Dubbel"]), step=1)
        tid_t = st.number_input("Tid Trippel", value=int(rad["Tid Trippel"]), step=1)
        sekunder = st.number_input("Sekunder", value=int(rad["Sekunder"]), step=1)
        varv = st.number_input("Varv", value=int(rad["Varv"]), step=1)

        submit = st.form_submit_button("💾 Spara ändringar")
        if submit:
            df.at[index, "Tid Singel"] = tid_s
            df.at[index, "Tid Dubbel"] = tid_d
            df.at[index, "Tid Trippel"] = tid_t
            df.at[index, "Sekunder"] = sekunder
            df.at[index, "Varv"] = varv

            df = update_calculations(df)
            update_row(worksheet, index, df.iloc[index].to_dict())
            st.success("✅ Uppdaterat! Ladda om sidan.")

# ------------- MAIN ---------------

def main():
    st.set_page_config(page_title="MalinApp", layout="wide")

    worksheet, df = load_data()
    df = update_calculations(df)

    st.sidebar.header("➕ Snabbval")
    if st.sidebar.button("📆 Lägg till ny dag"):
        inmatning(df, worksheet)

    if st.sidebar.button("🏡 Vilodag hemma"):
        vilodag_hemma(df, worksheet)

    if st.sidebar.button("💼 Vilodag jobb"):
        vilodag_jobb(df, worksheet)

    if st.sidebar.button("📋 Kopiera största raden"):
        kopiera_max(df, worksheet)

    if st.sidebar.button("🎲 Slumpa rad"):
        slumpa_rad(df, worksheet)

    huvudvy(df)
    radvy(df, worksheet)

if __name__ == "__main__":
    main()
