import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- Autentisering och dataladdning ---

def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(creds)
    return client

def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Svarta", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila",
        "Summa tid", "Klockan", "Tid kille", "Suger", "Filmer", "Pris",
        "Intäkter", "Malin lön", "Företagets lön", "Vänner lön",
        "Hårdhet", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2",
        "Känner", "Totalt män", "DeepT", "Grabbar", "Snitt", "Sekunder",
        "Varv", "Total tid", "Tid kille DT", "Runk"
    ]

    # Säkerställ att rubriker finns - skapa vid behov
    current_headers = worksheet.row_values(1)
    if current_headers != headers:
        worksheet.resize(rows=1)
        worksheet.append_row(headers)

    df = pd.DataFrame(worksheet.get_all_records())
    # Fyll NaN med 0 för beräkningar
    df.fillna(0, inplace=True)
    return worksheet, df

def append_row(row_dict):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    headers = worksheet.row_values(1)
    row = [row_dict.get(col, 0) for col in headers]
    worksheet.append_row(row)

def update_row(row_index, updates):
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    headers = worksheet.row_values(1)
    for col, val in updates.items():
        col_idx = headers.index(col) + 1
        worksheet.update_cell(row_index + 2, col_idx, val)  # +2 pga header + 0-index

# --- Beräkningar ---

def update_calculations(df):
    # Säkerställ heltal och ersätt NaN
    for col in df.columns:
        if col not in ["Datum", "Klockan"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Beräkna Känner
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)

    # Högsta värden (2-variant)
    df["Jobb 2"] = df["Jobb"].max()
    df["Grannar 2"] = df["Grannar"].max()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].max()
    df["Nils fam 2"] = df["Nils fam"].max()
    df["Känner 2"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].max(axis=1).max()

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner"]

    # Beräkna Summa singel, dubbel, trippel och vila i sekunder enligt regler
    df["Summa singel"] = (df["Tid Singel"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid Dubbel"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid Trippel"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])

    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + \
                      ((df["Dm"] + df["Df"] + df["Dr"]) * (df["Vila"] + 7)) + \
                      ((df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15))

    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    # Starttid 07:00 för klockan
    base_time = datetime(2025, 1, 1, 7, 0)
    df["Klockan"] = df["Summa tid"].apply(lambda x: (base_time + timedelta(seconds=x)).strftime("%H:%M:%S"))

    # Tid kille (sek) = tid s + tid d*2 + tid t*3 + suger + tid kille DT + runk (beräknas senare)
    df["Tid kille"] = df["Tid Singel"] + df["Tid Dubbel"] * 2 + df["Tid Trippel"] * 3

    # Suger = 60% av (Summa tid / Totalt män)
    df["Suger"] = 0
    mask = df["Totalt män"] > 0
    df.loc[mask, "Suger"] = 0.6 * (df.loc[mask, "Summa tid"] / df.loc[mask, "Totalt män"])

    # Filmer enligt viktad summa
    df["Hårdhet"] = 0
    df.loc[df["Män"] > 0, "Hårdhet"] += 1
    df.loc[df["Dm"] > 0, "Hårdhet"] += 2
    df.loc[df["Df"] > 0, "Hårdhet"] += 2
    df.loc[df["Dr"] > 0, "Hårdhet"] += 4
    df.loc[df["TPP"] > 0, "Hårdhet"] += 4
    df.loc[df["TAP"] > 0, "Hårdhet"] += 6
    df.loc[df["TPA"] > 0, "Hårdhet"] += 5

    df["Filmer"] = (
        df["Män"] + df["Fi"] + df["Rö"] +
        df["Dm"] * 2 + df["Df"] * 2 + df["Dr"] * 3 +
        df["TPP"] * 4 + df["TAP"] * 6 + df["TPA"] * 5
    ) * df["Hårdhet"]

    df["Pris"] = 19.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänner lön"] = df["Intäkter"] - df["Malin lön"] - df["Företagets lön"]

    # DeepT, Grabbar, Snitt, Sekunder, Varv, Total tid
    df["Snitt"] = 0
    mask = (df["Grabbar"] > 0)
    df.loc[mask, "Snitt"] = df.loc[mask, "DeepT"] / df.loc[mask, "Grabbar"]

    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = 0
    df.loc[df["Totalt män"] > 0, "Tid kille DT"] = df.loc[df["Totalt män"] > 0, "Total tid"] / df.loc[df["Totalt män"] > 0, "Totalt män"]

    df["Runk"] = 0
    df.loc[df["Totalt män"] > 0, "Runk"] = 0.6 * df.loc[df["Totalt män"] > 0, "Total tid"] / df.loc[df["Totalt män"] > 0, "Totalt män"]

    # Uppdatera Tid kille med suger, tid kille DT och runk
    df["Tid kille"] = df["Tid kille"] + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    return df

