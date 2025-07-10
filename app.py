import streamlit as st
import pandas as pd
import datetime
from google.oauth2 import service_account
import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe

st.set_page_config(page_title="Malinstatistik", layout="wide")

# Funktion för att ladda in data från Google Sheet
def las_in_data():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df = df.dropna(how="all")
    return df

# Funktion för att spara data till Google Sheet
def spara_data(df):
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    worksheet.clear()
    set_with_dataframe(worksheet, df)

# Funktion för att säkerställa att alla kolumner finns
def ensure_columns_exist(df, expected_columns):
    for col in expected_columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df[expected_columns]

# Funktion för att rensa hela databasen (behåll rubriker)
def rensa_allt():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    headers = worksheet.row_values(1)
    worksheet.clear()
    worksheet.append_row(headers)

# Funktion för att visa knapp för rensning
def visa_rensningsknapp():
    with st.expander("⚠️ Rensa hela databasen"):
        if st.button("❌ Rensa allt (kan inte ångras)"):
            rensa_allt()
            st.success("Databasen är nu helt rensad.")

# Kolumner enligt rätt ordning för manuell inmatning
ALL_COLUMNS = [
    "Dag", "Nya killar", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
    "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Svarta",
    "Tid singel", "Tid dubbel", "Tid trippel", "Vila",
    "DeepT", "Sekunder", "Vila mun", "Varv",
    "Snitt", "Tid mun", "Män", "Summa singel", "Summa dubbel", "Summa trippel",
    "Suger", "Total tid", "Tid kille dt", "Tid kille",
    "Tidsåtgång", "Filmer", "Intäkter", "Malin lön", "Kompisars lön",
    "Kompisaktievärde", "Kompisaktievärde/person", "ROI Malin/man"
]

# Specifik inmatningsordning (manuellt formulär)
MANUELL_ORDNING = [
    "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Älskar", "Sover med", "Svarta", "Tid singel", "Tid dubbel", "Tid trippel",
    "Vila", "DeepT", "Sekunder", "Varv", "Vila mun"
]

# Hjälpfunktion för att skapa en tom rad med alla kolumner
def skapa_tom_rad(dag):
    return pd.DataFrame([{col: None for col in ALL_COLUMNS} | {"Dag": dag}])

# Funktion för att extrahera maxvärden från Dag = 0
def hamta_maxvarden(df):
    if "Dag" not in df.columns:
        return pd.Series(dtype='float64')
    if 0 not in df["Dag"].values:
        return pd.Series(dtype='float64')
    return df[df["Dag"] == 0].iloc[0]

# Funktion för att säkerställa att inmatning inte överskrider maxgränser
def validera_maxvarden(rad, maxrad):
    for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if pd.notna(rad.get(kol)) and pd.notna(maxrad.get(kol)):
            if rad[kol] > maxrad[kol]:
                raise ValueError(f"{kol} = {rad[kol]} överskrider maxvärdet ({maxrad[kol]}) enligt Dag = 0.")

