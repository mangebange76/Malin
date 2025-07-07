import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisering mot Google Sheets
def auth_gspread():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# Säkerställ att rubriker finns i rätt ordning i kalkylbladet
def ensure_headers(worksheet, expected_headers):
    try:
        current_headers = worksheet.row_values(1)
        if current_headers != expected_headers:
            worksheet.resize(rows=1)
            worksheet.insert_row(expected_headers, index=1)
    except Exception:
        worksheet.resize(rows=1)
        worksheet.insert_row(expected_headers, index=1)

# Ladda data från Google Sheet, säkerställ rubriker, returnera worksheet och df
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    expected_headers = [
        "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr",
        "TPP", "TAP", "TPA", "Älskar", "Sover med",
        "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2",
        "Tjej PojkV", "Tjej PojkV 2", "Nils fam", "Nils fam 2",
        "Totalt män", "Tid Singel", "Tid Dubbel", "Tid Trippel",
        "Vila", "Summa singel", "Summa dubbel", "Summa trippel",
        "Summa vila", "Summa tid", "Klockan", "Tid kille",
        "Suger", "Filmer", "Pris", "Intäkter", "Malin lön",
        "Företag lön", "Vänner lön", "Hårdhet",
        "DeepT", "Grabbar", "Snitt", "Sekunder", "Varv",
        "Total tid", "Tid kille DT", "Runk", "Svarta"
    ]
    ensure_headers(worksheet, expected_headers)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    # Om df tom, skapa tom df med kolumner
    if df.empty:
        df = pd.DataFrame(columns=expected_headers)
    return worksheet, df

import random

# Funktion för att uppdatera alla beräkningar i df
def update_calculations(df):
    # Räkna Känner
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)

    # Maxvärden av 2-kolumner
    df["Jobb 2"] = df["Jobb"].cummax()
    df["Grannar 2"] = df["Grannar"].cummax()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].cummax()
    df["Nils fam 2"] = df["Nils fam"].cummax()

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner"]

    # Summa singel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])

    # Summa trippel
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa vila
    df["Summa vila"] = df["Totalt män"] * df["Vila"] + \
        (df["Dm"] + df["Df"] + df["Dr"]) * (df["Vila"] + 7) + \
        (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    # Klockan - start 07:00 plus summa tid i minuter (sekunder / 60)
    start_time = datetime(2025, 1, 1, 7, 0)
    df["Klockan"] = df["Summa tid"].apply(lambda s: (start_time + timedelta(seconds=s)).strftime("%H:%M"))

    # Tid kille (sekunder)
    # tid s + tid d * 2 + tid t * 3
    df["Tid kille"] = df["Tid Singel"] + df["Tid Dubbel"] * 2 + df["Tid Trippel"] * 3

    # Suger = 60% av (summa singel + summa dubbel + summa trippel) / totalt män
    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, np.nan)

    # Runk = 60% av total tid / totalt män (senare överlagras av beräkning)
    # Beräknas nedan efter total tid

    # DeepT, Grabbar, Snitt, Sekunder, Varv, Total tid, Tid kille DT, Runk
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, np.nan)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, np.nan)
    df["Runk"] = 0.6 * df["Total tid"] / df["Totalt män"].replace(0, np.nan)

    # Lägg till suger och runk till tid kille
    df["Tid kille"] = df["Tid kille"] + df["Suger"].fillna(0) + df["Tid kille DT"].fillna(0) + df["Runk"].fillna(0)

    # Filmer
    df["Filmer"] = (df["Män"] + df["Fi"] + df["Rö"] + df["Dm"] * 2 + df["Df"] * 2 + df["Dr"] * 3 +
                    df["TPP"] * 4 + df["TAP"] * 6 + df["TPA"] * 5)

    # Hårdhet
    def calc_hårdhet(row):
        if row["Män"] == 0:
            return 0
        h = 1
        if row["Dm"] > 0: h += 2
        if row["Df"] > 0: h += 2
        if row["Dr"] > 0: h += 4
        if row["TPP"] > 0: h += 4
        if row["TAP"] > 0: h += 6
        if row["TPA"] > 0: h += 5
        return h

    df["Hårdhet"] = df.apply(calc_hårdhet, axis=1)

    # Filmer x Hårdhet
    df["Filmer"] = df["Filmer"] * df["Hårdhet"]

    # Pris
    df["Pris"] = 19.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön: 5% av intäkter, max 1500 USD
    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    # Företagets lön 40% av intäkter
    df["Företag lön"] = df["Intäkter"] * 0.4

    # Vänner lön = intäkter - malin - företag / känner 2
    # För känner 2 använder vi maxvärdet av kolumn känner
    max_känner = df["Känner"].max() if not df.empty else 1
    df["Vänner lön"] = (df["Intäkter"] - df["Malin lön"] - df["Företag lön"]) / max_känner

    # Hantera NaN (ersätt med 0)
    df.fillna(0, inplace=True)
    return df

