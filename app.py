import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import random

def auth_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

def ensure_headers(worksheet, headers):
    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.resize(1)
        worksheet.update("A1", [headers])

def load_data():
    client = auth_gspread()
    sheet = client.open("MalinData")
    worksheet = sheet.worksheet("Blad1")
    
    headers = [
        "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2",
        "Tjej PojkV", "Tjej PojkV 2", "Nils fam", "Nils fam 2", "Totalt män",
        "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid",
        "Klockan", "Tid kille", "Suger", "Filmer", "Pris", "Intäkter",
        "Malin lön", "Företag lön", "Vänner lön", "Hårdhet",
        "DeepT", "Grabbar", "Snitt", "Sekunder", "Varv", "Total tid", "Tid kille DT", "Runk",
        "Svarta"
    ]

    ensure_headers(worksheet, headers)

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

    for col in headers:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

def append_row(worksheet, row_dict):
    values = [row_dict.get(col, 0) for col in worksheet.row_values(1)]
    worksheet.append_row(values)

def update_row(worksheet, index, row_dict):
    col_names = worksheet.row_values(1)
    values = [row_dict.get(col, 0) for col in col_names]
    range_str = f"A{index+2}:{chr(ord('A')+len(col_names)-1)}{index+2}"
    worksheet.update(range_str, [values])

def nästa_datum(df):
    if df.empty or df["Datum"].isnull().all():
        return datetime.today().strftime("%Y-%m-%d")
    try:
        sista = pd.to_datetime(df["Datum"], errors='coerce').max()
        return (sista + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.today().strftime("%Y-%m-%d")

def update_calculations(df):
    # Maxvärden
    jobb_max = df["Jobb"].max()
    grannar_max = df["Grannar"].max()
    tjej_max = df["Tjej PojkV"].max()
    nils_max = df["Nils fam"].max()

    # Känner 2 = konstant över alla rader
    känner2 = jobb_max + grannar_max + tjej_max + nils_max
    df["Jobb 2"] = jobb_max
    df["Grannar 2"] = grannar_max
    df["Tjej PojkV 2"] = tjej_max
    df["Nils fam 2"] = nils_max

    # Totalt män = Män + Känner 2
    df["Totalt män"] = df["Män"] + känner2

    # Känner (används för presentation)
    df["Känner"] = känner2

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

    # Suger
    df["Suger"] = 0
    mask = df["Totalt män"] > 0
    df.loc[mask, "Suger"] = (df.loc[mask, "Summa tid"] * 0.6) / df.loc[mask, "Totalt män"]

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)

    # Runk
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + df["Tid Dubbel"] * 2 + df["Tid Trippel"] * 3 + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Filmer
    df["Hårdhet"] = df[["Män", "DM", "DF", "DR", "TPP", "TAP", "TPA"]].astype(bool).sum(axis=1)
    df["Filmer"] = (df["Män"] + df["Fi"] + df["Rö"] + df["DM"]*2 + df["DF"]*2 + df["DR"]*3 + df["TPP"]*4 + df["TAP"]*6 + df["TPA"]*5) * df["Hårdhet"]

    # Pris
    df["Pris"] = 19.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön: 2% av intäkter, max 1000
    df["Malin lön"] = df["Intäkter"] * 0.02
    df.loc[df["Malin lön"] > 1000, "Malin lön"] = 1000

    # Företag lön: max 10000
    df["Företag lön"] = df["Intäkter"] * 0.4
    df.loc[df["Företag lön"] > 10000, "Företag lön"] = 10000

    # Vänner lön (summor över hela df)
    total_intäkt = df["Intäkter"].sum()
    total_malin = df["Malin lön"].sum()
    total_företag = df["Företag lön"].sum()
    df["Vänner lön"] = (total_intäkt - total_malin - total_företag) / känner2 if känner2 > 0 else 0

    # Klockan = 07:00 + (Summa singel + dubbel + trippel + total tid)
    def calc_klockan(row):
        try:
            start = datetime.strptime("07:00", "%H:%M")
            total_minutes = (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Total tid"]) / 60
            return (start + timedelta(minutes=total_minutes)).strftime("%H:%M")
        except:
            return ""
    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# Lägg till ny rad via formulär
def inmatning(df, worksheet):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        inputs = [
            "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
            "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
            "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
            "DeepT", "Grabbar", "Sekunder", "Varv"
        ]
        for f in inputs:
            ny_rad[f] = st.number_input(f, min_value=0, step=1, key=f)

        ny_rad["Datum"] = nästa_datum(df)

        submitted = st.form_submit_button("Spara")
        if submitted:
            append_row(worksheet, ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Vilodag jobb – sätt 30% av max för vissa kolumner
def vilodag_jobb(df, worksheet):
    ny_rad = {col: 0 for col in worksheet.row_values(1)}
    ny_rad["Datum"] = nästa_datum(df)

    for col in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        max_val = df[col].max() if col in df else 0
        ny_rad[col] = int(round(max_val * 0.3))

    ny_rad.update({
        "Älskar": 12,
        "Sover med": 1,
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

# Slumpa ny rad baserat på tidigare data
def slumpa_rad(df, worksheet):
    if df.empty:
        st.warning("Ingen data att slumpa från.")
        return

    cols_to_randomize = [
        "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
        "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
        "DeepT", "Grabbar", "Sekunder", "Varv"
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
    append_row(worksheet, ny_rad)
    st.success("✅ Slumpad rad tillagd.")

# Kopiera raden med högst Totalt män
def kopiera_max(df, worksheet):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return

    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]
    max_rad = df.loc[df["Totalt män"].idxmax()].to_dict()
    max_rad["Datum"] = nästa_datum(df)
    append_row(worksheet, max_rad)
    st.success("✅ Största raden kopierades.")

# Presentation: huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")

    # Känner 2 = summan av maxvärden för varje av fyra fält
    jobb_2 = df["Jobb"].max()
    grannar_2 = df["Grannar"].max()
    tjej_2 = df["Tjej PojkV"].max()
    nils_2 = df["Nils fam"].max()
    känner_2 = jobb_2 + grannar_2 + tjej_2 + nils_2

    män_total = df["Män"].sum()
    totalt_män = män_total + känner_2

    gangb = känner_2 / (jobb_2 + grannar_2 + tjej_2 + nils_2) if (jobb_2 + grannar_2 + tjej_2 + nils_2) > 0 else 0
    snitt_film = (män_total + känner_2) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0
    älskat = df["Älskar"].sum() / känner_2 if känner_2 > 0 else 0
    sover_med = df["Sover med"].sum() / nils_2 if nils_2 > 0 else 0

    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0

    filmer = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    företag_lön = min(df["Företag lön"].sum(), 10000)
    vänner_lön = (intäkter - malin_lön - företag_lön) / känner_2 if känner_2 > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (kompisar):** {känner_2}")
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

# Presentation: radvy
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
