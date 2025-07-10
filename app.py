import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import random

st.set_page_config(page_title="Malin App", layout="wide")

# ======= Autentisering & Sheets Setup =======
def las_in_data():
    credentials = service_account.Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"])
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    return pd.DataFrame(data), worksheet

def spara_data(df, worksheet):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def ensure_columns_exist(df, worksheet, required_columns):
    for col in required_columns:
        if col not in df.columns:
            df[col] = 0
    if df.columns.tolist() != required_columns:
        df = df[required_columns]
        spara_data(df, worksheet)
    return df

# ======= Kolumner och Maxrad-funktioner =======
ALLA_KOLUMNER = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila",
    "DeepT", "Sekunder", "Vila mun", "Varv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Fitta", "Rumpa", "Svarta", "Tid singel", "Tid dubbel", "Tid trippel",
    "Tid mun", "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid",
    "Suger", "Tid kille dt", "Tid kille", "Hårdhet", "Filmer", "Intäkter",
    "Malin lön", "Kompisar lön", "Kompisar aktievärde", "Kompisar aktievärde/pers"
]

MANUELLA_FALT = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila",
    "DeepT", "Sekunder", "Vila mun", "Varv", "DM", "DF", "DA", "TPP", "TAP", "TP",
    "Fitta", "Rumpa", "Svarta", "Tid singel", "Tid dubbel", "Tid trippel"
]

def hamta_maxrad(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return pd.Series({k: 0 for k in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]})
    return maxrad.iloc[0]

def validera_maxvarden(rad, maxrad):
    for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if rad.get(kol, 0) > maxrad.get(kol, 0):
            return False, f"Värdet för '{kol}' ({rad[kol]}) överskrider maxvärdet ({maxrad[kol]})."
    return True, ""

# ======= Beräkningar och uppdatering av DataFrame =======
def update_calculations(df):
    df = df.copy()
    df.fillna(0, inplace=True)

    # Vänner (från Dag = 0)
    maxrad = hamta_maxrad(df)
    vänner = maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum()

    # Totalt män = nya killar + vänner
    df["Totalt män"] = df["Nya killar"] + vänner

    # Snitt
    df["Snitt"] = df["DeepT"] / df["Totalt män"].replace(0, 1)

    # Tid mun
    df["Tid mun"] = ((df["Snitt"] * df["Sekunder"]) + df["Vila mun"]) * df["Varv"]

    # Summa singel
    df["Summa singel"] = df["Vila"] * (df["Totalt män"] + df["Fitta"] + df["Rumpa"])

    # Summa dubbel
    df["Summa dubbel"] = (df["Vila"] + 8) * (df["DM"] + df["DF"] + df["DA"])

    # Summa trippel
    df["Summa trippel"] = (df["Vila"] + 15) * (df["TPP"] + df["TAP"] + df["TP"])

    # Suger = 60% av (summa singel + dubbel + trippel) / totalt män
    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, 1)

    # Tid kille dt = 0.25 × (summa singel + dubbel + trippel) / totalt män
    df["Tid kille dt"] = 0.25 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, 1)

    # Tid kille = Tid singel + (Tid dubbel × 2) + (Tid trippel × 3) + Suger + Tid kille dt + Tid mun
    df["Tid kille"] = (
        df["Tid singel"] +
        df["Tid dubbel"] * 2 +
        df["Tid trippel"] * 3 +
        df["Suger"] +
        df["Tid kille dt"] +
        df["Tid mun"]
    )

    # Summa tid (timmar) = Summa singel + dubbel + trippel + tid mun + älskar × 1800 sek + Sover med × 1800 sek
    df["Summa tid"] = (
        df["Summa singel"] +
        df["Summa dubbel"] +
        df["Summa trippel"] +
        df["Tid mun"] +
        df["Älskar"] * 1800 +
        df["Sover med"] * 1800
    ) / 3600  # omräkning till timmar

    # Hårdhet
    df["Hårdhet"] = (
        (df["Nya killar"] > 0).astype(int) +
        (df["DM"] > 0).astype(int) * 2 +
        (df["DF"] > 0).astype(int) * 3 +
        (df["DA"] > 0).astype(int) * 4 +
        (df["TPP"] > 0).astype(int) * 5 +
        (df["TAP"] > 0).astype(int) * 7 +
        (df["TP"] > 0).astype(int) * 6
    )

    # Filmer
    df["Filmer"] = (
        df["Totalt män"] + df["Fitta"] + df["Rumpa"] +
        df["DM"] * 2 + df["DF"] * 2 + df["DA"] * 3 +
        df["TPP"] * 4 + df["TAP"] * 6 + df["TP"] * 5
    ) * df["Hårdhet"]

    # Intäkter (filmäkta × 39.99 USD)
    df["Intäkter"] = df["Filmer"] * 39.99

    # Malin lön = 1% av intäkter, max 700
    df["Malin lön"] = df["Intäkter"] * 0.01
    df.loc[df["Malin lön"] > 700, "Malin lön"] = 700

    # Kompisar lön = intäkter / vänner
    df["Kompisar lön"] = df["Intäkter"] / vänner if vänner != 0 else 0

    # Kompisars aktievärde = 5000 aktier × senaste aktiekurs
    try:
        sista_kurs = df[df["Intäkter"] > 0]["Intäkter"].iloc[-1] / df[df["Intäkter"] > 0]["Filmer"].iloc[-1] / 39.99
        aktievärde = sista_kurs * 5000
        df["Kompisar aktievärde"] = aktievärde
        df["Kompisar aktievärde/pers"] = aktievärde / vänner if vänner != 0 else 0
    except:
        df["Kompisar aktievärde"] = 0
        df["Kompisar aktievärde/pers"] = 0

    return df

