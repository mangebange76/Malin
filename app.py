import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import random
from google.oauth2.service_account import Credentials

# Autentisering till Google Sheets
SHEET_URL = "https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=SCOPE)
gc = gspread.authorize(creds)

# Kolumner som alltid ska finnas i databasen
REQUIRED_COLUMNS = [
    "Datum", "Typ", "DP", "DPP", "DAP", "TPA", "TPP", "TAP",
    "Enkel vaginal", "Enkel anal", "Kompisar", "Pappans vänner",
    "Nils vänner", "Nils familj", "Övriga män", "Älskar med", "Sover med", "Nils sex",
    "DT tid per man (sek)", "DT total tid (sek)", "Total tid (sek)", "Total tid (h)",
    "Prenumeranter", "Intäkt ($)", "Kvinnans lön ($)", "Mäns lön ($)", "Kompisars lön ($)",
    "Minuter per kille", "Scenens längd (h)"
]

def init_sheet():
    sh = gc.open_by_url(SHEET_URL)
    try:
        worksheet = sh.worksheet("Data")
    except:
        worksheet = sh.add_worksheet(title="Data", rows="1000", cols="50")

    data = worksheet.get_all_values()
    if not data:
        worksheet.update("A1", [REQUIRED_COLUMNS])
    else:
        current_cols = data[0]
        if current_cols != REQUIRED_COLUMNS:
            worksheet.clear()
            worksheet.update("A1", [REQUIRED_COLUMNS])

def ensure_columns_exist(df):
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[REQUIRED_COLUMNS]
    return df

def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet("Data")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df = ensure_columns_exist(df)
    return df

def save_data(df):
    df = df.fillna("")
    df = df.astype(str)
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet("Data")
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def läs_inställningar():
    sh = gc.open_by_url(SHEET_URL)
    try:
        worksheet = sh.worksheet("Inställningar")
    except:
        worksheet = sh.add_worksheet(title="Inställningar", rows="100", cols="2")
        worksheet.update("A1:B1", [["Namn", "Värde"]])
        default_settings = [
            ["Startdatum", "2014-03-26"],
            ["Kvinnans namn", "Malin"],
            ["Födelsedatum", "1984-03-26"],
            ["Kompisar", "40"],
            ["Pappans vänner", "30"],
            ["Nils vänner", "25"],
            ["Nils familj", "15"]
        ]
        worksheet.update("A2:B8", default_settings)

    inst_df = pd.DataFrame(worksheet.get_all_records())
    inst = {}
    for _, row in inst_df.iterrows():
        inst[row["Namn"]] = row["Värde"]
    return inst

def spara_inställningar(inst):
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet("Inställningar")
    rows = [[k, v] for k, v in inst.items()]
    worksheet.clear()
    worksheet.update("A1:B1", [["Namn", "Värde"]])
    worksheet.update("A2", rows)

