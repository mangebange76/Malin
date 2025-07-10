import streamlit as st
import pandas as pd
import random
from datetime import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import toml

# Läs in Google Sheets credentials och anslut
secrets = toml.load(".streamlit/secrets.toml")
SHEET_URL = secrets["SHEET_URL"]
credentials_dict = secrets["GOOGLE_CREDENTIALS"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP", "Älskar",
    "Sover med", "Tid S", "Tid D", "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv", "Känner", "Män", "Summa singel", "Summa dubbel",
    "Summa trippel", "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet", "Filmer",
    "Pris", "Intäkter", "Malin lön", "Kompisar", "Aktiekurs", "Kompisar aktievärde"
]

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[ALL_COLUMNS]

def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True).fillna(0)
    if df.empty:
        df = pd.DataFrame(columns=ALL_COLUMNS)
    df = ensure_columns_exist(df)
    df = df.fillna(0)
    return df

def save_data(df):
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def get_next_day(df):
    if df.empty:
        return 1
    return int(df["Dag"].max()) + 1

def veckodag_from_dag(dag):
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    return veckodagar[(dag - 1) % 7]

def hämta_maxvärden(df):
    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils familj": 0}
    return dag0.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].to_dict()

def visa_redigeringsformulär(rad, dag):
    with st.form(f"redigera_rad_{dag}"):
        ny_rad = rad.copy()
        for kolumn in ALL_COLUMNS:
            try:
                värde = ny_rad.get(kolumn, 0)
                if kolumn == "Dag":
                    st.number_input(kolumn, value=int(värde), disabled=True, key=f"{kolumn}_{dag}")
                elif isinstance(värde, float):
                    ny_rad[kolumn] = st.number_input(kolumn, value=float(värde), step=1.0, key=f"{kolumn}_{dag}")
                elif isinstance(värde, int):
                    ny_rad[kolumn] = st.number_input(kolumn, value=int(värde), step=1, key=f"{kolumn}_{dag}")
                else:
                    ny_rad[kolumn] = st.text_input(kolumn, value=str(värde), key=f"{kolumn}_{dag}")
            except Exception as e:
                st.error(f"Fel i kolumn '{kolumn}': {e}")
        if st.form_submit_button("Spara redigerad rad"):
            return ny_rad
    return None

def lägg_till_rad(df, ny_rad):
    ny_rad = pd.DataFrame([ny_rad])
    df = pd.concat([df, ny_rad], ignore_index=True)
    df = ensure_columns_exist(df)
    df = update_calculations(df)
    save_data(df)
    return df

def visa_varningar(rad):
    summa_tid = rad.get("Summa tid", 0)
    tid_kille = rad.get("Tid kille", 0)
    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.2f} timmar – det kan vara för mycket.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid per kille är {tid_kille:.2f} minuter – utanför rekommenderat intervall (9–15 min).")

def ny_rad_manuellt(df):
    st.subheader("➕ Lägg till ny rad manuellt")

    dag = get_next_day(df)
    ny_rad = {kolumn: 0 for kolumn in ALL_COLUMNS}
    ny_rad["Dag"] = dag
    ny_rad["Veckodag"] = veckodag_from_dag(dag)

    if rad := visa_redigeringsformulär(ny_rad, dag):
        df = lägg_till_rad(df, rad)
        visa_varningar(rad)
        st.success("Ny rad tillagd.")
    return df

