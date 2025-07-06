import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import json

# Autentisering via secrets
credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# Konstanter
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-bpY9Ahk9qKH2QIQzVUSZLX6qDc2UwjCmullMCNvENQ/edit"
SHEET_NAME = "Blad1"
STARTTID = datetime.strptime("07:00", "%H:%M")
PRIS_PER_FILM = 19.99

# Fält
KOLUMNER = [
    "Datum", "Män", "Fi", "Rö", "DM", "DF", "DR", "TPP", "TAP", "TPA",
    "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils Fam", "Svarta",
    "Tid Singel", "Tid Dubbel", "Tid Trippel", "Vila"
]

BERÄKNADE = [
    "Känner", "Totalt män", "Summa Singel", "Summa Dubbel", "Summa Trippel",
    "Summa Vila", "Summa Tid", "Klockan", "Tid Kille", "Filmer", "Intäkter",
    "Malin", "Företag", "Vänner", "GangB", "Älskat", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils Fam 2", "Känner 2"
]

def load_sheet():
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet(SHEET_NAME)
    data = ws.get_all_records()
    return ws, pd.DataFrame(data)

def save_sheet(ws, df):
    ws.update([df.columns.values.tolist()] + df.values.tolist())

def get_max_values(df):
    return {
        "Jobb 2": df["Jobb"].max() if not df["Jobb"].isna().all() else 0,
        "Grannar 2": df["Grannar"].max() if not df["Grannar"].isna().all() else 0,
        "Tjej PojkV 2": df["Tjej PojkV"].max() if not df["Tjej PojkV"].isna().all() else 0,
        "Nils Fam 2": df["Nils Fam"].max() if not df["Nils Fam"].isna().all() else 0
    }

def lägg_till_rad(förval=None):
    st.subheader("➕ Lägg till ny rad")

    with st.form("lägg_till_rad"):
        idag = datetime.today().strftime("%Y-%m-%d")
        datum = st.date_input("Datum", value=datetime.strptime(förval.get("Datum", idag), "%Y-%m-%d") if förval else datetime.today())

        input_data = {}
        for fält in KOLUMNER[1:]:
            input_data[fält] = st.number_input(fält, min_value=0, step=1, value=förval.get(fält, 0) if förval else 0)

        submit = st.form_submit_button("Spara rad")

    if submit:
        ny_rad = {"Datum": datum.strftime("%Y-%m-%d")}
        ny_rad.update(input_data)
        return ny_rad
    return None

def skapa_vilodag(typ, maxvärden):
    if typ == "Jobb":
        return {
            "Jobb": round(maxvärden["Jobb 2"] * 0.5),
            "Grannar": round(maxvärden["Grannar 2"] * 0.5),
            "Tjej PojkV": round(maxvärden["Tjej PojkV 2"] * 0.5),
            "Nils Fam": round(maxvärden["Nils Fam 2"] * 0.5),
            "Älskar": 12, "Sover med": 1
        }
    elif typ == "Hemma":
        return {
            "Jobb": 3, "Grannar": 3, "Tjej PojkV": 3, "Nils Fam": 3,
            "Älskar": 6, "Sover med": 0
        }

