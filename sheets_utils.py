# sheets_utils.py
import json
import pandas as pd
import streamlit as st

def _get_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS eller SHEET_URL i secrets.")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)
    ss = gc.open_by_url(st.secrets["SHEET_URL"])
    return ss

def _ensure_ws(ss, title, rows=4000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def data_title_for(profile_name: str) -> str:
    # En egen dataflik per profil
    return f"Data - {profile_name}"

# ---------------------------
# Profil-listan (flik: Profil)
# ---------------------------
def get_profile_names() -> list:
    try:
        ss = _get_client()
        try:
            ws = ss.worksheet("Profil")
        except Exception:
            return []
        names = ws.col_values(1) or []
        return [n.strip() for n in names if str(n).strip()]
    except Exception:
        return []

# ----------------------------------------
# Inställningar (flik med exakt profilnamn)
# ----------------------------------------
def load_profile_config(profile_name: str) -> dict:
    ss = _get_client()
    ws = _ensure_ws(ss, profile_name)
    rows = ws.get_all_values()
    cfg = {}
    for r in rows:
        if len(r) < 2:
            continue
        k = str(r[0]).strip()
        v = r[1]
        if not k:
            continue
        # försök typa
        try:
            if k in ("startdatum", "fodelsedatum"):
                cfg[k] = str(v)
            elif str(v).strip() == "":
                cfg[k] = 0
            elif "." in str(v):
                cfg[k] = float(v)
            else:
                cfg[k] = int(v)
        except Exception:
            cfg[k] = v
    return cfg

def save_profile_config(profile_name: str, cfg: dict):
    ss = _get_client()
    ws = _ensure_ws(ss, profile_name)
    rows = [["Key","Value"]]
    for k, v in cfg.items():
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        rows.append([k, str(v)])
    ws.clear()
    ws.update("A1", rows)

# ----------------------------------------
# Data per profil (flik: Data - <profil>)
# ----------------------------------------
def _get_data_ws(profile_name: str):
    ss = _get_client()
    title = data_title_for(profile_name)
    return _ensure_ws(ss, title)

def load_profile_rows(profile_name: str) -> pd.DataFrame:
    ws = _get_data_ws(profile_name)
    recs = ws.get_all_records() or []
    df = pd.DataFrame(recs)

    # typning
    numeric_cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Känner","Känner sammanlagt","Totalt Män",
        "Bonus deltagit","Personal deltagit",
        "Prenumeranter","Hårdhet",
        "Summa S (sek)","Summa D (sek)","Summa TP (sek)","Summa tid (sek)",
        "Suger","Suger per kille (sek)","Händer per kille (sek)","Händer aktiv",
        "Intäkter","Intäkt Känner","Kostnad män","Intäkt företag","Lön Malin","Vinst"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "Profil" in df.columns:
        df["Profil"] = df["Profil"].astype(str).fillna("")

    return df.reset_index(drop=True)

def append_row_to_profile(profile_name: str, row: dict):
    ws = _get_data_ws(profile_name)

    # säkerställ Profil-fältet
    if "Profil" not in row:
        row["Profil"] = profile_name

    # header-hantering
    header = ws.row_values(1) or []
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])

    # utöka header med nya kolumner om det tillkommit
    extra = [k for k in row.keys() if k not in header]
    if extra:
        header.extend(extra)
        ws.update("A1", [header])

    # bygg värderad i rätt ordning
    values = [row.get(col, "") for col in header]
    ws.append_row(values)
