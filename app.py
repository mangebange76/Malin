import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import random

# Autentisera Google Sheets
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# Ladda data och säkerställ rubriker
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Datum", "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
        "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta", "DeepT", "Grabbar",
        "Sekunder", "Varv",
        # Beräknade fält nedan, de kan ligga i sheet men räknas i kod
        "Känner", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils Fam 2", "Totalt män",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid",
        "Tid kille", "Suger", "Filmer", "Intäkter", "Malin lön", "Företag lön",
        "Vänner lön", "Hårdhet", "Snitt", "Total tid", "Tid kille DT", "Runk"
    ]

    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(rows=1)
        worksheet.append_row(headers)

    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df

# Uppdatera celler i en rad med dictionary {column_name: value}
def update_cells(worksheet, row_idx, updates):
    headers = worksheet.row_values(1)
    cells = []
    for col_name, val in updates.items():
        if col_name in headers:
            col_idx = headers.index(col_name) + 1
            cell = gspread.Cell(row_idx, col_idx, val)
            cells.append(cell)
    if cells:
        worksheet.update_cells(cells)

# Lägg till rad i Google Sheet
def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    headers = worksheet.row_values(1)
    row = [row_dict.get(h, 0) for h in headers]
    worksheet.append_row(row)

# Beräkna maxvärden för jobb 2 etc
def get_max_values(df):
    max_values = {}
    for col in ["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]:
        if col in df.columns and not df[col].empty:
            max_values[col + " 2"] = df[col].max()
        else:
            max_values[col + " 2"] = 0
    if all(x in df.columns for x in ["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]):
        df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
        max_values["Känner 2"] = df["Känner"].max() if not df["Känner"].empty else 0
    else:
        max_values["Känner 2"] = 0
    return max_values

# Beräkna alla fält enligt regler
def calculate_all(df):
    # Om df tom, returnera
    if df.empty:
        return df

    max_vals = get_max_values(df)

    # Känner = Jobb + Grannar + Tjej PojkV + Nils Fam
    df["Känner"] = df.get("Jobb", 0) + df.get("Grannar", 0) + df.get("Tjej PojkV", 0) + df.get("Nils Fam", 0)

    # Jobb 2, Grannar 2, Tjej PojkV 2, Nils Fam 2 (maxvärden)
    df["Jobb 2"] = max_vals["Jobb 2"]
    df["Grannar 2"] = max_vals["Grannar 2"]
    df["Tjej PojkV 2"] = max_vals["Tjej PojkV 2"]
    df["Nils Fam 2"] = max_vals["Nils Fam 2"]

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner"]

    # Summa singel = (Tid s + Vila) * Totalt män
    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]

    # Summa dubbel = ((Tid d + Vila) + 9) * (Dm + Df + Dr)
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])

    # Summa trippel = ((Tid t + Vila) + 15) * (TPP + TAP + TPA)
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["3f"] + df["3r"] + df["3p"])

    # Summa vila = (Totalt män * Vila) + (Dm+Df+Dr)*(Vila+7) + (TPP+TAP+TPA)*(Vila+15)
    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + (df["Dm"] + df["Df"] + df["Dr"]) * (df["Vila"] + 7) + \
                      (df["3f"] + df["3r"] + df["3p"]) * (df["Vila"] + 15)

    # Summa tid = sum singel + sum dubbel + sum trippel + sum vila
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    # Tid kille (sekunder) = Summa singel + 2*Summa dubbel + 3*Summa trippel delat på Totalt män
    df["Tid kille"] = (df["Summa singel"] + 2 * df["Summa dubbel"] + 3 * df["Summa trippel"]) / df["Totalt män"].replace(0, 1)

    # Suger = 60% av (Summa singel + Summa dubbel + Summa trippel) / Totalt män
    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, 1)

    # Lägg till suger i tid kille
    df["Tid kille"] += df["Suger"]

    # Hårdhet beräkning
    def beräkna_hårdhet(row):
        hårdhet = 0
        if row["Män"] > 0:
            hårdhet += 1
            if row["Dm"] > 0:
                hårdhet += 2
            if row["Df"] > 0:
                hårdhet += 2
            if row["Dr"] > 0:
                hårdhet += 4
            if row["3f"] > 0:
                hårdhet += 4
            if row["3r"] > 0:
                hårdhet += 6
            if row["3p"] > 0:
                hårdhet += 5
        return hårdhet

    df["Hårdhet"] = df.apply(beräkna_hårdhet, axis=1)

    # Filmer = (män + f + r + dm*2 + df*2 + dr*3 + tpp*4 + tap*6 + tpa*5) * hårdhet
    df["Filmer"] = (
        df["Män"] + df["F"] + df["R"] + df["Dm"] * 2 + df["Df"] * 2 + df["Dr"] * 3 +
        df["3f"] * 4 + df["3r"] * 6 + df["3p"] * 5
    ) * df["Hårdhet"]

    # Pris i dollar (fast)
    df["Pris"] = 19.99

    # Intäkter = filmer * pris
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Malin lön = 5% av intäkter max 1500 USD
    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    # Företagets lön = 40% av intäkter
    df["Företag lön"] = df["Intäkter"] * 0.4

    # Vänner lön = intäkter - malin lön - företagets lön
    df["Vänner lön"] = df["Intäkter"] - df["Malin lön"] - df["Företag lön"]

    # Snitt = DeepT / Grabbar (ersätt 0 med 1 för division)
    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)

    # Total tid = Snitt * (Sekunder * Varv)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])

    # Tid kille DT = Total tid / Totalt män
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)

    # Runk = 60% av Total tid / Totalt män
    df["Runk"] = 0.6 * df["Total tid"] / df["Totalt män"].replace(0, 1)

    # Lägg till runk till tid kille
    df["Tid kille"] += df["Runk"]

    return df

