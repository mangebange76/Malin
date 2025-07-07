import streamlit as st
import pandas as pd
import datetime
from google.oauth2.service_account import Credentials
import gspread

# --- Autentisering ---
def auth_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# --- Ladda data ---
def load_data():
    client = auth_gspread()
    sheet = client.open_by_url(st.secrets["SHEET_URL"])
    worksheet = sheet.worksheet("Blad1")
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df = ensure_columns(df, worksheet)
    return worksheet, df

# --- Spara data ---
def save_data(worksheet, df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- Säkerställ kolumner ---
def ensure_columns(df, worksheet):
    required_columns = [
        "Datum", "Män", "F", "R", "DM", "DF", "DR", "TPP", "TAP", "TPA", "Älskar", "Sover med", "Jobb", "Grannar", "Tjej PojkV", "Nils fam",
        "Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"
    ]
    calc_columns = [
        "Totalt män", "Känner", "Känner 2", "Jobb 2", "Grannar 2", "Tjej PojkV 2", "Nils fam 2", "Summa singel", "Summa dubbel",
        "Summa trippel", "Summa tid", "Suger", "Snitt", "Total tid", "Tid kille DT", "Runk", "Tid kille", "Klockan",
        "Filmer", "Pris USD", "Intäkter", "Malin lön", "Företagets lön", "Vänners lön", "Hårdhet"
    ]
    for col in required_columns + calc_columns:
        if col not in df.columns:
            df[col] = 0
    # Lägg till ny rad automatiskt om bara rubriker finns
    if df.shape[0] == 0:
        df.loc[0] = [""] * len(df.columns)
        df.at[0, "Datum"] = datetime.date.today().strftime("%Y-%m-%d")
        df.loc[1] = df.loc[0]
        df.at[1, "Datum"] = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        save_data(worksheet, df)
    return df

# --- Utför alla beräkningar ---
def perform_calculations(df):
    df["Totalt män"] = df["Män"] + df["F"] + df["R"]
    df["Känner"] = df["Män"] + df["F"] + df["R"]
    df["Känner 2"] = df["Känner"].replace(0, 1)
    df["Jobb 2"] = df["Jobb"].cummax()
    df["Grannar 2"] = df["Grannar"].cummax()
    df["Tjej PojkV 2"] = df["Tjej PojkV"].cummax()
    df["Nils fam 2"] = df["Nils fam"].cummax()

    df["Summa singel"] = (df["Tid s"] + df["Vila"]) * df["Totalt män"]
    df["Summa dubbel"] = ((df["Tid d"] + df["Vila"]) + 9) * (df["DM"] + df["DF"] + df["DR"])
    df["Summa trippel"] = ((df["Tid t"] + df["Vila"]) + 15) * (df["TPP"] + df["TAP"] + df["TPA"])
    df["Summa tid"] = df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"]

    df["Snitt"] = df["DeepT"] / df["Grabbar"].replace(0, 1)
    df["Total tid"] = df["Snitt"] * (df["Sekunder"] * df["Varv"])
    df["Tid kille DT"] = df["Total tid"] / df["Totalt män"].replace(0, 1)
    df["Runk"] = (df["Total tid"] * 0.6) / df["Totalt män"].replace(0, 1)
    df["Suger"] = (df["Summa tid"] * 0.6) / df["Totalt män"].replace(0, 1)

    df["Tid kille"] = df["Tid s"] + (df["Tid d"] * 2) + (df["Tid t"] * 3) + df["Suger"] + df["Tid kille DT"] + df["Runk"]

    df["Klockan"] = pd.to_datetime("07:00:00") + pd.to_timedelta(
        (df["Summa singel"] + df["Summa dubbel"] + df["Summa trippel"] + df["Total tid"]) / 60, unit='m')

    df["Hårdhet"] = (
        (df["Män"] > 0).astype(int)
        + (df["DM"] > 0).astype(int) * 2
        + (df["DF"] > 0).astype(int) * 2
        + (df["DR"] > 0).astype(int) * 4
        + (df["TPP"] > 0).astype(int) * 4
        + (df["TAP"] > 0).astype(int) * 6
        + (df["TPA"] > 0).astype(int) * 5
    )
    df["Filmer"] = (
        df["Män"] + df["F"] + df["R"] +
        df["DM"] * 2 + df["DF"] * 2 + df["DR"] * 3 +
        df["TPP"] * 4 + df["TAP"] * 6 + df["TPA"] * 5
    ) * df["Hårdhet"]

    df["Pris USD"] = 19.99
    df["Intäkter"] = df["Filmer"] * df["Pris USD"]
    df["Malin lön"] = df["Intäkter"] * 0.05
    df["Malin lön"] = df["Malin lön"].clip(upper=1500)
    df["Företagets lön"] = df["Intäkter"] * 0.4
    df["Vänners lön"] = df["Intäkter"] - df["Malin lön"] - df["Företagets lön"]
    return df

# --- Huvudfunktion ---
def main():
    st.title("Malin App")
    worksheet, df = load_data()
    df = perform_calculations(df)

    # --- HUVUDVY ---
    st.header("📊 Huvudvy – Summeringar")
    st.markdown(f"**Totalt antal män:** {df['Totalt män'].sum()}")
    st.markdown(f"**Känner:** {df['Känner 2'].sum()}")
    st.markdown(f"**Jobb:** {df['Jobb 2'].max()}")
    st.markdown(f"**Grannar + Grannar 2:** {df['Grannar'].sum()} + {df['Grannar 2'].max()}")
    st.markdown(f"**Tjej PojkV:** {df['Tjej PojkV 2'].max()}")
    st.markdown(f"**Nils fam:** {df['Nils fam 2'].max()}")

    aktiv_rad = df[df["Män"] > 0]
    aktiv_rows = aktiv_rad.shape[0]
    st.markdown(f"**Snitt film:** {(df['Totalt män'] + df['Känner']).sum() / aktiv_rows:.2f}" if aktiv_rows > 0 else "0")

    st.markdown(f"**GangB:** {df['Känner'].sum() / df['Känner 2'].sum():.2f}")
    st.markdown(f"**Älskat:** {df['Älskar'].sum() / df['Känner 2'].sum():.2f}")
    st.markdown(f"**Sover med:** {df['Sover med'].sum() / df['Nils fam 2'].sum():.2f}")

    vita = df["Totalt män"].sum()
    svarta = df["Män"].sum()
    vita_procent = 100 * (vita - svarta) / vita if vita > 0 else 0
    st.markdown(f"**Vita (%):** {vita_procent:.1f}%")

    st.markdown(f"**🎥 Filmer:** {df['Filmer'].sum()}")
    st.markdown(f"**💵 Intäkter:** {df['Intäkter'].sum():,.2f} USD")
    st.markdown(f"**Malin lön:** {df['Malin lön'].sum():,.2f} USD")
    st.markdown(f"**Företagets lön:** {df['Företagets lön'].sum():,.2f} USD")
    st.markdown(f"**Vänners lön per känner:** {(df['Vänners lön'].sum() / df['Känner 2'].sum()):.2f} USD")

    # --- RADVY ---
    st.header("📝 Radvy – Redigering per dag")
    for i, row in df.iterrows():
        with st.expander(f"Rad {i+1}: {row['Datum']}"):
            st.write(row[[
                "Totalt män", "Känner", "Summa tid", "Tid kille", "Klockan", "Filmer", "Intäkter", "Hårdhet"
            ]])
            if row["Tid kille"] < 600:
                tid_s = st.number_input(f"Tid s (rad {i+1})", value=row["Tid s"], step=1, key=f"tid_s_{i}")
                tid_d = st.number_input(f"Tid d (rad {i+1})", value=row["Tid d"], step=1, key=f"tid_d_{i}")
                tid_t = st.number_input(f"Tid t (rad {i+1})", value=row["Tid t"], step=1, key=f"tid_t_{i}")
                sek = st.number_input(f"DeepT Sekunder (rad {i+1})", value=row["Sekunder"], step=1, key=f"sek_{i}")
                varv = st.number_input(f"Varv (rad {i+1})", value=row["Varv"], step=1, key=f"varv_{i}")
                if st.button("✅ Spara ändringar", key=f"spara_{i}"):
                    df.at[i, "Tid s"] = tid_s
                    df.at[i, "Tid d"] = tid_d
                    df.at[i, "Tid t"] = tid_t
                    df.at[i, "Sekunder"] = sek
                    df.at[i, "Varv"] = varv
                    df = perform_calculations(df)
                    save_data(worksheet, df)
                    st.success("Sparat!")

    # --- KNAPPAR ---
    st.header("⚙️ Verktyg")
    if st.button("➕ Lägg till tom rad"):
        new_row = df.iloc[-1].copy()
        new_row["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(worksheet, df)
        st.success("Ny rad tillagd")

    if st.button("🎲 Slumpmässig rad (jobb)"):
        new_row = df.iloc[-1].copy()
        new_row["Datum"] = (pd.to_datetime(df.iloc[-1]["Datum"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for col in ["Tid s", "Tid d", "Tid t", "Vila", "DeepT", "Grabbar", "Sekunder", "Varv"]:
            new_row[col] = int(df[col].min()) + int((df[col].max() - df[col].min()) * 0.5)
        new_row["Älskar"] = 8
        new_row["Sover med"] = 1
        new_row["Vila"] = 7
        new_row["Älsk tid"] = 30
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df = perform_calculations(df)
        save_data(worksheet, df)
        st.success("Slumpmässig rad tillagd")

if __name__ == "__main__":
    main()
