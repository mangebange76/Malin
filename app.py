# Del 1: Importer, autentisering, ladda data och säkerställ kolumner

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import random

# Autentisering till Google Sheets
def auth_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Säkerställ rubrikerna i kalkylbladet
def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.resize(1)
        worksheet.update("A1", [headers])

# Ladda data och skapa kolumner om de saknas
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

# Hjälpfunktion: nästa dag (heltal) efter senaste dag i df
def nästa_dag(df):
    if df.empty or "Dag" not in df.columns:
        return 1
    else:
        return int(df["Dag"].max()) + 1

# Uppdatera alla beräkningar i df
def update_calculations(df):
    # Säkerställ att alla kolumner finns
    kolumner = [
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Män", "Älskar", "Totalt män",
        "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila", "DM", "DF", "DR",
        "TPP", "TAP", "TPA", "Filmer", "Pris", "Intäkter",
        "Malin lön", "Företag lön", "Vänner lön", "Sover med", "Svarta",
        "DeepT", "Sekunder", "Varv"
    ]
    for k in kolumner:
        if k not in df.columns:
            df[k] = 0

    # Känner 2 = maxvärden för respektive
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()

    df["Jobb 2"] = jobb_2
    df["Grannar 2"] = grannar_2
    df["Tjej PojkV 2"] = tjej_2
    df["Nils fam 2"] = nils_2

    # Känner = summa av maxvärden (Känner 2)
    df["Känner"] = jobb_2 + grannar_2 + tjej_2 + nils_2

    # Grabbar = Män + Känner (på radnivå)
    df["Grabbar"] = df["Män"] + df["Känner"]

    # Totalt män = Män + Känner 2
    df["Totalt män"] = df["Män"] + df["Känner"]

    # Summa singel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DR"])

    # Summa trippel
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa vila
    df["Summa vila"] = (
        df["Totalt män"] * df["Vila"]
        + (df["DM"] + df["DF"] + df["DR"]) * (df["Vila"] + 7)
        + (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)
    )

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)

    # Runk
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    # Suger (60% av summa tid / totalt män)
    df["Suger"] = (df["Summa tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    # Tid kille = tid s + 2*d + 3*t + suger + tid kille DT + runk
    df["Tid kille"] = (
        df["Tid Singel"]
        + 2 * df["Tid Dubbel"]
        + 3 * df["Tid Trippel"]
        + df["Suger"]
        + df["Tid kille DT"]
        + df["Runk"]
    )

    # Filmer
    df["Filmer"] = (
        df["Män"]
        + df["DM"] * 2
        + df["DF"] * 2
        + df["DR"] * 3
        + df["TPP"] * 4
        + df["TAP"] * 6
        + df["TPA"] * 5
    ) * df["Hårdhet"] if "Hårdhet" in df.columns else 0

    # Pris (fast)
    df["Pris"] = 39.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön – 1% av intäkter, max 800
    df["Malin lön"] = (df["Intäkter"] * 0.01).clip(upper=800)

    # Företag lön – max 10000 USD
    df["Företag lön"] = df["Intäkter"] * 0.4
    df["Företag lön"] = df["Företag lön"].clip(upper=10000)

    # Vänner lön – (summa intäkter - Malin lön - Företag lön) / känner 2
    tot_int = df["Intäkter"].sum()
    tot_malin = df["Malin lön"].sum()
    tot_företag = df["Företag lön"].sum()
    känner2 = jobb_2 + grannar_2 + tjej_2 + nils_2
    df["Vänner lön"] = (tot_int - tot_malin - tot_företag) / (känner2 if känner2 > 0 else 1)

    # Klockan (07:00 + tid)
    def calc_klockan(row):
        start = datetime.strptime("07:00", "%H:%M")
        tot_min = (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Total tid"]) / 60
        return (start + timedelta(minutes=tot_min)).strftime("%H:%M")

    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# === KNAPP: Kopiera största raden ===
def kopiera_max(df, worksheet):
    if df.empty:
        return
    max_index = df["Totalt män"].idxmax()
    ny_rad = df.loc[max_index].copy()
    ny_rad["Dag"] = nästa_dag(df)
    ny_rad_dict = ny_rad.to_dict()
    append_row(ny_rad_dict, worksheet)

# === KNAPP: Slumpa rad ===
def slumpa_rad(df, worksheet):
    if df.empty:
        return
    new_row = {}
    for col in df.columns:
        if col in ["Dag", "Älskar", "Sover med", "Vila", "Älsk tid"]:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            new_row[col] = random.randint(int(df[col].min()), int(df[col].max()))
        else:
            new_row[col] = ""
    new_row["Älskar"] = 8
    new_row["Sover med"] = 1
    new_row["Vila"] = 7
    new_row["Älsk tid"] = 30
    new_row["Dag"] = nästa_dag(df)

    df = df.append(new_row, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict(), worksheet)

# === KNAPP: Vilodag hemma ===
def vilodag_hemma(df, worksheet):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = nästa_dag(df)
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    append_row(ny_rad, worksheet)

# === KNAPP: Vilodag jobb (30% av maxvärde för vissa kolumner) ===
def vilodag_jobb(df, worksheet):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = nästa_dag(df)
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    for col in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        ny_rad[col] = int(df[col].max() * 0.3)
    append_row(ny_rad, worksheet)

# === PRESENTATION: Huvudvy ===
def huvudvy(df):
    st.header("📊 Huvudvy")

    # Känner 2 (maxvärden)
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()
    känner2 = jobb_2 + grannar_2 + tjej_2 + nils_2

    # Totalt antal män = Män + Känner 2 (per rad)
    df["Grabbar"] = df["Män"] + känner2
    totalt_män = df["Grabbar"].sum()

    # Antal filmer (rader med Män > 0)
    antal_filmer = df[df["Män"] > 0].shape[0]

    # PrivatGB (rader med Män = 0 men Känner > 0)
    privat_gb = df[(df["Män"] == 0) & (df["Känner"] > 0)].shape[0]

    # Snitt film
    snitt_film = (df["Män"].sum() + känner2) / antal_filmer if antal_filmer > 0 else 0

    # GangB
    gangb = df["Känner"].sum() / känner2 if känner2 > 0 else 0

    # Älskat
    älskat = df["Älskar"].sum() / känner2 if känner2 > 0 else 0

    # Sover med / Nils fam 2
    sover_med = df["Sover med"].sum() / nils_2 if nils_2 > 0 else 0

    # Vita/Svarta
    svarta_sum = df["Svarta"].sum()
    vita = (totalt_män - svarta_sum) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = svarta_sum / totalt_män * 100 if totalt_män > 0 else 0

    # Ekonomi
    filmer = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    företag_lön = min(df["Företag lön"].sum(), 10000)
    vänner_lön = (intäkter - malin_lön - företag_lön) / känner2 if känner2 > 0 else 0

    antal_dagar = df.shape[0]

    # === Presentation ===
    st.markdown(f"""
    **Totalt antal män:** {totalt_män}  
    **Känner (kompisar):** {känner2}  
    **Jobb:** {jobb_2}  
    **Grannar:** {grannar_2}  
    **Tjej PojkV:** {tjej_2}  
    **Nils fam:** {nils_2}  
    **Antal filmer:** {antal_filmer}  
    **PrivatGB:** {privat_gb}  
    **Snitt film:** {snitt_film:.2f}  
    **GangB:** {gangb:.2f}  
    **Älskat:** {älskat:.2f}  
    **Sover med / Nils fam 2:** {sover_med:.2f}  
    **Vita (%):** {vita:.1f}%  
    **Svarta (%):** {svarta:.1f}%  
    **Filmer:** {filmer}  
    **Intäkter:** ${intäkter:.2f}  
    **Malin lön:** ${malin_lön:.2f}  
    **Företagets lön:** ${företag_lön:.2f}  
    **Vänner lön (per kompis):** ${vänner_lön:.2f}  
    **Antal dagar:** {antal_dagar}
    """)

# === PRESENTATION: Radvy ===
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

# === MAIN-FUNKTION ===
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
        if st.button("📋 Kopiera största raden"):
            kopiera_max(df, worksheet)
    with col4:
        if st.button("🎲 Slumpa rad"):
            slumpa_rad(df, worksheet)

    inmatning(df, worksheet)
    huvudvy(df)
    radvy(df, worksheet)

if __name__ == "__main__":
    main()