# Funktion för att uppdatera alla beräkningar
def update_calculations(df):
    df = ensure_columns_exist(df, ALL_COLUMNS)

    df["Män"] = df["Nya killar"].fillna(0) + df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].fillna(0).sum(axis=1)

    df["Snitt"] = df["DeepT"].fillna(0) / df["Män"].replace(0, pd.NA)
    df["Tid mun"] = ((df["Snitt"].fillna(0) * df["Sekunder"].fillna(0)) + df["Vila mun"].fillna(0)) * df["Varv"].fillna(0)

    df["Summa singel"] = (df["Tid singel"].fillna(0) + df["Vila"].fillna(0) * (df["Män"].fillna(0) + df["Fitta"].fillna(0) + df["Röv"].fillna(0)))
    df["Summa dubbel"] = ((df["Tid dubbel"].fillna(0) + (df["Vila"].fillna(0) + 8)) *
                          (df["DM"].fillna(0) + df["DF"].fillna(0) + df["DA"].fillna(0)))
    df["Summa trippel"] = ((df["Tid trippel"].fillna(0) + (df["Vila"].fillna(0) + 15)) *
                           (df["TPP"].fillna(0) + df["TAP"].fillna(0) + df["TP"].fillna(0)))

    df["Suger"] = 0.6 * (df["Summa singel"].fillna(0) + df["Summa dubbel"].fillna(0) + df["Summa trippel"].fillna(0)) / df["Män"].replace(0, pd.NA)

    df["Total tid"] = df["Snitt"].fillna(0) * df["Sekunder"].fillna(0) * df["Varv"].fillna(0)
    df["Tid kille dt"] = df["Total tid"] / df["Män"].replace(0, pd.NA)

    df["Tid kille"] = (
        df["Tid singel"].fillna(0) +
        df["Tid dubbel"].fillna(0) * 2 +
        df["Tid trippel"].fillna(0) * 3 +
        df["Suger"].fillna(0) +
        df["Tid kille dt"].fillna(0) +
        df["Tid mun"].fillna(0)
    ) / 60  # till minuter

    df["Tidsåtgång"] = (
        df["Summa singel"].fillna(0) +
        df["Summa dubbel"].fillna(0) +
        df["Summa trippel"].fillna(0) +
        df["Tid mun"].fillna(0) +
        df["Älskar"].fillna(0) * 1800 +  # 30 minuter
        df["Sover med"].fillna(0) * 1800 +  # 30 minuter
        df.apply(lambda row: 3 * 3600 if (
            row["Män"] == 0 and
            row["Fitta"] == 0 and
            row["Röv"] == 0 and
            row["DM"] == 0 and
            row["DF"] == 0 and
            row["DA"] == 0 and
            row["TPP"] == 0 and
            row["TAP"] == 0 and
            row["TP"] == 0 and
            row["Älskar"] == 0 and
            row["Sover med"] == 0 and
            row["Nya killar"] == 0
        ) else 0, axis=1)
    ) / 3600  # till timmar

    df["Filmer"] = (
        (df["Män"].fillna(0) + df["Fitta"].fillna(0) + df["Röv"].fillna(0) +
         df["DM"].fillna(0) * 2 + df["DF"].fillna(0) * 2 + df["DA"].fillna(0) * 3 +
         df["TPP"].fillna(0) * 4 + df["TAP"].fillna(0) * 6 + df["TP"].fillna(0) * 5) *
        df.apply(lambda row: 0
                 + (1 if row["Nya killar"] > 0 else 0)
                 + (2 if row["DM"] > 0 else 0)
                 + (3 if row["DF"] > 0 else 0)
                 + (4 if row["DA"] > 0 else 0)
                 + (5 if row["TPP"] > 0 else 0)
                 + (7 if row["TAP"] > 0 else 0)
                 + (6 if row["TP"] > 0 else 0),
                 axis=1)
    )

    df["Intäkter"] = df["Filmer"] * 39.99
    df["Malin lön"] = df["Intäkter"] * 0.01
    df["Malin lön"] = df["Malin lön"].apply(lambda x: min(x, 700))

    # Beräkna Kompisars lön (vänners lön = intäkter / vänner från Dag 0)
    if 0 in df["Dag"].values:
        maxrad = df[df["Dag"] == 0].iloc[0]
        vanner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].fillna(0).sum()
        df["Kompisars lön"] = df["Intäkter"] / vanner if vanner > 0 else 0
        kurs = df["Intäkter"].iloc[-1] if not df["Intäkter"].empty else 0
        df["Kompisaktievärde"] = kurs * 5000
        df["Kompisaktievärde/person"] = (kurs * 5000) / vanner if vanner > 0 else 0
        df["ROI Malin/man"] = df["Malin lön"].sum() / (
            df[["Älskar", "Sover med", "Nya killar", "Män"]].fillna(0).sum(axis=1).sum()
        )

    return df

# --- Funktioner för formulär ---

def visa_maxvarde_form(df):
    st.subheader("Maxvärden – Dag 0")
    with st.form("form_maxvarden", clear_on_submit=False):
        kolumner = ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]
        maxdata = {}
        for kolumn in kolumner:
            maxdata[kolumn] = st.number_input(f"Maxvärde för {kolumn}", min_value=0, value=int(df[df["Dag"] == 0][kolumn].iloc[0]) if (df["Dag"] == 0).any() else 0)

        submitted = st.form_submit_button("Spara maxvärden")
        if submitted:
            if (df["Dag"] == 0).any():
                df.loc[df["Dag"] == 0, kolumner] = [maxdata[k] for k in kolumner]
            else:
                ny_rad = {k: maxdata[k] for k in kolumner}
                ny_rad.update({k: 0 for k in df.columns if k not in ny_rad})
                ny_rad["Dag"] = 0
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            spara_data(df)
            st.success("Maxvärden sparade!")
    return df

