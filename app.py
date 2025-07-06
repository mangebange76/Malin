import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta, time

# Anslut till Google Sheets
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit?usp=drivesdk"
SHEET_NAME = "Blad1"

ALL_COLUMNS = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
    "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta",
    "Känner", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2", "Totalt män",
    "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila",
    "Summa singel", "Summa dubbel", "Summa trippel", "Summa vila", "Summa tid", "Klockan",
    "Tid kille", "Suger", "Filmer", "Pris", "Intäkter",
    "Malin", "Företag", "Vänner", "Hårdhet"
]

def load_data():
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    if df.empty or list(df.columns) != ALL_COLUMNS:
        worksheet.clear()
        worksheet.append_row(ALL_COLUMNS)
        df = pd.DataFrame(columns=ALL_COLUMNS)

    return worksheet, df

def save_data(worksheet, df):
    worksheet.clear()
    worksheet.append_row(ALL_COLUMNS)
    worksheet.append_rows(df.astype(str).values.tolist())

def create_row_input(df, vilodag=None):
    st.subheader("Ny rad")
    today = datetime.today().date()
    if df.empty:
        datum = st.date_input("Datum", today)
    else:
        datum = st.date_input("Datum", pd.to_datetime(df["Datum"].iloc[-1]) + timedelta(days=1))

    ny_rad = {
        "Datum": str(datum),
        "Pris": 19.99
    }

    if vilodag == "Jobb":
        jobb2 = df["Jobb"].max() if not df.empty else 0
        grannar2 = df["Grannar"].max() if not df.empty else 0
        tjej2 = df["Tjej PojkV"].max() if not df.empty else 0
        nils2 = df["Nils fam"].max() if not df.empty else 0

        ny_rad.update({
            "Jobb": round(jobb2 * 0.5),
            "Grannar": round(grannar2 * 0.5),
            "Tjej PojkV": round(tjej2 * 0.5),
            "Nils fam": round(nils2 * 0.5),
            "Älskar": 12,
            "Sover med": 1,
        })

        for fält in ["Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila", "Svarta"]:
            ny_rad[fält] = 0

    elif vilodag == "Hemma":
        ny_rad.update({
            "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils fam": 3,
            "Älskar": 6, "Sover med": 0,
        })
        for fält in ["Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila", "Svarta"]:
            ny_rad[fält] = 0

    else:
        for fält in ["Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
                     "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam", "Svarta"]:
            ny_rad[fält] = st.number_input(fält, min_value=0, step=1)

        for fält in ["Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila"]:
            ny_rad[fält] = st.number_input(fält + " (sekunder)", min_value=0, step=1)

    return ny_rad

def calculate_fields(df, ny_rad):
    for col in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"]:
        ny_rad[f"{col} 2"] = max(df[col].max() if not df.empty else 0, ny_rad[col])

    ny_rad["Känner"] = sum(ny_rad[kol] for kol in ["Jobb", "Grannar", "Tjej PojkV", "Nils fam"])
    ny_rad["Totalt män"] = ny_rad["Män"] + ny_rad["Känner"]

    ny_rad["Summa singel"] = ny_rad["Tid Singel"] * ny_rad["Totalt män"]
    ny_rad["Summa dubbel"] = ny_rad["Tid Dubbel"] * ny_rad["Totalt män"]
    ny_rad["Summa trippel"] = ny_rad["Tid Trippel"] * ny_rad["Totalt män"]

    ny_rad["Summa vila"] = (
        ny_rad["Totalt män"] * ny_rad["Vila"]
        + ny_rad["DM"] * (ny_rad["Vila"] + 10)
        + ny_rad["DF"] * (ny_rad["Vila"] + 15)
        + ny_rad["DR"] * (ny_rad["Vila"] + 15)
        + ny_rad["TPP"] * (ny_rad["Vila"] + 15)
        + ny_rad["TAP"] * (ny_rad["Vila"] + 15)
        + ny_rad["TPA"] * (ny_rad["Vila"] + 15)
    )

    ny_rad["Summa tid"] = sum(ny_rad[kol] for kol in ["Summa singel", "Summa dubbel", "Summa trippel", "Summa vila"])
    ny_rad["Klockan"] = (datetime.combine(datetime.today(), time(7, 0)) + timedelta(seconds=ny_rad["Summa tid"])).strftime("%H:%M")

    tid_kille = (ny_rad["Summa singel"] + 2 * ny_rad["Summa dubbel"] + 3 * ny_rad["Summa trippel"]) / ny_rad["Totalt män"] if ny_rad["Totalt män"] else 0
    suger = (ny_rad["Summa singel"] + ny_rad["Summa dubbel"] + ny_rad["Summa trippel"]) * 0.6 / ny_rad["Totalt män"] if ny_rad["Totalt män"] else 0
    ny_rad["Tid kille"] = round((tid_kille + suger) / 60, 2)
    ny_rad["Suger"] = round(suger)

    ny_rad["Filmer"] = (
        ny_rad["Män"] + ny_rad["Fi"] + 2 * ny_rad["Rö"] + 1 * ny_rad["DM"] +
        3 * ny_rad["DF"] + 4 * ny_rad["DR"] + 5 * ny_rad["TPP"] + 7 * ny_rad["TAP"] + 6 * ny_rad["TPA"]
    )
    ny_rad["Hårdhet"] = (
        int(ny_rad["Män"] > 0) + int(ny_rad["DM"] > 0) + int(ny_rad["DF"] > 0) * 2 +
        int(ny_rad["DR"] > 0) + int(ny_rad["TPP"] > 0) * 4 + int(ny_rad["TAP"] > 0) * 5 +
        int(ny_rad["TPA"] > 0) * 4
    )

    ny_rad["Intäkter"] = ny_rad["Filmer"] * ny_rad["Pris"] * ny_rad["Hårdhet"]
    ny_rad["Malin"] = min(ny_rad["Intäkter"] * 0.01, 1500)
    ny_rad["Företag"] = ny_rad["Intäkter"] * 0.4
    ny_rad["Vänner"] = ny_rad["Intäkter"] - ny_rad["Malin"] - ny_rad["Företag"]

    return ny_rad

