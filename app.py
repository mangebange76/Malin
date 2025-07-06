import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# Konstanter
SPREADSHEET_ID = "1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ"
WORKSHEET_NAME = "Blad1"

REQUIRED_COLUMNS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Summa s", "Summa d", "Summa t",
    "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med", "Känner",
    "Jobb", "Grannar", "Nils kom", "Pv", "Tid kille", "Filmer",
    "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
    )
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    # Skapa rubriker om de saknas
    if worksheet.row_count < 1 or worksheet.row_values(1) != REQUIRED_COLUMNS:
        worksheet.clear()
        worksheet.append_row(REQUIRED_COLUMNS)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def beräkna_rader(df):
    if df.empty:
        return df

    df["Summa s"] = pd.to_numeric(df["Tid s"], errors="coerce").fillna(0)
    df["Summa d"] = pd.to_numeric(df["Tid d"], errors="coerce").fillna(0)
    df["Summa t"] = pd.to_numeric(df["Tid t"], errors="coerce").fillna(0)
    df["Summa v"] = df["Summa s"] + df["Summa d"] + df["Summa t"]

    df["Klockan"] = ["07:00"] + [
        (datetime.strptime(df.loc[i - 1, "Klockan"], "%H:%M") + timedelta(minutes=df.loc[i - 1, "Summa v"])).strftime("%H:%M")
        for i in range(1, len(df))
    ]

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Pv"] + df["Nils kom"]
    df["Tid kille"] = df["Män"]
    df["Filmer"] = df.apply(lambda row: 1 if row["Män"] > 0 else 0, axis=1)
    df["Pris"] = 19.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin"] = df["Älskar"] + df["Älsk tid"] + df["Sover med"]
    df["Företag"] = df["Jobb"]
    df["Vänner"] = df["Känner"]
    df["Hårdhet"] = df["Tid kille"]
    df["GB"] = df["Män"] + df["F"] + df["R"]

    return df

def skriv_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(REQUIRED_COLUMNS)
    rows = df[REQUIRED_COLUMNS].values.tolist()
    worksheet.append_rows(rows)

def main():
    st.title("MalinApp – Daglig inmatning & analys")

    worksheet, df = load_data()

    with st.form("ny_rad"):
        st.subheader("Mata in ny rad:")

        if df.empty:
            nästa_dag = datetime.today()
        else:
            senaste_dag = pd.to_datetime(df["Dag"].iloc[-1], errors="coerce")
            if pd.isnull(senaste_dag):
                nästa_dag = datetime.today()
            else:
                nästa_dag = senaste_dag + timedelta(days=1)

        dag = st.date_input("Dag", nästa_dag.date())
        män = st.number_input("Män", 0)
        f = st.number_input("F", 0)
        r = st.number_input("R", 0)
        dm = st.number_input("Dm", 0)
        df_f = st.number_input("Df", 0)
        dr = st.number_input("Dr", 0)
        _3f = st.number_input("3f", 0)
        _3r = st.number_input("3r", 0)
        _3p = st.number_input("3p", 0)
        tid_s = st.number_input("Tid s (min)", 0)
        tid_d = st.number_input("Tid d (min)", 0)
        tid_t = st.number_input("Tid t (min)", 0)
        vila = st.number_input("Vila (min)", 0)
        älskar = st.number_input("Älskar", 0)
        älsk_tid = st.number_input("Älsk tid", 0)
        sover_med = st.number_input("Sover med", 0)
        jobb = st.number_input("Jobb", 0)
        grannar = st.number_input("Grannar", 0)
        pv = st.number_input("Pv", 0)
        nils_kom = st.number_input("Nils kom", 0)
        svarta = st.number_input("Svarta", 0)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            ny_rad = {
                "Dag": dag.strftime("%Y-%m-%d"),
                "Män": män,
                "F": f,
                "R": r,
                "Dm": dm,
                "Df": df_f,
                "Dr": dr,
                "3f": _3f,
                "3r": _3r,
                "3p": _3p,
                "Tid s": tid_s,
                "Tid d": tid_d,
                "Tid t": tid_t,
                "Vila": vila,
                "Älskar": älskar,
                "Älsk tid": älsk_tid,
                "Sover med": sover_med,
                "Jobb": jobb,
                "Grannar": grannar,
                "Pv": pv,
                "Nils kom": nils_kom,
                "Svarta": svarta
            }

            for col in REQUIRED_COLUMNS:
                if col not in ny_rad:
                    ny_rad[col] = 0

            df = df.append(ny_rad, ignore_index=True)
            df = beräkna_rader(df)
            skriv_data(worksheet, df)
            st.success("Rad sparad!")

    if not df.empty:
        st.subheader("Senaste data")
        st.dataframe(df.tail(10), use_container_width=True)

if __name__ == "__main__":
    main()
