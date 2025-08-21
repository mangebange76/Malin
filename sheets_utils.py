# sheets_utils.py
import json
import pandas as pd
import streamlit as st

def _get_client_and_ss():
    """Returnerar (gspread_client, spreadsheet). Kräver st.secrets['GOOGLE_CREDENTIALS'] + ['SHEET_URL']."""
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Secrets för Google saknas (GOOGLE_CREDENTIALS och/eller SHEET_URL).")

    from google.oauth2.service_account import Credentials
    import gspread

    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return client, ss

def _ensure_ws(ss, title, rows=4000, cols=120):
    """Hämta/Skapa ett worksheet med titel."""
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

# ---------- Profiler ----------
def list_profiles():
    """Hämtar profilnamn från fliken 'Profil' (kolumn A)."""
    _, ss = _get_client_and_ss()
    ws = _ensure_ws(ss, "Profil")
    vals = ws.col_values(1)
    profiles = [v.strip() for v in vals if str(v).strip()]
    return profiles

def read_profile_settings(profile_name: str) -> dict:
    """
    Läser inställningar från bladet med samma namn som profilen.
    Stöd: 'Key/Value' eller första två kolumner = nyckel/värde.
    Returnerar dict.
    """
    if not profile_name:
        return {}
    _, ss = _get_client_and_ss()
    ws = _ensure_ws(ss, profile_name)

    values = ws.get_all_values()
    if not values:
        return {}

    # Försök tolka som Key/Value-tabell
    header = [h.strip().lower() for h in values[0]] if values else []
    key_candidates = {"key", "nyckel"}
    val_candidates = {"value", "värde", "varde"}
    cfg = {}

    def _auto_cast(s):
        # robust typning: int -> int, float med , eller . -> float, annars original str
        if s is None:
            return ""
        s2 = str(s).strip()
        if s2 == "":
            return ""
        # int?
        if s2.isdigit() or (s2.startswith("-") and s2[1:].isdigit()):
            try:
                return int(s2)
            except:
                pass
        # float?
        try:
            s3 = s2.replace(",", ".")
            return float(s3)
        except:
            return s

    if header and any(h in key_candidates for h in header) and any(h in val_candidates for h in header):
        # har "key/value"-typer
        # hitta index
        key_idx = next((i for i,h in enumerate(header) if h in key_candidates), 0)
        val_idx = next((i for i,h in enumerate(header) if h in val_candidates), 1)
        for row in values[1:]:
            if len(row) <= key_idx:
                continue
            key = str(row[key_idx]).strip()
            if not key:
                continue
            val = row[val_idx] if len(row) > val_idx else ""
            cfg[key] = _auto_cast(val)
    else:
        # ta första två kolumner som nyckel/värde
        for row in values:
            if len(row) < 2:
                continue
            key = str(row[0]).strip()
            if not key:
                continue
            val = row[1]
            cfg[key] = _auto_cast(val)

    return cfg

def save_profile_settings(profile_name: str, cfg: dict):
    """Skriver HELA cfg som Key/Value till profilens blad (ersätter innehåll)."""
    if not profile_name:
        raise RuntimeError("Ingen profil vald.")
    _, ss = _get_client_and_ss()
    ws = _ensure_ws(ss, profile_name)
    # skriv om allt: key/value
    rows = []
    for k, v in cfg.items():
        if hasattr(v, "strftime"):
            v = v.strftime("%Y-%m-%d")
        rows.append([k, str(v)])
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

# ---------- Data per profil ----------
def _read_df(ws) -> pd.DataFrame:
    try:
        recs = ws.get_all_records()
        return pd.DataFrame(recs)
    except Exception:
        vals = ws.get_all_values()
        if not vals:
            return pd.DataFrame()
        header = vals[0]
        rows = vals[1:]
        return pd.DataFrame(rows, columns=header)

def read_profile_data(profile_name: str) -> pd.DataFrame:
    """
    Läser scen-data för profilen. Primärt från blad 'Data_<Profil>'.
    Om ej finns: försök 'Data' och filtrera på kolumn 'Profil'.
    """
    if not profile_name:
        return pd.DataFrame()
    _, ss = _get_client_and_ss()
    # Försök Data_<Profil>
    title = f"Data_{profile_name}"
    try:
        ws = ss.worksheet(title)
        df = _read_df(ws)
        return df
    except Exception:
        pass

    # Fallback: Data, filtrera
    try:
        ws_data = _ensure_ws(ss, "Data")
        df = _read_df(ws_data)
        if "Profil" in df.columns:
            return df[df["Profil"] == profile_name].copy()
        return df
    except Exception:
        return pd.DataFrame()

def append_row_to_profile_data(profile_name: str, row: dict):
    """Append: lägg till rad i 'Data_<Profil>' (skapar bladet vid behov)."""
    if not profile_name:
        raise RuntimeError("Ingen profil vald.")
    _, ss = _get_client_and_ss()
    title = f"Data_{profile_name}"
    ws = _ensure_ws(ss, title)

    # Befintlig header?
    header = ws.row_values(1)
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])

    # Se till att vi inte tappar nya fält
    new_cols = [k for k in row.keys() if k not in header]
    if new_cols:
        # utöka header: append i slutet
        header = header + new_cols
        ws.update("A1", [header])

    # Mappa rad till header-ordning
    values = [row.get(col, "") for col in header]
    ws.append_row(values)
