import streamlit as st
import pandas as pd
import numpy as np
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime
from google.oauth2.service_account import Credentials

# ======== KONFIGURATION =========

ALL_COLUMNS = [
    "Dag", "Nya killar", "Fitta", "Röv", "DM", "DF", "DA",
    "TPP", "TAP", "TP", "Älskar", "Sover med", "Tid S", "Tid D",
    "Tid T", "Vila", "Jobb", "Grannar", "Tjej PojkV", "Nils familj",
    "Svarta", "DeepT", "Sekunder", "Vila mun", "Varv", "Känner", "Män",
    "Summa singel", "Summa dubbel", "Summa trippel", "Snitt", "Tid mun",
    "Summa tid", "Suger", "Tid kille", "Hårdhet", "Filmer", "Pris",
    "Intäkter", "Malin lön", "Kompisar", "Aktiekurs", "Kompisars aktievärde"
]

# ======== LADDA GOOGLE SHEET =========

SHEET_URL = st.secrets["SHEET_URL"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
client = gspread.authorize(credentials)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.worksheet("Blad1")

# ======== LADDA DATA =========

@st.cache_data(ttl=60)
def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True).fillna(0)
    df = df[[col for col in ALL_COLUMNS if col in df.columns]]  # rätt ordning
    df = df.astype({col: float for col in df.columns if col != "Dag"})
    df["Dag"] = df["Dag"].astype(int)
    return df

# ======== SPARA DATA =========

def save_data(df):
    df = df[ALL_COLUMNS]
    set_with_dataframe(worksheet, df.fillna(0), include_index=False)

# ======== SÄKERSTÄLL KOLUMNER =========

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df[ALL_COLUMNS]

# ======== HÄMTA MAXVÄRDEN FRÅN DAG 0 =========

def hamta_maxvarden(df):
    if 0 not in df["Dag"].values:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils familj": 0}
    maxrad = df[df["Dag"] == 0].iloc[-1]
    return {
        "Jobb": int(maxrad["Jobb"]),
        "Grannar": int(maxrad["Grannar"]),
        "Tjej PojkV": int(maxrad["Tjej PojkV"]),
        "Nils familj": int(maxrad["Nils familj"])
    }

# ======== VALIDERA MOT MAXVÄRDEN =========

def validera_maxvarden(rad, maxvarden):
    return all([
        rad["Jobb"] <= maxvarden["Jobb"],
        rad["Grannar"] <= maxvarden["Grannar"],
        rad["Tjej PojkV"] <= maxvarden["Tjej PojkV"],
        rad["Nils familj"] <= maxvarden["Nils familj"]
    ])

# ======== BERÄKNA OCH UPPDATERA KOLUMNER =========