def update_calculations(df):
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum(axis=1)
    df["Män"] = df["Nya killar"] + df["Känner"]

    df["Summa singel"] = (df["Tid S"] + df["Vila"]) * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = (df["Tid D"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = (df["Tid T"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Snitt"] = df.apply(
        lambda row: row["DeepT"] / row["Män"] if row["Män"] > 0 else 0,
        axis=1
    )
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]

    # Summa tid – 3h för rader där bara Känner > 0
    df["Summa tid"] = (
        df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]
        + df["Tid mun"] + (df["Älskar"] * 1800) + (df["Sover med"] * 1800)
    ) / 3600

    df.loc[
        (df["Nya killar"] == 0) &
        (df["Älskar"] == 0) &
        (df["Sover med"] == 0) &
        (df["Fitta"] == 0) &
        (df["Röv"] == 0) &
        (df["DM"] == 0) &
        (df["DF"] == 0) &
        (df["DA"] == 0) &
        (df["TPP"] == 0) &
        (df["TAP"] == 0) &
        (df["TP"] == 0) &
        (df["Känner"] > 0),
        "Summa tid"
    ] = 3

    df["Suger"] = df.apply(
        lambda row: (row["Summa singel"] + row["Summa dubbel"] + row["Summa trippel"]) * 0.6 / row["Män"]
        if row["Män"] > 0 else 0,
        axis=1
    )

    df["Tid kille"] = (
        df["Tid S"] +
        df["Tid D"] * 2 +
        df["Tid T"] * 3 +
        df["Suger"] +
        df["Tid mun"] +
        (df["Sover med"] * 1800 / df["Män"]).fillna(0) +
        (df["Älskar"] * 1800 / df["Män"]).fillna(0)
    ) / 60

    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int)
        + (df["DM"] > 0).astype(int) * 2
        + (df["DF"] > 0).astype(int) * 3
        + (df["DA"] > 0).astype(int) * 4
        + (df["TPP"] > 0).astype(int) * 5
        + (df["TAP"] > 0).astype(int) * 7
        + (df["TP"] > 0).astype(int) * 6
    )

    df["Filmer"] = (
        df["Män"] + df["Fitta"] + df["Röv"]
        + df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3
        + df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5
    ) * df["Hårdhet"]

    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = df["Intäkter"] * 0.01
    df.loc[df["Malin lön"] > 700, "Malin lön"] = 700

    maxrad = df[df["Dag"] == 0]
    if not maxrad.empty:
        kompisar = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
        df["Kompisar"] = (df["Intäkter"] - df["Malin lön"]) / kompisar if kompisar > 0 else 0
    else:
        df["Kompisar"] = 0

    df["Aktiekurs"] = df["Aktiekurs"].replace(0, method="ffill")
    df["Kompisar aktievärde"] = df["Aktiekurs"].fillna(0) * 5000

    return df

def statistikvy(df):
    st.subheader("📊 Statistik – summeringar och nyckeltal")

    if df.empty or df[df["Dag"] != 0].empty:
        st.info("Ingen data att visa.")
        return

    df = df[df["Dag"] != 0]  # Exkludera maxrad

    totalt_intakt = df["Intäkter"].sum()
    totalt_lön = df["Malin lön"].sum()
    totalt_kompisar = df["Kompisar"].sum()
    totalt_män = df["Män"].sum()
    totalt_filmer = df["Filmer"].sum()
    totalt_tid = df["Summa tid"].sum()
    snitt_tid = df["Tid kille"].mean()
    totalt_alskar = df["Älskar"].sum()
    totalt_sovermed = df["Sover med"].sum()
    totalt_killar = df["Nya killar"].sum()
    totalt_känner = df["Känner"].sum()

    # ROI
    roi_per_man = totalt_lön / (totalt_alskar + totalt_sovermed + totalt_killar + totalt_känner) if (totalt_alskar + totalt_sovermed + totalt_killar + totalt_känner) > 0 else 0

    # Aktiekurs och kompisars aktievärde
    aktiekurs = df["Aktiekurs"].replace(0, method="ffill").iloc[-1]
    dag0 = df[df["Dag"] == 0]
    kompisar_total = dag0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    aktievärde = aktiekurs * 5000
    aktievärde_per_kompis = aktievärde / kompisar_total if kompisar_total > 0 else 0

    # Presentation
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👥 Totalt män", int(totalt_män))
        st.metric("💞 Älskar", int(totalt_alskar))
        st.metric("🛌 Sover med", int(totalt_sovermed))
        st.metric("🎬 Antal filmer", int(totalt_filmer))

    with col2:
        st.metric("⏱️ Summa tid (h)", f"{totalt_tid:.1f}")
        st.metric("🕐 Tid per kille (min)", f"{snitt_tid:.2f}")
        st.metric("📈 ROI per man", f"${roi_per_man:.2f}")
        st.metric("💰 Intäkter (USD)", f"${totalt_intakt:,.2f}")

    with col3:
        st.metric("🧍‍♀️ Malin total lön", f"${totalt_lön:,.2f}")
        st.metric("👫 Kompisars lön", f"${totalt_kompisar:,.2f}")
        st.metric("💸 Kompisars aktievärde", f"${aktievärde:,.2f}")
        st.metric("📊 Per kompis", f"${aktievärde_per_kompis:.2f}")

