# sheets_utils.py
import json
from datetime import date, time, datetime
import streamlit as st

# ---- Interna hjälpmetoder ----
def _open_spreadsheet():
    """Öppna Google Sheet via secrets. Kräver GOOGLE_CREDENTIALS + SHEET_URL."""
    try:
        creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
        sheet_url = st.secrets["SHEET_URL"]
    except KeyError as e:
        raise RuntimeError(f"Saknar secret: {e}. Lägg till GOOGLE_CREDENTIALS och SHEET_URL i st.secrets.")

    # Tillåt både str och mapping
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        # säker konvertering av toml->json
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    from google.oauth2.service_account import Credentials
    import gspread

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(sheet_url)

def _ensure_ws(ss, title, rows=4000, cols=120):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def _coerce_value_by_key(key: str, val: str):
    """Försök typa config-värden smart, med specialfall för datum/tid."""
    if val is None:
        return val
    s = str(val).strip()

    # Specifika nycklar som ska bli date/time
    if key in ("startdatum", "fodelsedatum"):
        # Tillåt både YYYY-MM-DD och YYYY/MM/DD
        s2 = s.replace("/", "-")
        try:
            y, m, d = [int(x) for x in s2.split("-")]
            return date(y, m, d)
        except Exception:
            return s
    if key == "starttid":
        try:
            # HH:MM eller HH:MM:SS
            parts = [int(x) for x in s.split(":")]
            if len(parts) == 2:
                return time(parts[0], parts[1], 0)
            if len(parts) == 3:
                return time(parts[0], parts[1], parts[2])
        except Exception:
            return s

    # Generisk typning: int -> float -> bool -> str
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass
    try:
        return float(s)
    except Exception:
        pass
    s_low = s.lower()
    if s_low in ("true", "false"):
        return s_low == "true"
    return s

def _to_string_for_sheet(v):
    """Konvertera till str för Sheets-skrivning."""
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return str(v)

# ---- Publika funktioner som app.py importerar ----
def list_profiles():
    """
    Läser bladet 'Profil' och returnerar en list med namn (kolumn A).
    Om bladet saknas -> tom lista.
    """
    try:
        ss = _open_spreadsheet()
        try:
            ws = ss.worksheet("Profil")
        except Exception:
            return []
        names = ws.col_values(1) or []
        return [n.strip() for n in names if n and str(n).strip().lower() != "profil"]
    except Exception as e:
        # Visa ett snällt fel i UI:t men låt funktionen returnera []
        st.warning(f"Kunde inte läsa profiler: {e}")
        return []

def read_profile_settings(profile_name: str) -> dict:
    """
    Läser in inställningar för en profil från ett blad med samma namn.
    Förväntat format: två kolumner (Key/Value) eller (Nyckel/Värde).
    Ok att ha header-rad.
    Returnerar en dict med typade värden.
    """
    if not profile_name:
        return {}
    ss = _open_spreadsheet()
    ws = _ensure_ws(ss, profile_name)

    values = ws.get_all_values()
    if not values:
        return {}

    # Hoppa ev. header-rad om den ser ut som Key/Value
    start_row = 0
    if values and len(values[0]) >= 2:
        h0 = values[0][0].strip().lower()
        h1 = values[0][1].strip().lower()
        if h0 in ("key", "nyckel") and h1 in ("value", "värde", "varde"):
            start_row = 1

    cfg = {}
    for row in values[start_row:]:
        if not row:
            continue
        key = (row[0] if len(row) > 0 else "").strip()
        val = (row[1] if len(row) > 1 else "").strip()
        if not key:
            continue
        cfg[key] = _coerce_value_by_key(key, val)

    return cfg

def save_profile_settings(profile_name: str, cfg: dict):
    """
    Skriver hela CFG till ett blad med profilens namn som två kolumner (Key/Value).
    Nyskapar bladet om det inte finns.
    """
    if not profile_name:
        raise RuntimeError("Profilnamn saknas.")

    ss = _open_spreadsheet()
    ws = _ensure_ws(ss, profile_name)

    # Bygg rader (Key, Value)
    rows = []
    # Sortera nycklar för determinism (valfritt)
    for k in sorted(cfg.keys()):
        v = cfg[k]
        rows.append([k, _to_string_for_sheet(v)])

    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def _read_ws_as_df(ws):
    """Läs ett worksheet till DataFrame via get_all_records/högsta radprecision."""
    # get_all_records använder första raden som header
    records = ws.get_all_records()
    try:
        import pandas as pd
        return pd.DataFrame(records)
    except Exception:
        # Om pandas saknas (borde inte hända i Streamlit), fallback:
        return records

def read_profile_data(profile_name: str):
    """
    Läser data för profil. Först försöker vi 'Data_<Profil>',
    annars fall-back till 'Data' och filtrerar kolumnen 'Profil' == profilnamnet.
    Returnerar DataFrame (kan vara tom).
    """
    import pandas as pd
    ss = _open_spreadsheet()

    # 1) Försök Data_<Profil>
    target_title = f"Data_{profile_name}"
    try:
        ws = ss.worksheet(target_title)
        df = _read_ws_as_df(ws)
        # Säkerställ att df är en DataFrame
        if isinstance(df, list):
            df = pd.DataFrame(df)
        return df if not df.empty else pd.DataFrame()
    except Exception:
        pass

    # 2) Fallback: global "Data" med filter på kolumn "Profil"
    try:
        ws = ss.worksheet("Data")
        df = _read_ws_as_df(ws)
        if isinstance(df, list):
            df = pd.DataFrame(df)
        if "Profil" in df.columns:
            return df[df["Profil"] == profile_name].copy()
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def append_row_to_profile_data(profile_name: str, row: dict):
    """
    Appendar en rad till 'Data_<Profil>' (skapas och förses med header automatiskt vid behov).
    Om profilnamn saknas – skriver till global 'Data' och inkluderar fältet 'Profil'.
    """
    ss = _open_spreadsheet()
    target = f"Data_{profile_name}" if profile_name else "Data"
    ws = _ensure_ws(ss, target)

    # Befintlig header?
    header = ws.row_values(1)
    if not header:
        # skapa header från row-nycklar (stabil ordning)
        header = list(row.keys())
        ws.update("A1", [header])
    else:
        # Se till att alla nycklar finns i headern
        new_keys = [k for k in row.keys() if k not in header]
        if new_keys:
            header = header + new_keys
            ws.update("A1", [header])

    # Mappa enligt header
    values = [_to_string_for_sheet(row.get(col, "")) for col in header]
    ws.append_row(values)
