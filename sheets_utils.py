# sheets_utils.py — robust 429/backoff + cachead Spreadsheet-handle

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from collections.abc import Mapping
import time

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
    Stöder GOOGLE_CREDENTIALS som:
      - TOML-tabell / dict
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
                "GOOGLE_CREDENTIALS (str) måste vara giltig JSON eller läggas som TOML-tabell i secrets.toml."
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

@st.cache_resource(show_spinner=False)
def get_spreadsheet() -> Spreadsheet:
    """
    Cachear ett öppnat Spreadsheet-handle (minskar 'open_by_url'-läsningar).
    Innehåller exponential backoff för att rida ut 429 RATE_LIMIT_EXCEEDED.
    """
    if "SHEET_URL" not in st.secrets:
        raise RuntimeError("SHEET_URL saknas i st.secrets.")
    client = _get_gspread_client()
    url = st.secrets["SHEET_URL"]

    last_err = None
    delay = 0.5
    for _ in range(8):  # upp till ~8 försök med backoff
        try:
            return client.open_by_url(url)
        except Exception as e:
            last_err = e
            time.sleep(delay)
            delay = min(8.0, delay * 1.8)
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

def _get_or_create_primary_data_ws(ss: Spreadsheet, profile: str) -> Worksheet:
    """
    Använd **alltid** primärbladet: 'Data - {profile}'.
    Skapa om det saknas. Inga andra blad används/migreras.
    """
    title = _primary_data_title(profile)
    ws = _get_ws_by_title(ss, title)
    if ws is not None:
        return ws
    return ss.add_worksheet(title=title, rows=1, cols=1)


# =============================
# Profiler
# =============================

@st.cache_data(show_spinner=False, ttl=5)
def list_profiles() -> List[str]:
    """
    Läs profilnamn från bladet 'Profil', kolumn A. Cacheas i 5 sek.
    Kastar inte vidare läsfel — returnerar [] istället, hanteras i app.py.
    """
    ss = get_spreadsheet()
    ws = _get_ws_by_title(ss, "Profil")
    if ws is None:
        return []
    try:
        col = ws.col_values(1)  # 1 läsning (snålt)
    except APIError:
        return []
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

    # Heuristik: key/value per rad
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

    # Header + en rad
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
    ss = get_spreadsheet()
    ws = None
    for title in _settings_candidates(profile):
        ws = _get_ws_by_title(ss, title)
        if ws is not None:
            break
    if ws is None:
        return {}
    try:
        return _read_kv_sheet(ws)
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa inställningar för '{profile}': {e}")

def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    ss = get_spreadsheet()
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
# Data – läsa & skriva
# =============================

def _records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Viktigt: vi gör **ingen** numerisk tvångskonvertering här.
    Allt lämnas som object/str för att undvika NaN→int-fel i app-logiken.
    """
    if not records:
        return pd.DataFrame()
    normed = [{k: ("" if v is None else v) for k, v in rec.items()} for rec in records]
    return pd.DataFrame(normed, dtype=object)

def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läs alla rader för profil från **endast** 'Data - {profile}'.
    Skapa bladet om det saknas. Inga andra blad används.
    """
    ss = get_spreadsheet()
    ws = _get_or_create_primary_data_ws(ss, profile)

    try:
        records = ws.get_all_records(default_blank="")
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa data för '{profile}': {e}")

    return _records_to_dataframe(records)

def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """
    Lägg till en rad i **primärbladet** 'Data - {profile}'.
    Optimerad: läser ENDAST header-raden (rad 1) – INTE hela bladet.
    Uppdaterar header vid behov, och appender sedan raden.
    """
    ss = get_spreadsheet()
    ws = _get_or_create_primary_data_ws(ss, profile)

    try:
        headers = ws.row_values(1)  # billig läsning av endast rad 1
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa header för '{ws.title}': {e}")

    if not headers:
        headers = list(row.keys())
        values = [row.get(h, "") for h in headers]
        ws.update("A1", [headers])
        ws.append_row(values, value_input_option="USER_ENTERED")
        return

    new_cols = [k for k in row.keys() if k not in headers]
    if new_cols:
        headers_extended = headers + new_cols
        ws.update("A1", [headers_extended])
        headers = headers_extended

    values = [row.get(h, "") for h in headers]
    ws.append_row(values, value_input_option="USER_ENTERED")
