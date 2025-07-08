import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import random

# Autentisering
def auth_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Säkerställ att headers är korrekta
def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.resize(1)
        worksheet.update("A1", [headers])

# Ladda data
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

    for col in headers:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

# Spara ny rad
def append_row(worksheet, row_dict):
    values = [row_dict.get(col, 0) for col in worksheet.row_values(1)]
    worksheet.append_row(values)

# Uppdatera rad
def update_row(worksheet, index, row_dict):
    col_names = worksheet.row_values(1)
    values = [row_dict.get(col, 0) for col in col_names]
    range_str = f"A{index+2}:{chr(ord('A')+len(col_names)-1)}{index+2}"
    worksheet.update(range_str, [values])

# Beräkningar
def update_calculations(df):
    # Känner 2
    känner2 = {
        "Jobb 2": df["Jobb 2"].max(),
        "Grannar 2": df["Grannar 2"].max(),
        "Tjej PojkV 2": df["Tjej PojkV 2"].max(),
        "Nils fam 2": df["Nils fam 2"].max()
    }
    df["Känner 2"] = sum(känner2.values())

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner 2"]

    # Grabbar
    df["Grabbar"] = df["Totalt män"]

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, np.nan)

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, np.nan)

    # Runk
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, np.nan)

    # Summa singel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DR"])

    # Summa trippel
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa vila
    df["Summa vila"] = df["Vila"]

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + (df["Tid Dubbel"] * 2) + (df["Tid Trippel"] * 3) + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Filmer
    df["Filmer"] = np.where(df["Män"] > 0, 1, 0)

    # Pris
    df["Pris"] = 39.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön
    df["Malin lön"] = (df["Intäkter"] * 0.01).clip(upper=800)

    # Företagets lön
    df["Företag lön"] = 10000

    # Klockan
    def calc_klockan(row):
        start = datetime.strptime("07:00", "%H:%M")
        minutes = row["Summa tid"] + row["Total tid"]
        return (start + timedelta(minutes=minutes)).strftime("%H:%M")

    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# Statistik i huvudvyn
def visa_presentation(df):
    st.header("Presentation")

    # Känner 2 = största värdet från respektive fält
    känner2 = {
        "Jobb 2": df["Jobb 2"].max(),
        "Grannar 2": df["Grannar 2"].max(),
        "Tjej PojkV 2": df["Tjej PojkV 2"].max(),
        "Nils fam 2": df["Nils fam 2"].max()
    }
    känner_summa = sum(känner2.values())

    totalt_män = df["Män"].sum() + känner_summa
    snitt_film = totalt_män / len(df[df["Män"] > 0])
    älskat = df["Älskar"].sum() / känner_summa if känner_summa > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (kompisar):** {känner_summa}")
    st.write(f"**Jobb:** {känner2['Jobb 2']}")
    st.write(f"**Grannar:** {känner2['Grannar 2']}")
    st.write(f"**Tjej PojkV:** {känner2['Tjej PojkV 2']}")
    st.write(f"**Nils fam:** {känner2['Nils fam 2']}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")

    antal_filmer = df[df["Män"] > 0].shape[0]
    privat_gb = df[(df["Män"] == 0) & (df["Känner 2"] > 0)].shape[0]
    antal_dagar = len(df)

    st.write(f"**Antal filmer:** {antal_filmer}")
    st.write(f"**PrivatGB:** {privat_gb}")
    st.write(f"**Antal dagar:** {antal_dagar}")

    total_intakt = df["Intäkter"].sum()
    total_malin = df["Malin lön"].sum()
    total_företag = min(10000, df["Företag lön"].sum())
    vänner_lön = (total_intakt - total_malin - total_företag) / känner_summa if känner_summa > 0 else 0

    st.write(f"**Intäkter totalt:** ${total_intakt:,.2f}")
    st.write(f"**Malins lön:** ${total_malin:,.2f}")
    st.write(f"**Företagets lön:** ${total_företag:,.2f}")
    st.write(f"**Vänner lön (per kompis):** ${vänner_lön:,.2f}")

# Radvy för att redigera och uppdatera data
def radvy(df, worksheet):
    st.header("Radvy")
    if df.empty:
        st.info("Ingen data tillgänglig.")
        return

    index = st.number_input("Välj rad att visa/uppdatera (0 till n)", min_value=0, max_value=len(df) - 1, step=1)
    rad = df.iloc[index].copy()

    with st.form(key="radform"):
        updated = {}
        for col in df.columns:
            if col in ["Summa singel", "Summa dubbel", "Summa trippel", "Summa tid", "Klockan", "Tid kille", "Intäkter", "Malin lön", "Företag lön", "Vänner lön", "Grabbar", "Snitt", "Total tid", "Tid kille DT", "Runk"]:
                st.text_input(col, value=str(rad[col]), disabled=True)
            elif col == "Dag":
                st.number_input(col, value=int(rad[col]), step=1, disabled=True)
            elif isinstance(rad[col], int):
                updated[col] = st.number_input(col, value=int(rad[col]), step=1)
            elif isinstance(rad[col], float):
                updated[col] = st.number_input(col, value=float(rad[col]), step=0.1)
            else:
                updated[col] = st.text_input(col, value=str(rad[col]))

        if st.form_submit_button("Uppdatera rad"):
            for key in updated:
                df.at[index, key] = updated[key]
            df = update_calculations(df)
            row_dict = df.iloc[index].to_dict()
            update_row(worksheet, index, row_dict)
            st.success("Raden har uppdaterats.")

# Funktion för att slumpa en ny rad
def slumpa_rad(df, worksheet):
    if df.empty:
        ny_dag = 1
    else:
        ny_dag = df["Dag"].max() + 1

    max_values = df.max(numeric_only=True)
    ny_rad = {}
    for col in df.columns:
        if col == "Dag":
            ny_rad[col] = ny_dag
        elif col == "Älskar":
            ny_rad[col] = 8
        elif col == "Sover med":
            ny_rad[col] = 1
        elif col == "Vila":
            ny_rad[col] = 7
        elif col == "Älsk tid":
            ny_rad[col] = 30
        elif col in max_values:
            ny_rad[col] = int(random.randint(0, max_values[col]))
        else:
            ny_rad[col] = 0

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict())
    st.success("Slumpmässig rad tillagd.")

# Funktion för att kopiera raden med flest "Totalt män"
def kopiera_största_rad(df, worksheet):
    if df.empty or "Totalt män" not in df.columns:
        st.warning("Ingen data tillgänglig eller kolumnen 'Totalt män' saknas.")
        return

    max_index = df["Totalt män"].idxmax()
    ny_dag = df["Dag"].max() + 1 if not df.empty else 1
    ny_rad = df.iloc[max_index].copy()
    ny_rad["Dag"] = ny_dag

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict())
    st.success("Kopierade raden med flest 'Totalt män'.")

# Funktion för "Vilodag hemma"
def vilodag_hemma(df, worksheet):
    ny_dag = df["Dag"].max() + 1 if not df.empty else 1
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = ny_dag
    ny_rad["Vila"] = 7
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Älsk tid"] = 30

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict())
    st.success("Vilodag hemma tillagd.")

# Funktion för "Vilodag jobb"
def vilodag_jobb(df, worksheet):
    ny_dag = df["Dag"].max() + 1 if not df.empty else 1
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = ny_dag
    ny_rad["Vila"] = 7
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Älsk tid"] = 30

    for col in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if col in df.columns:
            ny_rad[col] = int(df[col].max() * 0.3)

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict())
    st.success("Vilodag jobb tillagd.")

# Kör appen
if __name__ == "__main__":
    main()
