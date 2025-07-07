import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisera Google Sheets
def auth_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Ladda data och säkerställ rubriker
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr",
        "TPP", "TAP", "TPA", "Älskar", "Sover med",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam",
        "Svarta", "DeepT", "Grabbar", "Sekunder", "Varv",
        "Tid s", "Tid d", "Tid t", "Vila",
        # Beräknade fält, behöver finnas i sheet för sparande/uppdatering:
        "Känner", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils Fam 2", "Totalt män",
        "Snitt", "Total tid", "Tid kille DT", "Runk",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid",
        "Klockan", "Tid kille", "Suger", "Filmer", "Intäkter",
        "Malin lön", "Företagets lön", "Vänner lön", "Hårdhet"
    ]

    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(rows=1)
        worksheet.update("A1", [headers])

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    return worksheet, df

# Spara rad till sheet
def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    cols = worksheet.row_values(1)
    row = [row_dict.get(c, 0) for c in cols]
    worksheet.append_row(row)

# Uppdatera celler i rad (för redigering)
def update_cells(worksheet, row_idx, updates: dict):
    cols = worksheet.row_values(1)
    updates_list = []
    for col, val in updates.items():
        if col in cols:
            col_idx = cols.index(col) + 1
            updates_list.append(gspread.Cell(row_idx, col_idx, val))
    if updates_list:
        worksheet.update_cells(updates_list)

# Beräkna maxvärden för 2:orna
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df.columns else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df.columns else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df.columns else 0,
        "Nils Fam 2": df["Nils Fam"].max() if "Nils Fam" in df.columns else 0,
        "Känner 2": 0
    }

