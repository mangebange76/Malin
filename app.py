import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets ---
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
    df = pd.DataFrame(records)

    return worksheet, df

def ensure_columns_exist(df, worksheet):
    expected = [
        "Dag", "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
        "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Tid singel", "Tid dubbel", "Tid trippel",
        "Vila", "DeepT", "Sekunder", "Varv"
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = 0
    return df

# --- Uppdatera en rad i Google Sheet ---
def update_row(worksheet, index, row_dict):
    cell_list = worksheet.range(index+2, 1, index+2, len(row_dict))
    for i, key in enumerate(row_dict):
        cell_list[i].value = row_dict[key]
    worksheet.update_cells(cell_list)

# --- Lägg till rad ---
def append_row(data):
    worksheet, _ = load_data()
    worksheet.append_row(list(data.values()))

# --- Beräkningar ---
def update_calculations(df):
    df = df.copy()

    # Känner 2
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

    # Grabbar, snitt, total tid
    df["Grabbar"] = df["Nya män"] + df["Känner 2"]
    df["Snitt"] = df["DeepT"] / df["Grabbar"]
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"]

    # Suger
    df["Suger"] = (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) * 0.6 / df["Totalt män"]

    # Tid kille
    df["Tid kille"] = df["Tid singel"] + df["Tid dubbel"] * 2 + df["Tid trippel"] * 3 + df["Suger"] + df["Tid kille DT"]

    # Klockan
    def calc_klockan(row):
        try:
            total_min = row["Summa tid"] + row["Total tid"]
            tid = pd.to_datetime("07:00", format="%H:%M") + pd.to_timedelta(total_min, unit="m")
            return tid.strftime("%H:%M")
        except:
            return ""
    df["Klockan"] = df.apply(calc_klockan, axis=1)

    return df

# --- Inmatningsformulär för ny rad ---
def inmatning(df, worksheet):
    with st.form("form_lagg_till"):
        st.subheader("➕ Lägg till ny rad")

        ny_rad = {}
        ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1

        fält_ordning = [
            "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
            "Trippel fitta", "Trippel röv", "Trippel penet",
            "Älskar", "Älsk tid", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Tid singel", "Tid dubbel", "Tid trippel",
            "Vila", "DeepT", "Sekunder", "Varv"
        ]

        for fält in fält_ordning:
            if fält in ["Tid singel", "Tid dubbel", "Tid trippel"]:
                ny_rad[fält] = st.number_input(f"{fält}", value=0.0, step=0.1)
            else:
                ny_rad[fält] = st.number_input(f"{fält}", value=0, step=1)

        if st.form_submit_button("💾 Spara rad"):
            ny_df = pd.DataFrame([ny_rad])
            ny_df = update_calculations(ny_df)
            df = pd.concat([df, ny_df], ignore_index=True)
            append_row(ny_df.iloc[0].to_dict())
            st.success("Raden har sparats.")
            st.experimental_rerun()

# --- Redigera existerande rader ---
def radvy(df, worksheet):
    st.subheader("📝 Redigera rader")
    for index, rad in df.iterrows():
        with st.expander(f"Dag {int(rad['Dag'])}"):
            with st.form(f"edit_form_{index}"):
                inputs = {}
                redigerbara_fält = [
                    "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
                    "Trippel fitta", "Trippel röv", "Trippel penet",
                    "Älskar", "Älsk tid", "Sover med",
                    "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
                    "Tid singel", "Tid dubbel", "Tid trippel",
                    "Vila", "DeepT", "Sekunder", "Varv"
                ]
                for fält in redigerbara_fält:
                    default_val = rad[fält]
                    if isinstance(default_val, float):
                        inputs[fält] = st.number_input(f"{fält}", value=float(default_val), step=0.1, key=f"{fält}_{index}")
                    else:
                        inputs[fält] = st.number_input(f"{fält}", value=int(default_val), step=1, key=f"{fält}_{index}")

                if st.form_submit_button("🔄 Uppdatera rad"):
                    for fält, val in inputs.items():
                        df.at[index, fält] = val
                    df = update_calculations(df)
                    update_row(worksheet, index, df.iloc[index].to_dict())
                    st.success("Raden har uppdaterats.")
                    st.experimental_rerun()

# --- Append-rad med formatering ---
def append_row(data_dict):
    worksheet, _ = load_data()
    values = [data_dict.get(col, 0) for col in data_dict.keys()]
    worksheet.append_row(values)

# --- Vilodag hemma ---
def vilodag_hemma(df):
    ny_rad = {fält: 0 for fält in df.columns}
    ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    append_row(ny_rad)

# --- Vilodag jobb ---
def vilodag_jobb(df):
    ny_rad = {fält: 0 for fält in df.columns}
    ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        ny_rad[fält] = int(df[fält].max() * 0.3)
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    append_row(ny_rad)

# --- Slumpa rad ---
def slumpa_rad(df):
    ny_rad = {fält: 0 for fält in df.columns}
    ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1

    for fält in df.columns:
        if fält in ["Dag", "Älskar", "Sover med", "Vila", "Älsk tid"]:
            continue
        if df[fält].dtype in [np.int64, np.float64]:
            min_val = int(df[fält].min())
            max_val = int(df[fält].max())
            ny_rad[fält] = random.randint(min_val, max_val) if max_val > 0 else 0

    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30

    df = df.append(ny_rad, ignore_index=True)
    df = update_calculations(df)
    append_row(df.iloc[-1].to_dict())

# --- Kopiera största raden ---
def kopiera_storsta(df):
    if df.empty:
        return
    idx = df["Totalt män"].idxmax()
    ny_rad = df.loc[idx].copy()
    ny_rad["Dag"] = int(df["Dag"].max() + 1)
    append_row(ny_rad.to_dict())

def main():
    st.title("📘 MalinData App")

    worksheet, df = load_data()
    df = ensure_columns_exist(df, worksheet)
    df = update_calculations(df)

    # Formulär: Lägg till ny rad
    with st.form("ny_rad_form"):
        st.subheader("➕ Lägg till ny dag")
        ny_rad = {}
        inmatningsfält = [
            "Nya män", "Fitta", "Rumpa", "Dubbelmacka", "Dubbel fitta", "Dubbel röv",
            "Trippel fitta", "Trippel röv", "Trippel penet", "Älskar", "Älsk tid",
            "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Tid singel", "Tid dubbel", "Tid trippel", "Vila", "DeepT", "Sekunder", "Varv"
        ]
        for fält in inmatningsfält:
            if fält in ["Tid singel", "Tid dubbel", "Tid trippel"]:
                ny_rad[fält] = st.number_input(fält, value=0.0, step=0.1)
            else:
                ny_rad[fält] = st.number_input(fält, value=0, step=1)

        submitted = st.form_submit_button("💾 Spara rad")
        if submitted:
            ny_rad["Dag"] = int(df["Dag"].max() + 1) if not df.empty else 1
            ny_df = pd.DataFrame([ny_rad])
            ny_df = update_calculations(ny_df)
            append_row(ny_df.iloc[0].to_dict())
            st.success("✅ Raden har sparats.")
            st.experimental_rerun()

    # Knappar
    st.subheader("⚡ Snabbkommandon")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🏠 Vilodag hemma"):
            vilodag_hemma(df)
            st.experimental_rerun()
    with c2:
        if st.button("💼 Vilodag jobb"):
            vilodag_jobb(df)
            st.experimental_rerun()
    with c3:
        if st.button("🎲 Slumpa rad"):
            slumpa_rad(df)
            st.experimental_rerun()
    with c4:
        if st.button("📋 Kopiera största raden"):
            kopiera_storsta(df)
            st.experimental_rerun()


if __name__ == "__main__":
    main()
