# sheets_utils.py
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SHEET_NAME = "Data"
PROFILE_SHEET = "Profil"
CFG_SHEET = "Inställningar"

def skapa_koppling(secrets):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(secrets, scopes=scope)
    client = gspread.authorize(credentials)
    return client

def hamta_data_fran_sheet(client, sheet_url, sheet_name=SHEET_NAME):
    """Hämtar hela datafliken från Google Sheets som DataFrame."""
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(sheet_name)
    rows = ws.get_all_records()
    return pd.DataFrame(rows)

def spara_data_till_sheet(client, sheet_url, df, sheet_name=SHEET_NAME):
    """Sparar en DataFrame till angiven flik i Google Sheets."""
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(sheet_name)
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

def hamta_inställningar(client, sheet_url):
    """Hämtar nyckel/värde-par från inställningsfliken."""
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(CFG_SHEET)
    inst_df = pd.DataFrame(ws.get_all_records())
    cfg = {}
    for _, row in inst_df.iterrows():
        nyckel = str(row.get("Nyckel", "")).strip()
        värde = str(row.get("Värde", "")).strip()
        if not nyckel:
            continue
        try:
            cfg[nyckel] = int(värde)
        except:
            try:
                cfg[nyckel] = float(värde)
            except:
                cfg[nyckel] = värde
    return cfg

def hamta_profil_lista(client, sheet_url):
    """Hämtar lista med alla tillgängliga profilnamn."""
    sh = client.open_by_url(sheet_url)
    ws = sh.worksheet(PROFILE_SHEET)
    return ws.col_values(1)

def hamta_profil_data(client, sheet_url, profilnamn):
    """Hämtar hela bladet för en specifik profil."""
    sh = client.open_by_url(sheet_url)
    try:
        ws = sh.worksheet(profilnamn)
        rows = ws.get_all_records()
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()

def hamta_scen_data(client, sheet_url, profilnamn):
    """Filtrerar ut scenrader från fliken 'Data' för en specifik profil."""
    df = hamta_data_fran_sheet(client, sheet_url)
    return df[df["Profil"] == profilnamn].copy() if "Profil" in df.columns else pd.DataFrame()