# Skapa nästa datum
def nästa_datum(df):
    if df.empty or "Datum" not in df.columns:
        return datetime.today().date()
    try:
        senaste = pd.to_datetime(df["Datum"], errors="coerce").dropna().max()
        return (senaste + timedelta(days=1)).date()
    except Exception:
        return datetime.today().date()

# Lägg till ny rad via formulär
def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        fält = [
            "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
            "Tid s", "Tid d", "Tid t", "Vila", "Älskar", "Älsk tid",
            "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
            "Svarta", "DeepT", "Grabbar", "Sekunder", "Varv"
        ]
        for f in fält:
            ny_rad[f] = st.number_input(f, min_value=0, step=1)
        ny_rad["Datum"] = nästa_datum(df).isoformat()
        submitted = st.form_submit_button("Spara")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Vilodag
def vilodag(df, jobb=True):
    ny_rad = {k:0 for k in [
        "Män", "F", "R", "Dm", "Df", "Dr", "3f", "3r", "3p",
        "Tid s", "Tid d", "Tid t", "Vila", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta",
        "DeepT", "Grabbar", "Sekunder", "Varv", "Älskar", "Älsk tid"
    ]}
    ny_rad["Datum"] = nästa_datum(df).isoformat()
    if jobb:
        ny_rad.update({
            "Älskar": 12,
            "Sover med": 1,
            "Jobb": df["Jobb"].max() if "Jobb" in df else 0,
            "Grannar": df["Grannar"].max() if "Grannar" in df else 0,
            "Tjej PojkV": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
            "Nils Fam": df["Nils Fam"].max() if "Nils Fam" in df else 0,
        })
    else:
        ny_rad.update({
            "Älskar": 6,
            "Sover med": 0,
            "Jobb": 3,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils Fam": 3,
        })
    append_row(ny_rad)
    st.success(f"✅ Vilodag {'jobb' if jobb else 'hemma'} tillagd.")

# Kopiera två rader med högst Totalt män
def kopiera_max(df):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Datum"] = nästa_datum(df).isoformat()
        append_row(ny)
    st.success("✅ Två rader kopierades från högsta Totalt män.")

# Presentation: Huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    totalt_män = df["Totalt män"].sum()
    känner_2 = df["Känner 2"].max() if "Känner 2" in df else 0
    jobb_2 = df["Jobb 2"].max() if "Jobb 2" in df else 0
    grannar_2 = df["Grannar 2"].max() if "Grannar 2" in df else 0
    tjej_pojkv_2 = df["Tjej PojkV 2"].max() if "Tjej PojkV 2" in df else 0
    nils_fam_2 = df["Nils Fam 2"].max() if "Nils Fam 2" in df else 0

    snitt_film = (totalt_män + df["Känner"].sum()) / max(1, len(df[df["Män"] > 0]))
    gangb = df["Känner"].sum() / max(1, känner_2)
    älskat = df["Älskar"].sum() / max(1, känner_2)
    sover_med = df["Sover med"].sum() / max(1, nils_fam_2)
    vita = (totalt_män - df["Svarta"].sum()) / max(1, totalt_män) * 100
    svarta = df["Svarta"].sum() / max(1, totalt_män) * 100

    filmer_summa = df["Filmer"].sum()
    intäkter_summa = df["Intäkter"].sum()
    malin_lön_summa = df["Malin lön"].sum()
    företag_lön_summa = df["Företag lön"].sum()
    vänner_lön_summa = df["Vänner lön"].sum() / max(1, känner_2)

    st.write(f"**Totalt antal män:** {totalt_män}")
    st.write(f"**Känner (Kompisar):** {känner_2}")
    st.write(f"**Jobb:** {jobb_2}")
    st.write(f"**Grannar:** {grannar_2}")
    st.write(f"**Tjej PojkV:** {tjej_pojkv_2}")
    st.write(f"**Nils Fam:** {nils_fam_2}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med:** {sover_med:.2f}")
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")
    st.write(f"**Filmer (totalt):** {filmer_summa}")
    st.write(f"**Intäkter (totalt):** ${intäkter_summa:.2f}")
    st.write(f"**Malin lön (totalt):** ${malin_lön_summa:.2f}")
    st.write(f"**Företagets lön (totalt):** ${företag_lön_summa:.2f}")
    st.write(f"**Vänner lön (per kompis):**
