# sheets_utils.py
# Version 250823 + auto-merge patch

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from collections.abc import Mapping
import time
import datetime as dt

import streamlit as st
import gspread
import pandas as pd
from gspread import Spreadsheet, Worksheet
from gspread.exceptions import APIError, WorksheetNotFound

# =============================
# Google auth & Spreadsheet
# =============================

def _normalize_private_key(creds: Dict[str, Any]) -> Dict[str, Any]:
    pk = creds.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        creds["private_key"] = pk.replace("\\n", "\n")
    return creds

def _load_google_credentials_dict() -> Dict[str, Any]:
    """
    Accepterar GOOGLE_CREDENTIALS i:
      - TOML-tabell / dict (rekommenderat i secrets.toml)
      - JSON-sträng
      - bytes (JSON)
    """
    if "GOOGLE_CREDENTIALS" not in st.secrets:
        raise RuntimeError("GOOGLE_CREDENTIALS saknas i st.secrets.")

    raw = st.secrets["GOOGLE_CREDENTIALS"]

    if isinstance(raw, Mapping):
        creds = dict(raw)
    elif isinstance(raw, str):
        s = raw.strip()
        try:
            creds = json.loads(s)
        except Exception as e:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS (str) måste vara giltig JSON eller läggas som TOML-tabell."
            ) from e
    elif isinstance(raw, (bytes, bytearray)):
        try:
            creds = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RuntimeError("GOOGLE_CREDENTIALS (bytes) gick inte att JSON-dekoda.") from e
    else:
        raise RuntimeError(f"GOOGLE_CREDENTIALS hade oväntad typ: {type(raw)}")

    return _normalize_private_key(creds)

@st.cache_resource(show_spinner=False)
def _get_gspread_client() -> gspread.Client:
    creds = _load_google_credentials_dict()
    try:
        client = gspread.service_account_from_dict(creds)
    except Exception as e:
        raise RuntimeError(
            "Kunde inte skapa gspread-klient av GOOGLE_CREDENTIALS. "
            "Kontrollera 'client_email' och 'private_key'."
        ) from e
    return client

def _open_spreadsheet(retries: int = 3, delay: float = 0.8) -> Spreadsheet:
    if "SHEET_URL" not in st.secrets:
        raise RuntimeError("SHEET_URL saknas i st.secrets.")
    client = _get_gspread_client()
    last_err = None
    for _ in range(max(1, retries)):
        try:
            return client.open_by_url(st.secrets["SHEET_URL"])
        except Exception as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")

def _get_ws_by_title(ss: Spreadsheet, title: str) -> Optional[Worksheet]:
    try:
        return ss.worksheet(title)
    except WorksheetNotFound:
        return None

# =============================
# Hjälpare för datablads-namn
# =============================

def _primary_data_title(profile: str) -> str:
    return f"Data - {profile}"

def _fallback_data_title(profile: str) -> str:
    return f"{profile}__data"

def _candidate_data_titles(profile: str) -> List[str]:
    return [_primary_data_title(profile), _fallback_data_title(profile)]

def _find_existing_data_ws(ss: Spreadsheet, profile: str) -> Optional[Worksheet]:
    for t in _candidate_data_titles(profile):
        ws = _get_ws_by_title(ss, t)
        if ws is not None:
            return ws
    return None

def _get_or_create_data_ws(ss: Spreadsheet, profile: str) -> Worksheet:
    """
    Returnera primärt datablads-worksheet:
      1) 'Data - {profile}' om det finns
      2) Annars första existerande av kandidaterna
      3) Annars skapa 'Data - {profile}'
    """
    ws = _get_ws_by_title(ss, _primary_data_title(profile))
    if ws is not None:
        return ws
    ws = _find_existing_data_ws(ss, profile)
    if ws is not None:
        return ws
    return ss.add_worksheet(title=_primary_data_title(profile), rows=1, cols=1)

# =============================
# Profiler
# =============================

@st.cache_data(show_spinner=False, ttl=5)
def list_profiles() -> List[str]:
    """
    Läs profilnamn från bladet 'Profil', kolumn A.
    """
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, "Profil")
    if ws is None:
        return []
    try:
        col = ws.col_values(1)
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa bladet 'Profil': {e}")
    names = [x.strip() for x in col if x and x.strip()]
    if names and names[0].lower() in ("profil", "namn", "profiles", "name"):
        names = names[1:]
    return names

