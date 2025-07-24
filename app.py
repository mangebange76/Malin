import streamlit as st
st.write("Secrets tillgängliga:", list(st.secrets.keys()))
import streamlit as st
import pandas as pd
import datetime
from google.oauth2.service_account import Credentials
import gspread
from konstanter import COLUMNS, säkerställ_kolumner

# Google Sheets autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(st.secrets["SHEET_URL"])
sheet = sh.sheet1

def hämta_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def säkerställ_startdatum():
    inst = st.session_state.get("inställningar", {})
    if "Startdatum" not in inst:
        inst["Startdatum"] = datetime.date.today().isoformat()
        st.session_state["inställningar"] = inst
    return inst

def säkerställ_kolumner_och_rensning(df):
    df = säkerställ_kolumner(df)
    df = df[COLUMNS]
    return df

def skapa_tom_rad():
    return {kolumn: 0 for kolumn in COLUMNS}

def scenformulär(df, inst, sheet):
    st.subheader("Lägg till scenrad i databasen")

    with st.form("scenformulär", clear_on_submit=False):
        dagens_datum = df["Datum"].iloc[-1] if not df.empty else inst.get("Startdatum", datetime.date.today().isoformat())
        dagens_datum = pd.to_datetime(dagens_datum) + pd.Timedelta(days=1)

        st.write(f"Datum för ny rad: **{dagens_datum.date()}**")
        f = {}
        f["Datum"] = dagens_datum.date().isoformat()
        f["Typ"] = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        f["Antal vilodagar"] = st.number_input("Antal vilodagar", 0, 30, 0)
        f["Nya män"] = st.number_input("Nya män", 0, 100, 0)
        f["Enkel vaginal"] = st.number_input("Enkel vaginal", 0, 100, 0)
        f["Enkel anal"] = st.number_input("Enkel anal", 0, 100, 0)
        f["DP"] = st.number_input("DP", 0, 100, 0)
        f["DPP"] = st.number_input("DPP", 0, 100, 0)
        f["DAP"] = st.number_input("DAP", 0, 100, 0)
        f["TPP"] = st.number_input("TPP", 0, 100, 0)
        f["TPA"] = st.number_input("TPA", 0, 100, 0)
        f["TAP"] = st.number_input("TAP", 0, 100, 0)
        f["Tid enkel"] = st.number_input("Tid enkel (sek)", 0, 10000, 0)
        f["Tid dubbel"] = st.number_input("Tid dubbel (sek)", 0, 10000, 0)
        f["Tid trippel"] = st.number_input("Tid trippel (sek)", 0, 10000, 0)
        f["Vila"] = st.number_input("Vila mellan byten (sek)", 0, 10000, 0)
        f["Kompisar"] = st.number_input("Kompisar", 0, 100, 0)
        f["Pappans vänner"] = st.number_input("Pappans vänner", 0, 100, 0)
        f["Nils vänner"] = st.number_input("Nils vänner", 0, 100, 0)
        f["Nils familj"] = st.number_input("Nils familj", 0, 100, 0)
        f["DT tid per man"] = st.number_input("DT tid per man (sek)", 0, 10000, 0)
        f["Antal varv"] = st.number_input("Antal varv", 0, 100, 0)
        f["Älskar med"] = st.number_input("Älskar med", 0, 100, 0)
        f["Sover med"] = st.number_input("Sover med", 0, 100, 0)
        f["Nils sex"] = st.number_input("Nils sex", 0, 100, 0)
        f["Prenumeranter"] = st.number_input("Prenumeranter", 0, 1000000, 0)
        f["Intäkt ($)"] = st.number_input("Intäkt ($)", 0.0, 1_000_000.0, 0.0)
        f["Kvinnans lön ($)"] = st.number_input("Kvinnans lön ($)", 0.0, 1_000_000.0, 0.0)
        f["Mäns lön ($)"] = st.number_input("Mäns lön ($)", 0.0, 1_000_000.0, 0.0)
        f["Kompisars lön ($)"] = st.number_input("Kompisars lön ($)", 0.0, 1_000_000.0, 0.0)
        f["DT total tid (sek)"] = st.number_input("DT total tid (sek)", 0, 1_000_000, 0)
        f["Total tid (sek)"] = st.number_input("Total tid (sek)", 0, 1_000_000, 0)
        total_tid_h = f["Total tid (sek)"] / 3600
        f["Total tid (h)"] = round(total_tid_h, 2)
        f["Minuter per kille"] = round(f["Total tid (sek)"] / max((f["Nya män"] + 1), 1) / 60, 6)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        if total_tid_h > 18:
            st.warning("Total tid överstiger 18 timmar. Justera tid för enkel/dubbel/trippel om det behövs.")

        submitted = st.form_submit_button("Lägg till")

    if submitted and bekräfta:
        ny_rad = skapa_tom_rad()
        for k in ny_rad:
            if k in f:
                ny_rad[k] = f[k]
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        spara_data(sheet, df)
        st.success("Raden sparades i databasen.")

    return df

def spara_data(sheet, df):
    try:
        df = säkerställ_kolumner_och_rensning(df)
        rows = df.values.tolist()
        rows = [[float(cell) if isinstance(cell, (int, float)) else str(cell) for cell in row] for row in rows]
        sheet.clear()
        sheet.append_row(COLUMNS, value_input_option="USER_ENTERED")
        for rad in rows:
            sheet.append_row(rad, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error("Fel vid skrivning till Google Sheet.")
        st.stop()

def inställningsformulär():
    st.sidebar.subheader("Inställningar")
    inst = st.session_state.get("inställningar", {})
    inst["Startdatum"] = st.sidebar.date_input("Startdatum", pd.to_datetime(inst.get("Startdatum", datetime.date.today())))
    if st.sidebar.button("Spara inställningar"):
        st.session_state["inställningar"] = inst
        st.sidebar.success("Inställningar sparade.")

def main():
    st.title("Malin-produktionsapp")
    inst = säkerställ_startdatum()
    inställningsformulär()
    df = hämta_data(sheet)
    df = säkerställ_kolumner_och_rensning(df)
    df = scenformulär(df, inst, sheet)

if __name__ == "__main__":
    main()