# --- Presentation ---

def present_main_view(df):
    st.header("📊 Huvudvy")

    totalt_män = df["Totalt män"].sum()
    känner_2 = df["Känner 2"].max() if "Känner 2" in df else 0
    jobb_2 = df["Jobb 2"].max() if "Jobb 2" in df else 0
    grannar_2 = df["Grannar 2"].max() if "Grannar 2" in df else 0
    tjej_pojkv_2 = df["Tjej PojkV 2"].max() if "Tjej PojkV 2" in df else 0
    nils_fam_2 = df["Nils fam 2"].max() if "Nils fam 2" in df else 0

    vita = 0
    svarta = 0
    if totalt_män > 0:
        svarta = df["Svarta"].sum() / totalt_män * 100
        vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100

    snitt_film = (totalt_män + df["Känner"].sum()) / len(df[df["Män"] > 0]) if len(df[df["Män"] > 0]) > 0 else 0
    gangb = df["Känner"].sum() / känner_2 if känner_2 > 0 else 0
    älskat = df["Älskar"].sum() / känner_2 if känner_2 > 0 else 0
    sover_med_kvot = df["Sover med"].sum() / nils_fam_2 if nils_fam_2 > 0 else 0

    filmer_sum = df["Filmer"].sum()
    intäkter_sum = df["Intäkter"].sum()
    malin_lön_sum = df["Malin lön"].sum()
    företag_lön_sum = df["Företagets lön"].sum()
    vänner_lön_sum = df["Vänner lön"].sum() / känner_2 if känner_2 > 0 else 0

    st.write(f"Totalt antal män: {totalt_män}")
    st.write(f"Känner (Kompisar): {känner_2}")
    st.write(f"Jobb (Jobb 2): {jobb_2}")
    st.write(f"Grannar (Grannar 2): {grannar_2}")
    st.write(f"Tjej PojkV (Tjej PojkV 2): {tjej_pojkv_2}")
    st.write(f"Nils fam (Nils fam 2): {nils_fam_2}")
    st.write(f"Vita (%): {vita:.1f}%")
    st.write(f"Svarta (%): {svarta:.1f}%")
    st.write(f"Snitt film: {snitt_film:.2f}")
    st.write(f"GangB: {gangb:.2f}")
    st.write(f"Älskat: {älskat:.2f}")
    st.write(f"Sover med kvot: {sover_med_kvot:.2f}")
    st.write(f"Filmer: {filmer_sum}")
    st.write(f"Intäkter: ${intäkter_sum:.2f}")
    st.write(f"Malin lön: ${malin_lön_sum:.2f}")
    st.write(f"Företagets lön: ${företag_lön_sum:.2f}")
    st.write(f"Vänner lön (per kompis): ${vänner_lön_sum:.2f}")

# --- Del 2 kommer med radvy, inmatning, knappar och main ---

# --- Radvyn ---

def radvy(df):
    st.header("📋 Radvyn")
    if df.empty:
        st.warning("Ingen data att visa.")
        return

    rad = df.iloc[-1]

    tid_kille_min = rad["Tid kille"] / 60
    varning = "⚠️ Öka tid!" if tid_kille_min < 10 else ""

    st.write(f"**Datum:** {rad['Datum'] if 'Datum' in rad else ''}")
    st.write(f"**Tid kille:** {tid_kille_min:.2f} minuter {varning}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")
    st.write(f"**Klockan:** {rad['Klockan']}")

    # Form för att redigera tid s, d, t om tid kille under 10 min
    with st.form("justera_tid_form"):
        tid_s = st.number_input("Tid Singel (sekunder)", min_value=0, value=int(rad["Tid Singel"]))
        tid_d = st.number_input("Tid Dubbel (sekunder)", min_value=0, value=int(rad["Tid Dubbel"]))
        tid_t = st.number_input("Tid Trippel (sekunder)", min_value=0, value=int(rad["Tid Trippel"]))
        submitted = st.form_submit_button("Spara ändring")

        if submitted:
            # Uppdatera dataraden i Google Sheet
            row_idx = len(df)  # sista raden (0-index => +1 header)
            updates = {
                "Tid Singel": tid_s,
                "Tid Dubbel": tid_d,
                "Tid Trippel": tid_t
            }
            update_row(row_idx, updates)
            st.success("⏱️ Tider uppdaterade! Ladda om sidan för uppdatering.")