def update_calculations(df):
    df = ensure_columns_exist(df)

    for i, row in df.iterrows():
        if row["Dag"] == 0:
            continue

        # Vänner = maxvärden från Dag = 0
        vänner = hamta_maxvarden(df)
        kompisar = vänner["Jobb"] + vänner["Grannar"] + vänner["Tjej PojkV"] + vänner["Nils familj"]
        df.at[i, "Kompisar"] = kompisar
        df.at[i, "Män"] = row["Nya killar"] + kompisar

        # Summa singel/dubbel/trippel
        df.at[i, "Summa singel"] = (
            (row["Tid S"] + row["Vila"]) * (row["Män"] + row["Fitta"] + row["Röv"])
        )
        df.at[i, "Summa dubbel"] = (
            (row["Tid D"] + row["Vila"] + 8) * (row["DM"] + row["DF"] + row["DA"])
        )
        df.at[i, "Summa trippel"] = (
            (row["Tid T"] + row["Vila"] + 15) * (row["TPP"] + row["TAP"] + row["TP"])
        )

        # Snitt & Tid mun
        if row["Män"] > 0:
            snitt = row["DeepT"] / row["Män"]
        else:
            snitt = 0
        df.at[i, "Snitt"] = snitt
        df.at[i, "Tid mun"] = (snitt * row["Sekunder"] + row["Vila mun"]) * row["Varv"]

        # Summa tid i timmar (lägg ihop alla delmoment)
        summa_tid = (
            df.at[i, "Summa singel"]
            + df.at[i, "Summa dubbel"]
            + df.at[i, "Summa trippel"]
            + df.at[i, "Tid mun"]
            + row["Älskar"] * 1800  # 30 min per älskar
            + row["Sover med"] * 1800  # 30 min per sover med
        )
        if (
            row["Nya killar"] == 0
            and row["Fitta"] == 0
            and row["Röv"] == 0
            and row["DM"] == 0
            and row["DF"] == 0
            and row["DA"] == 0
            and row["TPP"] == 0
            and row["TAP"] == 0
            and row["TP"] == 0
            and row["Älskar"] == 0
            and row["Sover med"] == 0
        ) and kompisar > 0:
            summa_tid += 10800  # 3h kompistid
        df.at[i, "Summa tid"] = round(summa_tid / 3600, 2)  # i timmar

        # Suger
        tot_män = row["Män"]
        total_sex = df.at[i, "Summa singel"] + df.at[i, "Summa dubbel"] + df.at[i, "Summa trippel"]
        df.at[i, "Suger"] = (total_sex * 0.6 / tot_män) if tot_män else 0

        # Tid kille
        df.at[i, "Tid kille"] = round(
            row["Tid S"] + row["Tid D"] * 2 + row["Tid T"] * 3
            + df.at[i, "Suger"] + df.at[i, "Tid mun"], 2
        )

        # Hårdhet
        hårdhet = 0
        if row["Nya killar"] > 0: hårdhet += 1
        if row["DM"] > 0: hårdhet += 2
        if row["DF"] > 0: hårdhet += 3
        if row["DA"] > 0: hårdhet += 4
        if row["TPP"] > 0: hårdhet += 5
        if row["TAP"] > 0: hårdhet += 7
        if row["TP"] > 0: hårdhet += 6
        df.at[i, "Hårdhet"] = hårdhet

        # Filmer
        filmer = (
            row["Män"] + row["Fitta"] + row["Röv"]
            + row["DM"] * 2 + row["DF"] * 2 + row["DA"] * 3
            + row["TPP"] * 4 + row["TAP"] * 6 + row["TP"] * 5
        ) * hårdhet
        df.at[i, "Filmer"] = filmer

        # Pris, intäkter, Malin lön
        pris = 39.99
        df.at[i, "Pris"] = pris
        intäkter = filmer * pris
        df.at[i, "Intäkter"] = intäkter
        df.at[i, "Malin lön"] = min(700, intäkter * 0.01)

        # Kompisars aktievärde (per rad)
        if kompisar > 0:
            aktievärde = (row["Aktiekurs"] * 5000) / kompisar
        else:
            aktievärde = 0
        df.at[i, "Kompisars aktievärde"] = round(aktievärde, 2)

    return df

# ======== FORMULÄR FÖR DAG = 0 (MAXVÄRDEN) ========

def formulär_maxvärden(df, worksheet):
    st.subheader("⬆️ Ange maxvärden (Dag = 0)")
    with st.form("maxvärden_formulär"):
        jobb = st.number_input("Max Jobb", min_value=0, step=1, value=int(df[df["Dag"] == 0]["Jobb"].max()) if 0 in df["Dag"].values else 0)
        grannar = st.number_input("Max Grannar", min_value=0, step=1, value=int(df[df["Dag"] == 0]["Grannar"].max()) if 0 in df["Dag"].values else 0)
        tjej = st.number_input("Max Tjej PojkV", min_value=0, step=1, value=int(df[df["Dag"] == 0]["Tjej PojkV"].max()) if 0 in df["Dag"].values else 0)
        nils = st.number_input("Max Nils familj", min_value=0, step=1, value=int(df[df["Dag"] == 0]["Nils familj"].max()) if 0 in df["Dag"].values else 0)
        submit = st.form_submit_button("Spara maxvärden")
    if submit:
        df = df[df["Dag"] != 0]
        ny_rad = {col: 0 for col in ALL_COLUMNS}
        ny_rad["Dag"] = 0
        ny_rad["Jobb"] = jobb
        ny_rad["Grannar"] = grannar
        ny_rad["Tjej PojkV"] = tjej
        ny_rad["Nils familj"] = nils
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Maxvärden sparade.")
    return df

