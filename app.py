import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Ladda data från Google Sheets ---
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets["GOOGLE_CREDENTIALS"]["type"],
        "project_id": st.secrets["GOOGLE_CREDENTIALS"]["project_id"],
        "private_key_id": st.secrets["GOOGLE_CREDENTIALS"]["private_key_id"],
        "private_key": st.secrets["GOOGLE_CREDENTIALS"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["GOOGLE_CREDENTIALS"]["client_email"],
        "client_id": st.secrets["GOOGLE_CREDENTIALS"]["client_id"],
        "auth_uri": st.secrets["GOOGLE_CREDENTIALS"]["auth_uri"],
        "token_uri": st.secrets["GOOGLE_CREDENTIALS"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open("MalinData")
    worksheet = sheet.worksheet("Blad1")
    records = worksheet.get_all_records()
    df = pd.DataFrame.from_dict(records)
    return worksheet, df

# --- Säkerställ kolumner ---
def ensure_columns_exist(df, worksheet):
    expected_cols = [
        "Dag", "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
        "Vila", "DeepT", "Sekunder", "Varv"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0
    return df

# --- Uppdatera alla beräkningar ---
def update_calculations(df):
    df = df.copy()

    # Kompisar maxvärden
    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils fam"].max()

    df["Jobb 2"] = jobb2
    df["Grannar 2"] = grannar2
    df["Tjej PojkV 2"] = tjej2
    df["Nils fam 2"] = fam2
    df["Känner 2"] = jobb2 + grannar2 + tjej2 + fam2

    # Totalt män
    df["Totalt män"] = df["Nya män"] + df["Känner 2"]
    df["Grabbar"] = df["Totalt män"]

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, np.nan)

    # Total tid
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, np.nan)

    # Summa singel
    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 9) * (
        df["Dubbelmacka"] + df["Dubbel fitta"] + df["Dubbel röv"]
    )

    # Summa trippel
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (
        df["Trippel fitta"] + df["Trippel röv"] + df["Trippel penet"]
    )

    # Suger – 60% av (summa singel + dubbel + trippel) / totalt män
    df["Suger"] = (
        (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) * 0.6
    ) / df["Totalt män"].replace(0, np.nan)

    # Tid kille
    df["Tid kille"] = (
        df["Tid singel"]
        + df["Tid dubbel"] * 2
        + df["Tid trippel"] * 3
        + df["Suger"]
        + df["Tid kille DT"]
    )

    # Klockan – start 07:00 + summa singel + dubbel + trippel + total tid
    def calc_klockan(row):
        total_min = row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"] + row["Total tid"]
        tid = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(total_min, unit="m")
        return tid.strftime("%H:%M")
    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# --- Säkerställ att alla kolumner finns ---
def ensure_columns_exist(df, worksheet):
    required = [
        "Dag", "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
        "Vila", "DeepT", "Sekunder", "Varv"
    ]
    for col in required:
        if col not in df.columns:
            df[col] = 0
    return df

# --- Lägg till rad manuellt ---
def add_manual_row(df, worksheet):
    with st.form("manual_input"):
        st.subheader("➕ Lägg till ny rad")
        ny_rad = {}
        ny_rad["Dag"] = int(df["Dag"].max() + 1 if not df.empty else 1)

        inmatningsfält = [
            "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
            "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
            "Vila", "DeepT", "Sekunder", "Varv"
        ]

        for col in inmatningsfält:
            step = 0.1 if "Tid" in col.lower() else 1
            ny_rad[col] = st.number_input(col, value=0.0 if step == 0.1 else 0, step=step)

        submitted = st.form_submit_button("💾 Spara rad")
        if submitted:
            for col in df.columns:
                if col not in ny_rad:
                    ny_rad[col] = 0
            new_df = pd.DataFrame([ny_rad])
            new_df = update_calculations(new_df)
            worksheet.append_row(list(new_df.iloc[0]))
            st.success("Ny rad sparad!")
            st.experimental_rerun()

# --- Uppdatera befintlig rad ---
def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index + 2, 1, index + 2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

# --- Slumpa rad ---
def slumpa_rad(df):
    if df.empty:
        ny_dag = 1
    else:
        ny_dag = df["Dag"].max() + 1

    ny_rad = {col: 0 for col in df.columns}
    ny_rad["Dag"] = ny_dag

    for col in df.columns:
        if col in ["Dag", "Älskar", "Sover med", "Vila", "Älsk tid"]:
            continue
        if df[col].dtype in [np.int64, np.float64]:
            max_val = int(df[col].max())
            min_val = int(df[col].min())
            ny_rad[col] = random.randint(min_val, max_val) if max_val > 0 else 0

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

# --- Huvudfunktion ---
def main():
    st.title("MalinData App")

    worksheet, df = load_data()
    df = ensure_columns_exist(df, worksheet)
    df = update_calculations(df)

    # --- Inmatningsformulär ---
    with st.form("add_row"):
        st.subheader("Lägg till ny rad")
        ny_rad = {}

        input_fields = [
            "Nya män", "Fitta", "Rumpa",
            "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
            "Trippel fitta", "Trippel röv", "Trippel penet",
            "Älskar", "Älsk tid", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Tid singel", "Tid dubbel", "Tid trippel",
            "Vila", "DeepT", "Sekunder", "Varv"
        ]

        for col in input_fields:
            ny_rad[col] = st.number_input(col, min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            ny_rad["Dag"] = int(df["Dag"].max()) + 1 if not df.empty else 1
            append_row(ny_rad)
            st.success("Raden har lagts till. Ladda om appen.")

    # --- Snabbvalsknappar ---
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

    # --- Radredigering (expander) ---
    with st.expander("📋 Redigera rader"):
        radvy(df, worksheet)
if __name__ == "__main__":
    main()
