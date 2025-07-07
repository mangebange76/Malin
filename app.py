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
        "Datum","Män","Fi","Rö","DM","DF","DR","TPP","TAP","TPA",
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

# Spara rad i sheet (append)
def append_row(worksheet, row_dict):
    values = [row_dict.get(col, 0) for col in worksheet.row_values(1)]
    worksheet.append_row(values)

# Uppdatera rad i sheet
def update_row(worksheet, index, row_dict):
    col_names = worksheet.row_values(1)
    values = [row_dict.get(col, 0) for col in col_names]
    range_str = f"A{index+2}:{chr(ord('A')+len(col_names)-1)}{index+2}"
    worksheet.update(range_str, [values])

# Hjälpfunktion: nästa datum efter sista datumet i df
def nästa_datum(df):
    if df.empty or df["Datum"].isnull().all():
        return datetime.today().strftime("%Y-%m-%d")
    else:
        try:
            sista = pd.to_datetime(df["Datum"], errors='coerce').max()
            return (sista + timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            return datetime.today().strftime("%Y-%m-%d")

# Uppdatera alla beräkningar i df
def update_calculations(df):
    # Känner
    df["Känner"] = df[["Jobb","Grannar","Tjej PojkV","Nils fam"]].sum(axis=1)

    # Maxvärden för 2-kolumner
    df["Jobb 2"] = df["Jobb"].max()
    df["Grannar 2"] = df["Grannar"].max()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].max()
    df["Nils fam 2"] = df["Nils fam"].max()

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner"]

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

    # Suger (60% av summa tid per totalt män)
    df["Suger"] = 0
    mask = df["Totalt män"] > 0
    df.loc[mask, "Suger"] = (df.loc[mask, "Summa tid"] * 0.6) / df.loc[mask, "Totalt män"]

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

    # Malin lön
    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    # Företag lön
    df["Företag lön"] = df["Intäkter"] * 0.4

    # Vänner lön
    df["Vänner lön"] = (df["Intäkter"] - df["Malin lön"] - df["Företag lön"]) / df["Känner"].replace(0,1)

    # DeepT, Grabbar, Snitt, Sekunder, Varv, Total tid, Tid kille DT, Runk
    df["DeepT"] = df.get("DeepT", 0)
    df["Grabbar"] = df.get("Grabbar", 1)
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0,1)
    df["Sekunder"] = df.get("Sekunder", 0)
    df["Varv"] = df.get("Varv", 0)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0,1)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0,1)

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + 2*df["Tid Dubbel"] + 3*df["Tid Trippel"] + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Klockan med fix (returnerar serie)
    def calc_klockan(row):
        try:
            start = datetime.strptime("07:00", "%H:%M")
            total_seconds = (row.get("Summa singel", 0) + row.get("Summa dubbel", 0) +
                             row.get("Summa trippel", 0) + row.get("Total tid", 0))
            total_minutes = total_seconds / 60
            klockan = (start + timedelta(minutes=total_minutes)).strftime("%H:%M")
            return klockan
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
            ny_rad.update({
                "Runk": 0, "Snitt": 0, "Total tid": 0, "Tid kille DT": 0,
                "Känner": 0, "Jobb 2": 0, "Grannar 2": 0, "Tjej PojkV 2": 0,
                "Nils fam 2": 0, "Totalt män": 0, "Summa singel": 0, "Summa dubbel": 0,
                "Summa trippel": 0, "Summa vila": 0, "Summa tid": 0, "Klockan": "",
                "Suger": 0, "Filmer": 0, "Pris": 19.99, "Intäkter": 0,
                "Malin lön": 0, "Företag lön": 0, "Vänner lön": 0, "Hårdhet": 0
            })
            append_row(worksheet, ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Vilodag jobb
def vilodag_jobb(df, worksheet):
    ny_rad = {col: 0 for col in worksheet.row_values(1)}
    ny_rad["Datum"] = nästa_datum(df)
    ny_rad.update({
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": int(df["Jobb"].max()) if not df.empty else 0,
        "Grannar": int(df["Grannar"].max()) if not df.empty else 0,
        "Tjej PojkV": int(df["Tjej PojkV"].max()) if not df.empty else 0,
        "Nils fam": int(df["Nils fam"].max()) if not df.empty else 0,
    })
    append_row(worksheet, ny_rad)
    st.success("✅ Vilodag jobb tillagd.")

# Vilodag hemma
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

# Kopiera två rader med högst Totalt män som två nya rader
def kopiera_max(df, worksheet):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Datum"] = nästa_datum(df)
        append_row(worksheet, ny)
    st.success("✅ Två rader kopierades.")

# Slumpa ny rad baserat på kolumner med inmatade värden
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
            elif col == "Älsk tid":
                ny_rad[col] = 30
            else:
                ny_rad[col] = random.randint(min_val, max_val)
        else:
            ny_rad[col] = 0
    ny_rad["Datum"] = nästa_datum(df)
    append_row(worksheet, ny_rad)
    st.success("✅ Slumpad rad tillagd.")

# Presentation huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    totalt_män = df["Totalt män"].sum()
    totalt_känner = df["Känner"].sum()

    # Maxvärden
    jobb_2 = df["Jobb"].max() if not df.empty else 0
    grannar_2 = df["Grannar"].max() if not df.empty else 0
    tjej_2 = df["Tjej PojkV"].max() if not df.empty else 0
    nils_2 = df["Nils fam"].max() if not df.empty else 0

    gangb = totalt_känner / (jobb_2 + grannar_2 + tjej_2 + nils_2) if (jobb_2 + grannar_2 + tjej_2 + nils_2) > 0 else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner > 0 else 0
    sover_med = df["Sover med"].sum() / nils_2 if nils_2 > 0 else 0

    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0

    snitt_film = (totalt_män + totalt_känner) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0

    filmer = df["Filmer"].sum()
    intäkter = df["Intäkter"].sum()
    malin_lön = df["Malin lön"].sum()
    företag_lön = df["Företag lön"].sum()
    vänner_lön = df["Vänner lön"].sum() / totalt_känner if totalt_känner > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (Kompisar):** {totalt_känner}")
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

# Presentation radvy
def radvy(df, worksheet):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    rad = df.iloc[-1]

    # Tid kille i minuter
    tid_kille_min = rad["Tid kille"] / 60 if rad["Tid kille"] else 0
    marker = "⚠️ Öka tid!" if tid_kille_min < 10 else ""

    st.write(f"**Tid kille:** {tid_kille_min:.2f} min {marker}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")

    # Klockan
    st.write(f"**Klockan:** {rad['Klockan']}")

    # Möjlighet att justera tid s, tid d, tid t, sekunder, varv
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

            # Uppdatera beräkningar efter ändring
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
        if st.button("📋 Kopiera två största"):
            kopiera_max(df, worksheet)
    with col4:
        if st.button("🎲 Slumpa rad"):
            slumpa_rad(df, worksheet)

    inmatning(df, worksheet)

    huvudvy(df)
    radvy(df, worksheet)

if __name__ == "__main__":
    main()
