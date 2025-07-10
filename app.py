import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 🧠 Rensa cache varje gång appen körs (tillfälligt)
st.cache_data.clear()

# Ladda Google Sheets-uppkoppling
SHEET_URL = st.secrets["SHEET_URL"]
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=SCOPE)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(SHEET_URL)
sheet = spreadsheet.worksheet("Blad1")

# Hämtar data som dataframe
def fetch_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

# Spara dataframe till Google Sheet
def save_data(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def main():
    st.title("Malin-appen")

    df = fetch_data()

    # Visa nuvarande data
    st.subheader("Databas")
    st.dataframe(df)

    # Lägg till ny rad manuellt
    if st.button("Ny rad manuellt"):
        with st.form("ny_rad_form"):
            ny_rad = {}
            for kolumn in df.columns:
                if kolumn.lower() == "dag":
                    ny_rad[kolumn] = st.number_input(kolumn, step=1, format="%d")
                elif kolumn.lower() in ["namn", "kommentar"]:
                    ny_rad[kolumn] = st.text_input(kolumn)
                else:
                    ny_rad[kolumn] = st.number_input(kolumn, step=1.0)
            submitted = st.form_submit_button("Spara ny rad")
            if submitted:
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                save_data(df)
                st.success("Ny rad sparad!")

    # Redigera tidigare rad
    st.subheader("Redigera rad")
    val = st.selectbox("Välj rad att redigera (index)", df.index)
    rad = df.loc[val].copy()
    with st.form("edit_form"):
        uppdaterad_rad = {}
        for kolumn in df.columns:
            if kolumn.lower() == "dag":
                uppdaterad_rad[kolumn] = st.number_input(kolumn, value=rad[kolumn], step=1, format="%d")
            elif kolumn.lower() in ["namn", "kommentar"]:
                uppdaterad_rad[kolumn] = st.text_input(kolumn, value=rad[kolumn])
            else:
                uppdaterad_rad[kolumn] = st.number_input(kolumn, value=rad[kolumn], step=1.0)
        submit_edit = st.form_submit_button("Spara redigerad rad")
        if submit_edit:
            for kolumn in df.columns:
                df.at[val, kolumn] = uppdaterad_rad[kolumn]
            save_data(df)
            st.success("Rad uppdaterad!")

    # Statistik
    st.subheader("Statistik")
    if not df.empty:
        try:
            totalt_tid_sek = df["Summa tid"].sum() * 3600
            totalt_tid_timmar = round(totalt_tid_sek / 3600, 2)
            totalt_filmer = df["Filmer"].sum()
            totalt_män = df["Män"].sum()
            totalt_alskar = df["Älskar"].sum()
            kompisar = df["Känner"].sum()
            totalt_malin = df["Malin lön"].sum()
            if (totalt_alskar + totalt_män + kompisar) > 0:
                roi_malin = round(totalt_malin / (totalt_alskar + totalt_män + kompisar), 2)
            else:
                roi_malin = 0.0
            aktiekurs = df["Aktiekurs"].dropna().iloc[-1] if "Aktiekurs" in df.columns else 0
            vanner = df.loc[df["Dag"] == 0, ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum()
            if vanner > 0:
                kompis_aktievarde = round((5000 * aktiekurs) / vanner, 2)
            else:
                kompis_aktievarde = 0.0

            st.metric("Totalt tid (timmar)", totalt_tid_timmar)
            st.metric("Totalt antal filmer", totalt_filmer)
            st.metric("Totalt antal män", totalt_män)
            st.metric("Totalt älskat", totalt_alskar)
            st.metric("Malin ROI per man", roi_malin)
            st.metric("Kompisars aktievärde per person", kompis_aktievarde)
        except Exception as e:
            st.error(f"Fel vid beräkning av statistik: {e}")

    # Varningar
    st.subheader("Varningar")
    senaste_rad = df.iloc[-1] if not df.empty else None
    if senaste_rad is not None:
        try:
            tid_kille = senaste_rad["Tid kille"]
            summa_tid = senaste_rad["Summa tid"]
            if summa_tid > 17:
                st.warning(f"⚠️ Summa tid ({summa_tid}h) överstiger 17 timmar!")
            if tid_kille < 9 or tid_kille > 15:
                st.warning(f"⚠️ Tid kille är {tid_kille} minuter – utanför gräns 9–15 min!")
        except Exception:
            pass

    # === Funktion för att visa formulär för maxvärden (Dag = 0) ===
    def formulär_maxvärden(df):
        st.subheader("Maxvärden – Kompisgrupper (Dag = 0)")
        dag_0 = df[df["Dag"] == 0].copy()
        jobb = dag_0["Jobb"].values[0] if not dag_0.empty else 0
        grannar = dag_0["Grannar"].values[0] if not dag_0.empty else 0
        tjejpojkv = dag_0["Tjej PojkV"].values[0] if not dag_0.empty else 0
        nils_fam = dag_0["Nils fam"].values[0] if not dag_0.empty else 0

        with st.form("form_max"):
            max_jobb = st.number_input("Max Jobb", value=jobb, step=1)
            max_grannar = st.number_input("Max Grannar", value=grannar, step=1)
            max_tjej = st.number_input("Max Tjej PojkV", value=tjejpojkv, step=1)
            max_nils = st.number_input("Max Nils fam", value=nils_fam, step=1)
            submitted = st.form_submit_button("Spara maxvärden")
            if submitted:
                df = df[df["Dag"] != 0]
                ny_rad = {"Dag": 0, "Jobb": max_jobb, "Grannar": max_grannar,
                          "Tjej PojkV": max_tjej, "Nils fam": max_nils}
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                st.success("Maxvärden uppdaterade.")
                spara_df_till_sheets(df)
                st.experimental_rerun()
        return df

    # === Ny rad manuellt ===
    def ny_rad_manuellt(df):
        st.subheader("Ny rad – manuell inmatning")
        with st.form("form_manuell"):
            ny_rad = {}
            for kolumn in ALL_COLUMNS:
                if kolumn == "Dag":
                    ny_rad[kolumn] = st.number_input(kolumn, step=1, value=int(df["Dag"].max() + 1))
                elif kolumn in BERÄKNADE_KOLUMNER:
                    continue
                else:
                    ny_rad[kolumn] = st.number_input(kolumn, step=1, value=0)
            submitted = st.form_submit_button("Spara rad")
            if submitted:
                for kol in BERÄKNADE_KOLUMNER:
                    ny_rad[kol] = 0
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                df = update_calculations(df)
                spara_df_till_sheets(df)
                st.success("Raden har sparats.")
                st.experimental_rerun()
        return df

    # === Funktion: Kopiera största raden ===
    def kopiera_största_rad(df):
        st.subheader("Kopiera största raden (baserat på Män)")
        if df.empty:
            st.warning("Ingen data att kopiera.")
            return df

        df_data = df[df["Dag"] > 0]
        största_rad = df_data.loc[df_data["Män"].idxmax()]
        ny_rad = största_rad.copy()
        ny_rad["Dag"] = int(df["Dag"].max() + 1)

        with st.form("form_kopiera"):
            for kolumn in ALL_COLUMNS:
                if kolumn in BERÄKNADE_KOLUMNER:
                    continue
                ny_rad[kolumn] = st.number_input(kolumn, value=int(ny_rad[kolumn]), step=1)
            submitted = st.form_submit_button("Spara kopierad rad")
            if submitted:
                for kol in BERÄKNADE_KOLUMNER:
                    ny_rad[kol] = 0
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                df = update_calculations(df)
                spara_df_till_sheets(df)
                st.success("Rad kopierad och sparad.")
                st.experimental_rerun()
        return df

    # === Vilodag-knappar ===
    def vilodag_helt(df):
        st.subheader("Vilodag – helt")
        ny_rad = {"Dag": int(df["Dag"].max() + 1)}
        for kol in ALL_COLUMNS:
            if kol == "Dag":
                continue
            ny_rad[kol] = 0
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        spara_df_till_sheets(df)
        st.success("Vilodag (helt) sparad.")
        return df

    def vilodag_hemma(df):
        st.subheader("Vilodag – hemma (Älskar=8, Sover med=1, Vila=7, Älsk tid=30)")
        ny_rad = {"Dag": int(df["Dag"].max() + 1)}
        for kol in ALL_COLUMNS:
            if kol == "Dag":
                continue
            ny_rad[kol] = 0
        ny_rad["Älskar"] = 8
        ny_rad["Sover med"] = 1
        ny_rad["Vila"] = 7
        ny_rad["Älsk tid"] = 30
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        spara_df_till_sheets(df)
        st.success("Vilodag (hemma) sparad.")
        return df

    def vilodag_jobb(df):
        st.subheader("Vilodag – jobb (30% av maxvärden)")
        maxrad = df[df["Dag"] == 0]
        if maxrad.empty:
            st.error("Maxvärden (Dag = 0) saknas.")
            return df
        ny_rad = {"Dag": int(df["Dag"].max() + 1)}
        ny_rad["Jobb"] = int(maxrad["Jobb"].values[0] * 0.3)
        ny_rad["Grannar"] = int(maxrad["Grannar"].values[0] * 0.3)
        ny_rad["Tjej PojkV"] = int(maxrad["Tjej PojkV"].values[0] * 0.3)
        ny_rad["Nils fam"] = int(maxrad["Nils fam"].values[0] * 0.3)
        for kol in ALL_COLUMNS:
            if kol in ny_rad or kol == "Dag":
                continue
            ny_rad[kol] = 0
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        spara_df_till_sheets(df)
        st.success("Vilodag (jobb) sparad.")
        return df

    def slumpa_film(df, typ="liten"):
        st.subheader(f"Slumpa film – {typ.capitalize()}")
        maxrad = df[df["Dag"] == 0]
        if maxrad.empty:
            st.error("Maxvärden (Dag = 0) saknas.")
            return df

        import random
        ny_rad = {"Dag": int(df["Dag"].max() + 1)}

        intervall = {
            "liten": {"Män": (1, 2), "Fitta": (0, 1), "Röv": (0, 1), "DM": (0, 1), "DF": (0, 1), "DA": (0, 1),
                      "TPP": (0, 0), "TAP": (0, 0), "TP": (0, 0), "DeepT": (10, 30), "Sekunder": (10, 20), "Vila mun": (5, 10),
                      "Varv": (1, 2)},
            "stor":  {"Män": (2, 4), "Fitta": (1, 2), "Röv": (1, 2), "DM": (1, 2), "DF": (1, 2), "DA": (1, 2),
                      "TPP": (1, 2), "TAP": (1, 1), "TP": (1, 1), "DeepT": (30, 80), "Sekunder": (20, 40), "Vila mun": (10, 20),
                      "Varv": (2, 4)}
        }

        for kol in ALL_COLUMNS:
            if kol == "Dag":
                continue
            elif kol in intervall[typ]:
                ny_rad[kol] = random.randint(*intervall[typ][kol])
            elif kol == "Vila":
                ny_rad[kol] = 7
            elif kol == "Älskar":
                ny_rad[kol] = 8
            elif kol == "Sover med":
                ny_rad[kol] = 1
            elif kol == "Älsk tid":
                ny_rad[kol] = 30
            else:
                ny_rad[kol] = 0

        with st.form(f"form_slump_{typ}"):
            for kol in ALL_COLUMNS:
                if kol in BERÄKNADE_KOLUMNER:
                    continue
                ny_rad[kol] = st.number_input(kol, value=int(ny_rad[kol]), step=1)
            submitted = st.form_submit_button(f"Spara slumpad {typ}")
            if submitted:
                for kol in BERÄKNADE_KOLUMNER:
                    ny_rad[kol] = 0
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                df = update_calculations(df)
                spara_df_till_sheets(df)
                visa_varningar(ny_rad)
                st.success(f"Slumpad {typ}-film sparad.")
                st.experimental_rerun()
        return df

    def visa_varningar(rad):
        timmar = rad.get("Summa tid", 0)
        tid_kille = rad.get("Tid kille", 0)
        if timmar > 17:
            st.warning(f"⚠️ Summa tid = {timmar:.1f} timmar – över 17 timmar!")
        if tid_kille < 9 or tid_kille > 15:
            st.warning(f"⚠️ Tid kille = {tid_kille:.1f} min – utanför normalt intervall (9–15 min).")

    def redigera_rad(df, rad_index):
        rad = df.iloc[rad_index].copy()
        st.subheader(f"Redigera rad (Dag = {rad['Dag']})")
        with st.form("form_redigera"):
            for kol in ALL_COLUMNS:
                if kol in BERÄKNADE_KOLUMNER:
                    continue
                rad[kol] = st.number_input(kol, value=int(rad[kol]), step=1)
            submitted = st.form_submit_button("Spara redigerad rad")
            if submitted:
                for kol in BERÄKNADE_KOLUMNER:
                    rad[kol] = 0
                df.iloc[rad_index] = rad
                df = update_calculations(df)
                spara_df_till_sheets(df)
                visa_varningar(rad)
                st.success("Raden uppdaterad.")
                st.experimental_rerun()
        return df

    def visa_senaste_rader(df):
        st.subheader("Senaste rader")
        senaste = df[df["Dag"] > 0].sort_values("Dag", ascending=False).head(10)
        st.dataframe(senaste[ALL_COLUMNS + BERÄKNADE_KOLUMNER])

    def main():
        df = hamta_df_fran_sheets()
        df = update_calculations(df)
        visa_maxvarde_formular(df)

        menyval = st.sidebar.radio("Välj vy", ["Ny rad manuellt", "Slumpa film liten", "Slumpa film stor",
                                               "Vilodag hemma", "Vilodag jobb", "Vilodag helt",
                                               "Kopiera största raden", "Statistik", "Senaste"])

        if menyval == "Ny rad manuellt":
            df = visa_manuellt_formular(df)
        elif menyval == "Slumpa film liten":
            df = slumpa_film(df, typ="liten")
        elif menyval == "Slumpa film stor":
            df = slumpa_film(df, typ="stor")
        elif menyval == "Vilodag hemma":
            df = skapa_vilodag(df, typ="hemma")
        elif menyval == "Vilodag jobb":
            df = skapa_vilodag(df, typ="jobb")
        elif menyval == "Vilodag helt":
            df = skapa_vilodag(df, typ="helt")
        elif menyval == "Kopiera största raden":
            df = kopiera_storsta_rad(df)
        elif menyval == "Statistik":
            visa_statistikvy(df)
        elif menyval == "Senaste":
            visa_senaste_rader(df)

    if __name__ == "__main__":
        main()