# Presentation av huvudvyn
def huvudvy(df):
    st.header("📊 Huvudvy")

    if df.empty:
        st.write("Ingen data att visa.")
        return

    totalt_män = df["Totalt män"].sum()
    totalt_känner = df["Känner"].sum()
    jobb_2 = df["Jobb 2"].max()
    grannar_2 = df["Grannar 2"].max()
    tjej_pojkv_2 = df["Tjej PojkV 2"].max()
    nils_fam_2 = df["Nils fam 2"].max()
    snitt_film = (totalt_män + totalt_känner) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0
    gangb = totalt_känner / (jobb_2 + grannar_2 + tjej_pojkv_2 + nils_fam_2) if (jobb_2 + grannar_2 + tjej_pojkv_2 + nils_fam_2) > 0 else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner > 0 else 0
    sover_med = df["Sover med"].sum() / nils_fam_2 if nils_fam_2 > 0 else 0
    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0
    filmer_sum = df["Filmer"].sum()
    intäkter_sum = df["Intäkter"].sum()
    malin_lön_sum = df["Malin lön"].sum()
    företag_lön_sum = df["Företag lön"].sum()
    vänner_lön_sum = df["Vänner lön"].sum()

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Antal känner (max):** {totalt_känner}")
    st.write(f"**Jobb (max):** {jobb_2}")
    st.write(f"**Grannar (max):** {grannar_2}")
    st.write(f"**Tjej PojkV (max):** {tjej_pojkv_2}")
    st.write(f"**Nils fam (max):** {nils_fam_2}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med (kvot):** {sover_med:.2f}")
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")
    st.write(f"**Filmer (summa):** {filmer_sum}")
    st.write(f"**Intäkter (summa):** ${intäkter_sum:.2f}")
    st.write(f"**Malin lön (summa):** ${malin_lön_sum:.2f}")
    st.write(f"**Företagets lön (summa):** ${företag_lön_sum:.2f}")
    st.write(f"**Vänner lön (summa):** ${vänner_lön_sum:.2f}")

# Presentation av radvy - endast senaste raden visas
def radvy(df):
    st.header("📋 Radvyn")

    if df.empty:
        st.write("Ingen data att visa.")
        return

    rad = df.iloc[-1]

    tid_kille_min = rad["Tid kille"] / 60
    tid_kille_flag = "⚠️ För kort tid (<10 min) - bör ökas!" if tid_kille_min < 10 else ""

    st.write(f"**Datum:** {rad['Datum'] if 'Datum' in rad else ''}")
    st.write(f"**Tid kille:** {tid_kille_min:.2f} minuter {tid_kille_flag}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")

    # Klockan med start 07:00 och tillägg av total tid i sekunder
    start_time = datetime(2025, 1, 1, 7, 0)
    total_tid_sec = rad["Summa tid"]
    sluttid = (start_time + timedelta(seconds=total_tid_sec)).strftime("%H:%M")
    st.write(f"**Klockan:** {sluttid}")

    # Redigeringsformulär om tid kille < 10 min
    if tid_kille_min < 10:
        st.markdown("---")
        st.write("### Justera tider för att öka Tid kille")
        with st.form("form_tid"):
            tid_s = st.number_input("Tid Singel", min_value=0, value=int(rad["Tid Singel"]))
            tid_d = st.number_input("Tid Dubbel", min_value=0, value=int(rad["Tid Dubbel"]))
            tid_t = st.number_input("Tid Trippel", min_value=0, value=int(rad["Tid Trippel"]))
            submitted = st.form_submit_button("Spara ändringar")

            if submitted:
                client = auth_gspread()
                sheet = client.open_by_url(st.secrets["SHEET_URL"])
                worksheet = sheet.worksheet("Blad1")
                row_index = len(df) + 1  # +1 pga header

                worksheet.update(f"L{row_index}:N{row_index}", [[tid_s, tid_d, tid_t]])
                st.success("✅ Tider uppdaterade, ladda om appen för att se uppdatering.")

