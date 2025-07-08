import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Ladda data från Google Sheets ---
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    records = worksheet.get_all_records()
    df = pd.DataFrame.from_dict(records)

    expected_columns = [
        'Dag', 'Män', 'Älskar', 'Sover med', 'Vila', 'Älsk tid',
        'Tid Singel', 'Tid Dubbel', 'Tid Trippel', 'Dm', 'Df', 'Dr',
        'TPP', 'TAP', 'TPA', 'DeepT', 'Sekunder', 'Varv', 'Suger',
        'Tid kille DT', 'Runk', 'Jobb', 'Grannar', 'Tjej PojkV', 'Nils fam'
    ]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

# --- Uppdatera rad i Google Sheets ---
def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index+2, 1, index+2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

# --- Lägg till rad i Google Sheets ---
def append_row(data):
    worksheet, _ = load_data()
    worksheet.append_row(list(data.values()))

def update_calculations(df):
    df = df.copy()

    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils fam"].max()
    df["Jobb 2"] = jobb2
    df["Grannar 2"] = grannar2
    df["Tjej PojkV 2"] = tjej2
    df["Nils fam 2"] = fam2
    känner2 = jobb2 + grannar2 + tjej2 + fam2
    df["Känner 2"] = känner2

    df["Totalt män"] = df["Män"] + känner2

    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]
    df["Grabbar"] = df["Män"] + känner2
    df["Snitt"] = df["DeepT"] / df["Grabbar"]
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"]
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"]

    df["Tid kille"] = df["Tid Singel"] + (df["Tid Dubbel"] * 2) + (df["Tid Trippel"] * 3) + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Fixad funktion – säkrare klockberäkning
    def calc_klockan(row):
        try:
            total_min = float(row["Summa tid"]) + float(row["Total tid"])
            tid = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(total_min, unit="m")
            return tid.strftime("%H:%M")
        except Exception:
            return "Fel"

    df["Klockan"] = df.apply(calc_klockan, axis=1)

    df["Filmer"] = df["Män"] > 0
    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = np.minimum(df["Intäkter"] * 0.01, 800)
    df["Företagets lön"] = 10000
    df["Vänner lön"] = (df["Intäkter"].sum() - df["Malin lön"].sum() - df["Företagets lön"].sum()) / känner2

    return df

# --- Inmatning av ny rad ---
def inmatning(df, worksheet):
    with st.expander("➕ Lägg till ny dag"):
        with st.form("ny_rad_form"):
            kolumner = [col for col in df.columns if col not in [
                "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid",
                "Grabbar", "Snitt", "Total tid", "Tid kille DT", "Runk",
                "Tid kille", "Klockan", "Filmer", "Pris", "Intäkter",
                "Malin lön", "Företagets lön", "Vänner lön",
                "Känner 2", "Totalt män", "Jobb 2", "Grannar 2",
                "Tjej PojkV 2", "Nils fam 2"
            ]]

            inputs = {}
            for col in kolumner:
                if col in ["Dag", "DeepT", "Sekunder", "Varv"]:
                    inputs[col] = st.number_input(col, value=0, step=1)
                elif col in ["Tid Singel", "Tid Dubbel", "Tid Trippel", "Suger"]:
                    inputs[col] = st.number_input(col, value=0.0, step=0.1)
                else:
                    inputs[col] = st.number_input(col, value=0, step=1)

            submitted = st.form_submit_button("Lägg till rad")
            if submitted:
                ny_rad = inputs.copy()
                ny_rad = {k: [v] for k, v in ny_rad.items()}
                ny_df = pd.DataFrame(ny_rad)
                ny_df = update_calculations(ny_df)
                df = pd.concat([df, ny_df], ignore_index=True)
                worksheet.append_row(list(df.iloc[-1]))
                st.success("Raden har lagts till!")

# --- Redigera befintliga rader ---
def radvy(df, worksheet):
    st.header("📝 Redigera dagar")
    for index, rad in df.iterrows():
        with st.expander(f"Dag {int(rad['Dag'])}"):
            with st.form(f"form_{index}"):
                inputs = {}
                for col in df.columns:
                    if col in [
                        "Tid Singel", "Tid Dubbel", "Tid Trippel",
                        "Suger", "DeepT", "Sekunder", "Varv", "Dag"
                    ]:
                        default_val = rad[col]
                        if isinstance(default_val, (int, float)):
                            inputs[col] = st.number_input(
                                f"{col} (Dag {int(rad['Dag'])})", value=float(default_val), step=1.0 if isinstance(default_val, float) else 1
                            )
                submitted = st.form_submit_button("Uppdatera rad")
                if submitted:
                    for col, val in inputs.items():
                        df.at[index, col] = val
                    df = update_calculations(df)
                    row_dict = df.iloc[index].to_dict()
                    update_row(worksheet, index, row_dict)
                    st.success("Raden har uppdaterats.")

