import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="MalinData Analys")

# Funktion: Läs eller skapa data
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
    )
    client = gspread.authorize(credentials)

    spreadsheet = client.open("MalinData")
    worksheet = spreadsheet.worksheet("Blad1")

    expected_headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s",
        "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t", "Summa v",
        "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner", "Jobb",
        "Grannar", "Tjej oj", "Nils kom", "Tid kille", "Filmer", "Pris",
        "Intäkter", "Malin", "Företag", "Hårdhet", "Svarta"
    ]

    current_values = worksheet.get_all_values()
    if not current_values:
        worksheet.insert_row(expected_headers, 1)
        return worksheet, pd.DataFrame(columns=expected_headers)

    headers = current_values[0]
    if headers != expected_headers:
        worksheet.delete_row(1)
        worksheet.insert_row(expected_headers, 1)
        current_values = worksheet.get_all_values()

    if len(current_values) <= 1:
        return worksheet, pd.DataFrame(columns=expected_headers)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    return worksheet, df

# Funktion: Visa nyckeltal
def visa_nyckeltal(df):
    st.header("Nyckeltal")

    if df.empty:
        st.info("Ingen data att visa ännu.")
        return

    try:
        max_jobb = df["Jobb"].max()
        max_grannar = df["Grannar"].max()
        max_pv = df["Tjej oj"].max()
        max_nils = df["Nils kom"].max()

        total_intakt = df["Intäkter"].sum()
        känner_tjänat = total_intakt / max((max_jobb + max_grannar + max_pv + max_nils), 1)

        filmrader = df[df["Män"] > 0]
        snitt_film = (df["Män"].sum() + df["F"].sum()) / len(filmrader) if len(filmrader) > 0 else 0

        malin_tjänst_snitt = df[["Män", "F", "Älskar", "Sover med"]].sum().sum()

        vita_summa = df["Män"].sum() + df["F"].sum()
        svarta_summa = df["Svarta"].sum()
        total_vit_svart = max((vita_summa + svarta_summa), 1)
        vita_procent = (vita_summa - svarta_summa) / total_vit_svart * 100
        svarta_procent = svarta_summa / total_vit_svart * 100

        st.metric("Känner tjänat", f"{känner_tjänat:.2f} kr")
        st.metric("Snitt film", f"{snitt_film:.2f}")
        st.metric("Malin tjänst snitt", f"{malin_tjänst_snitt:.2f}")
        st.metric("Vita (%)", f"{vita_procent:.2f}%")
        st.metric("Svarta (%)", f"{svarta_procent:.2f}%")

    except Exception as e:
        st.error(f"Fel vid nyckeltalsberäkning: {e}")

# Funktion: Formulär för ny post
def nytt_inlägg(worksheet, df):
    st.subheader("Lägg till ny rad")

    with st.form("data_form"):
        ny_rad = {}
        for col in df.columns:
            if col in ["Dag", "Klockan"]:
                ny_rad[col] = st.text_input(col)
            else:
                ny_rad[col] = st.number_input(col, value=0, step=1)
        submitted = st.form_submit_button("Spara")
        if submitted:
            rad = [ny_rad[col] for col in df.columns]
            worksheet.append_row(rad)
            st.success("Rad tillagd. Ladda om sidan.")

# Funktion: Visa data
def visa_tabell(df):
    st.subheader("Datatabell")
    if df.empty:
        st.info("Ingen data ännu.")
    else:
        st.dataframe(df)

# Huvudfunktion
def main():
    st.title("📊 MalinData Analys")
    worksheet, df = load_data()
    visa_nyckeltal(df)
    nytt_inlägg(worksheet, df)
    visa_tabell(df)

if __name__ == "__main__":
    main()