def visa_manuellt_form(df):
    st.subheader("Ny rad – Manuell inmatning")

    maxrad = df[df["Dag"] == 0].iloc[0] if (df["Dag"] == 0).any() else None

    with st.form("form_ny_rad", clear_on_submit=False):
        ny = {}

        for f in [
            "Nya killar", "Fitta", "Röv", "DM", "DF", "DA", "TPP", "TAP", "TP",
            "Älskar", "Sover med", "Svarta", "Tid singel", "Tid dubbel", "Tid trippel",
            "Vila", "DeepT", "Sekunder", "Varv", "Vila mun"
        ]:
            ny[f] = st.number_input(f, min_value=0, value=0)

        # Kontroll mot maxvärden
        for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            if maxrad is not None:
                ny[kol] = st.number_input(kol, min_value=0, max_value=int(maxrad[kol]), value=0)
            else:
                ny[kol] = st.number_input(kol, min_value=0, value=0)

        ny["Dag"] = int(df["Dag"].max()) + 1 if not df.empty else 1

        submitted = st.form_submit_button("Spara rad")
        if submitted:
            ny_rad = {k: ny[k] for k in ny}
            for k in df.columns:
                if k not in ny_rad:
                    ny_rad[k] = 0
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            df = update_calculations(df)
            spara_data(df)
            st.success("Rad sparad!")

            # Varningar
            sista = df.iloc[-1]
            if sista["Tidsåtgång"] > 17:
                st.warning(f"⚠️ Varning: Tidsåtgången är {sista['Tidsåtgång']:.1f} timmar.")
            if sista["Tid kille"] < 9 or sista["Tid kille"] > 15:
                st.warning(f"⚠️ Varning: Tid kille är {sista['Tid kille']:.1f} minuter.")

    return df

# --- Knappfunktioner för vilodagar, kopiera, slumpa ---

def slumpa_rad(df, liten=False):
    maxrad = df[df["Dag"] == 0].iloc[0] if (df["Dag"] == 0).any() else None
    if maxrad is None:
        st.error("Maxvärden saknas (Dag 0).")
        return df

    import random

    def slumptal(kolumn, faktor):
        maxv = maxrad[kolumn]
        if liten:
            return random.randint(0, max(0, int(maxv * 0.3)))
        else:
            return random.randint(int(maxv * 0.5), int(maxv))

    ny = {
        "Nya killar": random.randint(0, 4),
        "Fitta": random.randint(0, 3),
        "Röv": random.randint(0, 2),
        "DM": random.randint(0, 2),
        "DF": random.randint(0, 2),
        "DA": random.randint(0, 1),
        "TPP": random.randint(0, 1),
        "TAP": random.randint(0, 1),
        "TP": random.randint(0, 1),
        "Älskar": random.randint(0, 2),
        "Sover med": random.randint(0, 2),
        "Svarta": random.randint(0, 1),
        "Tid singel": random.randint(60, 600),
        "Tid dubbel": random.randint(60, 300),
        "Tid trippel": random.randint(30, 300),
        "Vila": random.randint(2, 15),
        "DeepT": random.randint(10, 100),
        "Sekunder": random.randint(30, 300),
        "Vila mun": random.randint(10, 60),
        "Varv": random.randint(1, 5),
        "Jobb": slumptal("Jobb", 0.5),
        "Grannar": slumptal("Grannar", 0.5),
        "Tjej PojkV": slumptal("Tjej PojkV", 0.5),
        "Nils fam": slumptal("Nils fam", 0.5),
        "Dag": int(df["Dag"].max()) + 1 if not df.empty else 1
    }

    with st.form("slumpad_rad"):
        st.subheader("Redigera slumpad rad")
        for k in ny:
            ny[k] = st.number_input(k, value=int(ny[k]), min_value=0)

        submitted = st.form_submit_button("Spara slumpad rad")
        if submitted:
            ny_rad = {k: ny[k] for k in ny}
            for k in df.columns:
                if k not in ny_rad:
                    ny_rad[k] = 0
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            df = update_calculations(df)
            spara_data(df)
            st.success("Rad sparad!")

            sista = df.iloc[-1]
            if sista["Tidsåtgång"] > 17:
                st.warning(f"⚠️ Tidsåtgång: {sista['Tidsåtgång']:.1f} timmar.")
            if sista["Tid kille"] < 9 or sista["Tid kille"] > 15:
                st.warning(f"⚠️ Tid kille: {sista['Tid kille']:.1f} minuter.")
    return df

