import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Autentisera Google Sheets
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# Ladda och säkerställ rubriker
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")

    headers = [
        "Datum", "Män", "Fi", "Rö", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Svarta", "Tid s", "Tid d", "Tid t", "Vila", "Älsk tid", "Totalt män",
        "Känner", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2",
        "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid",
        "Klockan", "Tid kille", "Suger", "Filmer", "Pris", "Intäkter",
        "Malin lön", "Företag lön", "Vänner lön", "Hårdhet",
        "DeepT", "Grabbar", "Snitt", "Sekunder", "Varv", "Total tid",
        "Tid kille DT", "Runk"
    ]

    current = worksheet.row_values(1)
    if current != headers:
        worksheet.resize(rows=1)
        worksheet.append_row(headers)

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# Hjälpmetoder för beräkningar etc.
def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if "Jobb" in df else 0,
        "Grannar 2": df["Grannar"].max() if "Grannar" in df else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if "Tjej PojkV" in df else 0,
        "Nils fam 2": df["Nils fam"].max() if "Nils fam" in df else 0,
        "Känner 2": (df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils fam"]).max() if not df.empty else 0
    }

def calculate_all(df):
    if df.empty:
        return df
    # Beräkna känner
    df["Känner"] = df[["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]].sum(axis=1)

    # Hämta maxvärden för 2:or
    max_vals = get_max_values(df)
    df["Jobb 2"] = max_vals["Jobb 2"]
    df["Grannar 2"] = max_vals["Grannar 2"]
    df["Tjej PojkV 2"] = max_vals["Tjej PojkV 2"]
    df["Nils fam 2"] = max_vals["Nils fam 2"]

    # Totalt män
    df["Totalt män"] = df["Män"] + df["Känner"]

    # Summeringar
    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["Dm"] + df["Df"] + df["Dr"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa vila"] = (df["Totalt män"] * df["Vila"]) + ((df["Dm"] + df["Df"] + df["Dr"]) * (df["Vila"] + 10)) + ((df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15))
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Summa vila"]

    # Tid kille (sekunder)
    df["Tid kille"] = df["Tid s"] + (df["Tid d"] * 2) + (df["Tid t"] * 3)

    # Suger
    df["Suger"] = 0.6 * (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]) / df["Totalt män"].replace(0, 1)

    # Lägg till suger på tid kille
    df["Tid kille"] += df["Suger"]

    # Filmer och hårdhet
    def calc_hardness(row):
        h = 0
        if row["Män"] > 0:
            h += 1
            if row["Dm"] > 0: h += 2
            if row["Df"] > 0: h += 2
            if row["Dr"] > 0: h += 4
            if row["TPP"] > 0: h += 4
            if row["TAP"] > 0: h += 6
            if row["TPA"] > 0: h += 5
        return h

    df["Hårdhet"] = df.apply(calc_hardness, axis=1)

    df["Filmer"] = (df["Män"] + df["Fi"] + df["Rö"] + df["Dm"] * 2 + df["Df"] * 2 + df["Dr"] * 3 + df["TPP"] * 4 + df["TAP"] * 6 + df["TPA"] * 5) * df["Hårdhet"]

    # Pris och intäkter
    df["Pris"] = 19.99
    df["Intäkter"] = df["Filmer"] * df["Pris"]

    # Löner
    df["Malin lön"] = df["Intäkter"] * 0.05
    df.loc[df["Malin lön"] > 1500, "Malin lön"] = 1500

    df["Företag lön"] = df["Intäkter"] * 0.4
    df["Vänner lön"] = df["Intäkter"] - df["Malin lön"] - df["Företag lön"]

    # DeepT, Grabbar, Snitt
    df["Snitt"] = 0
    if "DeepT" in df and "Grabbar" in df:
        df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)

    # Total tid etc.
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = 0.6 * df["Total tid"] / df["Totalt män"].replace(0, 1)

    return df

# Presentation av huvudvy
def huvudvy(df):
    st.header("📊 Huvudvy")

    if df.empty:
        st.warning("Ingen data att visa i huvudvyn.")
        return

    totalt_män = df["Totalt män"].sum()
    totalt_känner = df["Känner"].sum()
    max_vals = get_max_values(df)

    # Snitt film = (totalt män + känner) / antal rader där män > 0
    antal_rader = len(df[df["Män"] > 0])
    snitt_film = (totalt_män + totalt_känner) / antal_rader if antal_rader > 0 else 0

    # GangB = summan av känner / summan av känner 2
    gangb = totalt_känner / (max_vals["Känner 2"] if max_vals["Känner 2"] > 0 else 1)

    # Älskat = summan av älskar / känner 2
    älskat = df["Älskar"].sum() / (max_vals["Känner 2"] if max_vals["Känner 2"] > 0 else 1)

    # Sover med kvot
    sover_med_kvot = df["Sover med"].sum() / (max_vals["Nils fam 2"] if max_vals["Nils fam 2"] > 0 else 1)

    # Vita och svarta i procent
    svarta_summa = df["Svarta"].sum()
    vita = (totalt_män - svarta_summa) / totalt_män * 100 if totalt_män > 0 else 0
    svarta = svarta_summa / totalt_män * 100 if totalt_män > 0 else 0

    # Summor av intäkter och löner
    intäkter_summa = df["Intäkter"].sum()
    malin_lön_summa = df["Malin lön"].sum()
    företag_lön_summa = df["Företag lön"].sum()
    vänner_lön_summa = df["Vänner lön"].sum() / (max_vals["Känner 2"] if max_vals["Känner 2"] > 0 else 1)

    # Presentera allt
    st.write(f"**Totalt män:** {totalt_män}")
    st.write(f"**Antal känner (Kompisar):** {totalt_känner}")
    st.write(f"**Jobb:** {max_vals['Jobb 2']}")
    st.write(f"**Grannar:** {max_vals['Grannar 2']}")
    st.write(f"**Tjej PojkV:** {max_vals['Tjej PojkV 2']}")
    st.write(f"**Nils fam:** {max_vals['Nils fam 2']}")
    st.write(f"**Snitt film:** {snitt_film:.2f}")
    st.write(f"**GangB:** {gangb:.2f}")
    st.write(f"**Älskat:** {älskat:.2f}")
    st.write(f"**Sover med (kvot):** {sover_med_kvot:.2f}")
    st.write(f"**Vita (%):** {vita:.1f}%")
    st.write(f"**Svarta (%):** {svarta:.1f}%")
    st.write(f"**Filmer (summa):** {df['Filmer'].sum()}")
    st.write(f"**Intäkter (summa):** ${intäkter_summa:.2f}")
    st.write(f"**Malin lön (summa):** ${malin_lön_summa:.2f}")
    st.write(f"**Företag lön (summa):** ${företag_lön_summa:.2f}")
    st.write(f"**Vänner lön (per kompis):** ${vänner_lön_summa:.2f}")

# Presentation av radvy
def radvy(df):
    st.header("📋 Radvyn")

    if df.empty:
        st.warning("Ingen data att visa i radvyn.")
        return

    rad = df.iloc[-1]

    # Tid kille inkl tid kille DT och Runk
    tid_kille = rad["Tid kille"] + rad["Tid kille DT"] + rad["Runk"]
    tid_kille_min = tid_kille / 60
    markering = "⚠️ Tid kille under 10 min, överväg att öka" if tid_kille_min < 10 else ""

    st.write(f"**Tid kille (min):** {tid_kille_min:.2f} {markering}")
    st.write(f"**Filmer:** {int(rad['Filmer'])}")
    st.write(f"**Intäkter:** ${rad['Intäkter']:.2f}")

    # Beräkning av klockan start 07:00 + summa tid i minuter
    total_tid_min = rad["Summa tid"] / 60
    starttid = datetime(2025, 1, 1, 7, 0)
    sluttid = (starttid + timedelta(minutes=total_tid_min)).strftime("%H:%M")
    st.write(f"**Klockan:** {sluttid}")

    # Form för redigering om tid kille < 10 min
    if tid_kille_min < 10:
        st.subheader("⏱️ Justera tider för att öka Tid kille")

        with st.form("justera_tid_form"):
            tid_s_ny = st.number_input("Tid s", value=int(rad["Tid s"]), min_value=0, step=1)
            tid_d_ny = st.number_input("Tid d", value=int(rad["Tid d"]), min_value=0, step=1)
            tid_t_ny = st.number_input("Tid t", value=int(rad["Tid t"]), min_value=0, step=1)
            varv_ny = st.number_input("Varv", value=int(rad.get("Varv", 1)), min_value=1, step=1)
            sekunder_ny = st.number_input("Sekunder", value=int(rad.get("Sekunder", 1)), min_value=1, step=1)

            submit = st.form_submit_button("Spara ändringar")
            if submit:
                client = auth_gspread()
                sheet = client.open_by_url(st.secrets["SHEET_URL"])
                worksheet = sheet.worksheet("Blad1")

                rad_index = df.index[-1] + 2  # +2 pga sheet rad 1 är header, df index börjar på 0
                cell_range = f"T{rad_index}:X{rad_index}"  # Tid s, Tid d, Tid t, Varv, Sekunder

                worksheet.update(cell_range, [[tid_s_ny, tid_d_ny, tid_t_ny, varv_ny, sekunder_ny]])
                st.success("⏱️ Tider uppdaterade! Ladda om appen.")

import random

# Lägg till ny rad via formulär
def inmatning(df):
    st.header("➕ Lägg till ny rad")
    with st.form("form_ny_rad"):
        ny_rad = {}
        fält_lista = [
            "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
            "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
            "Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"
        ]
        for fält in fält_lista:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        ny_rad["Dag"] = (pd.to_datetime(df.iloc[-1]["Dag"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d")
        submitted = st.form_submit_button("Spara")
        if submitted:
            append_row(ny_rad)
            st.success("✅ Ny rad sparad. Ladda om appen för att se uppdatering.")

# Knapp för vilodag jobb
def vilodag_jobb(df):
    max_vals = get_max_values(df)
    ny_rad = {
        "Dag": (pd.to_datetime(df.iloc[-1]["Dag"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 12,
        "Sover med": 1,
        "Jobb": max_vals["Jobb 2"],
        "Grannar": max_vals["Grannar 2"],
        "Tjej PojkV": max_vals["Tjej PojkV 2"],
        "Nils fam": max_vals["Nils fam 2"]
    }
    # Sätt övriga fält till 0
    alla_fält = [
        "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv", "Svarta"
    ]
    for fält in alla_fält:
        ny_rad[fält] = 0

    append_row(ny_rad)
    st.success("✅ Vilodag jobb tillagd.")

# Knapp för vilodag hemma
def vilodag_hemma(df):
    ny_rad = {
        "Dag": (pd.to_datetime(df.iloc[-1]["Dag"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d"),
        "Älskar": 6,
        "Sover med": 0,
        "Jobb": 3,
        "Grannar": 3,
        "Tjej PojkV": 3,
        "Nils fam": 3
    }
    # Övriga fält 0
    alla_fält = [
        "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv", "Svarta"
    ]
    for fält in alla_fält:
        ny_rad[fält] = 0

    append_row(ny_rad)
    st.success("✅ Vilodag hemma tillagd.")

# Kopiera två rader med högst totalt män och skapa två nya rader
def kopiera_max(df):
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]
    top2 = df.sort_values("Totalt män", ascending=False).head(2)
    for _, rad in top2.iterrows():
        ny = rad.to_dict()
        ny["Dag"] = (pd.to_datetime(df.iloc[-1]["Dag"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d")
        append_row(ny)
    st.success("✅ Två rader kopierades från högsta Totalt män.")

# Slumpknapp: slumpa värden i manuella fält
def slumpa_rad(df):
    manual_fields = [
        "Män", "F", "R", "Dm", "Df", "Dr", "TPP", "TAP", "TPA",
        "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
        "Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"
    ]
    ny_rad = {}
    for fält in manual_fields:
        if fält in df.columns and not df.empty:
            min_val = df[fält].min()
            max_val = df[fält].max()
            if min_val == max_val:
                ny_rad[fält] = int(min_val)
            else:
                ny_rad[fält] = random.randint(int(min_val), int(max_val))
        else:
            ny_rad[fält] = 0
    # Specifika fasta värden
    ny_rad["Älskar"] = 8
    ny_rad["Sover med"] = 1
    ny_rad["Vila"] = 7
    ny_rad["Älsk tid"] = 30

    ny_rad["Dag"] = (pd.to_datetime(df.iloc[-1]["Dag"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if not df.empty else datetime.today().strftime("%Y-%m-%d")
    append_row(ny_rad)
    st.success("✅ Ny rad med slumpade värden tillagd.")

# Main funktion
def main():
    worksheet, df = load_data()

    st.title("MalinData App")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("➕ Lägg till vilodag jobb"):
            vilodag_jobb(df)
    with col2:
        if st.button("➕ Lägg till vilodag hemma"):
            vilodag_hemma(df)
    with col3:
        if st.button("📋 Kopiera två största"):
            kopiera_max(df)
    with col4:
        if st.button("🎲 Slumpa ny rad"):
            slumpa_rad(df)

    inmatning(df)
    huvudvy(df)
    radvy(df)


if __name__ == "__main__":
    main()
