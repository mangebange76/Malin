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

    df = ensure_columns_exist(df, worksheet)
    return worksheet, df

def ensure_columns_exist(df, worksheet):
    expected_cols = [
        "dag", "nya_man", "fitta", "rumpa", "dubbelmacka", "dubbel_fitta", "dubbel_rov",
        "trippel_fitta", "trippel_rov", "trippel_penet",
        "alskar", "alsk_tid", "sover_med",
        "kompisar_jobb", "kompisar_grannar", "kompisar_partner_vanner", "kompisar_nils_familj",
        "tid_singel", "tid_dubbel", "tid_trippel",
        "vila", "deept", "sekunder_per_varv", "antal_varv"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0
    return df

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
    jobb2 = df["kompisar_jobb"].max()
    grannar2 = df["kompisar_grannar"].max()
    partner2 = df["kompisar_partner_vanner"].max()
    fam2 = df["kompisar_nils_familj"].max()
    känner2 = jobb2 + grannar2 + partner2 + fam2

    df["jobb_2"] = jobb2
    df["grannar_2"] = grannar2
    df["partner_2"] = partner2
    df["fam_2"] = fam2
    df["känner_2"] = känner2

    # Totalt män
    df["totalt_män"] = df["nya_man"] + känner2

    # Summa singel, dubbel, trippel
    df["summa_singel"] = (df["tid_singel"] + df["vila"]) * df["totalt_män"]
    df["summa_dubbel"] = ((df["tid_dubbel"] + df["vila"]) + 9) * (df["dubbelmacka"] + df["dubbel_fitta"] + df["dubbel_rov"])
    df["summa_trippel"] = ((df["tid_trippel"] + df["vila"]) + 15) * (df["trippel_fitta"] + df["trippel_rov"] + df["trippel_penet"])

    # Summa tid
    df["summa_tid"] = df["summa_singel"] + df["summa_dubbel"] + df["summa_trippel"]

    # Grabbar (radnivå)
    df["grabbar"] = df["nya_man"] + känner2

    # Snitt
    df["snitt"] = df["deept"] / df["grabbar"]

    # Total tid
    df["total_tid"] = df["snitt"] * (df["sekunder_per_varv"] * df["antal_varv"])

    # Tid kille DT
    df["tid_kille_dt"] = df["total_tid"] / df["totalt_män"]

    # Runk
    df["runk"] = (df["total_tid"] * 0.6) / df["totalt_män"]

    # Suger (beräknat fält)
    df["suger"] = 0.6 * (df["summa_singel"] + df["summa_dubbel"] + df["summa_trippel"]) / df["totalt_män"]

    # Tid kille
    df["tid_kille"] = df["tid_singel"] + (df["tid_dubbel"] * 2) + (df["tid_trippel"] * 3) + df["suger"] + df["tid_kille_dt"] + df["runk"]

    # Klockan
    def calc_klockan(row):
        total_min = row["summa_tid"] + row["total_tid"]
        tid = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(total_min, unit="m")
        return tid.strftime("%H:%M")
    df["klockan"] = df.apply(calc_klockan, axis=1)

    # Filmer, Pris, Intäkter
    df["filmer"] = df["nya_man"] > 0
    df["pris"] = 39.99
    df["intäkter"] = df["filmer"] * df["pris"]

    # Malin lön – 2% av intäkter, max 1000
    df["malin_lön"] = np.minimum(df["intäkter"] * 0.02, 1000)

    # Företagets lön – alltid max 10000
    df["företagets_lön"] = 10000

    # Vänner lön
    df["vänner_lön"] = (df["intäkter"].sum() - df["malin_lön"].sum() - df["företagets_lön"].sum()) / känner2 if känner2 > 0 else 0

    return df

def inmatning(df, worksheet):
    with st.expander("➕ Lägg till ny dag"):
        with st.form("ny_rad_form"):

            kolumner = [
                "nya_man", "fitta", "rumpa",
                "dubbelmacka", "dubbel_fitta", "dubbel_rov",
                "trippel_fitta", "trippel_rov", "trippel_penet",
                "alskar", "alsk_tid", "sover_med",
                "kompisar_jobb", "kompisar_grannar", "kompisar_partner_vanner", "kompisar_nils_familj",
                "tid_singel", "tid_dubbel", "tid_trippel",
                "vila", "deept", "sekunder_per_varv", "antal_varv"
            ]

            inputs = {}
            for col in kolumner:
                inputs[col] = st.number_input(col.replace("_", " ").capitalize(), value=0, step=1)

            submitted = st.form_submit_button("Lägg till rad")
            if submitted:
                ny_rad = inputs.copy()
                ny_rad["dag"] = int(df["dag"].max() + 1) if not df.empty else 1
                ny_rad_df = pd.DataFrame([ny_rad])
                ny_rad_df = update_calculations(ny_rad_df)
                worksheet.append_row(ny_rad_df.iloc[0].to_dict().values())
                st.success("Raden har lagts till!")


def radvy(df, worksheet):
    st.header("📝 Redigera dagar")
    for index, rad in df.iterrows():
        with st.expander(f"Dag {int(rad['dag'])}"):
            with st.form(f"form_{index}"):
                inputs = {}
                for col in [
                    "tid_singel", "tid_dubbel", "tid_trippel",
                    "deept", "sekunder_per_varv", "antal_varv",
                    "dag", "alskar", "alsk_tid", "sover_med"
                ]:
                    if col in df.columns:
                        val = rad[col]
                        inputs[col] = st.number_input(
                            f"{col.replace('_', ' ').capitalize()} (dag {int(rad['dag'])})",
                            value=float(val) if isinstance(val, (int, float)) else 0,
                            step=1.0
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

    känner2 = df[["jobb_2", "grannar_2", "partner_2", "fam_2"]].iloc[0].sum()
    totalt_män = df["nya_man"].sum() + känner2
    antal_filmer = df[df["nya_man"] > 0].shape[0]
    privat_gb = df[(df["nya_man"] == 0) & (df["totalt_män"] > 0)].shape[0]

    snitt_film = (df["nya_man"].sum() + känner2) / antal_filmer if antal_filmer > 0 else 0
    älskat = df["alskar"].sum() / känner2 if känner2 > 0 else 0

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (kompisar):** {känner2}")
    st.write(f"**Jobb:** {df['kompisar_jobb'].max()}")
    st.write(f"**Grannar:** {df['kompisar_grannar'].max()}")
    st.write(f"**Tjej PojkV:** {df['kompisar_partner_vanner'].max()}")
    st.write(f"**Nils fam:** {df['kompisar_nils_familj'].max()}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med:** {df['sover_med'].sum()}")
    st.write(f"**Antal filmer:** {antal_filmer}")
    st.write(f"**Privat GB:** {privat_gb}")
    st.write(f"**Intäkter:** {df['intäkter'].sum():.2f} USD")
    st.write(f"**Malin lön:** {df['malin_lön'].sum():.2f} USD")
    st.write(f"**Företagets lön:** {df['företagets_lön'].sum():.2f} USD")
    vänner_lön = (df["intäkter"].sum() - df["malin_lön"].sum() - df["företagets_lön"].sum()) / känner2 if känner2 > 0 else 0
    st.write(f"**Vänner lön (per kompis):** {vänner_lön:.2f} USD")
    st.write(f"**Antal dagar:** {len(df)}")

def slumpa_rad(df):
    if df.empty:
        ny_dag = 1
    else:
        ny_dag = df["dag"].max() + 1

    ny_rad = {col: 0 for col in df.columns}
    ny_rad["dag"] = ny_dag

    for col in df.columns:
        if col in ["dag", "alskar", "sover_med", "vila", "alsk_tid"]:
            continue
        if df[col].dtype in [np.int64, np.float64] and not df[col].isnull().all():
            max_val = int(df[col].max())
            min_val = int(df[col].min())
            ny_rad[col] = random.randint(min_val, max_val) if max_val > 0 else 0

    ny_rad["alskar"] = 8
    ny_rad["sover_med"] = 1
    ny_rad["vila"] = 7
    ny_rad["alsk_tid"] = 30

    ny_rad_df = pd.DataFrame([ny_rad])
    ny_rad_df = update_calculations(ny_rad_df)
    append_row(ny_rad_df.iloc[0].to_dict())


def vilodag_hemma(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["dag"] = df["dag"].max() + 1 if not df.empty else 1
    ny_rad["vila"] = 7
    ny_rad["alsk_tid"] = 30
    ny_rad["alskar"] = 8
    ny_rad["sover_med"] = 1
    append_row(ny_rad)


def vilodag_jobb(df):
    ny_rad = {col: 0 for col in df.columns}
    ny_rad["dag"] = df["dag"].max() + 1 if not df.empty else 1
    for fält in ["kompisar_jobb", "kompisar_grannar", "kompisar_partner_vanner", "kompisar_nils_familj"]:
        max_val = df[fält].max()
        ny_rad[fält] = int(max_val * 0.3)
    ny_rad["vila"] = 7
    ny_rad["alsk_tid"] = 30
    ny_rad["alskar"] = 8
    ny_rad["sover_med"] = 1
    append_row(ny_rad)


def kopiera_storsta(df):
    if df.empty:
        return
    idx = df["totalt_män"].idxmax()
    ny_rad = df.loc[idx].copy()
    ny_rad["dag"] = df["dag"].max() + 1
    append_row(ny_rad.to_dict())

def main():
    st.title("📘 MalinData App")

    worksheet, df = load_data()
    df = ensure_columns_exist(df, worksheet)
    df = update_calculations(df)

    # Snabbvalsknappar
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

    # Lägg till ny rad manuellt
    inmatning(df, worksheet)

    # Huvudpresentation
    presentation(df)

    # Detaljvyn (redigera rader)
    with st.expander("📋 Redigera rader"):
        radvy(df, worksheet)


if __name__ == "__main__":
    main()
