import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, time
import json
from google.oauth2 import service_account

# Autentisering
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# Sheet-info
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

# Rubrikrader
KOLUMNNAMN = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Älskar",
    "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2", "Tjej PojkV",
    "Tjej PojkV 2", "Nils fam", "Nils fam 2", "Totalt män", "Tid singel",
    "Tid dubbel", "Tid trippel", "Vila", "Summa singel", "Summa dubbel",
    "Summa trippel", "Summa vila", "Summa tid", "Klockan", "Tid kille",
    "Suger", "Filmer", "Pris", "Intäkter", "Malin", "Företag", "Vänner", "Hårdhet",
    "Känner 2"
]

# Ladda data
def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    if not data:
        worksheet.update([KOLUMNNAMN])
        df = pd.DataFrame(columns=KOLUMNNAMN)
    else:
        df = pd.DataFrame(data)
        if df.columns.tolist() != KOLUMNNAMN:
            worksheet.clear()
            worksheet.update([KOLUMNNAMN])
            df = pd.DataFrame(columns=KOLUMNNAMN)
    return worksheet, df

# Spara data
def save_data(worksheet, df):
    worksheet.update([df.columns.tolist()] + df.fillna("").values.tolist())

# Hämta maxvärde i kolumn
def maxhistorik(df, kolumn):
    if kolumn in df.columns and not df[kolumn].isnull().all():
        return int(df[kolumn].max())
    return 0

# Huvudfunktion
def main():
    st.title("MalinApp – Inmatning")

    worksheet, df = load_data()
    st.write("🔍 Rader i databasen:", len(df))

    with st.form("data_form"):
        datum = st.date_input("Datum", datetime.today().date(), format="YYYY-MM-DD")
        män = st.number_input("Män", 0)
        fi = st.number_input("Fi", 0)
        rö = st.number_input("Rö", 0)
        dm = st.number_input("DM", 0)
        df_ = st.number_input("DF", 0)
        dr = st.number_input("DR", 0)
        tpp = st.number_input("TPP", 0)
        tap = st.number_input("TAP", 0)
        tpa = st.number_input("TPA", 0)
        älskar = st.number_input("Älskar", 0)
        sover_med = st.number_input("Sover med", 0)

        jobb = st.number_input("Jobb", 0)
        grannar = st.number_input("Grannar", 0)
        tjej_pojkv = st.number_input("Tjej PojkV", 0)
        nils_fam = st.number_input("Nils fam", 0)

        tid_singel = st.number_input("Tid singel (sekunder)", 0)
        tid_dubbel = st.number_input("Tid dubbel (sekunder)", 0)
        tid_trippel = st.number_input("Tid trippel (sekunder)", 0)
        vila = st.number_input("Vila (sekunder)", 0)

        submitted = st.form_submit_button("Spara")

    if submitted:
        ny = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Män": män, "Fi": fi, "Rö": rö, "DM": dm, "DF": df_, "DR": dr,
            "TPP": tpp, "TAP": tap, "TPA": tpa, "Älskar": älskar, "Sover med": sover_med,
            "Jobb": jobb, "Grannar": grannar, "Tjej PojkV": tjej_pojkv, "Nils fam": nils_fam
        }

        ny["Känner"] = jobb + grannar + tjej_pojkv + nils_fam
        ny["Totalt män"] = män + ny["Känner"]

        ny["Tid singel"] = tid_singel
        ny["Tid dubbel"] = tid_dubbel
        ny["Tid trippel"] = tid_trippel
        ny["Vila"] = vila

        ny["Summa singel"] = tid_singel * ny["Totalt män"]
        ny["Summa dubbel"] = tid_dubbel * ny["Totalt män"]
        ny["Summa trippel"] = tid_trippel * ny["Totalt män"]

        ny["Summa vila"] = (
            ny["Totalt män"] * vila +
            dm * (vila + 10) +
            df_ * (vila + 15) +
            dr * (vila + 15) +
            tpp * (vila + 15) +
            tap * (vila + 15) +
            tpa * (vila + 15)
        )

        ny["Summa tid"] = (
            ny["Summa singel"] +
            ny["Summa dubbel"] * 2 +
            ny["Summa trippel"] * 3 +
            ny["Summa vila"]
        )

        start = datetime.combine(datetime.today(), time(7, 0))
        klockan = start + timedelta(seconds=ny["Summa tid"])
        ny["Klockan"] = klockan.strftime("%H:%M")

        ny["Tid kille"] = round(
            (ny["Summa singel"] + ny["Summa dubbel"] * 2 + ny["Summa trippel"] * 3) / ny["Totalt män"] / 60, 1
        )

        ny["Suger"] = round(
            0.6 * (ny["Summa singel"] + ny["Summa dubbel"] + ny["Summa trippel"]) / ny["Totalt män"], 1
        )

        ny["Filmer"] = män + fi + rö * 2 + dm * 2 + df_ * 3 + dr * 4 + tpp * 5 + tap * 7 + tpa * 6
        ny["Hårdhet"] = sum([
            int(män > 0),
            int(dm > 0),
            int(df_ > 0) * 2,
            int(dr > 0),
            int(tpp > 0),
            int(tap > 0),
            int(tpa > 0)
        ])

        ny["Pris"] = 19.99
        ny["Intäkter"] = ny["Filmer"] * ny["Hårdhet"] * 19.99
        ny["Malin"] = min(1500, round(ny["Intäkter"] * 0.01, 2))
        ny["Företag"] = round(ny["Intäkter"] * 0.4, 2)
        ny["Vänner"] = round(ny["Intäkter"] - ny["Malin"] - ny["Företag"], 2)

        ny["Jobb 2"] = max(jobb, maxhistorik(df, "Jobb"))
        ny["Grannar 2"] = max(grannar, maxhistorik(df, "Grannar"))
        ny["Tjej PojkV 2"] = max(tjej_pojkv, maxhistorik(df, "Tjej PojkV"))
        ny["Nils fam 2"] = max(nils_fam, maxhistorik(df, "Nils fam"))
        ny["Känner 2"] = max(ny["Känner"], maxhistorik(df, "Känner"))

        df = pd.concat([df, pd.DataFrame([ny])], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Data sparad!")

    if not df.empty:
        st.subheader("Senaste raden")
        st.dataframe(df.tail(1), use_container_width=True)

if __name__ == "__main__":
    main()
