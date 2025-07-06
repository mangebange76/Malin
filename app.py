import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import math

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    return gspread.authorize(creds)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    expected_columns = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", 
        "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med", 
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
    ]
    if df.empty or list(df.columns) != expected_columns:
        worksheet.clear()
        worksheet.append_row(expected_columns)
        df = pd.DataFrame(columns=expected_columns)

    return worksheet, df

def presentera_huvudvy(df):
    st.subheader("🔢 Sammanställning")

    totalt_män = df["Män"].sum()
    totalt_känner = (df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]).sum()
    totalt_svarta = df["Svarta"].sum()

    giltiga_rader = df[(df["Män"] + df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]) > 0]
    snitt = (totalt_män + totalt_känner) / len(giltiga_rader) if len(giltiga_rader) > 0 else 0

    filmer = df["Män"].sum()
    pris = 19.99
    intäkter = filmer * pris

    malin_lön = min(intäkter * 0.01, 1500)
    företag_lön = intäkter * 0.40
    vänner_lön = intäkter - malin_lön - företag_lön

    max_jobb = df["Jobb"].max()
    max_grannar = df["Grannar"].max()
    max_tjej = df["Tjej PojkV"].max()
    max_nils = df["Nils Fam"].max()
    gangb_nämnare = max_jobb + max_grannar + max_tjej + max_nils
    gangb = totalt_känner / gangb_nämnare if gangb_nämnare > 0 else 0

    älskat_nämnare = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    älskat_total = df["Älskar"].sum()
    älskat = älskat_total / älskat_nämnare.sum() if älskat_nämnare.sum() > 0 else 0

    vita_procent = ((totalt_män - totalt_svarta) / totalt_män * 100) if totalt_män > 0 else 0
    svarta_procent = (totalt_svarta / totalt_män * 100) if totalt_män > 0 else 0

    st.write(f"**Totalt Män:** {totalt_män}")
    st.write(f"**Snitt (Män + Känner):** {snitt:.1f} per rad")
    st.write(f"**Intäkter:** {intäkter:.2f} USD")
    st.write(f"**Malin lön:** {malin_lön:.2f} USD")
    st.write(f"**Vänner lön:** {vänner_lön:.2f} USD")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Vita (%):** {vita_procent:.2f}%")
    st.write(f"**Svarta (%):** {svarta_procent:.2f}%")

def main():
    st.title("📊 MalinData – Daglig inmatning och analys")

    worksheet, df = load_data()

    if df.empty:
        st.info("❌ Inga data hittades i Google Sheet. Lägg till en ny rad nedan.")
    else:
        presentera_huvudvy(df)

    st.markdown("---")
    st.subheader("➕ Lägg till ny rad")
    with st.form("ny_rad_form"):
        idag = datetime.today().strftime("%Y-%m-%d")
        ny_rad = {
            "Dag": st.text_input("Dag (ÅÅÅÅ-MM-DD)", idag),
            "Män": st.number_input("Män", min_value=0, step=1),
            "F": st.number_input("F", min_value=0, step=1),
            "R": st.number_input("R", min_value=0, step=1),
            "Dm": st.number_input("Dm", min_value=0, step=1),
            "Df": st.number_input("Df", min_value=0, step=1),
            "Dr": st.number_input("Dr", min_value=0, step=1),
            "3f": st.number_input("3f", min_value=0, step=1),
            "3r": st.number_input("3r", min_value=0, step=1),
            "3p": st.number_input("3p", min_value=0, step=1),
            "Tid s": st.number_input("Tid singel (sekunder)", min_value=0, step=1),
            "Tid d": st.number_input("Tid dubbel (sekunder)", min_value=0, step=1),
            "Tid t": st.number_input("Tid trippel (sekunder)", min_value=0, step=1),
            "Vila": st.number_input("Vila (sekunder)", min_value=0, step=1),
            "Älskar": st.number_input("Älskar", min_value=0, step=1),
            "Älsk tid": st.number_input("Älsk tid (minuter)", min_value=0, step=1),
            "Sover med": st.number_input("Sover med", min_value=0, step=1),
            "Jobb": st.number_input("Jobb", min_value=0, step=1),
            "Grannar": st.number_input("Grannar", min_value=0, step=1),
            "Tjej PojkV": st.number_input("Tjej PojkV", min_value=0, step=1),
            "Nils Fam": st.number_input("Nils Fam", min_value=0, step=1),
            "Svarta": st.number_input("Svarta", min_value=0, step=1)
        }

        if st.form_submit_button("Lägg till rad"):
            new_df = pd.DataFrame([ny_rad])
            df = pd.concat([df, new_df], ignore_index=True)
            worksheet.append_row(list(ny_rad.values()))
            st.success("✅ Raden har lagts till!")

if __name__ == "__main__":
    main()
