import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import random

# Autentisering via secrets.toml
SHEET_URL = st.secrets["SHEET_URL"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

# Kolumndefinitioner
ALL_COLUMNS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar",
    "Älskar", "Sover med", "Vila", "Älsk tid", "DeepT", "Sekunder", "Vila mun", "Varv",
    "DM", "DF", "DA", "TPP", "TAP", "TP", "Fitta", "Röv", "Svarta",
    "Tid singel", "Tid dubbel", "Tid trippel", "Tid mun", "Tid kille dt",
    "Summa singel", "Summa dubbel", "Summa trippel", "Suger",
    "Tid kille", "Summa tid", "Intäkter", "Malin lön", "Kompisar lön",
    "Filmer", "Hårdhet", "Oms 2027", "Aktuell kurs", "Kompis aktievärde"
]

# Funktion: läs in data
def read_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df = ensure_columns_exist(df)
    return df

# Funktion: se till att alla kolumner finns
def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df

# Funktion: spara DataFrame till Google Sheets
def save_data(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

# Funktion: hämta maxvärden från rad med Dag = 0
def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    return {
        "Jobb": int(maxrad["Jobb"].values[0]),
        "Grannar": int(maxrad["Grannar"].values[0]),
        "Tjej PojkV": int(maxrad["Tjej PojkV"].values[0]),
        "Nils fam": int(maxrad["Nils fam"].values[0])
    }

# Funktion: validera mot maxvärden (gäller ej Dag = 0)
def validera_maxvarden(rad, maxvarden):
    if rad["Dag"] == 0:
        return True
    if int(rad["Jobb"]) > maxvarden["Jobb"]:
        return False
    if int(rad["Grannar"]) > maxvarden["Grannar"]:
        return False
    if int(rad["Tjej PojkV"]) > maxvarden["Tjej PojkV"]:
        return False
    if int(rad["Nils fam"]) > maxvarden["Nils fam"]:
        return False
    return True

# Funktion: skapa tom rad med alla fält
def skapa_tom_rad():
    return {col: 0 for col in ALL_COLUMNS}

# Funktion: skapa ny rad från formulär
def skapa_rad_från_formulär(maxvarden):
    st.subheader("Ny rad (manuell)")
    ny_rad = {}
    for col in ALL_COLUMNS:
        if col == "Dag":
            ny_rad[col] = st.number_input(col, step=1, value=1)
        elif col in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila", "Älsk tid",
                     "DeepT", "Sekunder", "Vila mun", "Varv", "DM", "DF", "DA", "TPP", "TAP", "TP", "Fitta", "Röv", "Svarta",
                     "Tid singel", "Tid dubbel", "Tid trippel", "Oms 2027"]:
            ny_rad[col] = st.number_input(col, step=1, value=0)
        else:
            ny_rad[col] = 0
    return ny_rad

def update_calculations(df):
    # Maxrad (Dag = 0) används för vänner
    maxrad = df[df["Dag"] == 0]
    vänner = 0
    if not maxrad.empty:
        vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()

    df["Män"] = df["Nya killar"] + vänner

    df["Snitt"] = df.apply(lambda row: row["DeepT"] / row["Män"] if row["Män"] > 0 else 0, axis=1)
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]
    df["Tid kille dt"] = df.apply(lambda row: row["Tid mun"] / row["Män"] if row["Män"] > 0 else 0, axis=1)

    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"]))
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"]))

    df["Suger"] = df.apply(lambda row: (
        0.6 * (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"]) / row["Män"]
        if row["Män"] > 0 else 0), axis=1)

    df["Tid kille"] = df["Tid singel"] + df["Tid dubbel"] * 2 + df["Tid trippel"] * 3 + df["Suger"] + df["Tid mun"] + df["Tid kille dt"]

    df["Tidsåtgång"] = (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Tid mun"] +
                        df["Älskar"] * 1800 + df["Sover med"] * 1800)
    df["Tidsåtgång"] = df["Tidsåtgång"] / 3600  # till timmar
    df["Tid kille"] = df["Tid kille"] / 60  # till minuter

    df["Filmer"] = (
        df["Män"] + df["Fitta"] + df["Röv"] +
        df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3 +
        df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5
    )

    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int) +
        (df["DM"] > 0).astype(int) * 2 +
        (df["DF"] > 0).astype(int) * 3 +
        (df["DA"] > 0).astype(int) * 4 +
        (df["TPP"] > 0).astype(int) * 5 +
        (df["TAP"] > 0).astype(int) * 7 +
        (df["TP"] > 0).astype(int) * 6
    )

    df["Intäkter"] = df["Filmer"] * df["Hårdhet"] * 39.99
    df["Malin lön"] = df["Intäkter"].apply(lambda x: min(x * 0.01, 700))

    df["Kompisars lön"] = df.apply(lambda row: (
        row["Intäkter"] / vänner if vänner > 0 else 0), axis=1)

    return df

