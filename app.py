# app.py
import streamlit as st
import pandas as pd
import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
WORKSHEET_NAME = "Blad1"

KOLUMNORDNING = [
    "Män", "F", "R", "Dm", "Df", "Dr",
    "3f", "3r", "3p", "Tid s", "Tid d", "Tid t",
    "Vila", "Älskar", "Älsk tid", "Sover med",
    "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta", "Dag"
]

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scope)
    return gspread.authorize(creds)

def load_data():
    gc = auth_gspread()
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty or list(df.columns) != KOLUMNORDNING:
        worksheet.clear()
        worksheet.append_row(KOLUMNORDNING)
        df = pd.DataFrame(columns=KOLUMNORDNING)
    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(KOLUMNORDNING)
    for _, row in df.iterrows():
        worksheet.append_row([row.get(k, 0) for k in KOLUMNORDNING])

def beräkna_tider(rad):
    singel = rad["Tid s"] * (rad["F"] + rad["R"])
    dubbel = rad["Tid d"] * (rad["Dm"] + rad["Df"] + rad["Dr"])
    trippel = rad["Tid t"] * (rad["3f"] + rad["3r"] + rad["3p"])
    vila = (
        (rad["Män"] + rad["Jobb"] + rad["Grannar"] + rad["Tjej PojkV"] + rad["Nils Fam"]) * rad["Vila"]
        + (rad["Dm"] + rad["Df"] + rad["Dr"]) * (rad["Vila"] + 7)
        + (rad["3f"] + rad["3r"] + rad["3p"]) * (rad["Vila"] + 15)
    )
    totalt = singel + dubbel + trippel + vila + rad["Älskar"] * rad["Älsk tid"] * 60
    return singel, dubbel, trippel, vila, totalt

def huvudvy(df):
    st.header("Huvudvy")
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])

    filmer = len(df[df["Män"] > 0])
    intäkter = filmer * 19.99
    malin_lön = min(intäkter * 0.01, 1500)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön

    jobb2 = df["Jobb"].max()
    grannar2 = df["Grannar"].max()
    tjej2 = df["Tjej PojkV"].max()
    fam2 = df["Nils Fam"].max()

    gangb = totalt_känner / (jobb2 + grannar2 + tjej2 + fam2) if (jobb2 + grannar2 + tjej2 + fam2) > 0 else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner > 0 else 0
    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0

    st.markdown(f"**Totalt män:** {totalt_män}")
    st.markdown(f"**Snitt (Män + Känner):** {snitt:.1f}")
    st.markdown(f"**Filmer:** {filmer}")
    st.markdown(f"**Intäkter:** ${intäkter:,.2f}")
    st.markdown(f"**Malin lön:** ${malin_lön:,.2f}")
    st.markdown(f"**Företag lön:** ${företag_lön:,.2f}")
    st.markdown(f"**Vänner lön:** ${vänner_lön:,.2f}")
    st.markdown(f"**GangB:** {gangb:.2f}")
    st.markdown(f"**Älskat:** {älskat:.2f}")
    st.markdown(f"**Vita (%):** {vita:.2f}")
    st.markdown(f"**Svarta (%):** {svarta:.2f}")

def radvy(df, worksheet):
    st.header("Radvyn (senaste raden)")
    if df.empty:
        st.warning("Ingen data.")
        return

    rad = df.iloc[-1].copy()
    st.markdown(f"**Datum:** {rad['Dag']}")
    tid_kille = (rad["Tid s"] * (rad["F"] + rad["R"]) +
                 rad["Tid d"] * (rad["Dm"] + rad["Df"] + rad["Dr"]) +
                 rad["Tid t"] * (rad["3f"] + rad["3r"] + rad["3p"])) / 60

    st.markdown(f"**Tid kille:** {tid_kille:.2f} min" + (" ⚠️ Justera tid!" if tid_kille < 10 else ""))

    rad["Tid s"] = st.number_input("Tid s", value=int(rad["Tid s"]), step=1)
    rad["Tid d"] = st.number_input("Tid d", value=int(rad["Tid d"]), step=1)
    rad["Tid t"] = st.number_input("Tid t", value=int(rad["Tid t"]), step=1)

    if st.button("Spara ändringar"):
        df.iloc[-1] = rad
        save_data(worksheet, df)
        st.success("Senaste raden uppdaterad!")

def lägg_till_data(worksheet, df, data):
    data["Dag"] = (pd.to_datetime(df["Dag"].max()) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.date.today().isoformat()
    ny_rad = pd.DataFrame([data])[KOLUMNORDNING]
    df = pd.concat([df, ny_rad], ignore_index=True)
    save_data(worksheet, df)

def knapp_vilodag(df, worksheet, typ):
    if df.empty:
        st.error("Ingen tidigare data finns.")
        return
    maxvärden = df.iloc[-1]
    ny = {k: 0 for k in KOLUMNORDNING}
    ny["Dag"] = (pd.to_datetime(df["Dag"].max()) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    if typ == "jobb":
        ny.update({
            "Jobb": round(df["Jobb"].max() * 0.5),
            "Grannar": round(df["Grannar"].max() * 0.5),
            "Tjej PojkV": round(df["Tjej PojkV"].max() * 0.5),
            "Nils Fam": round(df["Nils Fam"].max() * 0.5),
            "Älskar": 12, "Sover med": 1
        })
    elif typ == "hemma":
        ny.update({"Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3, "Älskar": 6, "Sover med": 0})

    ny_rad = pd.DataFrame([ny])[KOLUMNORDNING]
    df = pd.concat([df, ny_rad], ignore_index=True)
    save_data(worksheet, df)

def kopiera_största(df, worksheet):
    df["Totalt män"] = df["Män"] + df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    top2 = df.nlargest(2, "Totalt män")
    senaste_dag = pd.to_datetime(df["Dag"].max())
    nya_rader = []
    for i, (_, row) in enumerate(top2.iterrows(), start=1):
        ny = row.copy()
        ny["Dag"] = (senaste_dag + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        nya_rader.append(ny[KOLUMNORDNING])
    df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
    save_data(worksheet, df)

def main():
    st.title("Malin-appen 👩‍❤️‍👨")

    worksheet, df = load_data()
    huvudvy(df)
    radvy(df, worksheet)

    st.subheader("➕ Lägg till data manuellt")
    with st.form("manuell_inmatning"):
        ny_data = {k: st.number_input(k, value=0, step=1) for k in KOLUMNORDNING if k != "Dag"}
        submit = st.form_submit_button("Lägg till")
        if submit:
            lägg_till_data(worksheet, df, ny_data)
            st.success("Rad tillagd!")

    st.subheader("📌 Snabbknappar")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Vilodag jobb"):
            knapp_vilodag(df, worksheet, "jobb")
    with col2:
        if st.button("Vilodag hemma"):
            knapp_vilodag(df, worksheet, "hemma")
    with col3:
        if st.button("Kopiera 2 största rader"):
            kopiera_största(df, worksheet)
            st.success("Två rader kopierade!")

if __name__ == "__main__":
    main()