# ======= Formulär för maxvärden (Dag = 0) =======
def formulär_maxvärden(df):
    st.subheader("Steg 1: Ange maxvärden (Dag = 0)")
    maxrad = hamta_maxrad(df)
    with st.form("maxvärdesformulär"):
        jobb = st.number_input("Max Jobb", value=int(maxrad["Jobb"]), min_value=0)
        grannar = st.number_input("Max Grannar", value=int(maxrad["Grannar"]), min_value=0)
        tjej = st.number_input("Max Tjej PojkV", value=int(maxrad["Tjej PojkV"]), min_value=0)
        nils = st.number_input("Max Nils fam", value=int(maxrad["Nils fam"]), min_value=0)
        submitted = st.form_submit_button("Spara maxvärden")
        if submitted:
            df = df[df["Dag"] != 0]
            ny_rad = {"Dag": 0, "Jobb": jobb, "Grannar": grannar, "Tjej PojkV": tjej, "Nils fam": nils}
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            st.success("Maxvärden sparade.")
    return df


# ======= Formulär: Ny rad manuellt =======
def ny_rad_manuellt(df):
    st.subheader("Steg 2: Lägg till ny rad manuellt")
    maxrad = hamta_maxrad(df)
    with st.form("manuell_rad"):
        ny_rad = {"Dag": st.number_input("Dag", min_value=1, value=1)}
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                continue
            if kolumn in maxrad.index:
                ny_rad[kolumn] = st.number_input(f"{kolumn} (max {maxrad[kolumn]})", min_value=0, value=0, max_value=int(maxrad[kolumn]))
            else:
                ny_rad[kolumn] = st.number_input(kolumn, min_value=0, value=0)
        if st.form_submit_button("Spara rad"):
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
            st.success("Rad sparad.")
            df = update_calculations(df)
            visa_eventuella_varningar(df, ny_rad)
    return df


# ======= Redigeringsformulär för befintlig rad =======
def visa_redigeringsformulär(df, index):
    st.subheader("Redigera rad")
    rad = df.iloc[index]
    maxrad = hamta_maxrad(df)
    with st.form(f"redigera_{index}"):
        redigerad = {"Dag": st.number_input("Dag", min_value=1, value=int(rad["Dag"]))}
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                continue
            if kolumn in maxrad.index:
                redigerad[kolumn] = st.number_input(f"{kolumn} (max {maxrad[kolumn]})", min_value=0, value=int(rad.get(kolumn, 0)), max_value=int(maxrad[kolumn]))
            else:
                redigerad[kolumn] = st.number_input(kolumn, min_value=0, value=int(rad.get(kolumn, 0)))
        if st.form_submit_button("Spara redigerad rad"):
            df.iloc[index] = pd.Series(redigerad)
            df = update_calculations(df)
            st.success("Rad uppdaterad.")
            visa_eventuella_varningar(df, redigerad)
    return df