def main():
    st.set_page_config(page_title="Malins app", layout="wide")
    st.title("🎬 Malins Filmapp – Planering, registrering och analys")

    df = load_data()

    st.sidebar.header("📂 Meny")
    val = st.sidebar.radio("Välj vy:", [
        "📊 Statistik",
        "➕ Ny rad manuellt",
        "🎲 Slumpa film liten",
        "🎞️ Slumpa film stor",
        "📅 Sätt maxvärden",
        "📋 Kopiera största raden",
        "✏️ Redigera rad"
    ])

    if val == "📊 Statistik":
        statistikvy(df)

    elif val == "➕ Ny rad manuellt":
        df = ny_rad_manuellt(df)

    elif val == "🎲 Slumpa film liten":
        df = slumpa_film(df, "liten")

    elif val == "🎞️ Slumpa film stor":
        df = slumpa_film(df, "stor")

    elif val == "📅 Sätt maxvärden":
        df = formulär_maxvärden(df)

    elif val == "📋 Kopiera största raden":
        df = kopiera_största_raden(df)

    elif val == "✏️ Redigera rad":
        df = redigera_tidigare_rad(df)

if __name__ == "__main__":
    main()

def formulär_maxvärden(df):
    st.subheader("📅 Sätt maxvärden (Dag = 0) för Jobb, Grannar, Tjej PojkV, Nils familj")

    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        rad = {"Dag": 0, "Veckodag": "Max"}
    else:
        rad = dag0.iloc[0].to_dict()

    uppdaterad_rad = visa_redigeringsformulär(rad, 0)
    if uppdaterad_rad:
        df = df[df["Dag"] != 0]
        df = pd.concat([df, pd.DataFrame([uppdaterad_rad])], ignore_index=True)
        df = update_calculations(df)
        save_data(df)
        st.success("Maxvärden uppdaterade.")
    return df

def kopiera_största_raden(df):
    if df[df["Dag"] != 0].empty:
        st.warning("Ingen rad att kopiera.")
        return df

    största = df[df["Dag"] != 0].sort_values("Män", ascending=False).iloc[0]
    ny_rad = största.copy()
    ny_rad["Dag"] = get_next_day(df)
    ny_rad["Veckodag"] = veckodag_from_dag(ny_rad["Dag"])

    rad = visa_redigeringsformulär(ny_rad, ny_rad["Dag"])
    if rad:
        df = lägg_till_rad(df, rad)
        visa_varningar(rad)
        st.success("Rad kopierad.")
    return df

def redigera_tidigare_rad(df):
    st.subheader("✏️ Redigera tidigare rad")
    if df[df["Dag"] != 0].empty:
        st.warning("Inga rader att redigera.")
        return df

    valbara = df[df["Dag"] != 0]["Dag"].astype(int).tolist()
    vald_dag = st.selectbox("Välj Dag att redigera", sorted(valbara, reverse=True))

    rad = df[df["Dag"] == vald_dag].iloc[0].to_dict()
    ny_rad = visa_redigeringsformulär(rad, vald_dag)
    if ny_rad:
        df = df[df["Dag"] != vald_dag]
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        save_data(df)
        st.success(f"Dag {vald_dag} uppdaterad.")
        visa_varningar(ny_rad)
    return df
