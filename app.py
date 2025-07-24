import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader, konvertera_typer

scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(st.secrets["SHEET_KEY"]).sheet1

def läs_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df = säkerställ_kolumner(df)
        df = konvertera_typer(df)
    return df

def spara_data(sheet, df):
    try:
        df = säkerställ_kolumner(df)
        sheet.clear()
        sheet.append_row(COLUMNS)
        for _, row in df.iterrows():
            sheet.append_row(row.tolist())
    except Exception as e:
        st.error(f"Fel vid sparning: {e}")

def scenformulär(df):
    with st.form("scenformulär"):
        f = {}
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        for kolumn in COLUMNS[2:]:
            f[kolumn] = st.number_input(kolumn, value=0.0 if "($)" in kolumn else 0)
        submit = st.form_submit_button("Lägg till")

    if submit:
        df = process_lägg_till_rader(df, {}, f)
        spara_data(sheet, df)
        st.success("Rad tillagd!")
    return df

def main():
    st.title("Malin-produktionsapp")
    df = läs_data()
    df = scenformulär(df)
    st.dataframe(df)

if __name__ == "__main__":
    main()
