import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Anslutning till Google Sheets
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets["type"],
        "project_id": st.secrets["project_id"],
        "private_key_id": st.secrets["private_key_id"],
        "private_key": st.secrets["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["client_email"],
        "client_id": st.secrets["client_id"],
        "auth_uri": st.secrets["auth_uri"],
        "token_uri": st.secrets["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open("MalinData")
    worksheet = sheet.worksheet("Blad1")
    records = worksheet.get_all_records()
    df = pd.DataFrame.from_dict(records)

    # Säkerställ att rätt rubriker finns
    expected_columns = ['Dag', 'Män', 'Älskar', 'Sover med', 'Vila', 'Älsk tid', 'Tid Singel', 'Tid Dubbel', 'Tid Trippel',
                        'Dm', 'Df', 'Dr', 'TPP', 'TAP', 'TPA', 'DeepT', 'Sekunder', 'Varv', 'Suger', 'Tid kille DT',
                        'Runk', 'Jobb', 'Grannar', 'Tjej PojkV', 'Nils fam']
    for col in expected_columns:
        if col not in df.columns:
            df[col] = 0

    return worksheet, df

def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index+2, 1, index+2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

def append_row(data):
    worksheet, _ = load_data()
    worksheet.append_row(list(data.values()))

def update_calculations(df):
    df = df.copy()

    # Känner (kompisar)
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

    # Totalt män
    df["Totalt män"] = df["Män"] + känner2

    # Summa singel, dubbel, trippel
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    # Summa tid
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Grabbar (radnivå)
    df["Grabbar"] = df["Män"] + känner2

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"]

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"]

    # Runk
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"]

    # Tid kille
    df["Tid kille"] = df["Tid Singel"] + (df["Tid Dubbel"] * 2) + (df["Tid Trippel"] * 3) + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    # Klockan
    def calc_klockan(row):
        total_min = row["Summa tid"] + row["Total tid"]
        tid = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(total_min, unit="m")
        return tid.strftime("%H:%M")
    df["Klockan"] = df.apply(calc_klockan, axis=1)

    # Filmer
    df["Filmer"] = df["Män"] > 0

    # Pris
    df["Pris"] = 39.99

    # Intäkter
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön: 1% av intäkter, max 800
    df["Malin lön"] = np.minimum(df["Intäkter"] * 0.01, 800)

    # Företagets lön: alltid max 10000
    df["Företagets lön"] = 10000

    # Vänner lön
    df["Vänner lön"] = (df["Intäkter"].sum() - df["Malin lön"].sum() - df["Företagets lön"].sum()) / känner2

    return df

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

def presentation(df):
    st.header("📊 Presentation")

    känner2 = df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2"]].iloc[0].sum()
    totalt_män = df["Män"].sum() + känner2
    antal_filmer = df[df["Män"] > 0].shape[0]
    privat_gb = df[(df["Män"] == 0) & (df["Totalt män"] > 0)].shape[0]

    snitt_film = (df["Män"].sum() + känner2) / antal_filmer if antal_filmer > 0 else 0
    älskat = df["Älskar"].sum() / känner2 if känner2 > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (kompisar):** {känner2}")
    st.write(f"**Jobb:** {df['Jobb'].max()}")
    st.write(f"**Grannar:** {df['Grannar'].max()}")
    st.write(f"**Tjej PojkV:** {df['Tjej PojkV'].max()}")
    st.write(f"**Nils fam:** {df['Nils fam'].max()}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med:** {df['Sover med'].sum()}")
    st.write(f"**Antal filmer:** {antal_filmer}")
    st.write(f"**Privat GB:** {privat_gb}")
    st.write(f"**Intäkter:** {df['Intäkter'].sum():.2f} USD")
    st.write(f"**Malin lön:** {df['Malin lön'].sum():.2f} USD")
    st.write(f"**Företagets lön:** {df['Företagets lön'].sum():.2f} USD")
    vänner_lön = (df["Intäkter"].sum() - df["Malin lön"].sum() - df["Företagets lön"].sum()) / känner2 if känner2 > 0 else 0
    st.write(f"**Vänner lön (per kompis):** {vänner_lön:.2f} USD")
    st.write(f"**Antal dagar:** {len(df)}")

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
    st.subheader("Summering")

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
    df = ensure_columns_exist(df, worksheet)
    df = update_calculations(df)

    with st.form("add_row"):
        st.subheader("Lägg till ny rad")
        ny_rad = {}
        for col in df.columns:
            if col in ["Dag", "Totalt män", "Känner 2", "Grabbar", "Snitt", "Total tid", "Tid kille DT", "Runk", "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid", "Klockan", "Tid kille", "Suger", "Filmer", "Pris", "Intäkter", "Malin lön", "Företagets lön", "Vänner lön"]:
                continue
            ny_rad[col] = st.number_input(f"{col}", min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            ny_rad["Dag"] = df["Dag"].max() + 1 if not df.empty else 1
            append_row(ny_rad)
            st.success("Raden sparad. Ladda om appen.")

    # Visa knappar
    st.markdown("### Snabbval")
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

    # Visa huvudvy
    presentation(df)

    # Visa radvy
    with st.expander("📋 Redigera rader"):
        radvy(df, worksheet)


if __name__ == "__main__":
    main()