def huvudvy(df):
    st.subheader("📊 Huvudvy")
    if df.empty:
        st.info("Ingen data ännu.")
        return

    total_män = df["Män"].sum()
    total_känner = df["Känner"].sum()
    total_vänner = df["Vänner"].sum()
    total_malin = df["Malin"].sum()

    svarta = df["Svarta"].sum()
    vita = total_män - svarta
    total_män_and_svarta = total_män if total_män else 1

    gangb = round(total_känner / max(
        df["Jobb 2"].max(), df["Grannar 2"].max(), df["Tjej PojkV 2"].max(), df["Nils fam 2"].max(), 1
    ), 2)

    älskat = round(df["Älskar"].sum() / max(
        df["Jobb 2"].max(), df["Grannar 2"].max(), df["Tjej PojkV 2"].max(), df["Nils fam 2"].max(), 1
    ), 2)

    st.markdown(f"""
    - **Totalt Män**: {total_män}
    - **Malin lön (total)**: ${total_malin:,.2f}
    - **Vänner lön (total)**: ${total_vänner:,.2f}
    - **Vita (%)**: {round((vita / (total_män + svarta)) * 100, 2)}%
    - **Svarta (%)**: {round((svarta / (total_män + svarta)) * 100, 2)}%
    - **Snitt Män + Känner**: {round((total_män + total_känner) / len(df), 2)}
    - **GangB**: {gangb}
    - **Älskat**: {älskat}
    """)

def radvy(df):
    st.subheader("🔎 Detaljvy")
    if df.empty:
        return
    rad = st.selectbox("Välj rad", df.index[::-1])
    row = df.loc[rad]
    st.markdown(f"""
    **Datum**: {row['Datum']}  
    - **Tid kille**: {row['Tid kille']} min  
    - **Filmer**: {row['Filmer']}  
    - **Intäkter**: ${row['Intäkter']:,.2f}  
    - **Klockan**: {row['Klockan']}
    """)

def main():
    st.title("MalinData App")
    worksheet, df = load_data()

    with st.form("data_input"):
        st.write("### Lägg till ny rad")
        viloläge = st.radio("Vilodag?", ["Ingen", "Vilodag jobb", "Vilodag hemma"], horizontal=True)
        vilodag = "Jobb" if viloläge == "Vilodag jobb" else "Hemma" if viloläge == "Vilodag hemma" else None
        ny_rad = create_row_input(df, vilodag)
        submitted = st.form_submit_button("Spara")

    if submitted:
        ny_rad = calculate_fields(df, ny_rad)
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        save_data(worksheet, df)
        st.success("✅ Raden har sparats!")

    huvudvy(df)
    radvy(df)

if __name__ == "__main__":
    main()