def spara_rad(ny_rad, df, worksheet):
    df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
    df = update_calculations(df)

    # Spara tillbaka hela df till Google Sheet
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    # Varningar efter sparad rad
    sista = df.iloc[-1]
    if sista["Tidsåtgång"] > 17:
        st.warning("⚠️ Tidsåtgång överstiger 17 timmar.")
    if sista["Tid kille"] < 9:
        st.warning("⚠️ Tid kille är under 9 minuter.")
    elif sista["Tid kille"] > 15:
        st.warning("⚠️ Tid kille är över 15 minuter.")

    return df

def redigera_och_spara(index, redigerade_data, df, worksheet):
    for nyckel, värde in redigerade_data.items():
        df.at[index, nyckel] = värde
    df = update_calculations(df)
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

def statistikvy(df):
    df = update_calculations(df)

    # Statistik endast på rader där Dag ≠ 0
    df_stats = df[df["Dag"] != 0].copy()

    st.header("📊 Statistik")

    sum_malin_lön = df_stats["Malin lön"].sum()
    antal_män = df_stats["Män"].sum()
    antal_filmer = df_stats["Filmer"].sum()
    älskar = df_stats["Älskar"].sum()
    sover_med = df_stats["Sover med"].sum()
    nya_killar = df_stats["Nya killar"].sum()
    känner = df_stats["Jobb"].sum() + df_stats["Grannar"].sum() + df_stats["Tjej PojkV"].sum() + df_stats["Nils fam"].sum()

    total_tid = df_stats["Tidsåtgång"].sum()
    total_intakt = df_stats["Intäkter"].sum()
    kompis_lön_sum = df_stats["Kompisars lön"].sum()

    st.markdown(f"**Totala män:** {antal_män}")
    st.markdown(f"**Totalt antal filmer:** {antal_filmer}")
    st.markdown(f"**Summa Malin lön:** {sum_malin_lön:,.2f} USD")
    st.markdown(f"**Summa kompisars lön:** {kompis_lön_sum:,.2f} USD")
    st.markdown(f"**Totala intäkter:** {total_intakt:,.2f} USD")
    st.markdown(f"**Total tidsåtgång:** {total_tid:.2f} timmar")

    total_personer = älskar + sover_med + nya_killar + känner
    roi = sum_malin_lön / total_personer if total_personer > 0 else 0
    st.markdown(f"**Malin ROI per man:** {roi:.2f} USD")

    # Kompisars aktievärde
    sista_kurs = df_stats["Intäkter"].iloc[-1] / df_stats["Filmer"].iloc[-1] if df_stats["Filmer"].iloc[-1] > 0 else 0
    kompis_varde_total = 5000 * sista_kurs
    per_person = kompis_varde_total / känner if känner > 0 else 0

    st.markdown(f"**Kompisars aktievärde totalt:** {kompis_varde_total:,.2f} USD")
    st.markdown(f"**Kompisars aktievärde per person:** {per_person:,.2f} USD")