# ======== FORMULÄR: NY RAD MANUELLT ========

def ny_rad_manuellt(df, worksheet):
    maxvarden = hamta_maxvarden(df)
    st.subheader("📝 Lägg till ny rad manuellt")
    with st.form("manuell_form"):
        ny_rad = {"Dag": df["Dag"].max() + 1 if len(df) > 0 else 1}
        for col in ALL_COLUMNS:
            if col in ["Dag", "Känner", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
                       "Snitt", "Tid mun", "Summa tid", "Suger", "Tid kille", "Hårdhet",
                       "Filmer", "Pris", "Intäkter", "Malin lön", "Kompisar", "Kompisars aktievärde"]:
                continue
            default = 0
            if col in maxvarden:
                default = maxvarden[col]
            ny_rad[col] = st.number_input(col, value=int(default), step=1)
        submit = st.form_submit_button("Spara rad")
    if submit:
        ny_rad = {k: ny_rad[k] if isinstance(ny_rad[k], (int, float)) else 0 for k in ny_rad}
        ny_rad_df = pd.DataFrame([ny_rad])
        df = pd.concat([df, ny_rad_df], ignore_index=True)
        df = update_calculations(df)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Ny rad tillagd och beräkningar uppdaterade.")
    return df

# ======== KNAPP: SLUMPA FILM (liten/stor) ========

def slumpa_film(df, storlek):
    import random
    dag = df["Dag"].max() + 1 if len(df) > 0 else 1
    ny_rad = {col: 0 for col in ALL_COLUMNS}
    ny_rad["Dag"] = dag

    intervall = {
        "liten": {
            "Nya killar": (0, 2), "Fitta": (0, 1), "Röv": (0, 1), "DM": (0, 1),
            "DF": (0, 1), "DA": (0, 1), "TPP": (0, 1), "TAP": (0, 1), "TP": (0, 1),
            "Älskar": (0, 1), "Sover med": (0, 1), "Tid S": (0, 120), "Tid D": (0, 120),
            "Tid T": (0, 180), "Vila": (0, 5), "Jobb": (0, 3), "Grannar": (0, 2),
            "Tjej PojkV": (0, 2), "Nils familj": (0, 1), "Svarta": (0, 1),
            "DeepT": (0, 10), "Sekunder": (10, 120), "Vila mun": (0, 5), "Varv": (0, 3)
        },
        "stor": {
            "Nya killar": (1, 5), "Fitta": (1, 3), "Röv": (1, 3), "DM": (1, 2),
            "DF": (1, 2), "DA": (1, 2), "TPP": (1, 2), "TAP": (1, 2), "TP": (1, 2),
            "Älskar": (1, 2), "Sover med": (1, 2), "Tid S": (60, 240), "Tid D": (90, 240),
            "Tid T": (120, 300), "Vila": (2, 7), "Jobb": (1, 6), "Grannar": (1, 4),
            "Tjej PojkV": (1, 4), "Nils familj": (1, 3), "Svarta": (1, 2),
            "DeepT": (5, 25), "Sekunder": (30, 180), "Vila mun": (2, 10), "Varv": (1, 5)
        }
    }

    for key, (min_val, max_val) in intervall[storlek].items():
        ny_rad[key] = random.randint(min_val, max_val)

    return visa_redigeringsformulär(ny_rad, dag)

# ======== KNAPP: VILODAG JOBB/HEMMA/HELT ========

