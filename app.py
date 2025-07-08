import streamlit as st
import pandas as pd
import numpy as np
import gspread
import random
from google.oauth2.service_account import Credentials

# ---- Ladda data från Google Sheets ----
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = {
        "type": st.secrets["GOOGLE_CREDENTIALS"]["type"],
        "project_id": st.secrets["GOOGLE_CREDENTIALS"]["project_id"],
        "private_key_id": st.secrets["GOOGLE_CREDENTIALS"]["private_key_id"],
        "private_key": st.secrets["GOOGLE_CREDENTIALS"]["private_key"],
        "client_email": st.secrets["GOOGLE_CREDENTIALS"]["client_email"],
        "client_id": st.secrets["GOOGLE_CREDENTIALS"]["client_id"],
        "auth_uri": st.secrets["GOOGLE_CREDENTIALS"]["auth_uri"],
        "token_uri": st.secrets["GOOGLE_CREDENTIALS"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["client_x509_cert_url"]
    }

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Säkerställ att alla kolumner som krävs finns
    alla_kolumner = [
        "Dag", "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
        "Vila", "DeepT", "Sekunder", "Varv"
    ]
    for kolumn in alla_kolumner:
        if kolumn not in df.columns:
            df[kolumn] = 0

    return worksheet, df

# ---- Kalkylfunktioner ----
def update_calculations(df):
    df = df.copy()

    df["Totalt män"] = df["Nya män"] + df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].max(axis=1)

    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 9) * (df["Dubbelmacka"] + df["Dubbel fitta"] + df["Dubbel röv"])
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (df["Trippel fitta"] + df["Trippel röv"] + df["Trippel penet"])

    df["Snitt"] = df["DeepT"] / df["Totalt män"].replace(0, np.nan)
    df["Total tid"] = df["Snitt"] * df["Sekunder"] * df["Varv"]
    df["Tid kille dt"] = df["Total tid"] / df["Totalt män"].replace(0, np.nan)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, np.nan)

    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, np.nan)

    df["Tid kille"] = (
        df["Tid singel"]
        + (df["Tid dubbel"] * 2)
        + (df["Tid trippel"] * 3)
        + df["Suger"]
        + df["Tid kille dt"]
        + df["Runk"]
    )

    df["Intäkter"] = df["Tid kille"] * 1.2
    df["Malins lön"] = np.minimum(df["Intäkter"] * 0.02, 1000)
    df["Företagets lön"] = np.minimum(df["Intäkter"] - df["Malins lön"], 10000)
    df["Vänners lön"] = df["Intäkter"] - df["Malins lön"] - df["Företagets lön"]
    df["Hårdhet"] = df["Fitta"] + df["Rumpa"] + df["Dubbel fitta"] + df["Dubbel röv"]

    df["Tidsåtgång"] = df.apply(calc_tidsåtgång, axis=1)

    return df


def calc_tidsåtgång(row):
    try:
        summa_singel = float(row.get("Summa singel", 0) or 0)
        summa_dubbel = float(row.get("Summa dubbel", 0) or 0)
        summa_trippel = float(row.get("Summa trippel", 0) or 0)
        snitt = float(row.get("Snitt", 0) or 0)
        sek = float(row.get("Sekunder", 0) or 0)
        varv = float(row.get("Varv", 0) or 0)

        extra_tid = (snitt * sek * varv) / 60
        total_min = summa_singel + summa_dubbel + summa_trippel + extra_tid

        timmar = int(total_min // 60)
        minuter = int(total_min % 60)
        return f"{timmar} timmar {minuter} minuter"
    except Exception:
        return "0 timmar 0 minuter"

# ---- Inmatningsformulär ----
def skapa_inmatningsformulär():
    with st.form("data_form"):
        kol1, kol2, kol3 = st.columns(3)

        with kol1:
            nya_män = st.number_input("Nya män", min_value=0, step=1)
            fitta = st.number_input("Fitta", min_value=0, step=1)
            rumpa = st.number_input("Rumpa", min_value=0, step=1)
            dubbelmacka = st.number_input("Dubbelmacka", min_value=0, step=1)
            dubbel_fitta = st.number_input("Dubbel fitta", min_value=0, step=1)
            dubbel_röv = st.number_input("Dubbel röv", min_value=0, step=1)
            trippel_fitta = st.number_input("Trippel fitta", min_value=0, step=1)
            trippel_röv = st.number_input("Trippel röv", min_value=0, step=1)
            trippel_penet = st.number_input("Trippel penet", min_value=0, step=1)

        with kol2:
            älskar = st.number_input("Älskar", min_value=0, step=1)
            älsk_tid = st.number_input("Älsk tid", min_value=0, step=1)
            sover_med = st.number_input("Sover med", min_value=0, step=1)
            jobb = st.number_input("Jobb", min_value=0, step=1)
            grannar = st.number_input("Grannar", min_value=0, step=1)
            tjej_pojkv = st.number_input("Tjej PojkV", min_value=0, step=1)
            nils_fam = st.number_input("Nils fam", min_value=0, step=1)

        with kol3:
            tid_singel = st.number_input("Tid singel", min_value=0, step=1)
            tid_dubbel = st.number_input("Tid dubbel", min_value=0, step=1)
            tid_trippel = st.number_input("Tid trippel", min_value=0, step=1)
            vila = st.number_input("Vila", min_value=0, step=1)
            deept = st.number_input("DeepT", min_value=0, step=1)
            sekunder = st.number_input("Sekunder", min_value=0, step=1)
            varv = st.number_input("Varv", min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")

    if submitted:
        return {
            "Dag": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "Nya män": nya_män,
            "Fitta": fitta,
            "Rumpa": rumpa,
            "Dubbelmacka": dubbelmacka,
            "Dubbel fitta": dubbel_fitta,
            "Dubbel röv": dubbel_röv,
            "Trippel fitta": trippel_fitta,
            "Trippel röv": trippel_röv,
            "Trippel penet": trippel_penet,
            "Älskar": älskar,
            "Älsk tid": älsk_tid,
            "Sover med": sover_med,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": tjej_pojkv,
            "Nils fam": nils_fam,
            "Tid singel": tid_singel,
            "Tid dubbel": tid_dubbel,
            "Tid trippel": tid_trippel,
            "Vila": vila,
            "DeepT": deept,
            "Sekunder": sekunder,
            "Varv": varv
        }
    else:
        return None

# ---- Spara till Google Sheets ----
def spara_rad(worksheet, ny_rad):
    # Konvertera till dict om det är en Series
    if isinstance(ny_rad, pd.Series):
        ny_rad = ny_rad.to_dict()

    befintlig = worksheet.get_all_values()
    if len(befintlig) == 0:
        worksheet.append_row(list(ny_rad.keys()))
    worksheet.append_row(list(ny_rad.values()))


# ---- Huvudfunktion ----
def main():
    st.title("MalinApp – Datainmatning & Beräkningar")

    worksheet, df = load_data()
    ny_rad = skapa_inmatningsformulär()

    if ny_rad:
        ny_df = pd.DataFrame([ny_rad])
        ny_df = update_calculations(ny_df)
        spara_rad(worksheet, ny_df.iloc[0])  # fixad rad
        st.success("Rad sparad!")

    if df.empty:
        st.warning("Databasen är tom.")
        return

    df = update_calculations(df)
    st.subheader("Databasen")
    st.dataframe(df.tail(10), use_container_width=True)

# ---- Starta appen ----
if __name__ == "__main__":
    main()
