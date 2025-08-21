# sheets_utils.py
import json
import streamlit as st

def get_client():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar secrets GOOGLE_CREDENTIALS / SHEET_URL.")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def ensure_ws(ss, title, rows=4000, cols=80):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def list_profiles():
    """Returnerar namnlistan från fliken 'Profil' kolumn A."""
    try:
        ss = get_client()
        ws = ensure_ws(ss, "Profil", rows=100, cols=2)
        names = [x.strip() for x in ws.col_values(1) if x.strip()]
        return names
    except Exception as e:
        st.error(f"Kunde inte läsa profiler: {e}")
        return []

def load_profile_config(profile: str) -> dict:
    """Läser 'Inställningar_<Profil>' som (Key,Value)-tabell."""
    cfg = {}
    try:
        ss = get_client()
        ws = ensure_ws(ss, f"Inställningar_{profile}", rows=200, cols=4)
        values = ws.get_all_values()
        # skip header om finns
        for r in values[1:] if values and values[0] and values[0][0].lower() == "key" else values:
            if not r or len(r) < 2: 
                continue
            k = (r[0] or "").strip()
            v = r[1]
            if not k:
                continue
            # typning
            if k in ("startdatum","fodelsedatum"):
                try:
                    y,m,d = [int(x) for x in str(v).split("-")]
                    cfg[k] = __import__("datetime").date(y,m,d)
                    continue
                except:
                    pass
            # försök int/float
            try:
                if isinstance(v,str) and "." in v:
                    cfg[k] = float(v)
                else:
                    cfg[k] = int(v)
            except:
                # bool?
                if str(v).lower() in ("true","false"):
                    cfg[k] = (str(v).lower()=="true")
                else:
                    cfg[k] = v
        return cfg
    except Exception as e:
        st.error(f"Kunde inte läsa Inställningar för {profile}: {e}")
        return {}

def save_profile_config(profile: str, cfg: dict):
    """Skriver hela dicten till 'Inställningar_<Profil>' som (Key,Value)."""
    try:
        ss = get_client()
        ws = ensure_ws(ss, f"Inställningar_{profile}", rows=200, cols=4)
        rows = [["Key","Value"]]
        from datetime import date, datetime
        for k,v in cfg.items():
            if isinstance(v, (date, datetime)):
                rows.append([k, v.strftime("%Y-%m-%d")])
            else:
                rows.append([k, str(v)])
        ws.clear()
        ws.update("A1", rows)
    except Exception as e:
        st.error(f"Kunde inte spara Inställningar för {profile}: {e}")

def load_profile_rows(profile: str) -> list:
    """Returnerar list[dict] från 'Data_<Profil>' (tom lista om ej finns eller tom)."""
    try:
        ss = get_client()
        ws = ensure_ws(ss, f"Data_{profile}", rows=4000, cols=120)
        records = ws.get_all_records()
        return records or []
    except Exception as e:
        st.error(f"Kunde inte läsa Data för {profile}: {e}")
        return []

def append_profile_row(profile: str, row: dict):
    """Append en rad till 'Data_<Profil>'. Skapar header om tomt."""
    try:
        ss = get_client()
        ws = ensure_ws(ss, f"Data_{profile}", rows=4000, cols=120)

        header = ws.row_values(1)
        if not header:
            header = list(row.keys())
            ws.update("A1", [header])
        values = [row.get(col, "") for col in header]
        ws.append_row(values)
    except Exception as e:
        st.error(f"Kunde inte spara rad för {profile}: {e}")
