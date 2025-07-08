import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(st.secrets["SHEET_URL"])
worksheet = sheet.worksheet("Blad1")

# Kolumner som alltid ska finnas
ALL_COLUMNS = [
    "Veckodag", "Dag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D", "Tid T",
    "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj", "Svarta",
    "DeepT", "Sekunder", "Vila mun", "Varv",

    "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
    "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet",
    "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar"
]

def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df = ensure_columns_exist(df)
    return df

def save_data(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    df = df[ALL_COLUMNS]
    return df

def hamta_maxvarden(df):
    dag0 = df[df["Dag"] == 0]
    return {
        "Jobb": dag0["Jobb"].max(),
        "Grannar": dag0["Grannar"].max(),
        "Tjej PojkV": dag0["Tjej PojkV"].max(),
        "Nils familj": dag0["Nils familj"].max()
    }

def validera_maxvarden(rad, maxvarden):
    fel = []
    for kategori in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
        if rad.get(kategori, 0) > maxvarden.get(kategori, 0):
            fel.append(f"{kategori} överskrider maxvärdet {maxvarden.get(kategori, 0)}! Uppdatera Dag = 0 först.")
    return fel

def update_calculations(df):
    df = ensure_columns_exist(df)

    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    df["Veckodag"] = df["Dag"].apply(lambda x: veckodagar[(x - 1) % 7] if x > 0 else "")

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils familj"]
    df["Män"] = df["Nya killar"] + df["Känner"]

    df["Summa singel"] = (df["Tid S"] + df["Vila"]) * df["Män"]
    df["Summa dubbel"] = ((df["Tid D"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DA"])
    df["Summa trippel"] = ((df["Tid T"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    df["Snitt"] = df.apply(lambda row: 0 if row["Män"] == 0 else row["DeepT"] / row["Män"], axis=1)
    df["Tid mun"] = (df["Snitt"] * df["Sekunder"] + df["Vila mun"]) * df["Varv"]

    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Tid mun"]

    df["Suger"] = df.apply(lambda row: 0 if row["Män"] == 0 else 0.6 * row["Summa tid"] / row["Män"], axis=1)

    df["Tid kille"] = df.apply(lambda row: 0 if row["Män"] == 0 else (
        row["Summa singel"] +
        2 * row["Summa dubbel"] +
        3 * row["Summa trippel"] +
        row["Suger"] / row["Män"] +
        row["Tid mun"]
    ), axis=1)

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
        (df["Män"] +
         df["Fitta"] +
         df["Röv"] +
         df["DM"] * 2 +
         df["DF"] * 2 +
         df["DA"] * 3 +
         df["TPP"] * 4 +
         df["TAP"] * 6 +
         df["TP"] * 5) * df["Hårdhet"]
    ).round().astype(int)

    df["Pris"] = 39.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))

    try:
        dag0 = df[df["Dag"] == 0]
        kompisar_total = dag0["Jobb"].sum() + dag0["Grannar"].sum() + dag0["Tjej PojkV"].sum() + dag0["Nils familj"].sum()
        df["Kompisar"] = df.apply(
            lambda row: 0 if kompisar_total == 0 else (row["Intäkter"] - row["Malin lön"]) / kompisar_total,
            axis=1
        )
    except:
        df["Kompisar"] = 0.0

    return df

def skapa_ny_radform(df):
    st.subheader("➕ Lägg till ny rad")

    maxvarden = hamta_maxvarden(df)
    dagar = df[df["Dag"] > 0]["Dag"]
    ny_dag = 1 if dagar.empty else dagar.max() + 1

    with st.form("ny_rad_form"):
        st.markdown("### Inmatning")
        ny_rad = {
            "Dag": ny_dag,
            "Nya killar": st.number_input("Nya killar", value=0, step=1),
            "Fitta": st.number_input("Fitta", value=0, step=1),
            "Röv": st.number_input("Röv", value=0, step=1),
            "DM": st.number_input("Dubbelmacka", value=0, step=1),
            "DF": st.number_input("Dubbel fitta", value=0, step=1),
            "DA": st.number_input("Dubbel röv", value=0, step=1),
            "TPP": st.number_input("Trippel fitta", value=0, step=1),
            "TAP": st.number_input("Trippel röv", value=0, step=1),
            "TP": st.number_input("Trippel penet", value=0, step=1),
            "Tid S": st.number_input("Tid singel (sek)", value=0, step=1),
            "Tid D": st.number_input("Tid dubbel (sek)", value=0, step=1),
            "Tid T": st.number_input("Tid trippel (sek)", value=180, step=1),
            "Vila": st.number_input("Vila (sek)", value=0, step=1),
            "Älskar": st.number_input("Älskar", value=0, step=1),
            "Sover med": st.number_input("Sover med", value=0, step=1),
            "Jobb": st.number_input("Jobb", value=0, step=1),
            "Grannar": st.number_input("Grannar", value=0, step=1),
            "Tjej PojkV": st.number_input("Tjej PojkV", value=0, step=1),
            "Nils familj": st.number_input("Nils familj", value=0, step=1),
            "Svarta": st.number_input("Svarta", value=0, step=1),
            "DeepT": st.number_input("DeepT", value=0, step=1),
            "Sekunder": st.number_input("Sekunder (sek)", value=0, step=1),
            "Vila mun": st.number_input("Vila mun", value=0, step=1),
            "Varv": st.number_input("Varv", value=0, step=1)
        }

        submit = st.form_submit_button("✅ Spara rad")
        if submit:
            fel = validera_maxvarden(ny_rad, maxvarden)
            if fel:
                for f in fel:
                    st.error(f)
            else:
                for key in ALL_COLUMNS:
                    if key not in ny_rad:
                        ny_rad[key] = 0
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                df = update_calculations(df)
                save_data(df)
                st.success(f"Rad för dag {ny_dag} sparad!")

    return df

def visa_data(df):
    st.subheader("📊 Aktuell data")
    df_vy = df.copy()
    df_vy = df_vy.sort_values("Dag", ascending=True)
    st.dataframe(df_vy, use_container_width=True)

def main():
    st.title("📅 MalinData – Daglig logg och beräkningar")
    df = load_data()
    df = update_calculations(df)
    df = skapa_ny_radform(df)
    visa_data(df)

if __name__ == "__main__":
    main()
