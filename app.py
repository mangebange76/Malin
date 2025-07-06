import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scope)
    return gspread.authorize(creds)

# Grundläggande konfiguration
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"
ALL_COLUMNS = ["Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p", "Tid s", "Tid d", "Tid t", "Vila", "Älskar",
               "Älsk tid", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"]

# Ladda in data
def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    rows = worksheet.get_all_records()
    df = pd.DataFrame(rows)
    if df.empty or list(df.columns) != ALL_COLUMNS:
        worksheet.clear()
        worksheet.append_row(ALL_COLUMNS)
        df = pd.DataFrame(columns=ALL_COLUMNS)
    return worksheet, df

# Spara ny rad
def append_row(worksheet, new_row):
    worksheet.append_row([new_row.get(col, "") for col in ALL_COLUMNS])

# Maxvärden för 2-kolumner
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df else 0,
    }

# Beräkna känner, totalt män och övrigt
def calculate_derived_fields(df):
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]
    return df

# Huvudvy
def presentera_huvudvy(df):
    st.subheader("📊 Huvudvy")

    df = calculate_derived_fields(df)
    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()

    snitt = (totalt_män + totalt_känner) / len(df[df[["Män", "Känner"]].sum(axis=1) > 0]) if len(df) > 0 else 0
    filmer = totalt_män
    intäkter = filmer * 19.99
    malin_lön = min(intäkter * 0.01, 1500)
    företag_lön = intäkter * 0.40
    vänner_lön = intäkter - malin_lön - företag_lön

    max_vals = get_max_values(df)
    gangb = totalt_känner / sum(max_vals.values()) if sum(max_vals.values()) else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner else 0
    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män else 0

    st.markdown(f"**Totalt Män:** {totalt_män}")
    st.markdown(f"**Snitt (Män + Känner):** {snitt:.2f}")
    st.markdown(f"**Intäkter:** {intäkter:.2f} USD")
    st.markdown(f"**Malin lön:** {malin_lön:.2f} USD")
    st.markdown(f"**Företag lön:** {företag_lön:.2f} USD")
    st.markdown(f"**Vänner lön:** {vänner_lön:.2f} USD")
    st.markdown(f"**GangB:** {gangb:.2f}")
    st.markdown(f"**Älskat:** {älskat:.2f}")
    st.markdown(f"**Vita (%):** {vita:.2f}%")
    st.markdown(f"**Svarta (%):** {svarta:.2f}%")

# Radvyn
def presentera_radvyn(df):
    st.subheader("📄 Radvyn")

    if df.empty:
        st.info("Ingen data ännu.")
        return

    latest = df.iloc[-1].copy()

    # Redigerbar tid
    with st.form("redigera_tid"):
        tid_s = st.number_input("Tid s", value=int(latest["Tid s"]), step=1)
        tid_d = st.number_input("Tid d", value=int(latest["Tid d"]), step=1)
        tid_t = st.number_input("Tid t", value=int(latest["Tid t"]), step=1)
        if st.form_submit_button("Uppdatera tid"):
            latest["Tid s"] = tid_s
            latest["Tid d"] = tid_d
            latest["Tid t"] = tid_t
            worksheet, df = load_data()
            df.iloc[-1, df.columns.get_loc("Tid s")] = tid_s
            df.iloc[-1, df.columns.get_loc("Tid d")] = tid_d
            df.iloc[-1, df.columns.get_loc("Tid t")] = tid_t
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    känner = latest[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum()
    totalt_män = latest["Män"] + känner
    tid_kille = (latest["Tid s"] + latest["Tid d"] + latest["Tid t"]) / 60
    filmer = latest["Män"]
    intäkter = filmer * 19.99

    # Klockan
    start = datetime.datetime.strptime("07:00", "%H:%M")
    tid_total = (
        latest["Tid s"] * latest["Män"] +
        latest["Tid d"] * (latest["Dm"] + latest["Df"] + latest["Dr"]) +
        latest["Tid t"] * (latest["3f"] + latest["3r"] + latest["3p"]) +
        (latest["Män"] * latest["Vila"]) +
        (latest["Dm"] + latest["Df"] + latest["Dr"]) * (latest["Vila"] + 7) +
        (latest["3f"] + latest["3r"] + latest["3p"]) * (latest["Vila"] + 15) +
        latest["Älskar"] * latest["Älsk tid"] * 60
    )
    ny_tid = start + datetime.timedelta(seconds=tid_total)
    klockslag = ny_tid.strftime("%H:%M")

    st.markdown(f"**Tid kille:** {tid_kille:.2f} min " + ("⚠️" if tid_kille < 10 else ""))
    st.markdown(f"**Filmer:** {filmer}")
    st.markdown(f"**Intäkter:** {intäkter:.2f} USD")
    st.markdown(f"**Klockan:** {klockslag}")

# Vilodag-knappar
def skapa_vilodag(knapp, typ):
    _, df = load_data()
    max_vals = get_max_values(df)
    ny_rad = {col: 0 for col in ALL_COLUMNS}
    ny_rad["Dag"] = (pd.to_datetime(df["Dag"].iloc[-1]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.date.today().strftime("%Y-%m-%d")

    if typ == "jobb":
        ny_rad["Älskar"] = 12
        ny_rad["Sover med"] = 1
        ny_rad["Jobb"] = round(max_vals["Jobb 2"] * 0.5)
        ny_rad["Grannar"] = round(max_vals["Grannar 2"] * 0.5)
        ny_rad["Tjej PojkV"] = round(max_vals["Tjej PojkV 2"] * 0.5)
        ny_rad["Nils Fam"] = round(max_vals["Nils Fam 2"] * 0.5)
    elif typ == "hemma":
        ny_rad.update({
            "Jobb": 3,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils Fam": 3,
            "Älskar": 6,
            "Sover med": 0
        })

    worksheet, _ = load_data()
    append_row(worksheet, ny_rad)
    st.success(f"Vilodag {typ} inlagd!")

# Huvudfunktion
def main():
    st.title("📘 Daglig dataspårning")

    worksheet, df = load_data()

    # Vilodag-knappar
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Vilodag jobb"):
            skapa_vilodag("jobb", "jobb")
    with col2:
        if st.button("➕ Vilodag hemma"):
            skapa_vilodag("hemma", "hemma")

    presentera_huvudvy(df)
    presentera_radvyn(df)

if __name__ == "__main__":
    main()
