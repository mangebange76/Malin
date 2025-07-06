import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"
HEADERS = [
    "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA", "Tid Singel",
    "Tid Dubbel", "Tid Trippel", "Vila", "Älskar", "Älsk Tid", "Sover med",
    "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Pv", "Svarta"
]

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scope)
    return gspread.authorize(creds)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    try:
        worksheet = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=WORKSHEET_NAME, rows="100", cols="30")
    data = worksheet.get_all_records()
    if not data or list(data[0].keys()) != HEADERS:
        worksheet.clear()
        worksheet.append_row(HEADERS)
        return worksheet, pd.DataFrame(columns=HEADERS)
    else:
        return worksheet, pd.DataFrame(data)

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(HEADERS)
    for _, row in df.iterrows():
        worksheet.append_row([row.get(col, "") for col in HEADERS])

def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df else 0,
    }

def calculate_row(row, max_vals):
    känner = row["Jobb"] + row["Grannar"] + row["Tjej PojkV"] + row["Nils Fam"]
    totalt_män = row["Män"] + känner
    singel = (row["Fi"] + row["Rö"]) * row["Tid Singel"]
    dubbel = (row["Dm"] + row["Df"] + row["Dr"]) * row["Tid Dubbel"]
    trippel = (row["TPP"] + row["TAP"] + row["TPA"]) * row["Tid Trippel"]
    vila = row["Vila"] * totalt_män + (row["Dm"] + row["Df"] + row["Dr"]) * (row["Vila"] + 7) + (row["TPP"] + row["TAP"] + row["TPA"]) * (row["Vila"] + 15)
    summa_tid = singel + dubbel + trippel + vila
    tid_kille = (singel + dubbel * 2 + trippel * 3) / totalt_män if totalt_män else 0
    filmer = row["Män"] + row["Fi"] + row["Rö"] * 2 + row["Dm"] * 2 + row["Df"] * 3 + row["Dr"] * 4 + row["TPP"] * 5 + row["TAP"] * 7 + row["TPA"] * 6
    intäkter = filmer * 19.99
    malin = min(intäkter * 0.01, 1500)
    företag = intäkter * 0.4
    vänner = intäkter - malin - företag
    start = datetime.strptime("07:00", "%H:%M")
    klockan = (start + timedelta(seconds=summa_tid)).strftime("%H:%M")
    return {
        "Känner": känner,
        "Totalt Män": totalt_män,
        "Summa Singel": singel,
        "Summa Dubbel": dubbel,
        "Summa Trippel": trippel,
        "Summa Vila": vila,
        "Summa Tid": summa_tid,
        "Tid Kille": tid_kille,
        "Filmer": filmer,
        "Intäkter": intäkter,
        "Malin": malin,
        "Företag": företag,
        "Vänner": vänner,
        "Klockan": klockan,
    }

def main():
    st.title("Malin-appen 💙")
    worksheet, df = load_data()
    max_vals = get_max_values(df)

    with st.form("add_row"):
        st.subheader("Ny rad")
        datum = st.date_input("Datum", value=datetime.today())
        inputs = {col: st.number_input(col, min_value=0, step=1) for col in HEADERS[1:]}
        if st.form_submit_button("Spara rad"):
            new_row = {"Datum": str(datum)}
            new_row.update(inputs)
            beräkning = calculate_row(new_row, max_vals)
            new_row.update(beräkning)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(worksheet, df)
            st.success("Rad sparad!")

    if st.button("Vilodag jobb"):
        vilorad = {
            "Datum": str(datetime.today().date()),
            "Män": 0, "Fi": 0, "Rö": 0, "Dm": 0, "Df": 0, "Dr": 0,
            "TPP": 0, "TAP": 0, "TPA": 0, "Tid Singel": 0, "Tid Dubbel": 0,
            "Tid Trippel": 0, "Vila": 0, "Älskar": 12, "Älsk Tid": 0,
            "Sover med": 1, "Pv": 0, "Svarta": 0,
            "Jobb": round(max_vals["Jobb 2"] * 0.5),
            "Grannar": round(max_vals["Grannar 2"] * 0.5),
            "Tjej PojkV": round(max_vals["Tjej PojkV 2"] * 0.5),
            "Nils Fam": round(max_vals["Nils Fam 2"] * 0.5)
        }
        vilorad.update(calculate_row(vilorad, max_vals))
        df = pd.concat([df, pd.DataFrame([vilorad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Vilodag jobb sparad.")

    if st.button("Vilodag hemma"):
        vilorad = {
            "Datum": str(datetime.today().date()),
            "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3,
            "Älskar": 6, "Sover med": 0, "Pv": 0, "Svarta": 0
        }
        for col in HEADERS:
            if col not in vilorad:
                vilorad[col] = 0
        vilorad.update(calculate_row(vilorad, max_vals))
        df = pd.concat([df, pd.DataFrame([vilorad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Vilodag hemma sparad.")

    if not df.empty:
        st.subheader("📊 Huvudvy")
        män_sum = df["Män"].sum()
        känner_sum = df["Känner"].sum()
        svarta_sum = df["Svarta"].sum()
        snitt_män_känner = (män_sum + känner_sum) / len(df) if len(df) else 0
        gangb = känner_sum / sum(max_vals.values()) if sum(max_vals.values()) else 0
        älskat = df["Älskar"].sum() / känner_sum if känner_sum else 0
        vita = (män_sum - svarta_sum) / män_sum * 100 if män_sum else 0
        svarta = svarta_sum / män_sum * 100 if män_sum else 0
        st.metric("Totalt Män", män_sum)
        st.metric("Snitt (Män + Känner)", round(snitt_män_känner, 2))
        st.metric("Malin (USD)", round(df["Malin"].sum(), 2))
        st.metric("Vänner (USD)", round(df["Vänner"].sum(), 2))
        st.metric("GangB", round(gangb, 2))
        st.metric("Älskat", round(älskat, 2))
        st.metric("Vita (%)", round(vita, 1))
        st.metric("Svarta (%)", round(svarta, 1))

        st.subheader("📅 Radvy")
        val = st.selectbox("Välj datum", df["Datum"].tolist()[::-1])
        rad = df[df["Datum"] == val].iloc[0]
        st.write(f"**Tid Kille (min):** {round(rad['Tid Kille'] / 60, 2)}")
        st.write(f"**Filmer:** {int(rad['Filmer'])}")
        st.write(f"**Intäkter (USD):** {round(rad['Intäkter'], 2)}")
        st.write(f"**Klockan:** {rad['Klockan']}")

if __name__ == "__main__":
    main()
