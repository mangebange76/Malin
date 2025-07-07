import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# Autentisera Google Sheets
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
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

    if worksheet.row_values(1) != headers:
        worksheet.resize(rows=1)
        worksheet.append_row(headers)

    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df

# Lägg till ny rad
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

# Ny rad via formulär
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
        if st.form_submit_button("Spara"):
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen.")

# Vilodag
def vilodag(df, jobb=True):
    ny_rad = {
        "Dag": nästa_datum(df).isoformat(),
        "Älskar": 6,
        "Sover med": 1 if jobb else 0,
        "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3
    }
    append_row(ny_rad)
    st.success(f"✅ Vilodag {'jobb' if jobb else 'hemma'} tillagd.")

# Slumpknapp
def slumpmässig_rad(df):
    ny_rad = {}
    for col in df.columns:
        if col in ["Älskar"]:
            ny_rad[col] = 8
        elif col in ["Sover med"]:
            ny_rad[col] = 1
        elif col in ["Vila"]:
            ny_rad[col] = 7
        elif col in ["Älsk tid"]:
            ny_rad[col] = 30
        elif col == "Dag":
            ny_rad[col] = nästa_datum(df).isoformat()
        else:
            if df[col].dtype in ['int64', 'float64'] and df[col].max() > 0:
                ny_rad[col] = random.randint(0, int(df[col].max()))
            else:
                ny_rad[col] = 0
    append_row(ny_rad)
    st.success("✅ Slumprad tillagd.")

# Kopiera topp 2
def kopiera_max(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Dag"] = nästa_datum(df).isoformat()
        append_row(ny)
    st.success("✅ Två topp-rader kopierades.")

# Huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    kompisar = df["Känner"].max()
    snitt = (totalt_män + totalt_känner) / len(df[df["Män"] + df["Känner"] > 0])
    intäkter = df["3f"].sum() * 19.99
    malin_lön = min(1500, intäkter * 0.01)
    företag_lön = intäkter * 0.4
    vänner_lön = intäkter - malin_lön - företag_lön
    gangb = totalt_känner / kompisar if kompisar else 0
    sover_kvot = df["Sover med"].sum() / df["Nils Fam"].max() if df["Nils Fam"].max() else 0

    st.write(f"**Totalt män:** {totalt_män}")
    st.write(f"**Snitt (Män + Känner):** {snitt:.2f}")
    st.write(f"**Kompisar:** {kompisar}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Sover med / Nils Fam:** {sover_kvot:.2f}")
    st.write(f"**Intäkter:** ${intäkter:.2f}")
    st.write(f"**Malin lön:** ${malin_lön:.2f}")
    st.write(f"**Företag lön:** ${företag_lön:.2f}")
    st.write(f"**Vänner lön:** ${vänner_lön:.2f}")

# Radvyn
def radvy(df):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data.")
        return

    rad = df.iloc[-1]
    tid_kille = (rad["Tid s"] + rad["Tid d"] + rad["Tid t"]) / max(1, rad["Män"])
    st.write(f"**Tid kille:** {tid_kille:.2f} minuter {'⚠️' if tid_kille < 10 else ''}")

    if tid_kille < 10:
        with st.form("justera_tid"):
            rad["Tid s"] = st.number_input("Tid s", value=int(rad["Tid s"]), step=1)
            rad["Tid d"] = st.number_input("Tid d", value=int(rad["Tid d"]), step=1)
            rad["Tid t"] = st.number_input("Tid t", value=int(rad["Tid t"]), step=1)
            if st.form_submit_button("Spara ändring"):
                worksheet, _ = load_data()
                worksheet.update(f"K{len(df)+1}:M{len(df)+1}", [[rad["Tid s"], rad["Tid d"], rad["Tid t"]]])
                st.success("⏱️ Tider uppdaterade!")

    älskar_tid = rad["Älskar"] * rad["Älsk tid"]
    total_minuter = rad["Tid s"] + rad["Tid d"] + rad["Tid t"] + älskar_tid
    slut = (datetime(2025, 1, 1, 7, 0) + timedelta(minutes=total_minuter)).strftime("%H:%M")
    st.write(f"**Klockan:** {slut}")

# Kör app
def main():
    worksheet, df = load_data()

    st.sidebar.button("➕ Vilodag jobb", on_click=lambda: vilodag(df, True))
    st.sidebar.button("➕ Vilodag hemma", on_click=lambda: vilodag(df, False))
    st.sidebar.button("🎲 Slumprad", on_click=lambda: slumpmässig_rad(df))
    st.sidebar.button("📋 Kopiera 2 största", on_click=lambda: kopiera_max(df))

    inmatning(df)
    huvudvy(df)
    radvy(df)

if __name__ == "__main__":
    main()