# ======= Knappar: Slumpa rad (liten/stor), Vila (jobb/helt/hemma), Kopiera största =======
def slumpa_rad(df, variant="liten"):
    maxrad = hamta_maxrad(df)
    ny_rad = {"Dag": int(df["Dag"].max()) + 1 if not df.empty else 1}
    for kolumn in ALL_COLUMNS:
        if kolumn == "Dag":
            continue
        if kolumn in maxrad.index:
            if variant == "liten":
                ny_rad[kolumn] = random.randint(0, max(1, int(maxrad[kolumn] * 0.3)))
            else:
                ny_rad[kolumn] = random.randint(0, int(maxrad[kolumn]))
        else:
            ny_rad[kolumn] = random.randint(0, 10)
    return ny_rad


def skapa_vilodag(df, typ="jobb"):
    maxrad = hamta_maxrad(df)
    ny_rad = {"Dag": int(df["Dag"].max()) + 1 if not df.empty else 1}
    for kolumn in ALL_COLUMNS:
        if kolumn == "Dag":
            continue
        if kolumn == "Vila":
            ny_rad[kolumn] = 7 if typ == "hemma" else 10
        elif typ == "jobb" and kolumn in maxrad.index:
            ny_rad[kolumn] = int(maxrad[kolumn] * 0.3)
        else:
            ny_rad[kolumn] = 0
    return ny_rad


def kopiera_storsta_rad(df):
    if "Män" not in df.columns:
        return None
    storsta = df[df["Dag"] != 0].sort_values(by="Män", ascending=False).head(1)
    if storsta.empty:
        return None
    ny_rad = storsta.iloc[0].to_dict()
    ny_rad["Dag"] = int(df["Dag"].max()) + 1
    return ny_rad


# ======= Funktion för att visa och spara en ny genererad rad =======
def visa_formulär_och_spara(df, ny_rad_dict):
    with st.form("redigera_genererad_rad"):
        st.subheader("Redigera innan spara")
        maxrad = hamta_maxrad(df)
        for kolumn in ALL_COLUMNS:
            if kolumn == "Dag":
                continue
            if kolumn in maxrad.index:
                ny_rad_dict[kolumn] = st.number_input(f"{kolumn} (max {maxrad[kolumn]})", min_value=0, value=int(ny_rad_dict.get(kolumn, 0)), max_value=int(maxrad[kolumn]))
            else:
                ny_rad_dict[kolumn] = st.number_input(kolumn, min_value=0, value=int(ny_rad_dict.get(kolumn, 0)))
        if st.form_submit_button("Spara rad"):
            df = pd.concat([df, pd.DataFrame([ny_rad_dict])], ignore_index=True)
            df = update_calculations(df)
            st.success("Rad sparad.")
            visa_eventuella_varningar(df, ny_rad_dict)
    return df


# ======= Varningssystem efter spara/redigering =======
def visa_eventuella_varningar(df, rad_dict):
    tid_kille = rad_dict.get("Tid kille", 0)
    summa_tid = rad_dict.get("Summa tid", 0)
    if summa_tid > 17:
        st.warning("⚠️ Summa tid överstiger 17 timmar.")
    if tid_kille < 9:
        st.warning("⚠️ Tid kille är under 9 minuter.")
    elif tid_kille > 15:
        st.warning("⚠️ Tid kille är över 15 minuter.")

