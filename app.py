import streamlit as st
import pandas as pd
import numpy as np
import random
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from statistik import compute_stats

st.set_page_config(page_title="Malin-produktionsapp", layout="wide")

SHEET_URL = st.secrets["SHEET_URL"]
CFG_KEY = "INSTÄLLNINGAR"
PROFILE_SHEET = "Profil"
DATA_SHEET = "Data"
BONUS_LEFT_KEY = "BONUS_KVAR"

# Används för att identifiera vilka kolumner vi jobbar med
KOLUMNER_PROFIL = [
    "Födelsedatum", "Eskilstuna killar", "Bekanta", "Svarta",
    "Pappans vänner", "Grannar", "Nils vänner", "Nils familj",
    "Totalt personal", "Längd (m)"
]

KOLUMNER_DATA = [
    # De här läses in från data-bladet och är dynamiskt kopplade till profilen
    "Datum", "Veckodag", "Typ", "Män", "Svarta", "Bekanta", "Eskilstuna killar",
    "Känner", "Bonus killar", "Bonus deltagit", "Tid (h)", "Tid kille (min)",
    "Intäkt känner", "Kostnad män", "Intäkt företag", "Lön Malin", "Vinst",
    "S", "D", "TP", "Händer", "Suger"
]

DEFAULT_CFG = {
    "startdatum": datetime(1990, 1, 1).date(),
    "fodelsedatum": datetime(1970, 1, 1).date(),
    "bonus_procent": 1.0
}

def skapa_koppling():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
    client = gspread.authorize(credentials)
    return client.open_by_url(SHEET_URL)

def läs_profilnamn():
    ark = skapa_koppling()
    try:
        profilblad = ark.worksheet(PROFILE_SHEET)
        namn = profilblad.col_values(1)[1:]  # Skippa rubriken
        return [n for n in namn if n]
    except:
        return []

def läs_inställningar(profil_namn):
    ark = skapa_koppling()
    try:
        blad = ark.worksheet(profil_namn)
        df = pd.DataFrame(blad.get_all_records())
        inst = df.iloc[0].to_dict() if not df.empty else {}
    except:
        inst = {}

    # Konvertera datumfält
    if "Födelsedatum" in inst:
        try:
            inst["Födelsedatum"] = pd.to_datetime(inst["Födelsedatum"]).date()
        except:
            inst["Födelsedatum"] = DEFAULT_CFG["fodelsedatum"]
    else:
        inst["Födelsedatum"] = DEFAULT_CFG["fodelsedatum"]

    inst.setdefault("Längd (m)", 1.64)
    inst.setdefault("bonus_procent", DEFAULT_CFG["bonus_procent"])

    return inst

def läs_data():
    ark = skapa_koppling()
    try:
        blad = ark.worksheet(DATA_SHEET)
        df = pd.DataFrame(blad.get_all_records())
        return df
    except:
        return pd.DataFrame(columns=KOLUMNER_DATA)

def spara_data(df):
    ark = skapa_koppling()
    blad = ark.worksheet(DATA_SHEET)
    blad.clear()
    blad.update([df.columns.tolist()] + df.astype(str).values.tolist())

# Val av profil
tillgängliga_profiler = läs_profilnamn()
vald_profil = st.sidebar.selectbox("Välj profil", tillgängliga_profiler)

# Ladda inställningar för vald profil
profilinst = läs_inställningar(vald_profil)
CFG = DEFAULT_CFG.copy()
CFG.update(profilinst)

# Titel med namn från vald profil
st.title(f"Produktion – {vald_profil}")

# Visa nuvarande inställningar
with st.expander("Inställningar"):
    st.write("Födelsedatum:", CFG["fodelsedatum"])
    st.write("Startdatum:", CFG["startdatum"])
    st.write("Längd (m):", CFG.get("Längd (m)", 1.64))
    st.write("Bonus % av prenumeranter:", CFG.get("bonus_procent", 0.01))

# Data – ladda databladen
rows_df = läs_data()

# Statistik – (enkel placeholder från statistik.py)
from statistik import compute_stats
statistik = compute_stats(rows_df, CFG)

