import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisering och Sheets-URL
def auth_gspread():
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
    client = gspread.authorize(creds)
    return client

def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    expected_headers = [
        "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Älskar", "Älsk tid", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
        "Tid s", "Tid d", "Tid t", "Vila",
        "DeepT", "Grabbar", "Sekunder", "Varv"
    ]
    current = worksheet.row_values(1)
    if current != expected_headers:
        worksheet.resize(rows=1)
        worksheet.update("A1", [expected_headers])

    df = pd.DataFrame(worksheet.get_all_records())

    # Automatiska kolumner & beräkningar
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    df["Jobb 2"] = df["Jobb"].cummax()
    df["Grannar 2"] = df["Grannar"].cummax()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].cummax()
    df["Nils Fam 2"] = df["Nils Fam"].cummax()
    df["Känner 2"] = df["Jobb 2"] + df["Grannar 2"] + df["Tjej PojkV 2"] + df["Nils Fam 2"]

    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = 0.6 * df["Total tid"] / df["Totalt män"].replace(0, 1)

    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    df["Suger"] = 0.6 * df["Summa tid"] / df["Totalt män"].replace(0, 1)

    df["Tid kille"] = (
        df["Tid s"] + df["Tid d"] * 2 + df["Tid t"] * 3 + df["Suger"] + df["Tid kille DT"] + df["Runk"]
    ) / df["Totalt män"].replace(0, 1)

    df["Klockan"] = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(
        df["Summa tid"] + df["Total tid"], unit="s"
    )
    df["Klockan"] = df["Klockan"].dt.strftime("%H:%M")

    df["Hårdhet"] = 0
    df.loc[df["Män"] > 0, "Hårdhet"] += 1
    df.loc[df["Dm"] > 0, "Hårdhet"] += 2
    df.loc[df["Df"] > 0, "Hårdhet"] += 2
    df.loc[df["Dr"] > 0, "Hårdhet"] += 4
    df.loc[df["TPP"] > 0, "Hårdhet"] += 4
    df.loc[df["TAP"] > 0, "Hårdhet"] += 6
    df.loc[df["TPA"] > 0, "Hårdhet"] += 5

    df["Filmer"] = (
        df["Män"] +
        df["F"] +
        df["R"] +
        df["Dm"] * 2 +
        df["Df"] * 2 +
        df["Dr"] * 3 +
        df["TPP"] * 4 +
        df["TAP"] * 6 +
        df["TPA"] * 5
    ) * df["Hårdhet"]

    df["Intäkter"] = df["Filmer"] * 19.99
    df["Malins lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malins lön"] > 1500, "Malins lön"] = 1500
    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänners lön"] = df["Intäkter"] - df["Malins lön"] - df["Företagets lön"]

    return worksheet, df

import random

def create_new_row(df):
    if df.empty:
        base_date = datetime.today().date()
    else:
        last_date = pd.to_datetime(df["Dag"]).max().date()
        base_date = last_date + timedelta(days=1)

    new_row = {
        "Dag": str(base_date),
        "Män": random.randint(1, 10),
        "F": random.randint(0, 5),
        "R": random.randint(0, 5),
        "Dm": random.randint(0, 2),
        "Df": random.randint(0, 2),
        "Dr": random.randint(0, 2),
        "TPP": random.randint(0, 1),
        "TAP": random.randint(0, 1),
        "TPA": random.randint(0, 1),
        "Älskar": 8,
        "Älsk tid": 30,
        "Sover med": 1,
        "Jobb": random.randint(0, 4),
        "Grannar": random.randint(0, 4),
        "Tjej PojkV": random.randint(0, 3),
        "Nils Fam": random.randint(0, 3),
        "Tid s": random.randint(300, 600),
        "Tid d": random.randint(400, 700),
        "Tid t": random.randint(500, 900),
        "Vila": 7,
        "DeepT": random.randint(10, 100),
        "Grabbar": random.randint(1, 10),
        "Sekunder": random.randint(10, 90),
        "Varv": random.randint(1, 10),
    }
    return new_row

def save_new_row(worksheet, new_row):
    worksheet.append_row(list(new_row.values()))

def main():
    st.set_page_config(page_title="Malin App", layout="wide")
    st.title("Malin Data")

    worksheet, df = load_data()

    # HUVUDVY - Summerade värden
    st.subheader("Huvudvy – Statistik")
    totalt_man = df["Totalt män"].sum()
    känner = df["Känner 2"].iloc[-1]
    st.metric("Totalt antal män", totalt_man)
    st.metric("Känner (senaste)", känner)

    st.metric("Jobb", df["Jobb 2"].iloc[-1])
    st.metric("Grannar", df["Grannar"].iloc[-1] + df["Grannar 2"].iloc[-1])
    st.metric("Tjej PojkV", df["Tjej PojkV 2"].iloc[-1])
    st.metric("Nils fam", df["Nils Fam 2"].iloc[-1])

    snitt_film = (df["Totalt män"] + df["Känner"]).sum() / df[df["Män"] > 0].shape[0]
    st.metric("Snitt film", round(snitt_film, 2))

    gangb = df["Känner"].sum() / df["Känner 2"].iloc[-1]
    älskat = df["Älskar"].sum() / df["Känner 2"].iloc[-1]
    sover = df["Sover med"].sum() / df["Nils Fam 2"].iloc[-1]

    vita = 100 - (df["Män"].sum() / totalt_man * 100 if totalt_man > 0 else 0)

    st.metric("GangB", round(gangb, 2))
    st.metric("Älskat", round(älskat, 2))
    st.metric("Sover med", round(sover, 2))
    st.metric("Vita (%)", round(vita, 1))

    st.metric("Totalt antal filmer", df["Filmer"].sum())
    st.metric("Totala intäkter ($)", round(df["Intäkter"].sum(), 2))
    st.metric("Malins lön ($)", round(df["Malins lön"].sum(), 2))
    st.metric("Företagets lön ($)", round(df["Företagets lön"].sum(), 2))
    st.metric("Vänners lön/snubb", round(df["Vänners lön"].sum() / df["Känner 2"].iloc[-1], 2))

    # RADVY – Detaljerad data
    st.subheader("Radvy – Detaljer")

    selected_index = st.number_input("Välj rad (0 till {}):".format(len(df)-1), 0, len(df)-1, 0)
    selected_row = df.iloc[selected_index]

    st.write("### Detaljer för rad", selected_index)
    st.write(selected_row.to_frame())

    if selected_row["Tid kille"] < 600:
        st.warning("Tid kille < 10 min – Öka värden!")
        st.write("Redigera Tid s / Tid d / Tid t / Varv / Sekunder")

    # Knapp: Lägg till ny slumpmässig rad
    if st.button("➕ Slumpmässig ny rad"):
        new_row = create_new_row(df)
        save_new_row(worksheet, new_row)
        st.success("Ny rad tillagd!")

    # Knapp: Kopiera vald rad
    if st.button("📄 Kopiera vald rad"):
        new_row = selected_row.to_dict()
        new_row["Dag"] = str(datetime.today().date())
        save_new_row(worksheet, new_row)
        st.success("Rad kopierad!")

    # Visa datatabell
    st.subheader("Datatabell")
    st.dataframe(df)

if __name__ == "__main__":
    main()