# Utför alla beräkningar och uppdatera df
def calculate_all(df):
    # Känner
    df["Känner"] = df[["Jobb","Grannar","Tjej PojkV","Nils Fam"]].sum(axis=1)

    maxvals = get_max_values(df)
    maxvals["Känner 2"] = maxvals["Jobb 2"] + maxvals["Grannar 2"] + maxvals["Tjej PojkV 2"] + maxvals["Nils Fam 2"]

    df["Jobb 2"] = maxvals["Jobb 2"]
    df["Grannar 2"] = maxvals["Grannar 2"]
    df["Tjej PojkV 2"] = maxvals["Tjej PojkV 2"]
    df["Nils Fam 2"] = maxvals["Nils Fam 2"]

    df["Totalt män"] = df["Män"] + df["Känner"]

    df["Snitt"] = df.apply(lambda r: (r["DeepT"] / r["Grabbar"] if r["Grabbar"] != 0 else 0), axis=1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df.apply(lambda r: (r["Total tid"] / r["Totalt män"] if r["Totalt män"] > 0 else 0), axis=1)
    df["Runk"] = df["Tid kille DT"] * 0.6

    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + df["Summa dubbel"] + df["Summa trippel"]
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    start_time = datetime(2025, 1, 1, 7, 0)
    df["Klockan"] = df["Summa tid"].apply(lambda x: (start_time + timedelta(minutes=x/60)).strftime("%H:%M"))

    df["Suger"] = (df["Summa tid"] / df["Totalt män"]) * 0.6
    df["Tid kille"] = df["Tid s"] + df["Tid d"]*2 + df["Tid t"]*3 + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    def calc_hardness(row):
        if row["Män"] == 0:
            return 0
        h = 1
        if row["Dm"] > 0: h += 2
        if row["Df"] > 0: h += 2
        if row["Dr"] > 0: h += 4
        if row["TPP"] > 0: h += 4
        if row["TAP"] > 0: h += 6
        if row["TPA"] > 0: h += 5
        return h

    df["Hårdhet"] = df.apply(calc_hardness, axis=1)

    df["Filmer"] = (df["Män"] + df["Fi"] + df["Rö"] + df["Dm"]*2 + df["Df"]*2 + df["Dr"]*3 + df["TPP"]*4 + df["TAP"]*6 + df["TPA"]*5) * df["Hårdhet"]
    df["Intäkter"] = df["Filmer"] * 19.99

    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänner lön"] = df["Intäkter"] - df["Malin lön"] - df["Företagets lön"]

    return df

# Lägg till ny rad via formulär
def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        for fält in [
            "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr",
            "TPP", "TAP", "TPA", "Älskar", "Sover med",
            "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta",
            "DeepT", "Grabbar", "Sekunder", "Varv",
            "Tid s", "Tid d", "Tid t", "Vila"
        ]:
            if fält == "Datum":
                ny_rad[fält] = st.date_input(fält, value=datetime.today()).strftime("%Y-%m-%d")
            else:
                ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        submitted = st.form_submit_button("Spara")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Vilodagsfunktioner
def vilodag(df, jobb=True):
    ny_rad = {}
    try:
        last_date = pd.to_datetime(df["Datum"].dropna().iloc[-1])
        ny_rad["Datum"] = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")

    if jobb:
        max_jobb = df["Jobb"].max() if "Jobb" in df.columns else 0
        max_grannar = df["Grannar"].max() if "Grannar" in df.columns else 0
        max_tjej = df["Tjej PojkV"].max() if "Tjej PojkV" in df.columns else 0
        max_nils = df["Nils Fam"].max() if "Nils Fam" in df.columns else 0
        ny_rad.update({
            "Älskar": 12,
            "Sover med": 1,
            "Jobb": round(max_jobb * 0.5),
            "Grannar": round(max_grannar * 0.5),
            "Tjej PojkV": round(max_tjej * 0.5),
            "Nils Fam": round(max_nils * 0.5)
        })
        for f in ["Män","Fi","Rö","Dm","Df","Dr","TPP","TAP","TPA","Svarta",
                  "DeepT","Grabbar","Sekunder","Varv","Tid s","Tid d","Tid t","Vila"]:
            ny_rad[f] = 0
    else:
        ny_rad.update({
            "Älskar": 6,
            "Sover med": 0,
            "Jobb": 3,
            "Grannar": 3,
            "Tjej PojkV": 3,
            "Nils Fam": 3
        })
        for f in ["Män","Fi","Rö","Dm","Df","Dr","TPP","TAP","TPA","Svarta",
                  "DeepT","Grabbar","Sekunder","Varv","Tid s","Tid d","Tid t","Vila"]:
            ny_rad[f] = 0

    append_row(ny_rad)
    st.success(f"✅ Vilodag {'jobb' if jobb else 'hemma'} tillagd.")

# Kopiera två rader med flest Totalt män
def kopiera_max(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    try:
        last_date = pd.to_datetime(df["Datum"].dropna().iloc[-1])
        new_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        new_date = datetime.today().strftime("%Y-%m-%d")

    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Datum"] = new_date
        append_row(ny)
    st.success("✅ Två rader kopierades från högsta Totalt män.")

# Slumpa ny rad baserat på befintliga kolumners min-max
def slumpa_rad(df):
    import random
    kolumner = [
        "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta",
        "DeepT", "Grabbar", "Sekunder", "Varv",
        "Tid s", "Tid d", "Tid t"
    ]
    ny_rad = {}
    for kol in kolumner:
        if kol in df.columns:
            minimum = df[kol].min()
            maximum = df[kol].max()
            if pd.isna(minimum) or pd.isna(maximum):
                minimum, maximum = 0, 0
            ny_rad[kol] = random.randint(int(minimum), int(maximum)) if maximum >= minimum else 0
        else:
            ny_rad[kol] = 0

    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30
    try:
        last_date = pd.to_datetime(df["Datum"].dropna().iloc[-1])
        ny_rad["Datum"] = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")

    append_row(ny_rad)
    st.success("✅ Slumpmässig rad tillagd.")

# Presentation: Huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy - Summeringar")

    totalt_män = df["Totalt män"].sum() if "Totalt män" in df.columns else 0
    st.write(f"**Totalt antal män:** {totalt_män}")

    maxvals = get_max_values(df)
    känner_2 = maxvals.get("Känner 2", 0)
    st.write(f"**Känner:** {känner_2}")

    st.write(f"**Jobb:** {maxvals.get('Jobb 2', 0)}")
    st.write(f"**Grannar:** {maxvals.get('Grannar 2', 0)}")
    st.write(f"**Tjej PojkV:** {maxvals.get('Tjej PojkV 2', 0)}")
    st.write(f"**Nils fam:** {maxvals.get('Nils Fam 2', 0)}")

    antal_rader = len(df[df["Män"] > 0]) if "Män" in df.columns else 1
    snitt_film = ((df["Totalt män"].sum()) / antal_rader) if antal_rader > 0 else 0
    st.write(f"**Snitt film:** {snitt_film:.2f}")

    summa_känner = df["Känner"].sum() if "Känner" in df.columns else 0
    gangb = summa_känner / känner_2 if känner_2 > 0 else 0
    st.write(f"**GangB:** {gangb:.2f}")

    älskat = df["Älskar"].sum() / känner_2 if känner_2 > 0 else 0
    st.write(f"**Älskat:** {älskat:.2f}")

    sover_med_kvot = df["Sover med"].sum() / maxvals.get("Nils Fam 2", 1)
    st.write(f"**Sover med / Nils Fam 2:** {sover_med_kvot:.2f}")

    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män > 0 else 0
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")

    st.write(f"**Filmer:** {df['Filmer'].sum():.0f}")
    st.write(f"**Intäkter:** ${df['Intäkter'].sum():.2f}")
    st.write(f"**Malin lön:** ${df['Malin lön'].sum():.2f}")
    st.write(f"**Företagets lön:** ${df['Företagets lön'].sum():.2f}")
    vänner_lön_sum = df['Vänner lön'].sum() / maxvals.get("Känner 2", 1)
    st.write(f"**Vänner lön / Känner 2:** ${vänner_lön_sum:.2f}")

# Presentation: Radvyn
def radvy(df):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    rad = df.iloc[-1]
    tid_kille = rad["Tid kille"]
    marker = "⚠️ Öka tid!" if tid_kille < 10 else ""

    st.write(f"**Tid kille:** {tid_kille:.2f} minuter {marker}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")

    total_tid_min = (rad
