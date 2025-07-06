import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# Konstanter
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"
STARTTID = timedelta(hours=7)

# Autentisering
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
    return gspread.authorize(creds)

# Ladda data och skapa rubriker vid behov
def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)

    # Försök läsa data
    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except:
        df = pd.DataFrame()

    # Rätt rubriker
    expected_columns = [
        'Dag', 'Män', 'F', 'R', 'Dm', 'Df', 'Dr',
        '3f', '3r', '3p', 'Tid s', 'Tid d', 'Tid t', 'Vila',
        'Älskar', 'Älsk tid', 'Sover med', 'Jobb', 'Grannar',
        'Tjej PojkV', 'Nils Fam', 'Svarta'
    ]
    if df.empty or list(df.columns) != expected_columns:
        worksheet.clear()
        worksheet.append_row(expected_columns)
        df = pd.DataFrame(columns=expected_columns)
    return worksheet, df

# Spara ny rad
def append_row(worksheet, row_dict):
    worksheet.append_row([row_dict.get(col, 0) for col in worksheet.row_values(1)])

# Beräkna värden
def beräkna_rad(row):
    dm = row.get("Dm", 0)
    df_ = row.get("Df", 0)
    dr = row.get("Dr", 0)
    tpp = row.get("3f", 0)
    tap = row.get("3r", 0)
    tpa = row.get("3p", 0)

    tid_s = row.get("Tid s", 0)
    tid_d = row.get("Tid d", 0)
    tid_t = row.get("Tid t", 0)
    vila = row.get("Vila", 0)
    älskar = row.get("Älskar", 0)
    älsk_tid = row.get("Älsk tid", 0)

    män = row.get("Män", 0)
    känner = row.get("Jobb", 0) + row.get("Grannar", 0) + row.get("Tjej PojkV", 0) + row.get("Nils Fam", 0)

    summa_singel = tid_s * (row.get("F", 0) + row.get("R", 0))
    summa_dubbel = tid_d * (dm + df_ + dr)
    summa_trippel = tid_t * (tpp + tap + tpa)
    summa_vila = (män * vila) + (dm + df_ + dr) * (vila + 7) + (tpp + tap + tpa) * (vila + 15)
    total_tid = summa_singel + summa_dubbel + summa_trippel + summa_vila + (älskar * älsk_tid)
    klockan = STARTTID + timedelta(minutes=total_tid / 60)

    filmer = män
    intäkter = filmer * 19.99
    malin_lön = min(intäkter * 0.01, 1500)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön

    tid_kille = round(total_tid / män / 60, 2) if män else 0

    return {
        "Tid kille": tid_kille,
        "Filmer": filmer,
        "Intäkter": intäkter,
        "Malin lön": malin_lön,
        "Företag lön": företag_lön,
        "Vänner lön": vänner_lön,
        "Klockan": klockan.strftime("%H:%M")
    }

# Presentera huvudvy
def presentera_huvudvy(df):
    st.subheader("📊 Huvudvy")
    df = df.copy()
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])

    intäkter = df["Män"].sum() * 19.99
    malin = min(intäkter * 0.01, 1500)
    företag = intäkter * 0.4
    vänner = intäkter - malin - företag

    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils Fam"].max()

    gangb = totalt_känner / (jobb2 + grannar2 + tjej2 + fam2) if jobb2 + grannar2 + tjej2 + fam2 else 0
    älskat = df["Älskar"].sum() / (df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]).sum()

    svarta = df["Svarta"].sum()
    vita_pct = round((totalt_män - svarta) / totalt_män * 100, 2) if totalt_män else 0
    svarta_pct = round(svarta / totalt_män * 100, 2) if totalt_män else 0

    st.markdown(f"**Totalt män:** {totalt_män}")
    st.markdown(f"**Snitt (Män + Känner):** {snitt:.2f} per rad")
    st.markdown(f"**Intäkter:** {intäkter:.2f} USD")
    st.markdown(f"**Malin lön:** {malin:.2f} USD")
    st.markdown(f"**Företag lön:** {företag:.2f} USD")
    st.markdown(f"**Vänner lön:** {vänner:.2f} USD")
    st.markdown(f"**GangB:** {gangb:.2f}")
    st.markdown(f"**Älskat:** {älskat:.2f}")
    st.markdown(f"**Vita (%):** {vita_pct}%")
    st.markdown(f"**Svarta (%):** {svarta_pct}%")

# Presentera senaste rad
def presentera_senaste_rad(df):
    if df.empty:
        return
    st.subheader("🧾 Senaste rad")
    rad = df.iloc[-1]
    värden = beräkna_rad(rad)

    for nyckel, värde in värden.items():
        if nyckel == "Tid kille":
            if värde < 10:
                st.markdown(f"**{nyckel}:** ⚠️ {värde:.2f} min (öka tiden!)")
            else:
                st.markdown(f"**{nyckel}:** {värde:.2f} min")
        else:
            st.markdown(f"**{nyckel}:** {värde}")

# Ny rad
def ny_rad_input():
    st.subheader("➕ Lägg till ny rad")
    with st.form("ny_rad"):
        idag = datetime.today().date().isoformat()
        dag = st.text_input("Datum (YYYY-MM-DD)", idag)
        data = {f: st.number_input(f, min_value=0, step=1) for f in [
            "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
            "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
        ]}
        data["Dag"] = dag
        if st.form_submit_button("Spara ny rad"):
            return data
    return None

# Kopieringsfunktion
def kopiera_topp_två(df):
    df["Totalt män"] = df["Män"] + df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum(axis=1)
    topp = df.sort_values("Totalt män", ascending=False).head(2)
    return topp.drop(columns="Totalt män")

# Huvudfunktion
def main():
    st.title("🧠 MalinApp")

    worksheet, df = load_data()
    presentera_huvudvy(df)
    presentera_senaste_rad(df)

    # Lägg till ny rad
    ny = ny_rad_input()
    if ny:
        append_row(worksheet, ny)
        st.success("Ny rad tillagd!")

    # Kopiera två rader med högst Totalt män
    if st.button("📋 Kopiera 2 rader med högst Totalt män"):
        kopior = kopiera_topp_två(df)
        for _, row in kopior.iterrows():
            append_row(worksheet, row.to_dict())
        st.success("Kopior tillagda!")

    # Vilodag hemma
    if st.button("🏠 Vilodag hemma"):
        datum = (datetime.today() + timedelta(days=1)).date().isoformat()
        rad = {'Dag': datum, 'Jobb': 3, 'Grannar': 3, 'Tjej PojkV': 3, 'Nils Fam': 3,
               'Älskar': 6, 'Sover med': 0}
        append_row(worksheet, rad)
        st.success("Vilodag hemma tillagd!")

    # Vilodag jobb
    if st.button("💼 Vilodag jobb"):
        datum = (datetime.today() + timedelta(days=1)).date().isoformat()
        jobb2 = df["Jobb"].max()
        grannar2 = df["Grannar"].max()
        tjej2 = df["Tjej PojkV"].max()
        fam2 = df["Nils Fam"].max()
        rad = {
            'Dag': datum, 'Jobb': round(jobb2 * 0.5), 'Grannar': round(grannar2 * 0.5),
            'Tjej PojkV': round(tjej2 * 0.5), 'Nils Fam': round(fam2 * 0.5),
            'Älskar': 12, 'Sover med': 1
        }
        append_row(worksheet, rad)
        st.success("Vilodag jobb tillagd!")

if __name__ == "__main__":
    main()