def visa_formulär(titel, förifylld_rad, df, worksheet):
    st.subheader(titel)
    med_form = st.form(key=titel)
    ny_rad = {}

    for kolumn in ALL_COLUMNS:
        if kolumn == "Dag":
            ny_rad[kolumn] = med_form.number_input(kolumn, value=int(förifylld_rad.get(kolumn, 1)))
        elif kolumn in NUMERIC_COLUMNS:
            ny_rad[kolumn] = med_form.number_input(kolumn, value=float(förifylld_rad.get(kolumn, 0)))
        else:
            ny_rad[kolumn] = med_form.text_input(kolumn, value=förifylld_rad.get(kolumn, ""))

    submit = med_form.form_submit_button("Spara redigerad rad")
    if submit:
        df = spara_rad(ny_rad, df, worksheet)
        st.success("Rad sparad.")
    return df

def slumpa_värde(minv, maxv):
    return random.randint(minv, maxv) if maxv > minv else maxv

def slumpa_rad(df, liten=False):
    maxrad = df[df["Dag"] == 0].copy()
    ny = {"Dag": df["Dag"].max() + 1}

    for kolumn in ALL_COLUMNS:
        if kolumn == "Dag":
            continue
        elif kolumn == "Älskar":
            ny[kolumn] = 8
        elif kolumn == "Sover med":
            ny[kolumn] = 1
        elif kolumn == "Vila":
            ny[kolumn] = 7
        elif kolumn == "Älsk tid":
            ny[kolumn] = 30
        elif kolumn in maxrad.columns:
            maxv = maxrad[kolumn].max()
            if liten:
                ny[kolumn] = slumpa_värde(0, max(1, maxv // 3))
            else:
                ny[kolumn] = slumpa_värde(0, maxv)
        else:
            ny[kolumn] = 0
    return ny

def kopiera_största_rad(df):
    största = df[df["Dag"] != 0].sort_values("Män", ascending=False).iloc[0]
    ny = största.to_dict()
    ny["Dag"] = df["Dag"].max() + 1
    return ny

def vilodag_typ(df, hemma=True):
    maxrad = df[df["Dag"] == 0].copy()
    ny = {"Dag": df["Dag"].max() + 1}
    grupper = ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]

    for kolumn in ALL_COLUMNS:
        if kolumn == "Dag":
            continue
        elif kolumn in grupper:
            maxv = maxrad[kolumn].max()
            ny[kolumn] = int(round(maxv * (0.3 if not hemma else 1.0)))
        else:
            ny[kolumn] = 0
    return ny

def main():
    st.title("Malin App")
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    df = pd.DataFrame(worksheet.get_all_records())
    df = ensure_columns_exist(df, worksheet)
    df = update_calculations(df)

    menyval = st.sidebar.selectbox("Välj vy", [
        "Visa statistik", "Ny rad manuellt", "Slumpa film liten", "Slumpa film stor",
        "Vilodag hemma", "Vilodag jobb", "Kopiera största raden"
    ])

    if menyval == "Visa statistik":
        statistikvy(df)
    else:
        maxrad = df[df["Dag"] == 0]
        if maxrad.empty:
            st.warning("Du måste först fylla i maxvärden (Dag = 0)")
            ny_maxrad = {kol: 0 for kol in ALL_COLUMNS}
            ny_maxrad["Dag"] = 0
            ny_maxrad = visa_formulär("Ange maxvärden (Dag=0)", ny_maxrad, df, worksheet)
        else:
            if menyval == "Ny rad manuellt":
                ny_rad = {kol: 0 for kol in ALL_COLUMNS}
                ny_rad["Dag"] = int(df["Dag"].max() + 1)
            elif menyval == "Slumpa film liten":
                ny_rad = slumpa_rad(df, liten=True)
            elif menyval == "Slumpa film stor":
                ny_rad = slumpa_rad(df, liten=False)
            elif menyval == "Vilodag hemma":
                ny_rad = vilodag_typ(df, hemma=True)
            elif menyval == "Vilodag jobb":
                ny_rad = vilodag_typ(df, hemma=False)
            elif menyval == "Kopiera största raden":
                ny_rad = kopiera_största_rad(df)
            else:
                ny_rad = {kol: 0 for kol in ALL_COLUMNS}

            df = visa_formulär("Redigera ny rad innan spara", ny_rad, df, worksheet)

if __name__ == "__main__":
    main()

def spara_rad(rad, worksheet):
    values = worksheet.get_all_values()
    headers = values[0]
    new_row = [rad.get(col, "") for col in headers]
    worksheet.append_row(new_row)
    st.success("Raden har sparats.")

def ensure_columns_exist(df, worksheet):
    existing_cols = df.columns.tolist()
    for col in ALL_COLUMNS:
        if col not in existing_cols:
            df[col] = 0
    worksheet.update([df.columns.tolist()] + df.values.tolist())
    return df

def update_calculations(df):
    def get_maxrad():
        return df[df["Dag"] == 0]

    def get_vänner():
        maxrad = get_maxrad()
        return maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()

    df = df.copy()
    df["Män"] = df["Nya killar"] + get_vänner()
    df["Snitt"] = df["DeepT"] / df["Män"].replace(0, 1)
    df["Tid mun"] = ((df["Snitt"] * df["Sekunder"]) + df["Vila mun"]) * df["Varv"]

    df["Summa singel"] = (df["Tid singel"] + df["Vila"] * (df["Män"] + df["Fitta"] + df["Röv"]))
    df["Summa dubbel"] = ((df["Tid dubbel"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"]))
    df["Summa trippel"] = ((df["Tid trippel"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"]))

    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Män"].replace(0, 1)
    df["Tid kille dt"] = (df["Snitt"] * df["Sekunder"] * df["Varv"]) / df["Män"].replace(0, 1)

    df["Tid kille"] = (
        df["Tid singel"] +
        (df["Tid dubbel"] * 2) +
        (df["Tid trippel"] * 3) +
        df["Suger"] +
        df["Tid kille dt"] +
        df["Tid mun"]
    )

    df["Summa tid"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Tid mun"] +
        (df["Älskar"] * 1800) +
        (df["Sover med"] * 1800)
    )

    df["Tidsåtgång (h)"] = df["Summa tid"] / 3600
    df["Tid kille (min)"] = df["Tid kille"] / 60

    df["Filmer"] = (
        df["Män"] + df["Fitta"] + df["Röv"] +
        df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3 +
        df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5
    ) * df.apply(lambda r: (
        0 + 1*(r["Nya killar"] > 0) + 2*(r["DM"] > 0) +
        3*(r["DF"] > 0) + 4*(r["DA"] > 0) +
        5*(r["TPP"] > 0) + 7*(r["TAP"] > 0) + 6*(r["TP"] > 0)
    ), axis=1)

    df["Intäkter"] = df["Filmer"] * 39.99
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))

    vänner = get_vänner()
    df["Kompisars lön"] = df["Intäkter"] / vänner if vänner else 0

    sista_kurs = df["Aktuell kurs"].dropna().iloc[-1] if "Aktuell kurs" in df.columns else 0
    df["Kompis aktievärde"] = round((5000 * sista_kurs) / vänner, 2) if vänner else 0

    return df

def statistikvy(df):
    st.header("📊 Statistik")

    summering = {
        "Totala män": df["Män"].sum(),
        "Totalt älskat": df["Älskar"].sum(),
        "Totalt antal filmer": df["Filmer"].sum(),
        "Totala intäkter (USD)": round(df["Intäkter"].sum(), 2),
        "Total Malin-lön (USD)": round(df["Malin lön"].sum(), 2),
        "Total tid (timmar)": round(df["Summa tid"].sum() / 3600, 2)
    }

    st.subheader("Sammanställning")
    for k, v in summering.items():
        st.markdown(f"**{k}**: {v}")

    tot_män = (
        df["Älskar"].sum() + df["Sover med"].sum() +
        df["Nya killar"].sum() + df["Känner"].sum()
    )
    if tot_män > 0:
        roi = df["Malin lön"].sum() / tot_män
        st.subheader("📈 Malin ROI per man")
        st.markdown(f"**{roi:.2f} USD/man**")

    sista_kurs = df["Aktuell kurs"].dropna().iloc[-1] if "Aktuell kurs" in df.columns else 0
    vänner = df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()
    if vänner:
        aktievärde = (5000 * sista_kurs) / vänner
        st.subheader("📈 Kompisars aktievärde per person")
        st.markdown(f"**{aktievärde:.2f} USD/person**")
