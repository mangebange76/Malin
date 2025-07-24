import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from konstanter import COLUMNS, säkerställ_kolumner

# Setup
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(st.secrets["SHEET_URL"])
worksheet = sh.sheet1

# Hämta befintlig data
def hämta_data():
    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(values[1:], columns=values[0])
    df = säkerställ_kolumner(df)
    return df

# Spara nya rader
def spara_rad(rad):
    rad = [str(x) if x is not None else "" for x in rad]
    if len(rad) != len(COLUMNS):
        st.error(f"❌ Antal kolumner mismatch: {len(rad)} vs {len(COLUMNS)}")
        return
    worksheet.append_row(rad, value_input_option="USER_ENTERED")
    st.success("✅ Rad tillagd i databasen.")

# Datumlogik
def bestäm_datum(df):
    if df.empty:
        return datetime.today().strftime("%Y-%m-%d")
    senaste = df["Datum"].iloc[-1]
    try:
        nästa = datetime.strptime(senaste, "%Y-%m-%d") + pd.Timedelta(days=1)
    except:
        nästa = datetime.today()
    return nästa.strftime("%Y-%m-%d")

# Totaltid (sekunder)
def beräkna_total_tid(enkel, dubbel, trippel, antal_varv, vila):
    total = (enkel + dubbel + trippel + vila) * antal_varv
    return total

# Huvudapp
def main():
    st.title("Malin-produktionsapp")

    df = hämta_data()

    with st.form("scenformulär", clear_on_submit=False):
        st.subheader("Lägg till ny scen eller aktivitet")

        datum = bestäm_datum(df)
        st.markdown(f"**Datum (autogenererat):** {datum}")

        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1)
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
        vila = st.number_input("Vila (sek)", min_value=0, step=1)
        kompisar = st.number_input("Kompisar", min_value=0, step=1)
        pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1)
        nils_vänner = st.number_input("Nils vänner", min_value=0, step=1)
        nils_familj = st.number_input("Nils familj", min_value=0, step=1)
        dt_tid_per_man = st.number_input("DT tid per man", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=1, value=1)
        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)
        prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)
        intakt = st.number_input("Intäkt ($)", min_value=0.0, step=0.01)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=0.01)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=0.01)
        kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=0.01)
        dt_total_tid = st.number_input("DT total tid (sek)", min_value=0, step=1)

        total_tid_sek = beräkna_total_tid(tid_enkel, tid_dubbel, tid_trippel, antal_varv, vila)
        total_tid_h = round(total_tid_sek / 3600, 2)
        minuter_per_kille = round(total_tid_sek / max((nya_män + 1), 1) / 60, 2)

        st.markdown(f"**Total tid (h): {total_tid_h}**")
        if total_tid_h > 18:
            st.warning("⚠️ Total tid överstiger 18 timmar. Justera tider!")
            tid_enkel = st.number_input("⚙️ Justera Tid enkel", value=tid_enkel, step=1)
            tid_dubbel = st.number_input("⚙️ Justera Tid dubbel", value=tid_dubbel, step=1)
            tid_trippel = st.number_input("⚙️ Justera Tid trippel", value=tid_trippel, step=1)

        bekräfta = st.checkbox("✅ Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till rad")

        if submitted and bekräfta:
            ny_rad = [
                datum, typ, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal, dp, dpp, dap,
                tpp, tpa, tap, tid_enkel, tid_dubbel, tid_trippel, kompisar, pappans_vänner,
                nils_vänner, nils_familj, dt_tid_per_man, antal_varv, älskar_med, sover_med,
                nils_sex, prenumeranter, intakt, kvinnans_lön, mäns_lön, kompisars_lön,
                dt_total_tid, total_tid_sek, total_tid_h, minuter_per_kille, vila
            ]
            spara_rad(ny_rad)

if __name__ == "__main__":
    main()