def vila_knapp(df, typ):
    dag = df["Dag"].max() + 1 if len(df) > 0 else 1
    ny_rad = {col: 0 for col in ALL_COLUMNS}
    ny_rad["Dag"] = dag
    maxvarden = hamta_maxvarden(df)

    if typ == "jobb":
        ny_rad["Jobb"] = int(maxvarden["Jobb"] * 0.3)
        ny_rad["Grannar"] = int(maxvarden["Grannar"] * 0.3)
        ny_rad["Tjej PojkV"] = int(maxvarden["Tjej PojkV"] * 0.3)
        ny_rad["Nils familj"] = int(maxvarden["Nils familj"] * 0.3)
    elif typ == "hemma":
        ny_rad["Vila"] = 7
    elif typ == "helt":
        ny_rad["Vila"] = 12
    return visa_redigeringsformulär(ny_rad, dag)

# ======== KNAPP: KOPIERA STÖRSTA RADEN ========

def kopiera_storsta_raden(df):
    största = df[df["Dag"] > 0].sort_values(by="Män", ascending=False).iloc[0].to_dict()
    dag = df["Dag"].max() + 1 if len(df) > 0 else 1
    största["Dag"] = dag
    return visa_redigeringsformulär(största, dag)

# ======== REDIGERA FORMULÄR OCH SPARA ========

def visa_redigeringsformulär(ny_rad, dag):
    with st.form(f"redigera_{dag}"):
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                continue
            step = 1 if isinstance(ny_rad[kolumn], int) else 0.1
            ny_rad[kolumn] = st.number_input(
                kolumn, value=float(ny_rad.get(kolumn, 0)), step=step, key=f"{kolumn}_{dag}"
            )
        submit = st.form_submit_button("Spara redigerad rad")
    if submit:
        ny_rad["Dag"] = dag
        df = load_data()
        df = df[df["Dag"] != dag]
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        worksheet = load_worksheet()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Rad sparad.")
        visa_varningar(ny_rad)
    return df

# ======== VARNINGAR ========

def visa_varningar(rad):
    if rad.get("Summa tid", 0) > 17:
        st.warning(f"⚠️ Summa tid är {rad['Summa tid']} h – över 17 timmar.")
    if rad.get("Tid kille", 0) < 9 or rad.get("Tid kille", 0) > 15:
        st.warning(f"⚠️ Tid kille är {rad['Tid kille']} min – utanför 9–15 min.")

# ======== STATISTIKVY ========

def statistikvy(df):
    st.header("📊 Statistik")

    df_film = df[df["Dag"] > 0].copy()
    if df_film.empty:
        st.info("Ingen data att visa ännu.")
        return

    total_filmer = df_film["Filmer"].sum()
    total_alskar = df_film["Älskar"].sum()
    total_sover_med = df_film["Sover med"].sum()
    total_nya_killar = df_film["Nya killar"].sum()
    total_kompisar = df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]].sum().sum()
    total_man = total_alskar + total_sover_med + total_nya_killar + total_kompisar

    total_tid = df_film["Summa tid"].sum()
    total_tid_kille = df_film["Tid kille"].sum()
    total_intakter = df_film["Intäkter"].sum()
    total_malin_lon = df_film["Malin lön"].sum()

    kompisar_aktiekurs = df_film["Aktiekurs"].iloc[-1] if not df_film["Aktiekurs"].isnull().all() else 0
    kompisar_totalt = total_kompisar * 5000 * kompisar_aktiekurs
    kompisar_per_person = (kompisar_totalt / total_kompisar) if total_kompisar > 0 else 0

    roi_per_man = (total_malin_lon / total_man) if total_man > 0 else 0

    st.markdown("### 🎬 Filmstatistik")
    st.write(f"**Totalt antal filmer:** {int(total_filmer)}")
    st.write(f"**Totalt antal män:** {int(total_man)}")
    st.write(f"– Älskar: {int(total_alskar)}, Sover med: {int(total_sover_med)}, Nya killar: {int(total_nya_killar)}, Kompisar: {int(total_kompisar)}")

    st.markdown("### 💰 Ekonomi")
    st.write(f"**Totala intäkter:** {round(total_intakter, 2)} USD")
    st.write(f"**Malin lön (summa):** {round(total_malin_lon, 2)} USD")
    st.write(f"**Malin ROI per man:** {round(roi_per_man, 2)} USD/person")

    st.markdown("### 🕓 Tidsstatistik")
    st.write(f"**Total summa tid:** {round(total_tid, 2)} timmar")
    st.write(f"**Total 'Tid kille':** {round(total_tid_kille, 2)} minuter")

    st.markdown("### 📈 Kompisars aktievärde")
    st.write(f"**Senaste aktiekurs:** {kompisar_aktiekurs} USD")
    st.write(f"**Totalt aktievärde:** {round(kompisar_totalt, 2)} USD")
    st.write(f"**Per person:** {round(kompisar_per_person, 2)} USD/person")