# --- Inmatningsformulär för ny rad ---

def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        # Datum automatiskt: +1 dag från senaste datum eller idag
        if df.empty or "Datum" not in df.columns:
            ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")
        else:
            senaste_str = df.iloc[-1]["Datum"]
            try:
                senaste_dt = pd.to_datetime(senaste_str)
                ny_rad["Datum"] = (senaste_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                ny_rad["Datum"] = datetime.today().strftime("%Y-%m-%d")

        for fält in [
            "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
            "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
            "Svarta", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
            "DeepT", "Grabbar", "Sekunder", "Varv"
        ]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        ny_rad["Pris"] = 19.99

        submitted = st.form_submit_button("Spara ny rad")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad! Ladda om sidan för att se uppdatering.")

# --- Vilodagsknappar ---

def vilodag_jobb(df):
    ny_rad = {
        "Datum": (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": df["Jobb"].max() if "Jobb" in df.columns else 0,
        "Grannar": df["Grannar"].max() if "Grannar" in df.columns else 0,
        "Tjej PojkV": df["Tjej PojkV"].max() if "Tjej PojkV" in df.columns else 0,
        "Nils fam": df["Nils fam"].max() if "Nils fam" in df.columns else 0,
    }
    # Övriga fält 0
    for col in df.columns:
        if col not in ny_rad and col != "Datum":
            ny_rad[col] = 0

    append_row(ny_rad)
    st.success("✅ Vilodag jobb tillagd.")

def vilodag_hemma(df):
    ny_rad = {
        "Datum": (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 6,
        "Sover med": 0,
        "Jobb": 3,
        "Grannar": 3,
        "Tjej PojkV": 3,
        "Nils fam": 3,
    }
    for col in df.columns:
        if col not in ny_rad and col != "Datum":
            ny_rad[col] = 0

    append_row(ny_rad)
    st.success("✅ Vilodag hemma tillagd.")

# --- Kopiera två största rader (Totalt män) ---

def kopiera_max(df):
    if df.empty:
        st.warning("Ingen data att kopiera.")
        return

    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)

    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        append_row(ny)

    st.success("✅ Två rader kopierades.")

# --- Slumpknapp: slumpvärden i manuellt inmatade fält ---

def slumpa_rad(df):
    if df.empty:
        st.warning("Ingen data att slumpa från.")
        return

    ny_rad = {}
    # Datum ökar 1 dag från senaste
    ny_rad["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    manuella_fält = [
        "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Svarta", "Tid Singel", "Tid Dubbel", "Tid Trippel",
        "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"
    ]

    for fält in manuella_fält:
        min_val = int(df[fält].min()) if fält in df.columns and not df.empty else 0
        max_val = int(df[fält].max()) if fält in df.columns and not df.empty else 10
        if fält == "Älskar":
            ny_rad[fält] = 8
        elif fält == "Sover med":
            ny_rad[fält] = 1
        elif fält == "Vila":
            ny_rad[fält] = 7
        elif fält == "Älsk tid":
            ny_rad[fält] = 30
        else:
            if max_val < min_val:
                max_val = min_val + 10
            ny_rad[fält] = random.randint(min_val, max_val)

    ny_rad["Pris"] = 19.99

    append_row(ny_rad)
    st.success("✅ Ny rad med slumpmässiga värden tillagd.")

# --- Huvudfunktionen ---

def main():
    worksheet, df = load_data()
    df = update_calculations(df)

    st.title("Malin Data App")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("➕ Lägg till vilodag jobb"):
            vilodag_jobb(df)

    with col2:
        if st.button("➕ Lägg till vilodag hemma"):
            vilodag_hemma(df)

    with col3:
        if st.button("📋 Kopiera två största rader"):
            kopiera_max(df)

    with col4:
        if st.button("🎲 Lägg till slumpmässig rad"):
            slumpa_rad(df)

    inmatning(df)
    present_main_view(df)
    radvy(df)

if __name__ == "__main__":
    main()