def vila_rutin(df, typ):
    maxrad = df[df["Dag"] == 0].iloc[0] if (df["Dag"] == 0).any() else None
    if maxrad is None:
        st.error("Maxvärden saknas (Dag 0).")
        return df

    ny = {k: 0 for k in ALL_COLUMNS}
    ny["Dag"] = int(df["Dag"].max()) + 1 if not df.empty else 1

    if typ == "jobb":
        ny["Jobb"] = int(maxrad["Jobb"] * 0.3)
        ny["Grannar"] = int(maxrad["Grannar"] * 0.3)
        ny["Tjej PojkV"] = int(maxrad["Tjej PojkV"] * 0.3)
        ny["Nils fam"] = int(maxrad["Nils fam"] * 0.3)
    elif typ == "hemma":
        ny["Vila"] = 7
    elif typ == "helt":
        pass

    with st.form(f"vilodag_{typ}"):
        st.subheader("Redigera vilodag")
        for k in ny:
            if k in MANUELLA_FALT:
                ny[k] = st.number_input(k, value=int(ny[k]), min_value=0)
        submitted = st.form_submit_button("Spara vilodag")
        if submitted:
            df = pd.concat([df, pd.DataFrame([ny])], ignore_index=True)
            df = update_calculations(df)
            spara_data(df)
            st.success("Vilodag sparad!")

            sista = df.iloc[-1]
            if sista["Tidsåtgång"] > 17:
                st.warning(f"⚠️ Tidsåtgång: {sista['Tidsåtgång']:.1f} timmar.")
            if sista["Tid kille"] < 9 or sista["Tid kille"] > 15:
                st.warning(f"⚠️ Tid kille: {sista['Tid kille']:.1f} minuter.")
    return df


def kopiera_storsta_rad(df):
    if df.empty:
        st.warning("Ingen rad att kopiera.")
        return df
    storst = df[df["Män"] == df["Män"].max()].iloc[-1]
    ny = storst.copy()
    ny["Dag"] = int(df["Dag"].max()) + 1

    with st.form("kopiera_rad"):
        st.subheader("Redigera kopierad rad")
        for k in ny.index:
            if k in MANUELLA_FALT:
                ny[k] = st.number_input(k, value=int(ny[k]), min_value=0)
        submitted = st.form_submit_button("Spara kopierad rad")
        if submitted:
            ny_rad = ny.to_dict()
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            df = update_calculations(df)
            spara_data(df)
            st.success("Kopierad rad sparad!")

            sista = df.iloc[-1]
            if sista["Tidsåtgång"] > 17:
                st.warning(f"⚠️ Tidsåtgång: {sista['Tidsåtgång']:.1f} timmar.")
            if sista["Tid kille"] < 9 or sista["Tid kille"] > 15:
                st.warning(f"⚠️ Tid kille: {sista['Tid kille']:.1f} minuter.")
    return df

def rensa_allt(df):
    if st.button("❌ Rensa allt"):
        if st.confirm("Är du säker på att du vill radera hela databasen?"):
            tom_df = pd.DataFrame(columns=ALL_COLUMNS)
            spara_data(tom_df)
            st.success("Alla rader raderade.")
            st.stop()

def huvudvy(df):
    st.title("📊 Statistik och sammanställning")
    statistikvy(df)
    st.divider()
    with st.expander("📥 Ny rad manuellt"):
        df = visa_manuellt_formular(df)
    st.divider()
    st.subheader("Snabbknappar")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎲 Slumpa film liten"):
            df = slumpa_film(df, storlek="liten")
    with col2:
        if st.button("🎲 Slumpa film stor"):
            df = slumpa_film(df, storlek="stor")
    with col3:
        if st.button("📋 Kopiera största raden"):
            df = kopiera_storsta_rad(df)

    st.divider()
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("🏠 Vilodag hemma"):
            df = vila_rutin(df, "hemma")
    with col5:
        if st.button("💼 Vilodag jobb"):
            df = vila_rutin(df, "jobb")
    with col6:
        if st.button("😴 Vilodag helt"):
            df = vila_rutin(df, "helt")
    st.divider()

    st.subheader("📋 Redigera tidigare rader")
    visa_redigeringsform(df)

    st.divider()
    rensa_allt(df)


def main():
    df = las_in_data()
    ensure_columns_exist(df)
    df = update_calculations(df)
    df = df[ALL_COLUMNS]  # Säkerställ kolumnordning

    huvudvy(df)


if __name__ == "__main__":
    main()