# =============================
# Inställningar (key/value)
# =============================

def _coerce_setting(key: str, val: Any) -> Any:
    if val is None:
        return None
    s = str(val).strip()

    def _to_date(x: str):
        try:
            return pd.to_datetime(x).date()
        except Exception:
            return None

    def _to_time(x: str):
        x = x.strip()
        parts = x.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            sec = int(parts[2]) if len(parts) > 2 else 0
            return pd.Timestamp(year=2000, month=1, day=1, hour=h, minute=m, second=sec).time()
        except Exception:
            return None

    if key in ("startdatum", "fodelsedatum"):
        d = _to_date(s)
        return d if d else s
    if key == "starttid":
        t = _to_time(s)
        return t if t else s

    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        if "." in s or "," in s:
            s2 = s.replace(",", ".")
            return float(s2)
        return int(s)
    except Exception:
        return val

def _read_kv_sheet(ws: Worksheet) -> Dict[str, Any]:
    values = ws.get_all_values()
    if not values:
        return {}

    out: Dict[str, Any] = {}

    # Heuristik: key/value per rad om det ser ut som 2 kolumner med många rader
    non_empty_second_col = sum(1 for r in values if len(r) >= 2 and r[1].strip())
    if non_empty_second_col >= 1:
        for r in values:
            if not r:
                continue
            key = (r[0] or "").strip()
            if not key:
                continue
            val = r[1] if len(r) > 1 else ""
            out[key] = _coerce_setting(key, val)
        return out

    # Header + en rad värden
    header = [h.strip() for h in values[0]]
    valrow = values[1] if len(values) > 1 else []
    for i, h in enumerate(header):
        if not h:
            continue
        v = valrow[i] if i < len(valrow) else ""
        out[h] = _coerce_setting(h, v)
    return out

def _settings_candidates(profile: str) -> List[str]:
    return [f"Settings - {profile}", f"{profile}__settings", profile]

def read_profile_settings(profile: str) -> Dict[str, Any]:
    ss = _open_spreadsheet()
    ws = None
    for title in _settings_candidates(profile):
        ws = _get_ws_by_title(ss, title)
        if ws is not None:
            break
    if ws is None:
        return {}
    try:
        data = _read_kv_sheet(ws)
        return data
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa inställningar för '{profile}': {e}")

def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    ss = _open_spreadsheet()
    title = _settings_candidates(profile)[0]  # 'Settings - {profile}'
    ws = _get_ws_by_title(ss, title)
    if ws is None:
        ws = ss.add_worksheet(title=title, rows=2, cols=2)

    def _to_writable(v: Any) -> Any:
        try:
            import datetime as _dt
            if isinstance(v, _dt.date) and not isinstance(v, _dt.datetime):
                return v.isoformat()
            if isinstance(v, _dt.time):
                return v.strftime("%H:%M:%S")
        except Exception:
            pass
        return v

    rows = [[k, _to_writable(v)] for k, v in cfg.items()]
    ws.clear()
    if rows:
        ws.update("A1", rows)

# =============================
# Auto-merge patch (data)
# =============================

def _read_records(ws: Worksheet) -> List[Dict[str, Any]]:
    """
    Läser alla records som list[dict]. Tomt blad → [].
    """
    vals = ws.get_all_values()
    if not vals:
        return []
    header = vals[0]
    data = vals[1:]
    records: List[Dict[str, Any]] = []
    for row in data:
        if all((c is None or str(c).strip() == "") for c in row):
            continue
        rec = {}
        for i, h in enumerate(header):
            if not h:
                continue
            rec[h] = row[i] if i < len(row) else ""
        records.append(rec)
    return records

def _write_table(ws: Worksheet, headers: List[str], rows: List[List[Any]]) -> None:
    ws.clear()
    if headers:
        ws.update("A1", [headers])
    if rows:
        ws.update(f"A2", rows)

