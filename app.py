import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import gspread
from google.oauth2 import service_account  # ✅ Viktig import

st.set_page_config(layout="wide")
st.title("MalinApp – Datahantering & Statistik")

ALL_COLUMNS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar",
    "Älskar", "Sover med", "Vila", "DeepT", "Sekunder", "Vila mun", "Varv",
    "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Tid singel", "Tid dubbel", "Tid trippel", "Tid mun",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid",
    "Sug", "Tid kille dt", "Tid kille",
    "Män", "Kompisar", "Filmer", "Intäkter",
    "Malin lön", "Kompisars lön", "ROI", "Kompisvärde",
    "Svarta", "Hårdhet"
]

def las_in_data():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Om tomt, skapa en första rad med Dag=0 och alla kolumner
    if df.empty:
        df = pd.DataFrame(columns=ALL_COLUMNS)
        df.loc[0] = [0] + [0] * (len(ALL_COLUMNS) - 1)

    df = ensure_columns_exist(df, worksheet)
    return df

def las_in_data():
    client = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df, worksheet


def spara_dataframe_till_sheet(df, worksheet):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())


def säkerställ_kolumner(df, worksheet):
    befintliga = list(df.columns)
    for kolumn in ALL_COLUMNS:
        if kolumn not in befintliga:
            df[kolumn] = ""
    df = df[ALL_COLUMNS]
    spara_dataframe_till_sheet(df, worksheet)
    return df


def hamta_maxvarden(df):
    if "Dag" not in df.columns:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    maxrad = maxrad.iloc[0]
    return {
        "Jobb": int(maxrad.get("Jobb", 0)),
        "Grannar": int(maxrad.get("Grannar", 0)),
        "Tjej PojkV": int(maxrad.get("Tjej PojkV", 0)),
        "Nils fam": int(maxrad.get("Nils fam", 0)),
    }


def validera_maxvarden(rad, maxvarden):
    for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if int(rad.get(fält, 0)) > maxvarden.get(fält, 0):
            return False, f"{fält} överskrider maxvärde ({rad.get(fält)} > {maxvarden.get(fält)})"
    return True, ""

def update_calculations(df):
    df = df.copy()
    df.fillna(0, inplace=True)

    df["Män"] = df["Nya killar"] + df["Känner"]
    df["Snitt"] = df["DeepT"] / df["Män"].replace(0, np.nan)
    df["Tid mun"] = ((df["Snitt"] * df["Sekunder"]) + df["Vila mun"]) * df["Varv"]
    df["Summa singel"] = (df["Tid singel"] + df["Vila"]) * (
        df["Män"] + df["Fitta"] + df["Röv"]
    )
    df["Summa dubbel"] = (df["Tid dubbel"] + df["Vila"] + 8) * (
        df["DM"] + df["DF"] + df["DA"]
    )
    df["Summa trippel"] = (df["Tid trippel"] + df["Vila"] + 15) * (
        df["TPP"] + df["TAP"] + df["TP"]
    )

    df["Suger"] = (
        0.6
        * (
            df["Summa singel"]
            + df["Summa dubbel"]
            + df["Summa trippel"]
        )
        / df["Män"].replace(0, np.nan)
    )

    df["Tid kille dt"] = (
        df["Snitt"] * df["Sekunder"] * df["Varv"]
    ) / df["Män"].replace(0, np.nan)

    df["Tid kille"] = (
        df["Tid singel"]
        + (df["Tid dubbel"] * 2)
        + (df["Tid trippel"] * 3)
        + df["Suger"]
        + df["Tid kille dt"]
        + df["Tid mun"]
    ) / 60  # minuter

    df["Summa tid"] = (
        df["Summa singel"]
        + df["Summa dubbel"]
        + df["Summa trippel"]
        + df["Tid mun"]
        + df["Älskar"] * 1800
        + df["Sover med"] * 1800
    ) / 3600  # timmar

    df["Filmer"] = (
        df["Män"]
        + df["Fitta"]
        + df["Röv"]
        + df["DM"] * 2
        + df["DF"] * 2
        + df["DA"] * 3
        + df["TPP"] * 4
        + df["TAP"] * 6
        + df["TP"] * 5
    ) * df["Hårdhet"]

    df["Intäkter"] = df["Filmer"] * 39.99

    df["Malin lön"] = np.minimum(df["Intäkter"] * 0.01, 700)

    df["Kompisars lön"] = df["Intäkter"] / df["Känner"].replace(0, np.nan)

    return df