with st.expander("📊 Statistik"):
    for nyckel, värde i statistik.items():
        st.write(f"{nyckel}: {värde}")

from datetime import timedelta

def bestäm_datum(cfg, scen_nr):
    try:
        return cfg["startdatum"] + timedelta(days=scen_nr - 1)
    except Exception as e:
        st.error(f"Fel i datumräkning: {e}")
        return datetime.today().date()

def slumpa_prenumeranter():
    return random.randint(1000, 10000)

def slumpa_bonus(cfg, antal_prenumeranter):
    bonus_procent = cfg.get("bonus_procent", 0.01)
    return int(antal_prenumeranter * bonus_procent)

def lägg_till_scenrad(cfg, scen_nr):
    datum = bestäm_datum(cfg, scen_nr)
    pren = slumpa_prenumeranter()
    bonus = slumpa_bonus(cfg, pren)
    rad = {
        "Datum": datum,
        "Scen#": scen_nr,
        "Prenumeranter": pren,
        "Bonus killar": bonus,
        "Bonus deltagit": 0,
        "Händer aktiv": "Ja",  # standardaktivt
        # Fler fält fylls i senare i input-vyn
    }
    return rad

def scenformulär(cfg, scen_nr):
    with st.form("scenformulär"):
        st.markdown(f"### Ny scen #{scen_nr}")

        datum = bestäm_datum(cfg, scen_nr)
        st.write(f"**Datum:** {datum}")

        # Nyckelfält
        aktivitet = st.selectbox("Aktivitet", ["Scen", "Vila på plats", "Vilovecka hemma"])
        prenumeranter = st.number_input("Prenumeranter", value=slumpa_prenumeranter(), step=100)
        bonus_killar = st.number_input("Bonus killar", value=slumpa_bonus(cfg, prenumeranter), step=1)
        bonus_deltagit = st.number_input("Bonus deltagit", value=0, step=1)
        händer = st.radio("Händer aktiv", ["Ja", "Nej"])

        # Andra exempel på fält (lägg till fler här)
        antal_s = st.number_input("Antal S", value=0, step=1)
        antal_d = st.number_input("Antal D", value=0, step=1)
        antal_tp = st.number_input("Antal TP", value=0, step=1)
        totalt_män = st.number_input("Totalt män på raden", value=0, step=1)

        # Spara-knapp
        submitted = st.form_submit_button("Spara rad")

        if submitted:
            rad = {
                "Datum": datum,
                "Scen#": scen_nr,
                "Aktivitet": aktivitet,
                "Prenumeranter": prenumeranter,
                "Bonus killar": bonus_killar,
                "Bonus deltagit": bonus_deltagit,
                "Händer aktiv": händer,
                "S": antal_s,
                "D": antal_d,
                "TP": antal_tp,
                "Totalt män": totalt_män,
            }
            return rad
    return None

def beräkna_tid_kille(rad):
    try:
        män = max(rad.get("Totalt män", 0), 1)
        s = rad.get("S", 0)
        d = rad.get("D", 0)
        tp = rad.get("TP", 0)

        # Suger: 80% av varje kategori dividerat på antal män
        suger = ((s / män) * 0.8) + ((d / män) * 0.8) + ((tp / män) * 0.8)
        suger = round(suger, 3)

        # Händer: samma princip men gånger två (för två händer)
        if rad.get("Händer aktiv", "Ja") == "Ja":
            händer = 2 * (((s / män) * 0.8) + ((d / män) * 0.8) + ((tp / män) * 0.8))
            händer = round(händer, 3)
        else:
            händer = 0.0

        rad["Suger"] = suger
        rad["Händer"] = händer

        # Tid per kille – exempelformel (kan justeras)
        rad["Tid per kille (min)"] = round((s + d * 2 + tp * 3) * 2, 1)

        return rad
    except Exception as e:
        st.error(f"Fel i beräkning av tid per kille: {e}")
        return rad

def spara_rad(df, ny_rad, profilnamn):
    try:
        ny_df = pd.DataFrame([ny_rad])
        df = pd.concat([df, ny_df], ignore_index=True)

        ark_namn = profilnamn.strip()
        sheet = skapa_koppling(ark_namn)
        sheet.clear()
        sheet.update([df.columns.tolist()] + df.astype(str).values.tolist())
        st.success("Rad sparad till Google Sheets.")
    except Exception as e:
        st.error(f"Fel vid sparande: {e}")
    return df


