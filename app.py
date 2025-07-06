import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import json

# Autentisering från secrets
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# URL till kalkylarket
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

# Fältrubrikordning
RUBRIKER = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
    "Älskar med", "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2",
    "Tjej PojkV", "Tjej PojkV 2", "Nils fam", "Nils fam 2", "Känner 2", "Totalt män",
    "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila",
    "Summa tid", "Klockan", "Tid kille", "Suger", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet"
]

def skapa_rubrikrad(worksheet):
    existerande = worksheet.row_values(1)
    if existerande != RUBRIKER:
        worksheet.clear()
        worksheet.append_row(RUBRIKER)

def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    skapa_rubrikrad(worksheet)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

def save_data(worksheet, df):
    worksheet.update([df.columns.tolist()] + df.astype(str).values.tolist())

def main():
    st.title("MalinData Inmatning & Beräkning")
    worksheet, df = load_data()

    with st.form("inmatning"):
        datum = st.date_input("Datum", value=datetime.today())
        ny_rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Män": st.number_input("Män", 0, step=1),
            "Fi": st.number_input("Fi", 0, step=1),
            "Rö": st.number_input("Rö", 0, step=1),
            "DM": st.number_input("DM", 0, step=1),
            "DF": st.number_input("DF", 0, step=1),
            "DR": st.number_input("DR", 0, step=1),
            "TPP": st.number_input("TPP", 0, step=1),
            "TAP": st.number_input("TAP", 0, step=1),
            "TPA": st.number_input("TPA", 0, step=1),
            "Älskar med": st.number_input("Älskar med", 0, step=1),
            "Sover med": st.number_input("Sover med", 0, step=1),
            "Jobb": st.number_input("Jobb", 0, step=1),
            "Grannar": st.number_input("Grannar", 0, step=1),
            "Tjej PojkV": st.number_input("Tjej PojkV", 0, step=1),
            "Nils fam": st.number_input("Nils fam", 0, step=1),
            "Tid Singel": st.number_input("Tid Singel (sek)", 0, step=1),
            "Tid Dubbel": st.number_input("Tid Dubbel (sek)", 0, step=1),
            "Tid Trippel": st.number_input("Tid Trippel (sek)", 0, step=1),
            "Vila": st.number_input("Vila (sek)", 0, step=1)
        }

        submit = st.form_submit_button("Spara")

    if submit:
        # Beräkningar
        ny_rad["Känner"] = sum([
            ny_rad["Jobb"],
            ny_rad["Grannar"],
            ny_rad["Tjej PojkV"],
            ny_rad["Nils fam"]
        ])
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)

        for kolumn, kolumn2 in [("Jobb", "Jobb 2"), ("Grannar", "Grannar 2"),
                                ("Tjej PojkV", "Tjej PojkV 2"), ("Nils fam", "Nils fam 2"),
                                ("Känner", "Känner 2")]:
            df[kolumn2] = df[kolumn].cummax()

        df["Totalt män"] = df["Män"] + df["Känner"]
        df["Summa singel"] = df["Tid Singel"] * df["Totalt män"]
        df["Summa dubbel"] = df["Tid Dubbel"] * df["Totalt män"]
        df["Summa trippel"] = df["Tid Trippel"] * df["Totalt män"]

        df["Summa vila"] = (
            df["Totalt män"] * df["Vila"]
            + df["DM"] * (df["Vila"] + 10)
            + df["DF"] * (df["Vila"] + 15)
            + df["DR"] * (df["Vila"] + 15)
            + df["TPP"] * (df["Vila"] + 15)
            + df["TAP"] * (df["Vila"] + 15)
            + df["TPA"] * (df["Vila"] + 15)
        )

        df["Summa tid"] = (
            df["Summa singel"] + df["Summa dubbel"] * 2 +
            df["Summa trippel"] * 3 + df["Summa vila"]
        )

        klockslag = []
        for sekunder in df["Summa tid"]:
            tid = datetime.strptime("07:00", "%H:%M") + timedelta(seconds=sekunder)
            klockslag.append(tid.strftime("%H:%M"))
        df["Klockan"] = klockslag

        df["Tid kille"] = (
            df["Summa singel"] + df["Summa dubbel"] * 2 + df["Summa trippel"] * 3
        ) / df["Totalt män"]

        df["Suger"] = (
            0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"])
            / df["Totalt män"]
        )

        df["Tid kille"] += df["Suger"]

        df["Filmer"] = (
            df["Män"] + df["Fi"] + df["Rö"] * 2 + df["DM"] * 2 +
            df["DF"] * 3 + df["DR"] * 4 +
            df["TPP"] * 5 + df["TAP"] * 7 + df["TPA"] * 6
        )

        df["Hårdhet"] = (
            (df["Män"] > 0).astype(int) +
            (df["DM"] > 0).astype(int) +
            (df["DF"] > 0).astype(int) * 2 +
            (df["DR"] > 0).astype(int) * 1 +
            (df["TPP"] > 0).astype(int) * 4 +
            (df["TAP"] > 0).astype(int) * 5 +
            (df["TPA"] > 0).astype(int) * 4
        )

        df["Pris"] = 19.99
        df["Intäkter"] = df["Pris"] * df["Filmer"] * df["Hårdhet"]
        df["Malin"] = df["Intäkter"] * 0.01
        df["Malin"] = df["Malin"].clip(upper=1500)
        df["Företag"] = df["Intäkter"] * 0.40
        df["Vänner"] = df["Intäkter"] - df["Malin"] - df["Företag"]

        df["Vänner"] = df["Vänner"] / (
            df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2"]].max(axis=1).sum()
        )

        save_data(worksheet, df)
        st.success("Datan har sparats och beräkningar är gjorda.")

    if not df.empty:
        st.subheader("Senaste raden")
        st.dataframe(df.tail(1), use_container_width=True)