ALL_COLUMNS = [
    "Dag", "Nya killar", "Känner", "Älskar", "Sover med", "DeepT",
    "Sekunder", "Vila mun", "Varv", "Tid singel", "Fitta", "Röv",
    "Tid dubbel", "DM", "DF", "DA", "Tid trippel", "TPP", "TAP", "TP",
    "Vila", "Hårdhet",
    "Män", "Snitt", "Tid mun", "Summa singel", "Summa dubbel", "Summa trippel",
    "Suger", "Tid kille dt", "Tid kille", "Summa tid", "Filmer", "Intäkter",
    "Malin lön", "Kompisars lön"
]

def ensure_columns_exist(sheet, worksheet_name):
    worksheet = sheet.worksheet(worksheet_name)
    data = worksheet.get_all_records()
    if not data:
        worksheet.insert_row(ALL_COLUMNS, 1)
    else:
        existing_columns = list(data[0].keys())
        missing_columns = [col for col in ALL_COLUMNS if col not in existing_columns]
        if missing_columns:
            new_header = existing_columns + missing_columns
            all_data = worksheet.get_all_values()
            all_data[0] = new_header
            worksheet.update(all_data)

def las_in_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    ensure_columns_exist(sheet, "Blad1")
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def hamta_maxvarden(df):
    df = df.copy()
    if "Dag" not in df.columns or df.empty:
        return pd.Series({"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0})
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return pd.Series({"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0})
    return maxrad.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]]

def statistikvy(df):
    st.header("📊 Statistik")

    if df.empty:
        st.info("Ingen data tillgänglig.")
        return

    # Filtrera bort Dag = 0 (maxvärden)
    df = df[df["Dag"] != 0].copy()

    # Antal filmer
    total_filmer = df["Filmer"].sum()

    # Totala intäkter
    total_intakter = df["Intäkter"].sum()

    # Summa Malin lön
    total_malin_lon = df["Malin lön"].sum()

    # Totalt antal:
    total_alskar = df["Älskar"].sum()
    total_sover = df["Sover med"].sum()
    total_nyakillar = df["Nya killar"].sum()
    total_kanner = df["Känner"].sum()

    # Total kompisar = Känner (som är maxvärdessumma från Dag 0)
    maxrad = df[df["Dag"] == 0]
    if not maxrad.empty:
        maxjobb = maxrad["Jobb"].max()
        maxgrannar = maxrad["Grannar"].max()
        maxtjej = maxrad["Tjej PojkV"].max()
        maxnils = maxrad["Nils fam"].max()
        totalt_kompisar = maxjobb + maxgrannar + maxtjej + maxnils
    else:
        totalt_kompisar = 0

    # Kompisars aktievärde
    sista_kurs = total_intakter / total_filmer if total_filmer > 0 else 0
    total_aktievarde = sista_kurs * 5000
    aktievarde_per_kompis = round(total_aktievarde / totalt_kompisar, 2) if totalt_kompisar else 0

    # Malin ROI per man
    total_man = total_alskar + total_sover + total_nyakillar + total_kanner
    roi_per_man = round(total_malin_lon / total_man, 2) if total_man else 0

    st.metric("🎬 Antal filmer", int(total_filmer))
    st.metric("💰 Totala intäkter (USD)", round(total_intakter, 2))
    st.metric("💼 Malin lön (summa)", round(total_malin_lon, 2))
    st.metric("📈 Malin ROI per man", roi_per_man)
    st.metric("🧍‍♂️ Totalt antal män", int(total_man))
    st.metric("❤️ Totalt Älskar", int(total_alskar))
    st.metric("🛏️ Totalt Sover med", int(total_sover))
    st.metric("👥 Totalt kompisar (från maxrad)", int(totalt_kompisar))
    st.metric("💸 Kompisars aktievärde (total)", round(total_aktievarde, 2))
    st.metric("💵 Kompisars aktievärde per person", aktievarde_per_kompis)

def skapa_tom_rad(maxrad):
    return {col: 0 for col in ALL_COLUMNS if col in maxrad.columns}

def visa_formular(rad_data, maxrad):
    with st.form("ny_rad_formular"):
        ny_rad = {}
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                ny_rad[kolumn] = st.number_input("Dag", min_value=1, step=1, value=int(rad_data.get("Dag", 1)))
            elif kolumn in NUMERIC_FIELDS:
                maxvarde = maxrad.get(kolumn, 99999)
                ny_rad[kolumn] = st.number_input(kolumn, value=int(rad_data.get(kolumn, 0)), min_value=0, max_value=int(maxvarde))
            else:
                ny_rad[kolumn] = st.text_input(kolumn, value=str(rad_data.get(kolumn, "")))
        submitted = st.form_submit_button("Spara ny rad")
        if submitted:
            return ny_rad
    return None

def slumpa_rad(filmstorlek, maxrad):
    import random
    ny_rad = {"Dag": hamta_nasta_dag()}
    for kolumn in NUMERIC_FIELDS:
        if kolumn in ["Älskar"]:
            ny_rad[kolumn] = 8
        elif kolumn == "Sover med":
            ny_rad[kolumn] = 1
        elif kolumn == "Vila":
            ny_rad[kolumn] = 7
        elif kolumn == "Älsk tid":
            ny_rad[kolumn] = 30
        else:
            maxvarde = maxrad.get(kolumn, 10)
            ny_rad[kolumn] = random.randint(1, max(1, int(maxvarde / (2 if filmstorlek == "liten" else 1))))
    return ny_rad

def kopiera_storsta_rad(df):
    if df.empty:
        return None
    df_filtrerat = df[df["Dag"] != 0]
    if df_filtrerat.empty:
        return None
    maxrad = df_filtrerat.loc[df_filtrerat["Totalt män"].idxmax()]
    kopierad = maxrad.to_dict()
    kopierad["Dag"] = hamta_nasta_dag()
    return kopierad

def hamta_nasta_dag():
    df = las_in_data()
    if "Dag" in df.columns and not df.empty:
        return int(df["Dag"].max()) + 1
    return 1

def visa_redigeringsform(namn, data, maxrad):
    st.subheader(namn)
    redigerad_rad = visa_formular(data, maxrad)
    if redigerad_rad:
        df = las_in_data()
        df = df[df["Dag"] != redigerad_rad["Dag"]]
        df = df.append(redigerad_rad, ignore_index=True)
        df = update_calculations(df)
        spara_data(df)
        st.success("Raden har sparats.")
        visa_eventuella_varningar(redigerad_rad)

def visa_eventuella_varningar(rad):
    try:
        summa_tid = rad.get("Summa tid", 0)
        tid_kille = rad.get("Tid kille", 0)
        if summa_tid > 17:
            st.warning(f"⚠️ Summa tid överstiger 17 timmar: {summa_tid:.1f} h")
        if tid_kille < 9 or tid_kille > 15:
            st.warning(f"⚠️ Tid kille utanför normalintervall (9–15 min): {tid_kille:.1f} min")
    except Exception:
        pass

def main():
    st.set_page_config(page_title="Malin Dataapp", layout="wide")
    st.title("📊 Malins film- och tidsdatabas")

    df = las_in_data()
    df = update_calculations(df)
    ensure_columns_exist(df)
    spara_data(df)

    maxrad = hamta_maxvarden(df)

    menyval = st.sidebar.radio("Meny", [
        "📥 Lägg till ny rad manuellt",
        "🎲 Slumpa film liten",
        "🎬 Slumpa film stor",
        "🛌 Vilodag hemma",
        "🏢 Vilodag jobb",
        "📋 Kopiera största raden",
        "📈 Statistik"
    ])

    if menyval == "📥 Lägg till ny rad manuellt":
        st.subheader("Lägg till ny rad manuellt")
        ny_rad = skapa_tom_rad(maxrad)
        redigerad = visa_formular(ny_rad, maxrad)
        if redigerad:
            df = df.append(redigerad, ignore_index=True)
            df = update_calculations(df)
            spara_data(df)
            st.success("Ny rad har sparats.")
            visa_eventuella_varningar(redigerad)

    elif menyval == "🎲 Slumpa film liten":
        rad = slumpa_rad("liten", maxrad)
        visa_redigeringsform("Slumpad film (liten)", rad, maxrad)

    elif menyval == "🎬 Slumpa film stor":
        rad = slumpa_rad("stor", maxrad)
        visa_redigeringsform("Slumpad film (stor)", rad, maxrad)

    elif menyval == "🛌 Vilodag hemma":
        rad = skapa_tom_rad(maxrad)
        rad["Dag"] = hamta_nasta_dag()
        rad["Vila"] = 7
        rad["Vila mun"] = 5
        rad["Älskar"] = 0
        visa_redigeringsform("Vilodag hemma", rad, maxrad)

    elif menyval == "🏢 Vilodag jobb":
        rad = skapa_tom_rad(maxrad)
        rad["Dag"] = hamta_nasta_dag()
        for fält in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            rad[fält] = int(maxrad.get(fält, 0) * 0.3)
        rad["Vila"] = 7
        rad["Vila mun"] = 5
        rad["Älskar"] = 0
        visa_redigeringsform("Vilodag jobb", rad, maxrad)

    elif menyval == "📋 Kopiera största raden":
        rad = kopiera_storsta_rad(df)
        if rad:
            visa_redigeringsform("Kopierad rad", rad, maxrad)
        else:
            st.error("Ingen rad att kopiera.")

    elif menyval == "📈 Statistik":
        statistikvy(df)

if __name__ == "__main__":
    main()
