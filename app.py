import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisering för Google Sheets
def auth_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes
    )
    return gspread.authorize(creds)

# Säkerställ rätt rubriker i kalkylbladet
def ensure_headers(worksheet, headers):
    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(1)
        worksheet.update("A1", [headers])

# Läs in data från Google Sheets
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Datum","Män","Fi","Rö","DM","DF","DR",
        "TPP","TAP","TPA","Älskar","Sover med","Jobb","Jobb 2",
        "Grannar","Grannar 2","Tjej PojkV","Tjej PojkV 2","Nils fam","Nils fam 2",
        "Totalt män","Tid Singel","Tid Dubbel","Tid Trippel","Vila",
        "Summa singel","Summa dubbel","Summa trippel","Summa vila","Summa tid",
        "Klockan","Tid kille","Suger","Filmer","Pris","Intäkter",
        "Malin lön","Företag lön","Vänner lön","Hårdhet",
        "DeepT","Grabbar","Snitt","Sekunder","Varv",
        "Total tid","Tid kille DT","Runk","Svarta"
    ]
    ensure_headers(worksheet, headers)

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

    # Fyll på eventuella saknade kolumner
    for h in headers:
        if h not in df.columns:
            df[h] = 0

    return worksheet, df

# Uppdatera beräkningar i DataFrame
def update_calculations(df):
    # Känner 2 = maxvärden från fyra kolumner
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()

    df["Jobb 2"] = jobb_2
    df["Grannar 2"] = grannar_2
    df["Tjej PojkV 2"] = tjej_2
    df["Nils fam 2"] = nils_2

    känner_2 = jobb_2 + grannar_2 + tjej_2 + nils_2

    # Totalt män = Män + Känner 2
    df["Totalt män"] = df["Män"] + känner_2

    # Summa singel, dubbel, trippel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DR"])
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa vila
    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + \
        (df["DM"] + df["DF"] + df["DR"]) * (df["Vila"] + 7) + \
        (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Suger
    df["Suger"] = 0
    mask = df["Totalt män"] > 0
    df.loc[mask, "Suger"] = (df.loc[mask, "Summa tid"] * 0.6) / df.loc[mask, "Totalt män"]

    # DeepT, Grabbar, Snitt, Sekunder, Varv, Total tid, Tid kille DT, Runk
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + 2 * df["Tid Dubbel"] + 3 * df["Tid Trippel"] + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Hårdhet
    def calc_hårdhet(row):
        h = 0
        if row["Män"] > 0: h += 1
        if row["DM"] > 0: h += 2
        if row["DF"] > 0: h += 2
        if row["DR"] > 0: h += 4
        if row["TPP"] > 0: h += 4
        if row["TAP"] > 0: h += 6
        if row["TPA"] > 0: h += 5
        return h
    df["Hårdhet"] = df.apply(calc_hårdhet, axis=1)

    # Filmer
    df["Filmer"] = (df["Män"] + df["Fi"] + df["Rö"] + df["DM"]*2 + df["DF"]*2 + df["DR"]*3 +
                    df["TPP"]*4 + df["TAP"]*6 + df["TPA"]*5) * df["Hårdhet"]

    # Pris
    df["Pris"] = 19.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    return df

    # Malin lön (2% av intäkter, max 1000)
    df["Malin lön"] = df["Intäkter"] * 0.02
    df.loc[df["Malin lön"] > 1000, "Malin lön"] = 1000

    # Företagets lön – alltid max 10 000 USD
    df["Företag lön"] = 10000

    # Vänner lön – baserat på summering
    total_intäkter = df["Intäkter"].sum()
    total_malin = df["Malin lön"].sum()
    total_företag = df["Företag lön"].sum()
    känner_2 = df["Jobb"].max() + df["Grannar"].max() + df["Tjej PojkV"].max() + df["Nils fam"].max()
    df["Vänner lön"] = 0
    if känner_2 > 0:
        df["Vänner lön"] = (total_intäkter - total_malin - total_företag) / känner_2

    # Klockan = 07:00 + (Summa singel + Summa dubbel + Summa trippel + Total tid) i minuter
    def calc_klockan(row):
        start = datetime.strptime("07:00", "%H:%M")
        total_minuter = (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Total tid"]) / 60
        return (start + timedelta(minutes=total_minuter)).strftime("%H:%M")

    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# Ny rad via formulär
def inmatning(df, worksheet):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        inputs = [
            "Män","Fi","Rö","DM","DF","DR","TPP","TAP","TPA",
            "Älskar","Sover med","Jobb","Grannar","Tjej PojkV","Nils fam","Svarta",
            "Tid Singel","Tid Dubbel","Tid Trippel","Vila",
            "DeepT","Grabbar","Sekunder","Varv"
        ]
        for f in inputs:
            ny_rad[f] = st.number_input(f, min_value=0, step=1, key=f)

        ny_rad["Datum"] = nästa_datum(df)

        submitted = st.form_submit_button("Spara")
        if submitted:
            # Sätt defaultvärden för alla andra fält
            for col in worksheet.row_values(1):
                if col not in ny_rad:
                    ny_rad[col] = 0
            append_row(worksheet, ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Vilodag jobb – 30% av maxvärden (avrundat till heltal)
def vilodag_jobb(df, worksheet):
    ny_rad = {col: 0 for col in worksheet.row_values(1)}
    ny_rad["Datum"] = nästa_datum(df)
    ny_rad.update({
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": int(round(df["Jobb"].max() * 0.3)),
        "Grannar": int(round(df["Grannar"].max() * 0.3)),
        "Tjej PojkV": int(round(df["Tjej PojkV"].max() * 0.3)),
        "Nils fam": int(round(df["Nils fam"].max() * 0.3)),
    })
    append_row(worksheet, ny_rad)
    st.success("✅ Vilodag jobb tillagd.")

# Vilodag hemma – fasta värden
def vilodag_hemma(df, worksheet):
    ny_rad = {col: 0 for col in worksheet.row_values(1)}
    ny_rad["Datum"] = nästa_datum(df)
    ny_rad.update({
        "Älskar": 6,
        "Sover med": 0,
        "Jobb": 3,
        "Grannar": 3,
        "Tjej PojkV": 3,
        "Nils fam": 3,
    })
    append_row(worksheet, ny_rad)
    st.success("✅ Vilodag hemma tillagd.")

# Kopiera största raden (endast en, den med högst Totalt män)
def kopiera_största(df, worksheet):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    största = df.loc[df["Totalt män"].idxmax()].to_dict()
    största["Datum"] = nästa_datum(df)
    append_row(worksheet, största)
    st.success("✅ Raden med flest Totalt män kopierades.")

# Slumpa rad och beräkna efteråt
def slumpa_rad(df, worksheet):
    if df.empty:
        st.warning("Ingen data att slumpa från.")
        return

    cols_to_randomize = [
        "Män","Fi","Rö","DM","DF","DR","TPP","TAP","TPA",
        "Älskar","Sover med","Jobb","Grannar","Tjej PojkV","Nils fam","Svarta",
        "Tid Singel","Tid Dubbel","Tid Trippel","Vila",
        "DeepT","Grabbar","Sekunder","Varv"
    ]
    ny_rad = {}
    for col in cols_to_randomize:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            min_val = int(df[col].min())
            max_val = int(df[col].max())
            if col == "Älskar":
                ny_rad[col] = 8
            elif col == "Sover med":
                ny_rad[col] = 1
            elif col == "Vila":
                ny_rad[col] = 7
            else:
                ny_rad[col] = random.randint(min_val, max_val)
        else:
            ny_rad[col] = 0
    ny_rad["Datum"] = nästa_datum(df)

    for col in worksheet.row_values(1):
        if col not in ny_rad:
            ny_rad[col] = 0

    append_row(worksheet, ny_rad)
    st.success("✅ Slumpad rad tillagd. Ladda om appen för att se beräkningar.")

# Presentation huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")

    # Uppdaterade nyckelvärden
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()
    känner_2 = jobb_2 + grannar_2 + tjej_2 + nils_2
    totalt_män = df["Män"].sum() + känner_2

    gangb = df["Känner"].sum() / känner_2 if känner_2 > 0 else 0
    älskat = df["Älskar"].sum() / känner_2 if känner_2 > 0 else 0
    sover_med = df["Sover med"].sum() / nils_2 if nils_2 > 0 else 0

    snitt_film = (df["Män"].sum() + känner_2) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0

    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0

    filmer = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    företag_lön = df["Företag lön"].sum()
    vänner_lön = (intäkter - malin_lön - företag_lön) / känner_2 if känner_2 > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (Kompisar):** {känner_2}")
    st.write(f"**Jobb:** {jobb_2}")
    st.write(f"**Grannar:** {grannar_2}")
    st.write(f"**Tjej PojkV:** {tjej_2}")
    st.write(f"**Nils fam:** {nils_2}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med / Nils fam 2:** {sover_med:.2f}")
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")
    st.write(f"**Filmer:** {filmer}")
    st.write(f"**Intäkter:** ${intäkter:.2f}")
    st.write(f"**Malin lön:** ${malin_lön:.2f}")
    st.write(f"**Företagets lön:** ${företag_lön:.2f}")
    st.write(f"**Vänner lön (per kompis):** ${vänner_lön:.2f}")

# Radvy
def radvy(df, worksheet):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    rad = df.iloc[-1]
    tid_kille_min = rad["Tid kille"] / 60 if rad["Tid kille"] else 0
    marker = "⚠️ Öka tid!" if tid_kille_min < 10 else ""

    st.write(f"**Tid kille:** {tid_kille_min:.2f} min {marker}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")
    st.write(f"**Klockan:** {rad['Klockan']}")

    with st.form("form_justera_tid"):
        tid_s = st.number_input("Tid Singel", value=int(rad["Tid Singel"]), step=1)
        tid_d = st.number_input("Tid Dubbel", value=int(rad["Tid Dubbel"]), step=1)
        tid_t = st.number_input("Tid Trippel", value=int(rad["Tid Trippel"]), step=1)
        sekunder = st.number_input("Sekunder", value=int(rad.get("Sekunder", 0)), step=1)
        varv = st.number_input("Varv", value=int(rad.get("Varv", 0)), step=1)

        if st.form_submit_button("Spara ändringar"):
            index = df.index[-1]
            df.at[index, "Tid Singel"] = tid_s
            df.at[index, "Tid Dubbel"] = tid_d
            df.at[index, "Tid Trippel"] = tid_t
            df.at[index, "Sekunder"] = sekunder
            df.at[index, "Varv"] = varv

            df_updated = update_calculations(df)
            row_dict = df_updated.iloc[index].to_dict()
            update_row(worksheet, index, row_dict)
            st.success("⏱️ Tider uppdaterade! Ladda om för att se förändringar.")

# Huvudfunktion
def main():
    st.title("Malin Data App")
    worksheet, df = load_data()
    df = update_calculations(df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("➕ Vilodag jobb"):
            vilodag_jobb(df, worksheet)
    with col2:
        if st.button("➕ Vilodag hemma"):
            vilodag_hemma(df, worksheet)
    with col3:
        if st.button("📋 Kopiera största"):
            kopiera_största(df, worksheet)
    with col4:
        if st.button("🎲 Slumpa rad"):
            slumpa_rad(df, worksheet)

    inmatning(df, worksheet)
    huvudvy(df)
    radvy(df, worksheet)

if __name__ == "__main__":
    main()