# Inmatningsformulär för ny rad
def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        for fält in [
            "Män", "Fi", "Rö", "Dm", "Df", "Dr",
            "TPP", "TAP", "TPA", "Älskar", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
            "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
            "DeepT", "Grabbar", "Sekunder", "Varv"
        ]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        # Auto-fyll datum till nästa dag efter senaste
        ny_rad["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d")

        submitted = st.form_submit_button("Spara ny rad")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Funktioner för vilodagar
def vilodag_jobb(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad.update({
        "Datum": (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": max(df["Jobb"]) if not df.empty else 5,
        "Grannar": max(df["Grannar"]) if not df.empty else 5,
        "Tjej PojkV": max(df["Tjej PojkV"]) if not df.empty else 5,
        "Nils fam": max(df["Nils fam"]) if not df.empty else 5,
    })
    append_row(ny_rad)
    st.success("✅ Vilodag jobb tillagd.")

def vilodag_hemma(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad.update({
        "Datum": (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 6,
        "Sover med": 0,
        "Jobb": 3,
        "Grannar": 3,
        "Tjej PojkV": 3,
        "Nils fam": 3,
    })
    append_row(ny_rad)
    st.success("✅ Vilodag hemma tillagd.")

# Slumpfunktion som genererar en rad med slumpvärden i manuella fält, och fasta värden för vissa
def slumpa_rad(df):
    ny_rad = {}
    cols_slump = [
        "Män", "Fi", "Rö", "Dm", "Df", "Dr",
        "TPP", "TAP", "TPA",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Svarta", "Tid Singel", "Tid Dubbel", "Tid Trippel",
        "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"
    ]
    for col in df.columns:
        if col in cols_slump and col in df:
            max_val = df[col].max() if not df.empty else 10
            min_val = df[col].min() if not df.empty else 0
            ny_rad[col] = random.randint(min_val, max_val) if max_val > min_val else max_val
        elif col == "Älskar":
            ny_rad[col] = 8
        elif col == "Sover med":
            ny_rad[col] = 1
        elif col == "Älsk tid":
            ny_rad[col] = 30
        else:
            ny_rad[col] = 0
    ny_rad["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d")

    append_row(ny_rad)
    st.success("✅ Slumpmässig rad tillagd.")

# Kopiera två rader med högst Totalt män som två nya identiska rader efter sista raden
def kopiera_max(df):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)

    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        append_row(ny)
    st.success("✅ Två rader kopierades från högsta Totalt män.")

# Huvudfunktion
def main():
    st.title("MalinData App")

    worksheet, df = load_data()

    # Uppdatera beräkningar direkt
    df = update_calculations(df)

    # Knappsektion
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("➕ Lägg till ny rad manuellt"):
            st.experimental_rerun()
    with col2:
        if st.button("➕ Vilodag jobb"):
            vilodag_jobb(df)
            st.experimental_rerun()
    with col3:
        if st.button("➕ Vilodag hemma"):
            vilodag_hemma(df)
            st.experimental_rerun()
    with col4:
        if st.button("📋 Kopiera två största"):
            kopiera_max(df)
            st.experimental_rerun()

    # Slumpknapp under formuläret
    if st.button("🎲 Lägg till slumpmässig rad"):
        slumpa_rad(df)
        st.experimental_rerun()

    # Formulär för inmatning
    inmatning(df)

    # Presentationer
    huvudvy(df)
    radvy(df)

if __name__ == "__main__":
    main()
