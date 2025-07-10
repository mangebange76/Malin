import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import random
import datetime

st.set_page_config(page_title="MalinApp", layout="wide")

# Autentisering och koppling till Google Sheets
SHEET_URL = st.secrets["SHEET_URL"]
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=SCOPE)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

# Hämta data
def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

# Skriv data
def save_data(df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# Säkerställ att rätt kolumner finns
ALL_COLUMNS = [
    "Dag", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Nya killar", "Älskar", "Sover med", "Vila",
    "DM", "DF", "DA", "TPP", "TAP", "TP", "DeepT", "Sekunder", "Vila mun", "Varv",
    "Fitta", "Rumpa", "Dubbelmacka", "Trippel penet", "Svarta", "Omsättning 2027",
    "Tid singel", "Tid dubbel", "Tid trippel", "Snitt", "Tid mun", "Totalt män",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa tid", "Tid kille dt", "Tid kille",
    "Filmer", "Intäkter", "Malin lön", "Kompisars lön", "Hårdhet"
]

def ensure_columns_exist(df):
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = 0
    return df

# Hämta maxvärden från Dag = 0
def hamta_maxvarden(df):
    maxrad = df[df["Dag"] == 0]
    if maxrad.empty:
        return {"Jobb": 0, "Grannar": 0, "Tjej PojkV": 0, "Nils fam": 0}
    else:
        maxrad = maxrad.iloc[0]
        return {
            "Jobb": int(maxrad.get("Jobb", 0)),
            "Grannar": int(maxrad.get("Grannar", 0)),
            "Tjej PojkV": int(maxrad.get("Tjej PojkV", 0)),
            "Nils fam": int(maxrad.get("Nils fam", 0)),
        }

# Validera mot maxvärden
def validera_maxvarden(rad, maxvarden):
    fel = []
    for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        if int(rad.get(kolumn, 0)) > maxvarden.get(kolumn, 0):
            fel.append(f"{kolumn} överstiger maxvärdet ({rad.get(kolumn)} > {maxvarden.get(kolumn)})")
    return fel

# Visa formulär för att sätta maxvärden (Dag = 0)
def formulär_maxvärden(df):
    st.subheader("📊 Ange maxvärden (Dag = 0)")
    maxrad = df[df["Dag"] == 0].iloc[0] if not df[df["Dag"] == 0].empty else {}

    with st.form("maxvärdesformulär"):
        jobb = st.number_input("Max Jobb", value=int(maxrad.get("Jobb", 0)), step=1)
        grannar = st.number_input("Max Grannar", value=int(maxrad.get("Grannar", 0)), step=1)
        pojkv = st.number_input("Max Tjej PojkV", value=int(maxrad.get("Tjej PojkV", 0)), step=1)
        nils = st.number_input("Max Nils fam", value=int(maxrad.get("Nils fam", 0)), step=1)
        submit = st.form_submit_button("Spara maxvärden")

    if submit:
        ny_rad = {col: 0 for col in ALL_COLUMNS}
        ny_rad.update({
            "Dag": 0,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": pojkv,
            "Nils fam": nils
        })
        df = df[df["Dag"] != 0]  # ta bort eventuell gammal rad
        df = pd.concat([pd.DataFrame([ny_rad]), df], ignore_index=True)
        save_data(df)
        st.success("Maxvärden sparade.")
        st.rerun()

    return df

def update_calculations(df):
    # Hämta maxvärden från Dag=0 för vänners uträkningar
    maxrad = df[df["Dag"] == 0]
    if not maxrad.empty:
        maxrad = maxrad.iloc[0]
        vänner = (
            maxrad.get("Jobb", 0) +
            maxrad.get("Grannar", 0) +
            maxrad.get("Tjej PojkV", 0) +
            maxrad.get("Nils fam", 0)
        )
    else:
        vänner = 0

    filmer = []
    intakter = []
    malin_lon = []
    vanners_lon = []
    kompisars_aktievarde_total = []
    kompisars_aktievarde_per_person = []
    snitt_film = []
    alskat = []
    tidsatgang_timmar = []
    tid_kille_minuter = []

    for _, row in df.iterrows():
        if row["Dag"] == 0:
            # Tomma beräkningar för maxrad
            filmer.append(0)
            intakter.append(0)
            malin_lon.append(0)
            vanners_lon.append(0)
            kompisars_aktievarde_total.append(0)
            kompisars_aktievarde_per_person.append(0)
            snitt_film.append(0)
            alskat.append(0)
            tidsatgang_timmar.append(0)
            tid_kille_minuter.append(0)
            continue

        män = int(row.get("Män", 0))
        fitta = int(row.get("Fitta", 0))
        röv = int(row.get("Röv", 0))
        dm = int(row.get("DM", 0))
        df2 = int(row.get("DF", 0))
        da = int(row.get("DA", 0))
        tpp = int(row.get("TPP", 0))
        tap = int(row.get("TAP", 0))
        tp = int(row.get("TP", 0))

        hårdhet = 0
        if män > 0: hårdhet += 1
        if dm > 0: hårdhet += 2
        if df2 > 0: hårdhet += 3
        if da > 0: hårdhet += 4
        if tpp > 0: hårdhet += 5
        if tap > 0: hårdhet += 7
        if tp > 0: hårdhet += 6

        filmer_i_rad = (män + fitta + röv + 2 * dm + 2 * df2 + 3 * da + 4 * tpp + 6 * tap + 5 * tp) * hårdhet
        filmer.append(filmer_i_rad)

        total_intakt = filmer_i_rad * 39.99
        intakter.append(total_intakt)

        malin = min(total_intakt * 0.01, 700)
        malin_lon.append(malin)

        v_lön = total_intakt / vänner if vänner > 0 else 0
        vanners_lon.append(v_lön)

        # Aktievärde
        if vänner > 0:
            senaste_kurs = df[df["Aktuell kurs"] > 0]["Aktuell kurs"].iloc[-1] if not df[df["Aktuell kurs"] > 0].empty else 0
            total_aktievarde = 5000 * senaste_kurs
            kompisars_aktievarde_total.append(total_aktievarde)
            kompisars_aktievarde_per_person.append(round(total_aktievarde / vänner, 2))
        else:
            kompisars_aktievarde_total.append(0)
            kompisars_aktievarde_per_person.append(0)

        # Snitt film och älskat
        df_valid = df[(df["Män"] > 0) & (df["Dag"] != 0)]
        total_killar = df_valid["Män"].sum()
        snitt_f = (total_killar + vänner) / len(df_valid) if not df_valid.empty else 0
        snitt_film.append(snitt_f)

        alskar = df["Älskar"].sum()
        alskat.append(alskar / vänner if vänner > 0 else 0)

        # Tidsåtgång: singel/dubbel/trippel och mun och sover med
        tid_singel = (män + fitta + röv) * (int(row.get("Vila", 0)))
        tid_dubbel = (dm + df2 + da) * (int(row.get("Vila", 0)) + 8)
        tid_trippel = (tpp + tap + tp) * (int(row.get("Vila", 0)) + 15)

        deept = int(row.get("DeepT", 0))
        sek = int(row.get("Sekunder", 0))
        varv = int(row.get("Varv", 0))
        vila_mun = int(row.get("Vila mun", 0))
        män_raden = int(row.get("Män", 0))
        snitt = deept / män_raden if män_raden > 0 else 0
        tid_mun = (snitt * sek + vila_mun) * varv

        sover_med = int(row.get("Sover med", 0)) * 1800
        alskar_tid = int(row.get("Älskar", 0)) * 1800

        summa_tid = tid_singel + tid_dubbel + tid_trippel + tid_mun + sover_med + alskar_tid
        tidsatgang_timmar.append(round(summa_tid / 3600, 2))

        tid_kille_dt = 0
        if män + vänner > 0:
            tid_kille_dt = snitt * sek * varv / (män + vänner)
        tid_kille = tid_singel + tid_dubbel * 2 + tid_trippel * 3 + tid_mun + tid_kille_dt
        tid_kille_minuter.append(round(tid_kille / 60, 1))

    df["Filmer"] = filmer
    df["Intäkter"] = intakter
    df["Malin lön"] = malin_lon
    df["Vänners lön"] = vanners_lon
    df["Kompisars aktievärde"] = kompisars_aktievarde_total
    df["Kompisars aktievärde per person"] = kompisars_aktievarde_per_person
    df["Snitt film"] = snitt_film
    df["Älskat"] = alskat
    df["Tidsåtgång (h)"] = tidsatgang_timmar
    df["Tid kille (min)"] = tid_kille_minuter

    return df

def formulär_maxvärden(df, worksheet):
    st.subheader("📏 Ange maxvärden för kompisar (Dag = 0)")

    dag0 = df[df["Dag"] == 0]
    initial_values = dag0.iloc[0] if not dag0.empty else {}

    with st.form("maxvarden_form"):
        jobb = st.number_input("Max Jobb", min_value=0, value=int(initial_values.get("Jobb", 0)))
        grannar = st.number_input("Max Grannar", min_value=0, value=int(initial_values.get("Grannar", 0)))
        tjejpojkv = st.number_input("Max Tjej PojkV", min_value=0, value=int(initial_values.get("Tjej PojkV", 0)))
        nilsfam = st.number_input("Max Nils fam", min_value=0, value=int(initial_values.get("Nils fam", 0)))
        submit = st.form_submit_button("Spara maxvärden")

    if submit:
        new_row = {
            "Dag": 0,
            "Jobb": jobb,
            "Grannar": grannar,
            "Tjej PojkV": tjejpojkv,
            "Nils fam": nilsfam
        }
        df = df[df["Dag"] != 0]  # Ta bort gammal maxrad
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Maxvärden uppdaterade.")
        st.experimental_rerun()


def ny_rad_manuellt(df, worksheet):
    st.subheader("➕ Lägg till ny rad manuellt")

    # Visa maxvärden för användaren
    dag0 = df[df["Dag"] == 0]
    if not dag0.empty:
        maxrad = dag0.iloc[0]
        st.info(f"Maxvärden: Jobb={maxrad['Jobb']}, Grannar={maxrad['Grannar']}, Tjej PojkV={maxrad['Tjej PojkV']}, Nils fam={maxrad['Nils fam']}")
    else:
        st.warning("Du måste först ange maxvärden innan du kan lägga till ny rad.")
        return

    with st.form("manual_input_form"):
        ny_rad = {}
        for col in ALL_COLUMNS:
            if col == "Dag":
                ny_rad[col] = st.number_input(col, min_value=1, step=1)
            elif col in KOL_FÖRVALDA:
                ny_rad[col] = st.number_input(col, min_value=0, step=1, value=0)
        submit = st.form_submit_button("Spara rad")

    if submit:
        # Validera mot max
        for kolumn in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
            if ny_rad.get(kolumn, 0) > maxrad.get(kolumn, 0):
                st.error(f"{kolumn}-värdet överskrider maxvärdet. Uppdatera maxvärden först.")
                return

        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = update_calculations(df)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Rad sparad.")
        # Varningar efter spara
        varna_om_tider(df.iloc[-1])


def varna_om_tider(rad):
    tid_kille = rad.get("Tid kille (min)", 0)
    summa_tid = rad.get("Tidsåtgång (h)", 0)

    if summa_tid > 17:
        st.warning(f"Tidsåtgång är {summa_tid} timmar – över 17h.")
    if tid_kille < 9 or tid_kille > 15:
        st.warning(f"Tid kille är {tid_kille} minuter – utanför 9–15 min.")

def statistikvy(df):
    st.subheader("📊 Statistik")

    df_data = df[df["Dag"] != 0].copy()

    totalt_män = df_data["Män"].sum()
    totalt_filmer = df_data["Filmer"].sum()
    totalt_alskar = df_data["Älskar"].sum()
    totalt_sovermed = df_data["Sover med"].sum()
    totalt_nyakillar = df_data["Nya killar"].sum()
    totalt_vanner = df_data["Känner"].sum()

    tot_intakter = df_data["Intäkter (USD)"].sum()
    tot_malinlon = df_data["Malin lön (USD)"].sum()

    st.markdown(f"- **Totalt antal män:** {totalt_män}")
    st.markdown(f"- **Totalt antal filmer:** {totalt_filmer}")
    st.markdown(f"- **Totalt antal älskat:** {totalt_alskar}")
    st.markdown(f"- **Totalt 'sover med':** {totalt_sovermed}")
    st.markdown(f"- **Totalt nya killar:** {totalt_nyakillar}")
    st.markdown(f"- **Totalt kompisar (känner):** {totalt_vanner}")
    st.markdown(f"- **Totala intäkter:** ${round(tot_intakter, 2)}")
    st.markdown(f"- **Malins lön (totalt):** ${round(tot_malinlon, 2)}")

    if (totalt_alskar + totalt_sovermed + totalt_nyakillar + totalt_vanner) > 0:
        roi = tot_malinlon / (totalt_alskar + totalt_sovermed + totalt_nyakillar + totalt_vanner)
        st.markdown(f"- **Malin ROI per man:** ${round(roi, 2)}")
    else:
        st.markdown("- **Malin ROI per man:** -")

    # Aktievärde
    if not df_data.empty:
        sista_raden = df_data.iloc[-1]
        aktiekurs = sista_raden.get("Aktuell kurs", 0)
        vänner = sista_raden.get("Känner", 0)
        totalt_aktievärde = 5000 * aktiekurs
        per_person = totalt_aktievärde / vänner if vänner else 0

        st.markdown(f"- **Kompisars aktievärde (totalt):** ${round(totalt_aktievärde, 2)}")
        st.markdown(f"- **Kompisars aktievärde per person:** ${round(per_person, 2)}")


def uppdatera_aktuell_kurs(df):
    if "Aktuell kurs" in df.columns and not df.empty:
        sista_raden = df[df["Dag"] != 0].iloc[-1]
        try:
            kurs = float(sista_raden["Aktuell kurs"])
            df["Aktuell kurs"] = kurs
        except:
            df["Aktuell kurs"] = 0
    return df

def slumpa_film_liten(df):
    st.subheader("🎲 Slumpa Film liten")
    if df.empty:
        st.warning("Ingen data att basera slumpen på.")
        return

    maxrad = hamta_maxvarden(df)
    ny_rad = {
        "Dag": hamta_nasta_dag(df),
        "Jobb": random.randint(1, maxrad.get("Jobb", 1)),
        "Grannar": random.randint(0, maxrad.get("Grannar", 1)),
        "Tjej PojkV": random.randint(0, maxrad.get("Tjej PojkV", 1)),
        "Nils fam": random.randint(0, maxrad.get("Nils fam", 1)),
        "Män": random.randint(1, 2),
        "Fitta": random.randint(0, 1),
        "Röv": 0,
        "DM": 0,
        "DF": 0,
        "DA": 0,
        "TPP": 0,
        "TAP": 0,
        "TP": 0,
        "DeepT": 1,
        "Sekunder": 60,
        "Varv": 1,
        "Vila": 5,
        "Vila mun": 3,
        "Sover med": 1,
        "Älskar": 1,
        "Nya killar": 1,
        "Aktuell kurs": 0,
        "Svarta": 0,
        "Omsättning 2027": 0
    }
    visa_redigeringsformulär(df, ny_rad)


def slumpa_film_stor(df):
    st.subheader("🎲 Slumpa Film stor")
    if df.empty:
        st.warning("Ingen data att basera slumpen på.")
        return

    maxrad = hamta_maxvarden(df)
    ny_rad = {
        "Dag": hamta_nasta_dag(df),
        "Jobb": random.randint(1, maxrad.get("Jobb", 1)),
        "Grannar": random.randint(0, maxrad.get("Grannar", 1)),
        "Tjej PojkV": random.randint(0, maxrad.get("Tjej PojkV", 1)),
        "Nils fam": random.randint(0, maxrad.get("Nils fam", 1)),
        "Män": random.randint(2, 4),
        "Fitta": random.randint(1, 2),
        "Röv": random.randint(0, 2),
        "DM": random.randint(0, 1),
        "DF": random.randint(0, 1),
        "DA": random.randint(0, 1),
        "TPP": random.randint(0, 1),
        "TAP": random.randint(0, 1),
        "TP": random.randint(0, 1),
        "DeepT": 2,
        "Sekunder": 90,
        "Varv": 2,
        "Vila": 7,
        "Vila mun": 5,
        "Sover med": 1,
        "Älskar": 2,
        "Nya killar": 2,
        "Aktuell kurs": 0,
        "Svarta": 0,
        "Omsättning 2027": 0
    }
    visa_redigeringsformulär(df, ny_rad)


def vilodag_hemma(df):
    st.subheader("🛋️ Vilodag hemma")
    ny_rad = {
        "Dag": hamta_nasta_dag(df),
        "Jobb": 0,
        "Grannar": 0,
        "Tjej PojkV": 0,
        "Nils fam": 0,
        "Män": 0,
        "Fitta": 0,
        "Röv": 0,
        "DM": 0,
        "DF": 0,
        "DA": 0,
        "TPP": 0,
        "TAP": 0,
        "TP": 0,
        "DeepT": 0,
        "Sekunder": 0,
        "Varv": 0,
        "Vila": 0,
        "Vila mun": 0,
        "Sover med": 0,
        "Älskar": 0,
        "Nya killar": 0,
        "Aktuell kurs": 0,
        "Svarta": 0,
        "Omsättning 2027": 0
    }
    visa_redigeringsformulär(df, ny_rad)


def vilodag_jobb(df):
    st.subheader("🏢 Vilodag jobb")
    maxrad = hamta_maxvarden(df)
    ny_rad = {
        "Dag": hamta_nasta_dag(df),
        "Jobb": round(maxrad.get("Jobb", 0) * 0.3),
        "Grannar": round(maxrad.get("Grannar", 0) * 0.3),
        "Tjej PojkV": round(maxrad.get("Tjej PojkV", 0) * 0.3),
        "Nils fam": round(maxrad.get("Nils fam", 0) * 0.3),
        "Män": 0,
        "Fitta": 0,
        "Röv": 0,
        "DM": 0,
        "DF": 0,
        "DA": 0,
        "TPP": 0,
        "TAP": 0,
        "TP": 0,
        "DeepT": 0,
        "Sekunder": 0,
        "Varv": 0,
        "Vila": 0,
        "Vila mun": 0,
        "Sover med": 0,
        "Älskar": 0,
        "Nya killar": 0,
        "Aktuell kurs": 0,
        "Svarta": 0,
        "Omsättning 2027": 0
    }
    visa_redigeringsformulär(df, ny_rad)


def kopiera_storsta_raden(df):
    st.subheader("📋 Kopiera största raden")
    if df.empty:
        st.warning("Ingen data att kopiera från.")
        return
    rad = df[df["Män"] == df["Män"].max()].iloc[-1].to_dict()
    rad["Dag"] = hamta_nasta_dag(df)
    visa_redigeringsformulär(df, rad)

def main():
    st.set_page_config(page_title="MalinApp", layout="wide")
    st.title("📊 Malin Dataanalys")

    try:
        df = las_in_data()
        df = update_calculations(df)
        ensure_columns_exist(df)
    except Exception as e:
        st.error(f"Fel vid inläsning: {e}")
        return

    menyval = st.sidebar.radio("📂 Meny", ["Statistik", "Ny rad manuellt", "Slumpa Film liten", "Slumpa Film stor", "Vilodag hemma", "Vilodag jobb", "Kopiera största raden"])

    if menyval == "Statistik":
        statistikvy(df)
    elif menyval == "Ny rad manuellt":
        maxrad = hamta_maxvarden(df)
        if maxrad.empty or maxrad[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum().sum() == 0:
            st.warning("❗ Du måste först lägga in maxvärden (Dag = 0) innan du kan lägga till andra rader.")
            visa_maxvarde_formular(df)
        else:
            st.subheader("📝 Lägg till ny rad manuellt")
            ny_rad = {col: 0 for col in ALL_COLUMNS}
            ny_rad["Dag"] = hamta_nasta_dag(df)
            visa_redigeringsformulär(df, ny_rad)
    elif menyval == "Slumpa Film liten":
        slumpa_film_liten(df)
    elif menyval == "Slumpa Film stor":
        slumpa_film_stor(df)
    elif menyval == "Vilodag hemma":
        vilodag_hemma(df)
    elif menyval == "Vilodag jobb":
        vilodag_jobb(df)
    elif menyval == "Kopiera största raden":
        kopiera_storsta_raden(df)


if __name__ == "__main__":
    main()