def _ensure_merged_data_sheets(ss: Spreadsheet, profile: str) -> Worksheet:
    """
    Om både 'Data - {profile}' och '{profile}__data' finns:
      - slå ihop till 'Data - {profile}'
      - ta union av kolumner (primär ordning först, sedan ev. extra kolumner i den ordning de förekommer i sekundär)
      - ta bort exakta dubletter
      - döp om sekundär till '{profile}__data__backup_YYYYMMDD_HHMMSS'
    Returnerar worksheet som ska användas fortsättningsvis (primär).
    """
    primary_title = _primary_data_title(profile)
    fallback_title = _fallback_data_title(profile)

    ws_primary = _get_ws_by_title(ss, primary_title)
    ws_fallback = _get_ws_by_title(ss, fallback_title)

    # Inget att slå ihop
    if ws_fallback is None or ws_primary is None:
        return ws_primary or ws_fallback or _get_or_create_data_ws(ss, profile)

    # Läs båda
    rec_primary = _read_records(ws_primary)
    rec_fallback = _read_records(ws_fallback)

    # Hämta header-ordningar
    vals_p = ws_primary.get_all_values()
    header_p = vals_p[0] if vals_p else []
    vals_f = ws_fallback.get_all_values()
    header_f = vals_f[0] if vals_f else []

    # Union av headers: primärs ordning först, sedan ev. nya från fallback i deras ordning
    seen = set(h for h in header_p if h)
    headers: List[str] = [h for h in header_p if h]
    for h in header_f:
        if h and h not in seen:
            headers.append(h)
            seen.add(h)

    # Bygg rader enligt headers
    def rec_to_row(rec: Dict[str, Any]) -> List[Any]:
        return [rec.get(h, "") for h in headers]

    all_rows = [rec_to_row(r) for r in rec_primary] + [rec_to_row(r) for r in rec_fallback]

    # Deduplicera exakta rader
    unique_rows: List[List[Any]] = []
    seen_tuples = set()
    for r in all_rows:
        t = tuple(r)
        if t in seen_tuples:
            continue
        seen_tuples.add(t)
        unique_rows.append(r)

    # Skriv ihop i primär
    _write_table(ws_primary, headers, unique_rows)

    # Döp om fallback till backup
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        ws_fallback.update_title(f"{fallback_title}__backup_{stamp}")
    except Exception:
        # Om det skulle misslyckas lämnar vi bladet orört men eftersom titeln inte längre matchar fallback
        # kommer appen ändå att ignorera det framöver.
        pass

    return ws_primary

# =============================
# Data – läsa & skriva
# =============================

def _records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # försök numerisk konvertering
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass
    return df

def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läs alla rader för profil. Om både primär och fallback finns, slå ihop dem
    automatiskt och läs sedan från primär.
    """
    ss = _open_spreadsheet()
    ws = _ensure_merged_data_sheets(ss, profile)
    if ws is None:
        return pd.DataFrame()

    try:
        # använd records → DataFrame
        records = ws.get_all_records(default_blank="")
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa data för '{profile}': {e}")

    return _records_to_dataframe(records)

def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """
    Lägg till en rad i profilens databladsark.
    Auto-merge körs först om både primär och fallback finns.
    """
    ss = _open_spreadsheet()
    ws = _ensure_merged_data_sheets(ss, profile)  # säkerställ primär & sammanslagen

    # Läs befintlig header
    try:
        existing = ws.get_all_values()
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa befintliga värden för '{ws.title}': {e}")

    if not existing:
        headers = list(row.keys())
        values = [row.get(h, "") for h in headers]
        ws.update("A1", [headers, values])
        return

    headers = existing[0] if existing else []
    if not headers:
        headers = list(row.keys())
        ws.update("A1", [headers])

    # Om raden har nya fält som inte finns i header → utöka headern
    new_cols = [k for k in row.keys() if k not in headers]
    if new_cols:
        headers_extended = headers + new_cols
        # hämta befintliga rader (exkl. header)
        body = existing[1:] if len(existing) > 1 else []
        # fyll upp gamla rader med tomma för nya kolumner
        body_ext = [r + [""] * (len(headers_extended) - len(r)) for r in body]
        _write_table(ws, headers_extended, body_ext)
        headers = headers_extended

    values = [row.get(h, "") for h in headers]
    ws.append_row(values, value_input_option="USER_ENTERED")
