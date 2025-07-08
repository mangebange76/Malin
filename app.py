import streamlit as st
import pandas as pd
import numpy as np
import gspread
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

    # Alla kolumner som ska finnas
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

# ---- Hjälpberäkningar ----
def update_calculations(df):
    df["Känner 2"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].max(axis=0).sum()
    df["Totalt män"] = df["Nya män"] + df["Känner 2"]

    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 9) * (df["Dubbelmacka"] + df["Dubbel fitta"] + df["Dubbel röv"])
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (df["Trippel fitta"] + df["Trippel röv"] + df["Trippel penet"])

    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, np.nan)
    df["Suger"] = df["Suger"].fillna(0)

    df["Snitt"] = df["DeepT"] / df["Känner 2"].replace(0, np.nan)
    df["Snitt"] = df["Snitt"].fillna(0)

    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, np.nan)
    df["Tid kille DT"] = df["Tid kille DT"].fillna(0)

    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, np.nan)
    df["Runk"] = df["Runk"].fillna(0)

    df["Tid kille"] = (
        df["Tid singel"] +
        (df["Tid dubbel"] * 2) +
        (df["Tid trippel"] * 3) +
        df["Suger"] +
        df["Tid kille DT"] +
        df["Runk"]
    )

    df["Tidsåtgång"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Total tid"]
    )

    return df

# ---- Inmatningsformulär ----
def skapa_inmatningsformulär():
    st.subheader("Lägg till ny rad")
    with st.form("ny_rad"):
        dag = st.date_input("Dag")
        nya_män = st.number_input("Nya män", value=0, step=1)
        fitta = st.number_input("Fitta", value=0, step=1)
        rumpa = st.number_input("Rumpa", value=0, step=1)
        dubbelmacka = st.number_input("Dubbelmacka", value=0, step=1)
        dubbel_fitta = st.number_input("Dubbel fitta", value=0, step=1)
        dubbel_röv = st.number_input("Dubbel röv", value=0, step=1)
        trippel_fitta = st.number_input("Trippel fitta", value=0, step=1)
        trippel_röv = st.number_input("Trippel röv", value=0, step=1)
        trippel_penet = st.number_input("Trippel penet", value=0, step=1)
        älskar = st.number_input("Älskar", value=0, step=1)
        älsk_tid = st.number_input("Älsk tid", value=0, step=1)
        sover_med = st.number_input("Sover med", value=0, step=1)
        jobb = st.number_input("Jobb", value=0, step=1)
        grannar = st.number_input("Grannar", value=0, step=1)
        tjej_pojkv = st.number_input("Tjej PojkV", value=0, step=1)
        nils_fam = st.number_input("Nils fam", value=0, step=1)
        tid_singel = st.number_input("Tid singel", value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel", value=0, step=1)
        tid_trippel = st.number_input("Tid trippel", value=0, step=1)
        vila = st.number_input("Vila", value=0, step=1)
        deept = st.number_input("DeepT", value=0, step=1)
        sekunder = st.number_input("Sekunder", value=0, step=1)
        varv = st.number_input("Varv", value=0, step=1)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            return {
                "Dag": str(dag),
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
    return None

# ---- Spara till Google Sheets ----
def spara_rad(worksheet, ny_rad):
    if isinstance(ny_rad, pd.Series):
        ny_rad = ny_rad.to_dict()

    befintlig = worksheet.get_all_values()
    if len(befintlig) == 0:
        worksheet.append_row(list(ny_rad.keys()))  # Lägg till rubriker om tomt

    header = worksheet.row_values(1)
    row_values = [ny_rad.get(col, "") for col in header]
    worksheet.append_row(row_values)


# ---- Huvudfunktion ----
def main():
    st.title("MalinApp – Inmatning och Beräkning")

    worksheet, df = load_data()

    ny_rad = skapa_inmatningsformulär()

    if ny_rad is not None:
        ny_df = pd.DataFrame([ny_rad])
        ny_df = update_calculations(ny_df)
        spara_rad(worksheet, ny_df.iloc[0].to_dict())
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