def skapa_koppling(sheet_namn):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["SHEET_URL"]).worksheet(sheet_namn)
    return sheet


def läs_data(profilnamn):
    try:
        ark_namn = profilnamn.strip()
        sheet = skapa_koppling(ark_namn)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Kunde inte läsa data för {profilnamn}: {e}")
        return pd.DataFrame()

from statistik import compute_stats

def visa_statistik(df, cfg):
    st.subheader("📊 Statistik")

    if df.empty:
        st.info("Ingen data att visa statistik för ännu.")
        return

    try:
        stats = compute_stats(df, cfg)
        for nyckel, värde in stats.items():
            st.write(f"**{nyckel}:** {värde}")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")

def main():
    st.set_page_config(layout="wide", page_title="Malin-produktionsapp")
    st.title("🎬 Malin-produktionsapp")

    # Val av profil
    profil_namn = st.selectbox("Välj profil", hamta_profiler())
    if not profil_namn:
        st.warning("Ingen profil vald.")
        return

    # Läs in inställningar + profildata
    try:
        profil_df = hamta_profil_data(profil_namn)
        CFG = skapa_cfg_dict(profil_df)
        rows_df = hamta_scen_data(profil_namn)
    except Exception as e:
        st.error(f"Kunde inte läsa in data för vald profil: {e}")
        return

    # Visa inputfält
    st.divider()
    st.subheader("🎥 Lägg till scen")
    try:
        rows_df = render_input_fields(CFG, rows_df)
    except Exception as e:
        st.error(f"Kunde inte visa inmatningsfält: {e}")
        return

    # Visa statistik
    st.divider()
    visa_statistik(rows_df, CFG)

    # Visa hela databasen för profil
    st.divider()
    st.subheader("📄 Sparad data för denna profil")
    st.dataframe(rows_df)

if __name__ == "__main__":
    main()

def hamta_profiler():
    """Hämtar listan med tillgängliga profiler från fliken 'Profil'."""
    try:
        sheet = skapa_koppling()
        profiler = sheet.worksheet("Profil").col_values(1)
        return [p.strip() for p in profiler if p.strip()]
    except Exception as e:
        st.error(f"Kunde inte läsa profiler: {e}")
        return []

def hamta_profil_data(namn):
    """Hämtar inställningar för vald profil från dess blad."""
    df = skapa_koppling().worksheet(namn).get_all_records()
    return pd.DataFrame(df)

def hamta_scen_data(namn):
    """Hämtar sparade scenrader för vald profil från fliken 'Data'."""
    df = skapa_koppling().worksheet("Data").get_all_records()
    df = pd.DataFrame(df)
    return df[df["Profil"] == namn].copy() if "Profil" in df.columns else df

def skapa_cfg_dict(profil_df):
    """Konverterar inställningsrader från profilens blad till CFG-dict."""
    cfg = {}
    for _, row in profil_df.iterrows():
        nyckel = str(row.get("Nyckel", "")).strip()
        värde = str(row.get("Värde", "")).strip()
        if not nyckel:
            continue
        # Försök konvertera till int eller float
        if värde.isdigit():
            cfg[nyckel] = int(värde)
        else:
            try:
                cfg[nyckel] = float(värde)
            except:
                cfg[nyckel] = värde
    return cfg

def render_input_fields(cfg):
    """Visar formulärfält för manuell inmatning."""
    with st.form("ny_scen_formulär", clear_on_submit=True):
        st.subheader("📝 Ny scen")

        datum = st.date_input("Datum", value=cfg["startdatum"])
        aktivitet = st.selectbox("Typ av scen", ["Vanlig", "Vila på inspelningsplats", "Vilovecka hemma"])
        antal_minuter = st.number_input("Minuter", min_value=0, step=5)
        antal_män = st.number_input("Antal män", min_value=0, max_value=20)
        älskar = st.checkbox("Älskar", value=True)
        händer = st.checkbox("Händer", value=True)
        kommentar = st.text_input("Kommentar")

        submitted = st.form_submit_button("Spara scen")
        if submitted:
            return {
                "Datum": datum,
                "Aktivitet": aktivitet,
                "Minuter": antal_minuter,
                "Antal män": antal_män,
                "Älskar": älskar,
                "Händer": händer,
                "Kommentar": kommentar,
            }
    return None