# ======= Statistikvy =======
def statistikvy(df):
    if df.empty:
        st.info("Ingen data att visa.")
        return

    df = df[df["Dag"] != 0]
    st.subheader("📊 Statistik")

    totalt_filmer = df["Filmer"].sum()
    totalt_intakter = df["Totala intäkter"].sum()
    totalt_malins_lon = df["Malins lön"].sum()
    totalt_alskar = df["Älskar"].sum()
    totalt_sover_med = df["Sover med"].sum()
    totalt_män = df["Nya killar"].sum()
    totalt_vanner = df["Känner"].sum()

    antal_kompisar = totalt_vanner
    aktiekurs = 39.99
    aktievarde_totalt = aktiekurs * 5000
    aktievarde_per_person = aktievarde_totalt / antal_kompisar if antal_kompisar > 0 else 0

    total_tid = df["Summa tid"].sum()
    total_tid_minuter = total_tid * 60

    roi = 0
    if (totalt_alskar + totalt_sover_med + totalt_män + totalt_vanner) > 0:
        roi = totalt_malins_lon / (totalt_alskar + totalt_sover_med + totalt_män + totalt_vanner)

    st.write(f"🎬 **Totalt antal filmer:** {int(totalt_filmer)}")
    st.write(f"💰 **Totala intäkter:** {round(totalt_intakter, 2)} USD")
    st.write(f"🧍‍♀️ **Malins lön:** {round(totalt_malins_lon, 2)} USD")
    st.write(f"🧠 **Malin ROI per man:** {round(roi, 2)}")
    st.write(f"⏱️ **Total tidsåtgång:** {round(total_tid, 2)} timmar")
    st.write(f"👬 **Totalt antal män:** {int(totalt_män)}")
    st.write(f"❤️ **Totalt älskar:** {int(totalt_alskar)}")
    st.write(f"🛏️ **Totalt sover med:** {int(totalt_sover_med)}")
    st.write(f"🤝 **Kompisars lön:** {round(totalt_intakter / totalt_vanner, 2) if totalt_vanner else 0} USD")
    st.write(f"📈 **Kompisars aktievärde totalt:** {round(aktievarde_totalt, 2)} USD")
    st.write(f"📊 **Kompisars aktievärde per person:** {round(aktievarde_per_person, 2)} USD")


# ======= Huvudmeny =======
def huvudmeny(df):
    st.title("MalinApp 📒")

    menyval = st.sidebar.selectbox("Välj vy", ["Ny rad manuellt", "Statistik"])

    if menyval == "Statistik":
        statistikvy(df)
        return df

    # Visa formulär för maxvärden först (Dag = 0)
    if "Dag" not in df.columns or 0 not in df["Dag"].values:
        st.subheader("📌 Fyll i maxvärden för vänner (Dag = 0)")
        df = formulär_maxvärden(df)
        return df

    st.subheader("📝 Lägg till ny rad manuellt")
    df = formulär_ny_rad(df)

    st.markdown("### ➕ Andra sätt att lägga till rad:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎲 Slumpa Film liten"):
            rad = slumpa_rad(df, "liten")
            df = visa_formulär_och_spara(df, rad)
        if st.button("🛏️ Vilodag hemma"):
            rad = skapa_vilodag(df, "hemma")
            df = visa_formulär_och_spara(df, rad)
    with col2:
        if st.button("🎲 Slumpa Film stor"):
            rad = slumpa_rad(df, "stor")
            df = visa_formulär_och_spara(df, rad)
        if st.button("🏢 Vilodag jobb"):
            rad = skapa_vilodag(df, "jobb")
            df = visa_formulär_och_spara(df, rad)
    with col3:
        if st.button("😴 Vilodag helt"):
            rad = skapa_vilodag(df, "helt")
            df = visa_formulär_och_spara(df, rad)
        if st.button("📋 Kopiera största raden"):
            rad = kopiera_storsta_rad(df)
            if rad:
                df = visa_formulär_och_spara(df, rad)
            else:
                st.warning("Ingen rad att kopiera.")

    return df

# ======= Huvudfunktion =======
def main():
    # Ladda in data
    df = las_in_data()

    # Säkerställ att alla nödvändiga kolumner finns
    df = ensure_columns_exist(df)

    # Huvudmenyn
    df = huvudmeny(df)

    # Uppdatera beräkningar
    df = update_calculations(df)

    # Spara till Google Sheets
    spara_data(df)


# ======= Streamlit Startpunkt =======
if __name__ == "__main__":
    main()