def beräkna(df):
    df = df.copy()

    # Känner och maxvärden
    df["Känner"] = df["Jobb"] + df["Grannar"] + df["Tjej PojkV"] + df["Nils Fam"]
    df["Totalt män"] = df["Män"] + df["Känner"]

    df["Jobb 2"] = df["Jobb"].cummax()
    df["Grannar 2"] = df["Grannar"].cummax()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].cummax()
    df["Nils Fam 2"] = df["Nils Fam"].cummax()
    df["Känner 2"] = df["Känner"].cummax()

    # Tid
    df["Summa Singel"] = (df["Fi"] + df["Rö"]) * df["Tid Singel"]
    df["Summa Dubbel"] = (df["DM"] + df["DF"] + df["DR"]) * df["Tid Dubbel"]
    df["Summa Trippel"] = (df["TPP"] + df["TAP"] + df["TPA"]) * df["Tid Trippel"]

    df["Summa Vila"] = (
        df["Totalt män"] * df["Vila"] +
        (df["DM"] + df["DF"] + df["DR"]) * (df["Vila"] + 7) +
        (df["TPP"] + df["TAP"] + df["TPA"]) * (df["Vila"] + 15)
    )

    df["Summa Tid"] = df["Summa Singel"] + df["Summa Dubbel"] + df["Summa Trippel"] + df["Summa Vila"]

    df["Klockan"] = df["Summa Tid"].apply(lambda s: (STARTTID + timedelta(seconds=s)).strftime("%H:%M"))
    df["Tid Kille"] = ((df["Summa Singel"] + df["Summa Dubbel"] * 2 + df["Summa Trippel"] * 3) / df["Totalt män"]).fillna(0) / 60

    # Filmer och intäkter
    df["Filmer"] = (
        df["Män"] + df["Fi"] + df["Rö"]*2 + df["DM"]*2 + df["DF"]*3 + df["DR"]*4 +
        df["TPP"]*5 + df["TAP"]*7 + df["TPA"]*6
    )

    df["Intäkter"] = df["Filmer"] * PRIS_PER_FILM
    df["Malin"] = df["Intäkter"] * 0.01
    df.loc[df["Malin"] > 1500, "Malin"] = 1500
    df["Företag"] = df["Intäkter"] * 0.40
    df["Vänner"] = df["Intäkter"] - df["Malin"] - df["Företag"]

    return df

def visa_data(df):
    st.subheader("📊 Huvudvy")

    totalt_män = df["Män"].sum()
    totalt_känner = df["Känner"].sum()
    snitt = (totalt_män + totalt_känner) / len(df)

    vita = (totalt_män - df["Svarta"].sum()) / totalt_män * 100 if totalt_män else 0
    svarta = df["Svarta"].sum() / totalt_män * 100 if totalt_män else 0

    gangb = totalt_känner / (df[["Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils Fam 2"]].iloc[-1].sum())
    älskat = df["Älskar"].sum() / df[["Jobb", "Grannar", "Tjej PojkV", "Nils Fam"]].sum().sum()

    st.markdown(f"""
    **Totalt Män**: {totalt_män}  
    **Snitt (Män + Känner)**: {snitt:.1f}  
    **Malin lön**: {df["Malin"].sum():,.2f} USD  
    **Vänner lön**: {df["Vänner"].sum():,.2f} USD  
    **GangB**: {gangb:.2f}  
    **Älskat**: {älskat:.2f}  
    **Vita (%)**: {vita:.1f}%  
    **Svarta (%)**: {svarta:.1f}%
    """)

    rad = st.selectbox("📅 Välj rad att visa detaljer:", df["Datum"])
    vald = df[df["Datum"] == rad]

    if not vald.empty:
        st.markdown(f"""
        **Tid Kille**: {vald["Tid Kille"].values[0]:.1f} min  
        **Filmer**: {vald["Filmer"].values[0]}  
        **Intäkter**: {vald["Intäkter"].values[0]:,.2f} USD  
        **Klockan**: {vald["Klockan"].values[0]}
        """)

# === APP START ===
def main():
    worksheet, df = load_sheet()

    maxvärden = get_max_values(df)

    # Lägg till ny rad manuellt
    ny_rad = lägg_till_rad()

    # Vilodag
    if st.button("📴 Vilodag Jobb"):
        ny_rad = {"Datum": (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")}
        ny_rad.update({k: 0 for k in KOLUMNER[1:]})
        ny_rad.update(skapa_vilodag("Jobb", maxvärden))
    if st.button("🏠 Vilodag Hemma"):
        ny_rad = {"Datum": (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")}
        ny_rad.update({k: 0 for k in KOLUMNER[1:]})
        ny_rad.update(skapa_vilodag("Hemma", maxvärden))

    # Om rad lagts till
    if ny_rad:
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        df = beräkna(df)
        save_sheet(worksheet, df)
        st.success("Raden har lagts till! 🔄")

    # Visa appens data
    df = beräkna(df)
    visa_data(df)

if __name__ == "__main__":
    main()
