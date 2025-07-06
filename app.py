import streamlit as st
import pandas as pd
import datetime
import json
from google.oauth2.service_account import Credentials
import gspread

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

# Konstanter
SHEET_NAME = "MalinData"
WORKSHEET_NAME = "Blad1"
HEADERS = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila",
    "Summa s", "Summa d", "Summa t", "Summa v", "Klockan", "Älskar", "Älsk tid", "Sover med",
    "Känner", "Jobb", "Grannar", "Nils kom", "Pv", "Tid kille", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet", "Svarta", "GB"
]

def load_data():
    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=HEADERS)

    # Säkerställ att alla headers finns i rätt ordning
    if list(df.columns) != HEADERS:
        worksheet.clear()
        worksheet.append_row(HEADERS)
        df = pd.DataFrame(columns=HEADERS)

    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(HEADERS)
    for row in df.itertuples(index=False):
        worksheet.append_row(list(row))

def main():
    st.title("📊 MalinApp – Datainmatning & Statistik")

    worksheet, df = load_data()

    st.subheader("➕ Lägg till ny rad")

    with st.form("data_form"):
        today = (
            pd.to_datetime(df["Dag"], errors="coerce").max() + pd.Timedelta(days=1)
            if not df.empty else datetime.date.today()
        )
        ny_dag = st.date_input("Dag", today)

        kolumner = {
            "Män": 0, "F": 0, "R": 0, "Dm": 0, "Df": 0, "Dr": 0, "3f": 0, "3r": 0, "3p": 0,
            "Tid s": 0, "Tid d": 0, "Tid t": 0, "Vila": 0, "Älskar": 0, "Älsk tid": 0, "Sover med": 0,
            "Jobb": 0, "Grannar": 0, "Nils kom": 0, "Pv": 0, "Svarta": 0
        }

        inputs = {key: st.number_input(key, min_value=0, value=0) for key in kolumner}

        submitted = st.form_submit_button("Spara rad")

        if submitted:
            # Beräkningar
            summa_s = inputs["Tid s"]
            summa_d = inputs["Tid d"]
            summa_t = inputs["Tid t"]
            summa_v = inputs["Vila"]
            klockan = "07:00"
            känner = inputs["Jobb"] + inputs["Grannar"] + inputs["Pv"] + inputs["Nils kom"]
            tid_kille = inputs["Tid s"] + inputs["Tid d"] + inputs["Tid t"]
            filmer = 1 if inputs["Män"] > 0 else 0
            pris = 19.99
            intäkter = filmer * pris
            malin = inputs["Älskar"] + inputs["Älsk tid"] + inputs["Sover med"]
            företag = känner
            vänner = känner
            hårdhet = inputs["Män"] + inputs["F"] + inputs["R"]
            gb = känner

            ny_rad = {
                "Dag": str(ny_dag), **inputs,
                "Summa s": summa_s, "Summa d": summa_d, "Summa t": summa_t, "Summa v": summa_v,
                "Klockan": klockan, "Känner": känner, "Tid kille": tid_kille,
                "Filmer": filmer, "Pris": pris, "Intäkter": intäkter,
                "Malin": malin, "Företag": företag, "Vänner": vänner,
                "Hårdhet": hårdhet, "GB": gb
            }

            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            save_data(worksheet, df)
            st.success("✅ Raden sparades i Google Sheets!")

    # Statistik
    st.subheader("📈 Statistik och nyckeltal")

    try:
        max_jobb = df["Jobb"].max()
        max_grannar = df["Grannar"].max()
        max_pv = df["Pv"].max()
        max_nils = df["Nils kom"].max()
        total_känner = max_jobb + max_grannar + max_pv + max_nils

        total_intäkt = df["Intäkter"].sum()
        känner_tjänat = round(total_intäkt / total_känner, 2) if total_känner else 0

        total_män = df["Män"].sum()
        total_gb = df["GB"].sum()
        total_svarta = df["Svarta"].sum()

        vita_procent = round((total_män + total_gb - total_svarta) / (total_män + total_gb + total_svarta) * 100, 2) if (total_män + total_gb + total_svarta) else 0
        svarta_procent = round((total_svarta) / (total_män + total_gb + total_svarta) * 100, 2) if (total_män + total_gb + total_svarta) else 0

        film_rader = df[df["Män"] > 0]
        snitt_film = round((df["Män"].sum() + df["GB"].sum()) / len(film_rader), 2) if len(film_rader) else 0

        malin_tjänat = total_män + total_gb + df["Älskar"].sum() + df["Sover med"].sum()

        st.markdown(f"""
        - 👑 **Max Jobb**: {max_jobb}  
        - 🏡 **Max Grannar**: {max_grannar}  
        - 💗 **Max Pv**: {max_pv}  
        - 👦 **Max Nils kom**: {max_nils}  
        - 🧠 **Känner (total)**: {total_känner}  
        - 💰 **Intäkt per känner**: {känner_tjänat} USD  
        - 🎬 **Snitt film**: {snitt_film}  
        - 👩‍❤️‍👨 **Malin tjänat**: {malin_tjänat}  
        - ⚪ **Vita (%)**: {vita_procent}%  
        - ⚫ **Svarta (%)**: {svarta_procent}%  
        """)
    except Exception as e:
        st.error(f"Fel vid beräkning: {e}")

if __name__ == "__main__":
    main()
