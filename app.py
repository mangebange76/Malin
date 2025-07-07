import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)
    return client

# Ladda data och säkerställ kolumner
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
        "Tid s", "Tid d", "Tid t", "Vila", "Älsk tid",
        "DeepT", "Grabbar", "Sekunder", "Varv",
        "Snitt", "Total tid", "Tid kille DT", "Runk",
        "Känner", "Totalt män", "Summa singel", "Summa dubbel", "Summa trippel",
        "Summa tid", "Suger", "Tid kille", "Filmer", "Hårdhet",
        "Intäkter", "Malins lön", "Företagets lön", "Vänners lön", "Klockan"
    ]

    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(rows=1)
        worksheet.update("A1", [headers])

    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df

# Lägg till ny rad
def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    worksheet.append_row([row_dict.get(col, "") for col in worksheet.row_values(1)])

# Nästa datum
def nästa_datum(df):
    if df.empty or "Dag" not in df.columns:
        return datetime.today().date()
    try:
        senaste = pd.to_datetime(df["Dag"], errors="coerce").dropna().max()
        return (senaste + timedelta(days=1)).date()
    except:
        return datetime.today().date()

# Beräkna kolumner
def beräkna_kolumner(df):
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = 0.6 * df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa tid"] = df[["Summa singel", "Summa dubbel", "Summa trippel"]].sum(axis=1)
    df["Suger"] = 0.6 * df["Summa tid"] / df["Totalt män"].replace(0, 1)
    df["Tid kille"] = df["Tid s"] + (df["Tid d"] * 2) + (df["Tid t"] * 3) + df["Suger"]
    df["Filmer"] = (df["Män"] + df["F"] + df["R"] + df["Dm"]*2 + df["Df"]*2 + df["Dr"]*3 +
                    df["TPP"]*4 + df["TAP"]*6 + df["TPA"]*5) * df["Hårdhet"]
    df["Intäkter"] = df["Filmer"] * 19.99
    df["Malins lön"] = df["Intäkter"].apply(lambda x: min(x * 0.05, 1500))
    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänners lön"] = df["Intäkter"] - df["Malins lön"] - df["Företagets lön"]
    df["Klockan"] = (pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(
        (df["Summa tid"] + df["Total tid"]) / 60, unit="m")).dt.strftime("%H:%M")
    df["Hårdhet"] = df.apply(lambda rad: 0 if rad["Män"] == 0 else (
        1 + 2*(rad["Dm"]>0) + 2*(rad["Df"]>0) + 4*(rad["Dr"]>0) +
        4*(rad["TPP"]>0) + 6*(rad["TAP"]>0) + 5*(rad["TPA"]>0)), axis=1)
    return df

# Huvudfunktion
def main():
    st.title("📊 MalinData")
    worksheet, df = load_data()
    if not df.empty:
        df = beräkna_kolumner(df)
        st.dataframe(df.tail(1))

if __name__ == "__main__":
    main()
