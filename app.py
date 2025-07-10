import streamlit as st
import pandas as pd
import numpy as np
import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2 import service_account
import toml

# Läs in secrets
with open("secrets.toml", "r") as f:
    secrets = toml.load(f)

SHEET_URL = secrets["SHEET_URL"]
GOOGLE_CREDENTIALS = secrets["GOOGLE_CREDENTIALS"]
SPREADSHEET_ID = SHEET_URL.split("/d/")[1].split("/")[0]

ALL_COLUMNS = [
    "Dag", "Veckodag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Tid S", "Tid D", "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv",
    "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel", "Snitt", "Tid mun",
    "Summa tid", "Suger", "Tid kille", "Hårdhet", "Filmer", "Pris", "Intäkter", "Malin lön",
    "Kompisar", "Aktiekurs", "Kompisars aktievärde"
]

MANUAL_COLUMNS = [
    "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Tid S", "Tid D", "Tid T", "Vila",
    "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv"
]

# Autentisering och Google Sheets-koppling
def autentisera_google():
    credentials = service_account.Credentials.from_service_account_info(GOOGLE_CREDENTIALS)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = sheet.worksheet("Blad1")
    return worksheet

# Ladda data
def load_data():
    worksheet = autentisera_google()
    df = get_as_dataframe(worksheet, evaluate_formulas=True).fillna(0)
    df = df[[col for col in ALL_COLUMNS if col in df.columns]]
    return df

# Spara data
def save_data(df):
    worksheet = autentisera_google()
    worksheet.clear()
    set_with_dataframe(worksheet, df)

def veckodag(dagnummer):
    dagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    return dagar[(dagnummer - 1) % 7]

def hamta_maxvarden(df):
    dag0 = df[df["Dag"] == 0]
    if dag0.empty:
        return None
    return dag0.iloc[0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].astype(float)

def validera_maxvarden(rad, maxvarden):
    for kolumn in maxvarden.index:
        if rad[kolumn] > maxvarden[kolumn]:
            return False, f"❌ {kolumn} överskrider maxvärdet ({rad[kolumn]} > {maxvarden[kolumn]})"
    return True, ""

