import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from konstanter import COLUMNS, säkerställ_kolumner

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(st.secrets["SHEET_URL"])
sheet = sh.sheet1

def ladda_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return säkerställ_kolumner(df)

def spara_data(sheet, df):
    df = säkerställ_kolumner(df)
    values = df.astype(object).where(pd.notnull(df), "").values.tolist()

    try:
        sheet.clear()
        sheet.append_row(COLUMNS)
        sheet.append_rows(values)
        st.success("✅ Data sparad!")
    except Exception as e:
        st.error(f"❌ Fel vid skrivning: {e}")

def bestäm_datum(df, inst):
    if df.empty:
        startdatum = inst.get("Startdatum")
        if isinstance(startdatum, str):
            try:
                return datetime.strptime(startdatum, "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                pass
        return datetime.today().strftime("%Y-%m-%d")
    else:
        senaste_datum = df["Datum"].iloc[-1]
        try:
            senaste = pd.to_datetime(senaste_datum, errors="coerce")
            if pd.isna(senaste):
                return datetime.today().strftime("%Y-%m-%d")
            nästa = senaste + timedelta(days=1)
            return nästa.strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")

def scenformulär(df, inst):
    with st.form("scenformulär", clear_on_submit=False):
        st.markdown("### Lägg till scen eller vila")
        mode = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])

        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1) if mode == "Vila inspelningsplats" else 0
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

        dt_tid_per_man = st.number_input("DT tid per man (sek)", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=0, step=1)

        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)

        prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)
        intäkt = st.number_input("Intäkt ($)", min_value=0.0, step=0.01)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=0.01)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=0.01)
        kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=0.01)

        dt_total_tid = antal_varv * dt_tid_per_man
        total_tid = (tid_enkel * enkel_vaginal + tid_enkel * enkel_anal +
                     tid_dubbel * (dp + dpp + dap) +
                     tid_trippel * (tpp + tpa + tap)) + \
                    (vila * (enkel_vaginal + enkel_anal + dp + dpp + dap + tpp + tpa + tap))
        total_tid_h = total_tid / 3600

        minuter_per_kille = round((total_tid / max(1, nya_män + kompisar + pappans_vänner + nils_vänner + nils_familj)) / 60, 5)

        st.markdown(f"**Total tid (h):** {round(total_tid_h, 2)}")
        if total_tid_h > 18:
            st.warning("⚠️ Total tid överstiger 18 timmar – justera tid enkel/dubbel/trippel!")

        bekräfta = st.checkbox("Bekräfta att du vill lägga till raden")

        submitted = st.form_submit_button("Lägg till rad")
        if submitted and bekräfta:
            ny_rad = [
                bestäm_datum(df, inst), mode, antal_vilodagar, nya_män, enkel_vaginal, enkel_anal,
                dp, dpp, dap, tpp, tpa, tap,
                tid_enkel, tid_dubbel, tid_trippel, vila,
                kompisar, pappans_vänner, nils_vänner, nils_familj,
                dt_tid_per_man, antal_varv, älskar_med, sover_med, nils_sex, prenumeranter,
                intäkt, kvinnans_lön, mäns_lön, kompisars_lön,
                dt_total_tid, total_tid, total_tid_h, minuter_per_kille
            ]
            df.loc[len(df)] = ny_rad
            spara_data(sheet, df)

def main():
    st.title("Malin produktionsapp")
    st.markdown("En app för att registrera scener, vila och beräkningar.")
    df = ladda_data()
    inst = {"Startdatum": st.text_input("Startdatum (YYYY-MM-DD)", value="2014-03-26")}
    scenformulär(df, inst)

if __name__ == "__main__":
    main()
