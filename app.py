import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import json

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# Inställningar
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit"
SHEET_NAME = "Blad1"
STARTKLOCKA = datetime.strptime("07:00", "%H:%M")

# Fältnamn
FIELDS = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Älskar",
    "Sover med", "Känner", "Jobb", "Jobb 2", "Grannar", "Grannar 2", "Tjej PojkV", "Tjej PojkV 2",
    "Nils Fam", "Nils Fam 2", "Totalt Män", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid", "Klockan",
    "Tid kille", "Suger", "Filmer", "Pris", "Intäkter", "Malin lön", "Företag lön", "Vänner lön",
    "Hårdhet", "Svarta"
]

# Hjälpfunktioner
def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        worksheet.append_row(FIELDS)
        df = pd.DataFrame(columns=FIELDS)
    else:
        missing_cols = [col for col in FIELDS if col not in df.columns]
        for col in missing_cols:
            df[col] = None
        df = df[FIELDS]
    return worksheet, df

def save_row(worksheet, df, row):
    row_data = [row.get(col, "") for col in FIELDS]
    worksheet.append_row(row_data)
    df.loc[len(df)] = row
    return df

def calculate_fields(row, df):
    # Datum
    row["Datum"] = row.get("Datum") or datetime.today().strftime("%Y-%m-%d")

    # Känner
    row["Känner"] = sum([row.get(f, 0) for f in ["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]])

    # Känner 2
    row["Jobb 2"] = max([df["Jobb"].max() if not df.empty else 0, row["Jobb"]])
    row["Grannar 2"] = max([df["Grannar"].max() if not df.empty else 0, row["Grannar"]])
    row["Tjej PojkV 2"] = max([df["Tjej PojkV"].max() if not df.empty else 0, row["Tjej PojkV"]])
    row["Nils Fam 2"] = max([df["Nils Fam"].max() if not df.empty else 0, row["Nils Fam"]])
    row["Känner 2"] = max([df["Känner"].max() if not df.empty else 0, row["Känner"]])

    # Totalt Män
    row["Totalt Män"] = row["Män"] + row["Känner"]

    # Summeringar
    row["Summa singel"] = row["Tid Singel"] * row["Totalt Män"]
    row["Summa dubbel"] = row["Tid Dubbel"] * row["Totalt Män"]
    row["Summa trippel"] = row["Tid Trippel"] * row["Totalt Män"]
    vila = row["Vila"]
    row["Summa vila"] = (
        row["Totalt Män"] * vila +
        row["DM"] * (vila + 10) +
        row["DF"] * (vila + 15) +
        row["DR"] * (vila + 15) +
        row["TPP"] * (vila + 15) +
        row["TAP"] * (vila + 15) +
        row["TPA"] * (vila + 15)
    )
    row["Summa tid"] = row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Summa vila"]
    row["Klockan"] = (STARTKLOCKA + timedelta(seconds=row["Summa tid"])).strftime("%H:%M")

    # Tid kille
    row["Tid kille"] = round((
        row["Summa singel"] +
        row["Summa dubbel"] * 2 +
        row["Summa trippel"] * 3
    ) / row["Totalt Män"] / 60, 1)  # i minuter

    # Suger
    row["Suger"] = round(0.6 * (
        row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"]
    ) / row["Totalt Män"])

    # Filmer
    filmer = (
        row["Män"] + row["Fi"] + row["Rö"]*2 + row["DM"]*2 + row["DF"]*3 +
        row["DR"]*4 + row["TPP"]*5 + row["TAP"]*7 + row["TPA"]*6
    )
    row["Filmer"] = filmer
    row["Pris"] = 19.99
    row["Intäkter"] = round(row["Filmer"] * row["Pris"], 2)

    # Malin lön
    row["Malin lön"] = min(1500, round(0.01 * row["Intäkter"], 2))
    row["Företag lön"] = round(0.4 * row["Intäkter"], 2)
    row["Vänner lön"] = round(row["Intäkter"] - row["Malin lön"] - row["Företag lön"], 2)

    # Hårdhet
    hard = 0
    if row["Män"] > 0: hard += 1
    if row["DM"] > 0: hard += 1
    if row["DF"] > 0: hard += 2
    if row["DR"] > 0: hard += 1
    if row["TPP"] > 0: hard += 4
    if row["TAP"] > 0: hard += 5
    if row["TPA"] > 0: hard += 4
    row["Hårdhet"] = hard
    return row

# Streamlit UI
def main():
    st.title("MalinApp")

    worksheet, df = load_data()

    with st.form("inmatning"):
        st.subheader("Lägg till ny rad")
        ny_rad = {}
        for f in FIELDS:
            if f == "Datum":
                ny_rad[f] = st.date_input(f, datetime.today())
            elif f in ["Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila"]:
                ny_rad[f] = st.number_input(f, min_value=0, step=1)
            elif f in ["Pris"]:
                ny_rad[f] = 19.99
            elif f in ["Klockan"]:
                continue
            elif f in FIELDS[FIELDS.index("Män"):FIELDS.index("Tid Singel")]:
                ny_rad[f] = st.number_input(f, min_value=0, step=1)
        if st.form_submit_button("Spara rad"):
            ny_rad = calculate_fields(ny_rad, df)
            df = save_row(worksheet, df, ny_rad)
            st.success("Raden sparad!")

    if not df.empty:
        st.header("📊 Huvudvy")
        total_män = df["Män"].sum()
        total_känner = df["Känner"].sum()
        total_älskar = df["Älskar"].sum()
        total_malin = df["Malin lön"].sum()
        total_vänner = df["Vänner lön"].sum()
        total_svarta = df["Svarta"].sum()

        st.markdown(f"- **Totalt Män:** {total_män}")
        st.markdown(f"- **Malin lön:** {total_malin:.2f} USD")
        st.markdown(f"- **Vänner lön:** {total_vänner:.2f} USD")
        if total_män > 0:
            vita = (total_män - total_svarta) / total_män * 100
            svarta = total_svarta / total_män * 100
            st.markdown(f"- **Vita (%):** {vita:.1f}%")
            st.markdown(f"- **Svarta (%):** {svarta:.1f}%")

        rader_med_värde = df[df["Män"] + df["Känner"] > 0]
        if not rader_med_värde.empty:
            snitt = (rader_med_värde["Män"] + rader_med_värde["Känner"]).mean()
            st.markdown(f"- **Snitt (Män + Känner):** {snitt:.1f}")

        # GangB och Älskat
        denom = df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils Fam 2"]].max().sum()
        if denom > 0:
            gangb = total_känner / denom
            alskat = total_älskar / denom
            st.markdown(f"- **GangB:** {gangb:.2f}")
            st.markdown(f"- **Älskat:** {alskat:.2f}")

        st.header("📄 Enskild rad")
        val = st.selectbox("Välj rad", df.index[::-1])
        rad = df.loc[val]
        st.markdown(f"- **Klockan:** {rad['Klockan']}")
        st.markdown(f"- **Tid kille:** {rad['Tid kille']} min")
        st.markdown(f"- **Filmer:** {rad['Filmer']}")
        st.markdown(f"- **Intäkter:** {rad['Intäkter']} USD")

if __name__ == "__main__":
    main()
