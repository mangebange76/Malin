import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from konstanter import säkerställ_kolumner

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)

# Öppna kalkylarket
sheet = gc.open_by_key(st.secrets["SHEET_KEY"]).sheet1

# Hjälpfunktion för att läsa inställningar
def läs_inställningar():
    try:
        inst = st.session_state.get("inställningar", {})
        if not inst:
            inst = {
                "Startdatum": datetime.today().strftime("%Y-%m-%d")
            }
        return inst
    except:
        return {"Startdatum": datetime.today().strftime("%Y-%m-%d")}

# Bestäm datum för ny rad
def bestäm_datum(df, inst):
    if df.empty:
        startdatum = inst.get("Startdatum")
        try:
            return datetime.strptime(startdatum, "%Y-%m-%d").strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")
    else:
        senaste = pd.to_datetime(df["Datum"].iloc[-1], errors="coerce")
        if pd.isna(senaste):
            return datetime.today().strftime("%Y-%m-%d")
        return (senaste + timedelta(days=1)).strftime("%Y-%m-%d")

# Läs in befintlig data
@st.cache_data(ttl=60)
def hämta_data():
    df = pd.DataFrame(sheet.get_all_records())
    df = säkerställ_kolumner(df)
    return df

def scenformulär(df, inst, sheet):
    st.subheader("Lägg till sceninformation")

    datum = bestäm_datum(df, inst)
    st.info(f"Datum för ny rad: **{datum}**")

    med st.form("scenformulär", clear_on_submit=False):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1, value=0)
        nya_män = st.number_input("Nya män", min_value=0, step=1)
        enkel_vaginal = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        tid_enkel = st.number_input("Tid enkel (sek)", min_value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel (sek)", min_value=0, step=1)
        tid_trippel = st.number_input("Tid trippel (sek)", min_value=0, step=1)
        kompisar = st.number_input("Kompisar", min_value=0, step=1)
        pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1)
        nils_vänner = st.number_input("Nils vänner", min_value=0, step=1)
        nils_familj = st.number_input("Nils familj", min_value=0, step=1)
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=0, step=1)
        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)
        prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)
        intäkt = st.number_input("Intäkt ($)", min_value=0.0, step=1.0)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=1.0)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=1.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=1.0)
        dt_total_tid = st.number_input("DT total tid (sek)", min_value=0, step=1)
        total_tid = st.number_input("Total tid (sek)", min_value=0, step=1)
        total_tid_h = round(total_tid / 3600, 2)
        minuter_per_kille = st.number_input("Minuter per kille", min_value=0.0, step=0.01)
        vila = st.number_input("Vila (sek)", min_value=0, step=1)

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        if bekräfta and st.form_submit_button("Lägg till rad"):
            ny_rad = [
                datum, typ, antal_vilodagar, nya_män,
                enkel_vaginal, enkel_anal, dp, dpp, dap, tpp, tpa, tap,
                tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner,
                nils_vänner, nils_familj, dt_tid_per_man, antal_varv,
                älskar_med, sover_med, nils_sex, prenumeranter, intäkt,
                kvinnans_lön, mäns_lön, kompisars_lön,
                dt_total_tid, total_tid, total_tid_h, minuter_per_kille, vila
            ]

            if total_tid_h > 18:
                st.warning("⚠️ Totaltid överskrider 18 timmar. Justera gärna tid enkel/dubbel/trippel.")

            df.loc[len(df)] = ny_rad
            spara_data(sheet, df)
            st.success("Rad tillagd!")

def spara_data(sheet, df):
    from konstanter import säkerställ_kolumner

    df = säkerställ_kolumner(df)

    df_san = df.fillna("").copy()
    df_san = df_san.astype(str)

    headers = list(df_san.columns)
    df_values = df_san.values.tolist()

    try:
        existing = sheet.get_all_values()
    except Exception as e:
        st.error("Kunde inte läsa från Google Sheets.")
        st.stop()

    if existing:
        sheet.clear()

    rows_to_write = [headers] + df_values

    try:
        sheet.update(f"A1", rows_to_write)
    except Exception as e:
        st.error(f"❌ Fel vid skrivning till databasen:\n{e}")
        st.stop()


def main():
    st.title("Malin-produktionsapp")

    # Initiera Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    gc = gspread.authorize(credentials)

    SHEET_URL = st.secrets["SHEET_URL"]
    sh = gc.open_by_url(SHEET_URL)
    sheet = sh.sheet1

    # Läs in data
    try:
        data = sheet.get_all_values()
        if data:
            df = pd.DataFrame(data[1:], columns=data[0])
        else:
            df = pd.DataFrame(columns=COLUMNS)
    except Exception as e:
        st.error(f"Kunde inte läsa in data från arket.\n{e}")
        return

    df = säkerställ_kolumner(df)

    inst = hämta_inställningar()

    visa_inställningar(inst)
    scenformulär(df, inst, sheet)


if __name__ == "__main__":
    main()
