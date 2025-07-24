import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner, bestäm_datum
from berakningar import process_lägg_till_rader, uppdatera_beräkningar, konvertera_typer
import datetime

# --- Autentisering och Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds_info = st.secrets["GOOGLE_CREDENTIALS"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    gc = gspread.authorize(credentials)
except Exception as e:
    st.error(f"🚫 Fel vid autentisering: {e}")
    st.stop()

# --- Hämta länk till kalkylarket ---
try:
    SHEET_URL = st.secrets["SHEET_URL"]
    if not SHEET_URL or "docs.google.com/spreadsheets" not in SHEET_URL:
        raise ValueError("Ogiltig eller saknad SHEET_URL i .streamlit/secrets.toml")
except Exception as e:
    st.error(f"🚫 Fel med kalkylarkets URL: {e}")
    st.stop()

# --- Öppna kalkylarket ---
try:
    sh = gc.open_by_url(SHEET_URL)
except Exception as e:
    st.error(f"🚫 Kunde inte öppna kalkylarket:\n{e}")
    st.stop()

# --- Ladda data ---
def läs_data(sh):
    try:
        df = pd.DataFrame(sh.worksheet("Data").get_all_records())
        df = säkerställ_kolumner(df)
        df = konvertera_typer(df)
        return df
    except Exception as e:
        st.warning(f"⚠️ Kunde inte läsa in data: {e}")
        return pd.DataFrame(columns=COLUMNS)

# --- Spara data ---
def spara_data(sh, df):
    try:
        sheet = sh.worksheet("Data")
        df = säkerställ_kolumner(df)
        last_row = len(sheet.get_all_values())
        chunk = [list(df.iloc[-1])]
        if len(chunk[0]) != len(COLUMNS):
            st.error(f"❌ Fel antal kolumner: {len(chunk[0])} (förväntat: {len(COLUMNS)})")
            st.text(f"Chunk: {chunk}")
            return
        cell_range = f"A{last_row+1}"
        sheet.update(cell_range, chunk)
        st.success("✅ Rad tillagd i databasen!")
    except Exception as e:
        st.error(f"❌ Fel vid skrivning till databasen: {e}")
        raise e

# --- Läs inställningar ---
def läs_inställningar(sh):
    try:
        inst = dict(sh.worksheet("Inställningar").get_all_records()[0])
        return inst
    except:
        return {}

# --- Formulär för att lägga till scen ---
def scenformulär(df, inst, sh):
    st.header("📋 Lägg till ny scen / händelse")

    med st.form("scenformulär", clear_on_submit=False):
        typ = st.selectbox("Typ av rad", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        scenens_längd = st.number_input("Scenens längd (h)", min_value=0.0, step=0.5)
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, value=0)
        övriga_män = st.number_input("Övriga män", min_value=0)
        enkel_vaginal = st.number_input("Enkel vaginal", min_value=0)
        enkel_anal = st.number_input("Enkel anal", min_value=0)
        dp = st.number_input("DP", min_value=0)
        dpp = st.number_input("DPP", min_value=0)
        dap = st.number_input("DAP", min_value=0)
        tpp = st.number_input("TPP", min_value=0)
        tpa = st.number_input("TPA", min_value=0)
        tap = st.number_input("TAP", min_value=0)
        kompisar = st.number_input("Kompisar", min_value=0)
        pappans_vänner = st.number_input("Pappans vänner", min_value=0)
        nils_vänner = st.number_input("Nils vänner", min_value=0)
        nils_familj = st.number_input("Nils familj", min_value=0)
        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0)
        älskar_med = st.number_input("Älskar med", min_value=0)
        sover_med = st.number_input("Sover med", min_value=0)
        nils_sex = st.number_input("Nils sex", min_value=0)
        prenumeranter = st.number_input("Prenumeranter", min_value=0)

        bekräfta = st.checkbox("✅ Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till")

    if submitted:
        if not bekräfta:
            st.warning("❗ Bekräfta att du vill lägga till raden innan du sparar.")
            return

        f = {
            "Datum": bestäm_datum(df, inst),
            "Typ": typ,
            "Scenens längd (h)": scenens_längd,
            "Antal vilodagar": antal_vilodagar,
            "Övriga män": övriga_män,
            "Enkel vaginal": enkel_vaginal,
            "Enkel anal": enkel_anal,
            "DP": dp,
            "DPP": dpp,
            "DAP": dap,
            "TPP": tpp,
            "TPA": tpa,
            "TAP": tap,
            "Kompisar": kompisar,
            "Pappans vänner": pappans_vänner,
            "Nils vänner": nils_vänner,
            "Nils familj": nils_familj,
            "DT tid per man (sek)": dt_tid_per_man,
            "Älskar med": älskar_med,
            "Sover med": sover_med,
            "Nils sex": nils_sex,
            "Prenumeranter": prenumeranter
        }

        # Fyll i resten av kolumnerna så att de inte blir NaN
        for col in COLUMNS:
            if col not in f:
                f[col] = 0

        df = process_lägg_till_rader(df, inst, f)
        df = uppdatera_beräkningar(df)
        spara_data(sh, df)

# --- Huvudfunktion ---
def main():
    st.title("🎬 Malin-produktionsapp")
    inst = läs_inställningar(sh)
    df = läs_data(sh)
    scenformulär(df, inst, sh)

if __name__ == "__main__":
    main()