def scenformulär(df, inst):
    st.subheader("Lägg till scen eller vila")

    with st.form("scenform"):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        vilodagar = st.number_input("Antal vilodagar (om vila)", min_value=0, value=0, step=1)
        scenlängd = st.number_input("Scenens längd (i timmar)", min_value=0.0, value=0.0, step=0.5)
        övriga = st.number_input("Övriga män", min_value=0, value=0, step=1)

        enkel_v = st.number_input("Enkel vaginal", min_value=0, value=0, step=1)
        enkel_a = st.number_input("Enkel anal", min_value=0, value=0, step=1)
        dp = st.number_input("DP", min_value=0, value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, value=0, step=1)
        dap = st.number_input("DAP", min_value=0, value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, value=0, step=1)
        tap = st.number_input("TAP", min_value=0, value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, value=0, step=1)

        kompisar = st.number_input("Kompisar", min_value=0, value=0, step=1, max_value=int(inst.get("Kompisar", 0)))
        pappans_v = st.number_input("Pappans vänner", min_value=0, value=0, step=1, max_value=int(inst.get("Pappans vänner", 0)))
        nils_v = st.number_input("Nils vänner", min_value=0, value=0, step=1, max_value=int(inst.get("Nils vänner", 0)))
        nils_f = st.number_input("Nils familj", min_value=0, value=0, step=1, max_value=int(inst.get("Nils familj", 0)))

        dt_tid = st.number_input("Deep throat-tid per man (sekunder)", min_value=0, value=60, step=5)
        älskar = st.number_input("Antal älskar med", min_value=0, value=0, step=1)
        sover = st.number_input("Antal sover med", min_value=0, value=0, step=1)

        # Visa direkt beräknad totaltid, tid per man + dt-tid
        antal_män = sum([
            övriga, kompisar, pappans_v, nils_v, nils_f,
            enkel_v + enkel_a,
            2 * (dp + dpp + dap),
            3 * (tpp + tap + tpa)
        ])
        total_tid_h = scenlängd + (antal_män * dt_tid / 3600)
        tid_per_kille_min = (total_tid_h * 60) / antal_män if antal_män > 0 else 0

        st.markdown(f"**Total tid:** {total_tid_h:.2f} timmar")
        st.markdown(f"**Tid per kille inkl. deep throat:** {tid_per_kille_min:.2f} minuter")

        if total_tid_h > 18:
            st.error("Varning: Total tid överstiger 18 timmar!")

        submitted = st.form_submit_button("Lägg till")

        if submitted:
            datum = generera_nytt_datum(df, typ, vilodagar)
            ny_rad = {
                "Datum": datum,
                "Typ": typ,
                "Antal vilodagar": vilodagar,
                "Scenens längd (h)": scenlängd,
                "Övriga män": övriga,
                "Enkel vaginal": enkel_v,
                "Enkel anal": enkel_a,
                "DP": dp,
                "DPP": dpp,
                "DAP": dap,
                "TPP": tpp,
                "TAP": tap,
                "TPA": tpa,
                "Kompisar": kompisar,
                "Pappans vänner": pappans_v,
                "Nils vänner": nils_v,
                "Nils familj": nils_f,
                "DT tid per man": dt_tid,
                "Antal älskar med": älskar,
                "Antal sover med": sover,
            }
            df = df.append(ny_rad, ignore_index=True)
            save_data(df)
            st.success("Rad tillagd!")
            st.experimental_rerun()

def visa_databas(df):
    st.subheader("Databas – alla rader")
    st.dataframe(df)

    if not df.empty:
        df_copy = df.copy()
        df_copy["Totaltid (h)"] = df_copy.apply(lambda row: (
            float(row["Scenens längd (h)"]) + (
                (
                    int(row["Övriga män"]) +
                    int(row["Kompisar"]) +
                    int(row["Pappans vänner"]) +
                    int(row["Nils vänner"]) +
                    int(row["Nils familj"]) +
                    int(row["Enkel vaginal"]) +
                    int(row["Enkel anal"]) +
                    2 * (int(row["DP"]) + int(row["DPP"]) + int(row["DAP"])) +
                    3 * (int(row["TPP"]) + int(row["TAP"]) + int(row["TPA"]))
                ) * float(row["DT tid per man"]) / 3600
            )
        ), axis=1)

        df_copy["Antal män"] = df_copy.apply(lambda row: (
            int(row["Övriga män"]) +
            int(row["Kompisar"]) +
            int(row["Pappans vänner"]) +
            int(row["Nils vänner"]) +
            int(row["Nils familj"]) +
            int(row["Enkel vaginal"]) +
            int(row["Enkel anal"]) +
            2 * (int(row["DP"]) + int(row["DPP"]) + int(row["DAP"])) +
            3 * (int(row["TPP"]) + int(row["TAP"]) + int(row["TPA"]))
        ), axis=1)

        df_copy["Tid per man (minuter inkl. DT)"] = df_copy.apply(lambda row: (
            (row["Totaltid (h)"] * 60 / row["Antal män"]) if row["Antal män"] > 0 else 0
        ), axis=1)

        df_copy["Varning"] = df_copy["Totaltid (h)"].apply(lambda x: "Över 18h" if x > 18 else "")

        st.dataframe(df_copy[[
            "Datum", "Typ", "Scenens längd (h)", "DT tid per man",
            "Totaltid (h)", "Tid per man (minuter inkl. DT)", "Varning"
        ]])

def main():
    st.set_page_config(page_title="Malin App", layout="wide")

    st.title("🎬 Malin – Beräkningar och statistik")

    # Autentisering och hämtning av kalkylarket
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"],
        scopes=scope
    )
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1--mqpIEEta9An4kFvHZBJoFlRz1EtozxCy2PnD4PNJ0/edit?usp=drivesdk")

    # Initiera ark
    df = init_sheet(sh)
    inst = init_inställningar(sh)

    # Visa redigerbar sidopanel
    visa_inställningar(inst)

    # Visa formulär för att lägga till scen eller vila
    scenformulär(df, inst)

    # Visa databas + summering
    visa_databas(df)


if __name__ == "__main__":
    main()
