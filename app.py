import streamlit as st
import pandas as pd
import numpy as np
import gspread
import random
from google.oauth2.service_account import Credentials

# ---- Ladda data från Google Sheets ----
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = {
        "type": st.secrets["GOOGLE_CREDENTIALS"]["type"],
        "project_id": st.secrets["GOOGLE_CREDENTIALS"]["project_id"],
        "private_key_id": st.secrets["GOOGLE_CREDENTIALS"]["private_key_id"],
        "private_key": st.secrets["GOOGLE_CREDENTIALS"]["private_key"],
        "client_email": st.secrets["GOOGLE_CREDENTIALS"]["client_email"],
        "client_id": st.secrets["GOOGLE_CREDENTIALS"]["client_id"],
        "auth_uri": st.secrets["GOOGLE_CREDENTIALS"]["auth_uri"],
        "token_uri": st.secrets["GOOGLE_CREDENTIALS"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["GOOGLE_CREDENTIALS"]["client_x509_cert_url"]
    }

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Säkerställ att alla kolumner som krävs finns
    alla_kolumner = [
        "Dag", "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
        "Vila", "DeepT", "Sekunder", "Varv"
    ]
    for kolumn in alla_kolumner:
        if kolumn not in df.columns:
            df[kolumn] = 0

    return worksheet, df

# ---- Uppdatera rad i Google Sheets ----
def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index+2, 1, index+2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

# ---- Lägg till ny rad i Google Sheets ----
def append_row(data):
    worksheet, _ = load_data()
    worksheet.append_row(list(data.values()))

# ---- Beräkningar ----
def update_calculations(df):
    df = df.copy()

    # Känner (kompisar) – maxvärden
    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils fam"].max()

    df["Jobb 2"] = jobb2
    df["Grannar 2"] = grannar2
    df["Tjej PojkV 2"] = tjej2
    df["Nils fam 2"] = fam2

    df["Känner 2"] = jobb2 + grannar2 + tjej2 + fam2
    df["Totalt män"] = df["Nya män"] + df["Känner 2"]

    # Summa singel, dubbel, trippel
    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 9) * (df["Dubbelmacka"] + df["Dubbel fitta"] + df["Dubbel röv"])
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (df["Trippel fitta"] + df["Trippel röv"] + df["Trippel penet"])

    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    # Suger = 60% av summa / totalt män
    df["Suger"] = (df["Summa tid"] * 0.6) / df["Totalt män"]

    # Grabbar & snitt
    df["Grabbar"] = df["Nya män"] + df["Känner 2"]
    df["Snitt"] = df["DeepT"] / df["Grabbar"]

    # Total tid & tid per kille
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"]
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"]

    df["Tid kille"] = (
        df["Tid singel"] +
        (df["Tid dubbel"] * 2) +
        (df["Tid trippel"] * 3) +
        df["Suger"] +
        df["Tid kille DT"] +
        df["Runk"]
    )

    # Tidsåtgång i format "X h Y min"
    def calc_tidsåtgång(row):
        total_min = float(row.get("Summa tid", 0)) + float(row.get("Total tid", 0))
        timmar = int(total_min // 60)
        minuter = int(total_min % 60)
        return f"{timmar} h {minuter} min"

    df["Tidsåtgång"] = df.apply(calc_tidsåtgång, axis=1)

    # Övriga beräkningar
    df["Filmer"] = df["Nya män"] > 0
    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = np.minimum(df["Intäkter"] * 0.02, 1000)
    df["Företagets lön"] = 10000

    int_sum = df["Intäkter"].sum()
    malin_sum = df["Malin lön"].sum()
    foretag_sum = df["Företagets lön"].sum()
    känner2 = df["Känner 2"].iloc[0] if "Känner 2" in df else 0

    if känner2 > 0:
        df["Vänner lön"] = (int_sum - malin_sum - foretag_sum) / känner2
    else:
        df["Vänner lön"] = 0

    return df

# ---- Inmatning av ny rad ----
def inmatning(df, worksheet):
    st.subheader("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1

        fält_ordning = [
            "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
            "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid",
            "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Tid singel", "Tid dubbel", "Tid trippel", "Vila", "DeepT", "Sekunder", "Varv"
        ]

        for fält in fält_ordning:
            if "Tid" in fält or fält in ["Snitt"]:
                ny_rad[fält] = st.number_input(fält, value=0.0, step=0.1)
            else:
                ny_rad[fält] = st.number_input(fält, value=0, step=1)

        if st.form_submit_button("💾 Spara rad"):
            ny_df = pd.DataFrame([ny_rad])
            ny_df = update_calculations(ny_df)
            append_row(ny_df.iloc[0].to_dict())
            st.success("✅ Raden sparades!")
            st.experimental_rerun()

# ---- Redigera befintliga rader ----
def redigera_rader(df, worksheet):
    st.subheader("📝 Redigera befintliga rader")
    for i, row in df.iterrows():
        with st.expander(f"Dag {int(row['Dag'])}"):
            with st.form(f"form_edit_{i}"):
                uppdaterad = {}
                redigerbara = [
                    "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
                    "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid",
                    "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
                    "Tid singel", "Tid dubbel", "Tid trippel", "Vila", "DeepT", "Sekunder", "Varv"
                ]
                for fält in redigerbara:
                    if "Tid" in fält:
                        uppdaterad[fält] = st.number_input(f"{fält}", value=float(row[fält]), step=0.1, key=f"{fält}_{i}")
                    else:
                        uppdaterad[fält] = st.number_input(f"{fält}", value=int(row[fält]), step=1, key=f"{fält}_{i}")

                if st.form_submit_button("Uppdatera rad"):
                    for key, val in uppdaterad.items():
                        df.at[i, key] = val
                    df = update_calculations(df)
                    update_row(worksheet, i, df.iloc[i].to_dict())
                    st.success("✅ Raden uppdaterades.")
                    st.experimental_rerun()

# ---- Kommandon ----

def kopiera_storsta(df):
    if df.empty:
        return
    idx = df["Totalt män"].idxmax()
    ny_rad = df.loc[idx].copy()
    ny_rad["Dag"] = int(df["Dag"].max()) + 1
    ny_df = pd.DataFrame([ny_rad])
    ny_df = update_calculations(ny_df)
    append_row(ny_df.iloc[0].to_dict())

def slumpa_rad(df):
    if df.empty:
        ny_dag = 1
    else:
        ny_dag = int(df["Dag"].max()) + 1

    ny_rad = {
        "Dag": ny_dag,
        "Älskar": 8,
        "Sover med": 1,
        "Vila": 7,
        "Älsk tid": 30
    }

    inmatningsfält = [
        "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Tid singel", "Tid dubbel", "Tid trippel", "DeepT", "Sekunder", "Varv"
    ]

    for fält in inmatningsfält:
        if fält in df.columns:
            min_val = int(df[fält].min())
            max_val = int(df[fält].max())
            ny_rad[fält] = random.randint(min_val, max_val) if max_val > 0 else 0
        else:
            ny_rad[fält] = 0

    ny_df = pd.DataFrame([ny_rad])
    ny_df = update_calculations(ny_df)
    append_row(ny_df.iloc[0].to_dict())

def vilodag_hemma(df):
    ny_rad = {
        "Dag": int(df["Dag"].max() + 1) if not df.empty else 1,
        "Vila": 7,
        "Älskar": 8,
        "Sover med": 1,
        "Älsk tid": 30
    }
    ny_df = pd.DataFrame([ny_rad])
    ny_df = update_calculations(ny_df)
    append_row(ny_df.iloc[0].to_dict())

def vilodag_jobb(df):
    ny_rad = {
        "Dag": int(df["Dag"].max() + 1) if not df.empty else 1,
        "Vila": 7,
        "Älskar": 8,
        "Sover med": 1,
        "Älsk tid": 30
    }
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        max_val = int(df[fält].max()) if fält in df.columns else 0
        ny_rad[fält] = int(max_val * 0.3)
    ny_df = pd.DataFrame([ny_rad])
    ny_df = update_calculations(ny_df)
    append_row(ny_df.iloc[0].to_dict())

def main():
    st.set_page_config(page_title="MalinData", layout="wide")
    st.title("📊 MalinData-app")

    worksheet, df = load_data()
    df = update_calculations(df)

    st.markdown("## ➕ Ny inmatning")
    inmatning(df, worksheet)

    st.markdown("---")
    st.markdown("## ✏️ Redigera rader")
    redigera_rader(df, worksheet)

    st.markdown("---")
    st.markdown("## ⚙️ Snabbkommandon")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏠 Vilodag hemma"):
            vilodag_hemma(df)
            st.experimental_rerun()
    with col2:
        if st.button("💼 Vilodag jobb"):
            vilodag_jobb(df)
            st.experimental_rerun()
    with col3:
        if st.button("🎲 Slumpa rad"):
            slumpa_rad(df)
            st.experimental_rerun()
    with col4:
        if st.button("📋 Kopiera största raden"):
            kopiera_storsta(df)
            st.experimental_rerun()

if __name__ == "__main__":
    main()
