import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import json

# Inställningar
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"
KOLUMNER = [
    "Dag", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
    "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
]

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    rows = worksheet.get_all_values()
    if not rows or rows[0] != KOLUMNER:
        worksheet.clear()
        worksheet.append_row(KOLUMNER)
        return worksheet, pd.DataFrame(columns=KOLUMNER)
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df = df.replace("", 0)
    for col in KOLUMNER:
        if col == "Dag":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return worksheet, df

def spara_data(df, worksheet):
    worksheet.clear()
    worksheet.append_row(KOLUMNER)
    for _, row in df.iterrows():
        row = [row[kol] if kol in row else "" for kol in KOLUMNER]
        worksheet.append_row(row)

def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max(),
        "Grannar 2": df["Grannar"].max(),
        "Tjej PojkV 2": df["Tjej PojkV"].max(),
        "Nils Fam 2": df["Nils Fam"].max()
    }

def beräkna_radvärden(rad):
    tid_singel = rad["Tid s"]
    tid_dubbel = rad["Tid d"]
    tid_trippel = rad["Tid t"]
    vila = rad["Vila"]
    älskar = rad["Älskar"]
    älsk_tid = rad["Älsk tid"]

    dm = rad["Dm"]
    df = rad["Df"]
    dr = rad["Dr"]
    tpp = rad["3f"]
    tap = rad["3r"]
    tpa = rad["3p"]
    män = rad["Män"]
    känner = rad["Jobb"] + rad["Grannar"] + rad["Tjej PojkV"] + rad["Nils Fam"]
    totalt_män = män + känner

    sum_singel = tid_singel * (rad["F"] + rad["R"])
    sum_dubbel = tid_dubbel * (dm + df + dr)
    sum_trippel = tid_trippel * (tpp + tap + tpa)
    sum_vila = (totalt_män * vila) + (dm + df + dr) * (vila + 7) + (tpp + tap + tpa) * (vila + 15)
    summa_tid = sum_singel + sum_dubbel + sum_trippel + sum_vila + (älskar * älsk_tid)

    klockan = (datetime.strptime("07:00", "%H:%M") + timedelta(minutes=summa_tid // 60)).strftime("%H:%M")

    filmer = män
    intäkter = filmer * 19.99
    tid_kille = summa_tid / män if män > 0 else 0

    return {
        "Tid kille": tid_kille,
        "Filmer": filmer,
        "Intäkter": intäkter,
        "Klockan": klockan
    }

def presentera_huvudvy(df):
    st.header("📊 Huvudvy")

    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt Män"] = df["Män"] + df["Känner"]
    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()

    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0]) if len(df) > 0 else 0
    filmer = totalt_män
    intäkter = filmer * 19.99
    malin_lön = min(1500, intäkter * 0.01)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön

    maxvärden = get_max_values(df)
    gangb = totalt_känner / (maxvärden["Jobb 2"] + maxvärden["Grannar 2"] + maxvärden["Tjej PojkV 2"] + maxvärden["Nils Fam 2"]) if sum(maxvärden.values()) > 0 else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner > 0 else 0
    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0

    st.metric("Totalt Män", totalt_män)
    st.metric("Snitt (Män + Känner)", round(snitt, 2))
    st.metric("Intäkter", f"{intäkter:.2f} USD")
    st.metric("Malin lön", f"{malin_lön:.2f} USD")
    st.metric("Företag lön", f"{företag_lön:.2f} USD")
    st.metric("Vänner lön", f"{vänner_lön:.2f} USD")
    st.metric("GangB", f"{gangb:.2f}")
    st.metric("Älskat", f"{älskat:.2f}")
    st.metric("Vita (%)", f"{vita:.2f}%")
    st.metric("Svarta (%)", f"{svarta:.2f}%")

def presentera_radvy(df):
    st.header("📄 Radvy")
    if df.empty:
        st.info("Ingen data tillgänglig ännu.")
        return

    rad = df.iloc[-1]
    beräkning = beräkna_radvärden(rad)
    st.subheader(f"Senaste dag: {rad['Dag']}")
    st.write(f"**Tid kille:** {beräkning['Tid kille']:.2f} min" + (" ⚠️ Bör ökas!" if beräkning["Tid kille"] < 10 else ""))
    st.write(f"**Filmer:** {int(beräkning['Filmer'])}")
    st.write(f"**Intäkter:** {beräkning['Intäkter']:.2f} USD")
    st.write(f"**Klockan:** {beräkning['Klockan']}")

def lägg_till_rad(df, ny_rad, worksheet):
    ny_rad_df = pd.DataFrame([ny_rad], columns=KOLUMNER)
    df = pd.concat([df, ny_rad_df], ignore_index=True)
    spara_data(df, worksheet)
    st.success("Ny rad tillagd.")
    st.experimental_rerun()

def main():
    worksheet, df = load_data()

    # PRESENTATION
    presentera_huvudvy(df)
    presentera_radvy(df)

    # REDIGERA SENASTE RAD
    st.subheader("✏️ Redigera senaste rad (Tid s, d, t)")
    if not df.empty:
        senast = df.iloc[-1].copy()
        tid_s = st.number_input("Tid s", value=int(senast["Tid s"]), step=1)
        tid_d = st.number_input("Tid d", value=int(senast["Tid d"]), step=1)
        tid_t = st.number_input("Tid t", value=int(senast["Tid t"]), step=1)
        if st.button("Spara ändringar"):
            df.at[df.index[-1], "Tid s"] = tid_s
            df.at[df.index[-1], "Tid d"] = tid_d
            df.at[df.index[-1], "Tid t"] = tid_t
            spara_data(df, worksheet)
            st.success("Ändringar sparade.")
            st.experimental_rerun()

if __name__ == "__main__":
    main()
