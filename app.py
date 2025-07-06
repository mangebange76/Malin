import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import math

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    return gspread.authorize(creds)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(WORKSHEET_NAME)

    # Kontrollera rubriker
    expected_columns = [
        "Datum", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
        "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
    ]

    data = worksheet.get_all_values()
    if not data or data[0] != expected_columns:
        worksheet.clear()
        worksheet.append_row(expected_columns)
        df = pd.DataFrame(columns=expected_columns)
    else:
        df = pd.DataFrame(data[1:], columns=data[0])
        df.replace("", 0, inplace=True)
        numeric_cols = expected_columns[1:]
        df[numeric_cols] = df[numeric_cols].astype(float)

    return worksheet, df

def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if not df["Jobb"].isna().all() else 0,
        "Grannar 2": df["Grannar"].max() if not df["Grannar"].isna().all() else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if not df["Tjej PojkV"].isna().all() else 0,
        "Nils Fam 2": df["Nils Fam"].max() if not df["Nils Fam"].isna().all() else 0,
        "Känner 2": df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1).max()
    }

def presentera_huvudvy(df):
    if df.empty:
        st.warning("Ingen data att visa ännu.")
        return

    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    totala_rader = len(df[df["Män"] + df["Känner"] > 0])
    snitt = round((totalt_män + totalt_känner) / totala_rader, 2) if totala_rader else 0

    filmer = df["Män"].sum()
    intäkter = round(filmer * 19.99, 2)
    malin = min(1500, round(intäkter * 0.01, 2))
    företag = round(intäkter * 0.4, 2)
    vänner = round(intäkter - malin - företag, 2)

    maxvärden = get_max_values(df)
    gangb_divisor = maxvärden["Jobb 2"] + maxvärden["Grannar 2"] + maxvärden["Tjej PojkV 2"] + maxvärden["Nils Fam 2"]
    gangb = round(totalt_känner / gangb_divisor, 2) if gangb_divisor else 0

    älskar_sum = df["Älskar"].sum()
    känner_sum = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum().sum()
    älskat = round(älskar_sum / känner_sum, 2) if känner_sum else 0

    svarta = df["Svarta"].sum()
    vita_pct = round((totalt_män - svarta) / totalt_män * 100, 2) if totalt_män else 0
    svarta_pct = round(svarta / totalt_män * 100, 2) if totalt_män else 0

    st.subheader("🔢 Huvudvy")
    st.markdown(f"- **Totalt män:** {int(totalt_män)}")
    st.markdown(f"- **Snitt (Män + Känner):** {snitt}")
    st.markdown(f"- **Malin lön:** {malin} USD")
    st.markdown(f"- **Vänner lön:** {vänner} USD")
    st.markdown(f"- **GangB:** {gangb}")
    st.markdown(f"- **Älskat:** {älskat}")
    st.markdown(f"- **Vita (%):** {vita_pct}%")
    st.markdown(f"- **Svarta (%):** {svarta_pct}%")

def presentera_radvy(df):
    index = st.selectbox("Välj rad att visa", df.index)
    rad = df.loc[index]

    tid_singel = rad["Tid s"]
    tid_dubbel = rad["Tid d"]
    tid_trippel = rad["Tid t"]
    vila = rad["Vila"]

    dm = rad["Dm"]
    df_ = rad["Df"]
    dr = rad["Dr"]
    tpp = rad["3f"]
    tap = rad["3r"]
    tpa = rad["3p"]

    män = rad["Män"]
    känner = rad[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum()
    totalt_män = män + känner

    summa_singel = tid_singel * män
    summa_dubbel = tid_dubbel * (dm + df_ + dr)
    summa_trippel = tid_trippel * (tpp + tap + tpa)
    summa_vila = (totalt_män * vila) + (dm + df_ + dr) * (vila + 7) + (tpp + tap + tpa) * (vila + 15)

    total_tid = summa_singel + summa_dubbel + summa_trippel + summa_vila
    klockan = datetime.strptime("07:00", "%H:%M") + timedelta(seconds=total_tid)
    tid_kille = total_tid / totalt_män if totalt_män else 0

    filmer = män
    intäkter = round(filmer * 19.99, 2)

    st.subheader("📄 Radvy")
    st.write(f"**Tid kille:** {int(tid_kille // 60)} min")
    st.write(f"**Filmer:** {int(filmer)}")
    st.write(f"**Intäkter:** {intäkter} USD")
    st.write(f"**Klockan:** {klockan.strftime('%H:%M')}")

def main():
    st.title("📊 MalinData App")
    worksheet, df = load_data()
    presentera_huvudvy(df)
    if not df.empty:
        presentera_radvy(df)

if __name__ == "__main__":
    main()
