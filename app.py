import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Autentisera Google Sheets
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scope)
    client = gspread.authorize(creds)
    return client

# Ladda och säkerställ rubriker
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
        "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid",
        "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
        "Svarta", "Dag"
    ]

    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(rows=1)
        worksheet.append_row(headers)

    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df

# Spara ny rad till Google Sheet
def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    worksheet.append_row([row_dict.get(col, 0) for col in worksheet.row_values(1)])

# Hämta nästa datum
def nästa_datum(df):
    if df.empty or "Dag" not in df.columns:
        return datetime.today().date()
    try:
        senaste = pd.to_datetime(df["Dag"], errors="coerce").dropna().max()
        return (senaste + timedelta(days=1)).date()
    except:
        return datetime.today().date()

# Summera specifika kolumner
def summera(df, kolumner):
    return sum(df[k] for k in kolumner if k in df.columns)

# Hämta maxvärden för beräkning
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df else 0,
        "Känner 2": (df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]).max()
    }

# Lägg till ny rad via formulär
def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        for fält in [
            "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
            "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid",
            "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta"
        ]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        ny_rad["Dag"] = nästa_datum(df).isoformat()
        submitted = st.form_submit_button("Spara")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Lägg till vilodag
def vilodag(df, jobb=True):
    ny_rad = {
        "Dag": nästa_datum(df).isoformat(),
        "Älskar": 6,
        "Sover med": 1 if jobb else 0,
        "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3
    }
    append_row(ny_rad)
    st.success(f"✅ Vilodag {'jobb' if jobb else 'hemma'} tillagd.")

# Kopiera två rader med flest Totalt män
def kopiera_max(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Dag"] = nästa_datum(df).isoformat()
        append_row(ny)
        df = df.append(ny, ignore_index=True)
    st.success("✅ Två rader kopierades från högsta Totalt män.")

# Huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    intäkter = df["3f"].sum() * 19.99
    malin_lön = min(1500, intäkter * 0.01)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön

    maxvärden = get_max_values(df)
    gangb = totalt_känner / sum(maxvärden.values()) if sum(maxvärden.values()) > 0 else 0
    älskat = df["Älskar"].sum() / totalt_känner if totalt_känner > 0 else 0
    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0
    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])
    kompisar = maxvärden["Känner 2"]
    sover_med_kvot = df["Sover med"].sum() / maxvärden["Nils Fam 2"] if maxvärden["Nils Fam 2"] else 0

    st.write(f"**Totalt män:** {totalt_män}")
    st.write(f"**Snitt (Män + Känner):** {snitt:.2f}")
    st.write(f"**Intäkter:** ${intäkter:.2f}")
    st.write(f"**Malin lön:** ${malin_lön:.2f}")
    st.write(f"**Företag lön:** ${företag_lön:.2f}")
    st.write(f"**Vänner lön:** ${vänner_lön:.2f}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")
    st.write(f"**Kompisar:** {kompisar}")
    st.write(f"**Sover med / Nils Fam 2:** {sover_med_kvot:.2f}")

# Radvyn
def radvy(df):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    rad = df.iloc[-1]
    tid_kille = (rad["Tid s"] + rad["Tid d"] + rad["Tid t"]) / max(1, rad["Män"])
    st.write(f"**Tid kille:** {tid_kille:.2f} minuter {'⚠️' if tid_kille < 10 else ''}")
    st.write(f"**Filmer:** {int(rad['3f'])}")
    st.write(f"**Intäkter:** ${rad['3f'] * 19.99:.2f}")

    total_tid = rad["Tid s"] + rad["Tid d"] + rad["Tid t"]
    älskar_tid = rad["Älskar"] * rad["Älsk tid"]
    total_minuter = total_tid + älskar_tid
    slut = (datetime(2025, 1, 1, 7, 0) + timedelta(minutes=total_minuter)).strftime("%H:%M")
    st.write(f"**Klockan:** {slut}")

    if tid_kille < 10:
        with st.form("justera_tid"):
            rad["Tid s"] = st.number_input("Tid s", value=int(rad["Tid s"]), step=1)
            rad["Tid d"] = st.number_input("Tid d", value=int(rad["Tid d"]), step=1)
            rad["Tid t"] = st.number_input("Tid t", value=int(rad["Tid t"]), step=1)
            if st.form_submit_button("Spara ändring"):
                client = auth_gspread()
                sheet = client.open_by_url(st.secrets["SHEET_URL"])
                worksheet = sheet.worksheet("Blad1")
                worksheet.update(f"K{len(df)+1}:M{len(df)+1}", [[rad["Tid s"], rad["Tid d"], rad["Tid t"]]])
                st.success("⏱️ Tider uppdaterade!")

# Huvudfunktion
def main():
    worksheet, df = load_data()

    # Knappfunktioner
    if st.button("➕ Lägg till vilodag jobb"):
        vilodag(df, jobb=True)
    if st.button("➕ Lägg till vilodag hemma"):
        vilodag(df, jobb=False)
    if st.button("📋 Kopiera två största"):
        kopiera_max(df)

    # Formulär för manuell inmatning
    inmatning(df)

    # Presentation
    huvudvy(df)
    radvy(df)

if __name__ == "__main__":
    main()