# ======== HUVUDMENY & LOGIK ========

def main():
    st.set_page_config(page_title="MalinApp", layout="wide")
    st.title("💗 MalinApp")
    df = load_data()

    menyval = st.sidebar.radio("Välj vy", [
        "📥 Lägg till ny rad",
        "📊 Statistik",
        "📜 Visa databas",
    ])

    if menyval == "📥 Lägg till ny rad":
        st.subheader("📥 Lägg till ny rad i databasen")

        # Visa formulär för maxvärden om Dag=0 inte finns
        if not (df["Dag"] == 0).any():
            st.warning("⚠️ Du måste först lägga till maxvärden för kompisar (Dag = 0).")
            ny_maxrad = formulär_maxvärden()
            if ny_maxrad is not None:
                df = df.append(ny_maxrad, ignore_index=True)
                df = update_calculations(df)
                save_data(df)
                st.success("Maxvärden sparade. Nu kan du lägga till vanliga rader.")
                st.experimental_rerun()
        else:
            # Visa aktuella maxvärden för kontroll
            st.markdown("### Aktuella maxvärden (Dag = 0)")
            st.dataframe(df[df["Dag"] == 0][["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]])

            ny_rad = visa_redigeringsformulär(skapa_tom_rad(df), dag=hamta_nasta_dag(df))
            if ny_rad:
                ny_rad["Dag"] = hamta_nasta_dag(df)
                df = df.append(ny_rad, ignore_index=True)
                df = update_calculations(df)
                df = validera_maxvarden(df)
                save_data(df)
                visa_varningar(df, ny_rad)
                st.success("Ny rad sparad!")

    elif menyval == "📊 Statistik":
        statistikvy(df)

    elif menyval == "📜 Visa databas":
        st.subheader("📜 Alla rader i databasen")
        st.dataframe(df.sort_values("Dag"))

# ======== HJÄLPFUNKTIONER ========

def hamta_nasta_dag(df):
    if df.empty:
        return 1
    else:
        return df["Dag"].max() + 1

def validera_maxvarden(df):
    maxrad = df[df["Dag"] == 0].iloc[0]
    for i, row in df.iterrows():
        if row["Dag"] == 0:
            continue
        for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils familj"]:
            if row[kol] > maxrad[kol]:
                df.at[i, kol] = maxrad[kol]
    return df

def visa_varningar(df, ny_rad):
    tid_kille = ny_rad.get("Tid kille", 0)
    summa_tid = ny_rad.get("Summa tid", 0)

    if summa_tid > 17:
        st.warning(f"⚠️ Summa tid är {summa_tid:.1f} h – över 17 timmar!")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"⚠️ Tid kille är {tid_kille:.1f} min – utanför normalt intervall (9–15 min)")

def skapa_tom_rad(df):
    rad = {}
    for kol in ALL_COLUMNS:
        rad[kol] = 0
    rad["Pris"] = 39.99
    rad["Dag"] = hamta_nasta_dag(df)
    return rad

# ======== START APP ========
if __name__ == "__main__":
    main()