def update_calculations(df):
    if df.empty:
        return df

    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum(axis=1)
    df["Män"] = df["Nya killar"] + df["Känner"]
    df["Summa singel"] = df["Tid S"] * (df["Män"] + df["Fitta"] + df["Röv"]) + df["Vila"] * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = (df["Tid D"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = (df["Tid T"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"])
    df["Snitt"] = df["DeepT"] / df["Män"].replace(0, np.nan)
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]
    df["Summa tid"] = (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Tid mun"] + df["Älskar"] * 1800 + df["Sover med"] * 1800) / 3600
    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Män"].replace(0, np.nan) / 60
    df["Tid kille"] = (df["Tid S"] + df["Tid D"] * 2 + df["Tid T"] * 3 + df["Suger"] * 60 + df["Tid mun"] + df["Sover med"] * 1800 + df["Älskar"] * 1800) / 60
    df["Hårdhet"] = (df["Nya killar"] > 0).astype(int) + (df["DM"] > 0).astype(int)*2 + (df["DF"] > 0).astype(int)*3 + \
                    (df["DA"] > 0).astype(int)*4 + (df["TPP"] > 0).astype(int)*5 + (df["TAP"] > 0).astype(int)*7 + (df["TP"] > 0).astype(int)*6
    df["Filmer"] = (df["Män"] + df["Fitta"] + df["Röv"] + df["DM"]*2 + df["DF"]*2 + df["DA"]*3 + df["TPP"]*4 + df["TAP"]*6 + df["TP"]*5) * df["Hårdhet"]
    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))
    dag0 = df[df["Dag"] == 0]
    if not dag0.empty:
        vanner = dag0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum(axis=1).iloc[0]
        df["Kompisar"] = (df["Intäkter"] - df["Malin lön"]) / vanner if vanner > 0 else 0
        df["Aktiekurs"] = df["Intäkter"].ffill().fillna(0)
        df["Kompisars aktievärde"] = round((5000 * df["Aktiekurs"]) / vanner, 2) if vanner > 0 else 0
    else:
        df["Kompisar"] = 0
        df["Aktiekurs"] = 0
        df["Kompisars aktievärde"] = 0
    df["Veckodag"] = df["Dag"].apply(lambda x: veckodag(x) if x > 0 else "")
    return df

def formulär_maxvärden(df):
    st.header("⚙️ Ange maxvärden (Dag = 0)")
    dag0 = df[df["Dag"] == 0]
    första_gången = dag0.empty

    jobb = st.number_input("Max Jobb", value=float(dag0["Jobb"].iloc[0]) if not första_gången else 0, step=1.0)
    grannar = st.number_input("Max Grannar", value=float(dag0["Grannar"].iloc[0]) if not första_gången else 0, step=1.0)
    tjej = st.number_input("Max Tjej PojkV", value=float(dag0["Tjej PojkV"].iloc[0]) if not första_gången else 0, step=1.0)
    nils = st.number_input("Max Nils familj", value=float(dag0["Nils familj"].iloc[0]) if not första_gången else 0, step=1.0)

    if st.button("💾 Spara maxvärden"):
        ny_rad = {col: 0 for col in ALL_COLUMNS}
        ny_rad["Dag"] = 0
        ny_rad["Jobb"] = jobb
        ny_rad["Grannar"] = grannar
        ny_rad["Tjej PojkV"] = tjej
        ny_rad["Nils familj"] = nils
        df = df[df["Dag"] != 0]  # ta bort tidigare rad Dag = 0 om den finns
        df = pd.concat([pd.DataFrame([ny_rad]), df], ignore_index=True)
        df = update_calculations(df)
        save_data(df)
        st.success("Maxvärden har sparats.")
        st.experimental_rerun()

    return df

def maxvarden_saknas(df):
    return df[df["Dag"] == 0].empty

def ny_rad_manuellt(df):
    st.header("➕ Lägg till ny rad manuellt")

    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        st.warning("⚠️ Du måste först ange maxvärden (Dag = 0).")
        return df

    maxv = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].iloc[0]

    st.markdown("**Aktuella maxvärden (Dag = 0):**")
    st.write(maxv)

    ny_rad = {col: 0 for col in ALL_COLUMNS if col != "Dag"}
    dag = int(df["Dag"].max()) + 1 if not df.empty else 1

    with st.form("manuell_ny_rad"):
        for kolumn in ny_rad:
            if kolumn not in BERÄKNADE_KOLUMNER:
                ny_rad[kolumn] = st.number_input(
                    kolumn,
                    value=0.0,
                    step=1.0,
                    key=f"manuell_{kolumn}"
                )
        submitted = st.form_submit_button("💾 Spara rad")
        if submitted:
            ny_rad["Dag"] = dag
            ny_rad_df = pd.DataFrame([ny_rad])
            ny_rad_df = update_calculations(ny_rad_df)

            ok, fel = validera_maxvarden(ny_rad_df.iloc[0], maxv)
            if not ok:
                st.error(fel)
                return df

            df = pd.concat([df, ny_rad_df], ignore_index=True)
            save_data(df)
            st.success(f"Ny rad med Dag {dag} har sparats.")
            st.experimental_rerun()

    return df

def visa_redigeringsformulär(ny_rad, dag, label="📝 Redigera innan spara"):
    st.subheader(label)
    with st.form(f"form_{dag}"):
        for kolumn in MANUAL_COLUMNS:
            ny_rad[kolumn] = st.number_input(
                kolumn,
                value=float(ny_rad.get(kolumn, 0)),
                step=1.0,
                key=f"{kolumn}_{dag}"
            )
        submitted = st.form_submit_button("💾 Spara redigerad rad")
        if submitted:
            ny_rad["Dag"] = dag
            ny_rad_df = pd.DataFrame([ny_rad])
            ny_rad_df = update_calculations(ny_rad_df)
            maxrad = df[df["Dag"] == 0]
            if not maxrad.empty:
                ok, fel = validera_maxvarden(ny_rad_df.iloc[0], maxrad.iloc[0])
                if not ok:
                    st.error(fel)
                    return None
            return ny_rad_df.iloc[0]
    return None

def slumpa_film(df, variant="liten"):
    import random
    dag = int(df["Dag"].max()) + 1
    ny_rad = {col: 0 for col in ALL_COLUMNS}

    # Exempel på slumpintervall (anpassa om du vill)
    if variant == "liten":
        ny_rad["Nya killar"] = random.randint(0, 2)
        ny_rad["Älskar"] = 1
    else:
        ny_rad["Nya killar"] = random.randint(1, 5)
        ny_rad["Älskar"] = 3

    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Varv"] = 1
    ny_rad["DeepT"] = 10
    ny_rad["Sekunder"] = 30
    ny_rad["Vila mun"] = 5

    redigerad_rad = visa_redigeringsformulär(ny_rad, dag)
    if redigerad_rad is not None:
        df = pd.concat([df, pd.DataFrame([redigerad_rad])], ignore_index=True)
        save_data(df)
        st.success("Slumpad rad sparad.")
        st.experimental_rerun()
    return df

def kopiera_största_raden(df):
    st.subheader("📋 Kopiera rad med flest män")
    dag = int(df["Dag"].max()) + 1
    df_temp = df[df["Dag"] > 0]
    if df_temp.empty:
        st.info("Ingen rad att kopiera från.")
        return df
    maxrad = df_temp.sort_values("Män", ascending=False).iloc[0].copy()
    maxrad["Dag"] = dag
    redigerad = visa_redigeringsformulär(maxrad, dag, "📝 Redigera kopierad rad")
    if redigerad is not None:
        df = pd.concat([df, pd.DataFrame([redigerad])], ignore_index=True)
        save_data(df)
        st.success("Rad kopierad och sparad.")
        st.experimental_rerun()
    return df

def update_calculations(df):
    df = df.copy()

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils familj"]
    df["Män"] = df["Nya killar"] + df["Känner"]

    df["Summa singel"] = (df["Tid S"] + df["Vila"]) * (df["Män"] + df["Fitta"] + df["Röv"])
    df["Summa dubbel"] = (df["Tid D"] + df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = (df["Tid T"] + df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Snitt"] = df.apply(lambda x: x["DeepT"] / x["Män"] if x["Män"] > 0 else 0, axis=1)
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]

    df["Sover tid"] = df["Sover med"] * 1800
    df["Älskar tid"] = df["Älskar"] * 1800

    df["Summa tid"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Tid mun"] +
        df["Suger"] +
        df["Tid kille"] +
        df["Sover tid"] +
        df["Älskar tid"]
    ) / 3600  # till timmar

    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int) * 1 +
        (df["DM"] > 0).astype(int) * 2 +
        (df["DF"] > 0).astype(int) * 3 +
        (df["DA"] > 0).astype(int) * 4 +
        (df["TPP"] > 0).astype(int) * 5 +
        (df["TAP"] > 0).astype(int) * 7 +
        (df["TP"] > 0).astype(int) * 6
    )

    df["Filmer"] = (
        (df["Män"] + df["Fitta"] + df["Röv"] +
         df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3 +
         df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5) * df["Hårdhet"]
    )

    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))

    dag0 = df[df["Dag"] == 0]
    if not dag0.empty:
        vänner = dag0[["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
        df["Kompisar"] = vänner
        df["Kompisar"] = df["Kompisar"].replace(0, 1)
        df["Kompisar aktievärde"] = (5000 * df["Aktiekurs"]) / df["Kompisar"]
        df["Kompisar aktievärde"] = df["Kompisar aktievärde"].round(2)
    else:
        df["Kompisar"] = 0
        df["Kompisar aktievärde"] = 0

    return df

def main():
    st.title("📊 MalinData – Daglig logg och statistik")

    df = load_data()
    df = update_calculations(df)

    menyval = st.sidebar.selectbox("Meny", [
        "📌 Maxvärden (Dag = 0)",
        "➕ Lägg till ny rad manuellt",
        "🎲 Slumpa film liten",
        "🎲 Slumpa film stor",
        "😴 Vila hemma",
        "🏢 Vila jobb",
        "🛌 Vila helt",
        "📋 Kopiera största raden",
        "📈 Statistik",
        "🧾 Visa data"
    ])

    if menyval == "📌 Maxvärden (Dag = 0)":
        df = formulär_maxvärden(df)
    elif menyval == "➕ Lägg till ny rad manuellt":
        df = ny_rad_manuellt(df)
    elif menyval == "🎲 Slumpa film liten":
        df = slumpa_film(df, "liten")
    elif menyval == "🎲 Slumpa film stor":
        df = slumpa_film(df, "stor")
    elif menyval == "😴 Vila hemma":
        df = vila_knapp(df, variant="hemma")
    elif menyval == "🏢 Vila jobb":
        df = vila_knapp(df, variant="jobb")
    elif menyval == "🛌 Vila helt":
        df = vila_knapp(df, variant="helt")
    elif menyval == "📋 Kopiera största raden":
        df = kopiera_största_raden(df)
    elif menyval == "📈 Statistik":
        statistikvy(df)
    elif menyval == "🧾 Visa data":
        st.dataframe(df)

if __name__ == "__main__":
    main()
