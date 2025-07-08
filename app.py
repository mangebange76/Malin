import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Laddar data från Google Sheets
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

    return worksheet, df

def update_calculations(df):
    df = df.copy()

    df["Jobb 2"] = df["Jobb"].max()
    df["Grannar 2"] = df["Grannar"].max()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].max()
    df["Nils fam 2"] = df["Nils fam"].max()

    df["Känner 2"] = df["Jobb 2"] + df["Grannar 2"] + df["Tjej PojkV 2"] + df["Nils fam 2"]
    df["Totalt män"] = df["Nya män"] + df["Känner 2"]

    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"]) + 9) * (df["dubbelmacka"] + df["dubbel fitta"] + df["dubbel röv"])
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"]) + 15) * (df["trippel fitta"] + df["trippel röv"] + df["trippel penet"])

    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"]
    df["Grabbar"] = df["Nya män"] + df["Känner 2"]
    df["Snitt"] = df["deept"] / df["Grabbar"]
    df["Total tid"] = df["Snitt"] * (df["sekunder_per_varv"] * df["antal_varv"])
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

    df["Klockan"] = pd.to_datetime("07:00") + pd.to_timedelta(df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Total tid"], unit="m")
    df["Klockan"] = df["Klockan"].dt.strftime("%H:%M")

    return df

def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index+2, 1, index+2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

def append_row(data):
    worksheet, _ = load_data()
    worksheet.append_row(list(data.values()))

def inmatning(df, worksheet):
    st.subheader("➕ Lägg till ny rad")
    with st.form("ny_rad_form"):
        inputs = {}

        inmatningsfält = [
            "Nya män", "fitta", "rumpa", "dubbelmacka", "dubbel fitta", "dubbel röv",
            "trippel fitta", "trippel röv", "trippel penet",
            "Älskar", "Älsk tid", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Tid singel", "Tid dubbel", "Tid trippel",
            "Vila", "deept", "sekunder_per_varv", "antal_varv"
        ]

        for col in inmatningsfält:
            inputs[col] = st.number_input(col, min_value=0, step=1)

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            ny_rad = {col: inputs.get(col, 0) for col in df.columns}
            for key in inputs:
                ny_rad[key] = inputs[key]
            ny_rad["Dag"] = df["Dag"].max() + 1 if not df.empty else 1

            ny_df = pd.DataFrame([ny_rad])
            ny_df = update_calculations(ny_df)
            worksheet.append_row(list(ny_df.iloc[0]))
            st.success("Raden har sparats!")

def main():
    st.title("MalinData App – Inmatning och beräkning")
    worksheet, df = load_data()

    if df.empty:
        st.warning("Databasen är tom.")
        return

    df = update_calculations(df)
    inmatning(df, worksheet)

if __name__ == "__main__":
    main()