# --- Slumpa rad ---
def slumpa_rad(df):
    if df.empty:
        ny_dag = 1
    else:
        ny_dag = df["Dag"].max() + 1

    ny_rad = {col: 0 for col in df.columns}

    for col in df.columns:
        if col in ["Dag", "Älskar", "Sover med", "Vila", "Älsk tid"]:
            continue
        if df[col].dtype in [np.int64, np.float64]:
            max_val = int(df[col].max())
            min_val = int(df[col].min())
            ny_rad[col] = random.randint(min_val, max_val) if max_val > 0 else 0

    ny_rad["Dag"] = ny_dag
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(ny_rad)

# --- Vilodag hemma ---
def vilodag_hemma(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = df["Dag"].max() + 1 if not df.empty else 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    append_row(ny_rad)

# --- Vilodag jobb ---
def vilodag_jobb(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = df["Dag"].max() + 1 if not df.empty else 1
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        max_val = df[fält].max()
        ny_rad[fält] = int(max_val * 0.3)
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    append_row(ny_rad)

# --- Kopiera största raden ---
def kopiera_storsta(df):
    if df.empty:
        return
    idx = df["Totalt män"].idxmax()
    ny_rad = df.loc[idx].copy()
    ny_rad["Dag"] = df["Dag"].max() + 1
    append_row(ny_rad.to_dict())

# --- Presentation huvudvy ---
def presentation(df):
    st.subheader("📊 Summering")

    jobb = df["Jobb"].sum()
    grannar = df["Grannar"].sum()
    tjej = df["Tjej PojkV"].sum()
    fam = df["Nils fam"].sum()

    känner2 = df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2"]].iloc[0].sum()
    män_sum = df["Män"].sum()
    totalt_män = män_sum + känner2

    snitt_film = (män_sum + känner2) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0
    älskat = df["Älskar"].sum() / känner2 if känner2 > 0 else 0
    antal_filmer = len(df[df["Män"] > 0])
    privatgb = len(df[(df["Män"] == 0) & (df["Känner 2"] > 0)])
    antal_dagar = len(df)

    st.write(f"**Jobb:** {jobb}")
    st.write(f"**Grannar:** {grannar}")
    st.write(f"**Tjej PojkV:** {tjej}")
    st.write(f"**Nils fam:** {fam}")
    st.write(f"**Känner (kompisar):** {känner2}")
    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Antal filmer:** {antal_filmer}")
    st.write(f"**PrivatGB:** {privatgb}")
    st.write(f"**Antal dagar:** {antal_dagar}")

# --- Huvudfunktion ---
def main():
    st.title("MalinData App")

    worksheet, df = load_data()
    df = update_calculations(df)

    # Lägg till ny rad manuellt
    with st.form("add_row"):
        st.subheader("➕ Lägg till ny rad manuellt")

        # Endast dessa fält ska vara manuellt ifyllda – i denna ordning
        inmatningsfält = [
            "Män", "Älskar", "Sover med", "Vila", "Älsk tid",
            "Tid Singel", "Tid Dubbel", "Tid Trippel",
            "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
            "DeepT", "Sekunder", "Varv", "Suger",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam"
        ]

        ny_rad = {}
        for col in inmatningsfält:
            ny_rad[col] = st.number_input(f"{col}", min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            try:
                ny_rad["Dag"] = df["Dag"].max() + 1 if not df.empty else 1
                append_row(ny_rad)
                st.success("Raden sparad. Ladda om appen.")
            except Exception as e:
                st.error(f"Fel vid sparning: {e}")

    # Knappar
    st.markdown("### ⚡ Snabbval")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Vilodag hemma"):
            vilodag_hemma(df)
            st.experimental_rerun()
    with col2:
        if st.button("Vilodag jobb"):
            vilodag_jobb(df)
            st.experimental_rerun()
    with col3:
        if st.button("Slumpa rad"):
            slumpa_rad(df)
            st.experimental_rerun()
    with col4:
        if st.button("Kopiera största raden"):
            kopiera_storsta(df)
            st.experimental_rerun()

    # Visa summering
    presentation(df)

    # Visa redigerbara rader
    with st.expander("📋 Redigera rader"):
        radvy(df, worksheet)


if __name__ == "__main__":
    main()