def spara_rad(cfg, fält):
    """Sparar scenraden till rätt flik i Google Sheets."""
    try:
        sheet = skapa_koppling().worksheet("Data")
        befintlig = sheet.get_all_records()
        df = pd.DataFrame(befintlig)

        ny_rad = fält.copy()
        ny_rad["Profil"] = cfg["profil"]

        # Lägg till kolumner som saknas
        for col in ["Profil", "Datum", "Aktivitet", "Minuter", "Antal män", "Älskar", "Händer", "Kommentar"]:
            if col not in df.columns:
                df[col] = ""

        df = df.append(ny_rad, ignore_index=True)
        sheet.clear()
        sheet.update([df.columns.tolist()] + df.astype(str).values.tolist())
        st.success("✅ Raden sparades.")
    except Exception as e:
        st.error(f"❌ Misslyckades att spara: {e}")

def render_live_and_preview(cfg, rows_df):
    """Renderar aktuell scen och förhandsgranskning samt statistik."""
    base = _build_base(cfg)

    st.subheader("📆 Nästa scen")
    st.write(f"Dagens datum: **{base['_rad_datum'].strftime('%Y-%m-%d')}**")

    preview = calc_row_values(
        base,
        base["_rad_datum"],
        cfg["fodelsedatum"],
        cfg["starttid"]
    )
    st.write("🔍 Förhandsgranskning:")
    st.dataframe(pd.DataFrame([preview]))

    try:
        stats = compute_stats(rows_df, cfg)
        st.subheader("📊 Statistik")
        for nyckel, värde in stats.items():
            st.write(f"- {nyckel}: {värde}")
    except Exception as e:
        st.warning(f"⚠️ Kunde inte beräkna statistik: {e}")

    return base, preview

def main():
    st.title("🎬 Malin Produktionsapp")

    # Val av profil
    profilblad = skapa_koppling("Profil")
    profiler = profilblad.col_values(1)[1:]
    vald_profil = st.selectbox("Välj profil", profiler)
    if not vald_profil:
        st.stop()

    # Läs inställningar från profilens blad
    inst_df = skapa_df(vald_profil)
    inställningar = inst_df.set_index("Fält")["Värde"].to_dict()
    st.session_state[CFG_KEY] = parse_inställningar(inställningar)
    CFG.update(st.session_state[CFG_KEY])

    # Läs in befintlig data från profilspecifikt blad
    try:
        df = skapa_df(vald_profil + "_data")
        rows_df = pd.DataFrame(df)
    except Exception:
        rows_df = pd.DataFrame(columns=ALL_COLUMNS)

    # Visa livevy och förhandsgranskning
    base, preview = render_live_and_preview(CFG, rows_df)

    # Formulär: lägga till scen
    render_scenformulär(base, preview, rows_df, vald_profil + "_data")

if __name__ == "__main__":
    main()

# Extra: säkerställ att rätt kolumner finns om vi läser en tom sheet
def säkerställ_kolumner(sheet_name):
    sheet = skapa_koppling(sheet_name)
    befintliga = sheet.row_values(1)
    om_något_saknas = any(kol not in befintliga for kol in ALL_COLUMNS)
    if om_något_saknas:
        sheet.clear()
        sheet.append_row(ALL_COLUMNS)

# Extra: placeholder för statistik om compute_stats finns
try:
    import statistik
    def visa_statistik(rows_df):
        st.subheader("📊 Statistik")
        if len(rows_df) > 0:
            stats = statistik.compute_stats(rows_df, CFG)
            for k, v in stats.items():
                st.markdown(f"- **{k}:** {v}")
except ImportError:
    def visa_statistik(rows_df):
        st.subheader("📊 Statistik")
        st.warning("Modulen statistik.py kunde inte importeras.")
