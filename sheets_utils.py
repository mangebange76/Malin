# sheets_utils.py
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
    # 1) primär finns?
    ws = _get_ws_by_title(ss, _primary_data_title(profile))
    if ws is not None:
        return ws
    # 2) annan kandidat?
    ws = _find_existing_data_ws(ss, profile)
    if ws is not None:
        return ws
    # 3) skapa primärt
    return ss.add_worksheet(title=_primary_data_title(profile), rows=1, cols=1)

# =============================
# Profiler
# =============================

@st.cache_data(show_spinner=False, ttl=5)
def list_profiles() -> List[str]:
    """
    Läs profilnamn från bladet 'Profil', kolumn A (första kolumnen, utan header).
    """
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, "Profil")
    if ws is None:
        return []
    try:
        col = ws.col_values(1)  # hela kolumn A
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa bladet 'Profil': {e}")
    # filtrera tomma och ev. header
    names = [x.strip() for x in col if x and x.strip()]
    # Ta bort en eventuell rubrikrad "Profil" / "Namn"
    if names and names[0].lower() in ("profil", "namn", "profiles", "name"):
        names = names[1:]
    return names

# =============================
# Inställningar (key/value)
# =============================

def _coerce_setting(key: str, val: Any) -> Any:
    """
    Försök typa om några välkända nycklar till rätt Python-typer som appen väntar sig.
    Datum/tid returneras som date/time-objekt.
    """
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
        # tillåt "HH:MM", "HH:MM:SS"
        parts = x.split(":")
        try:
            h = int(parts[0]); m = int(parts[1]) if len(parts) > 1 else 0; sec = int(parts[2]) if len(parts) > 2 else 0
            return pd.Timestamp(year=2000, month=1, day=1, hour=h, minute=m, second=sec).time()
        except Exception:
            return None

    # datum/tid
    if key in ("startdatum", "fodelsedatum"):
        d = _to_date(s)
        return d if d else s
    if key == "starttid":
        t = _to_time(s)
        return t if t else s

    # numeriskt
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
    """
    Läs key/value där antingen:
      A) Kolumn A=nyckel, kolumn B=värde (flera rader)
      B) Första raden = headers, andra raden = värden
    Returnerar dict med ev. typning.
    """
    values = ws.get_all_values()
    if not values:
        return {}

    out: Dict[str, Any] = {}

    # A) Key/Value i kolumner
    if len(values) >= 1 and len(values[0]) >= 2 and (values[1:] and values[0][1] == "" or True):
        # Heuristik: fler rader än kolumner → betrakta som nyckel/värde per rad
        kv_mode = False
        # Om första två raderna ser ut som "key | value"
        non_empty_second_col = sum(1 for r in values if len(r) >= 2 and r[1].strip())
        if non_empty_second_col >= 1:
            kv_mode = True

        if kv_mode:
            for r in values:
                if not r:
                    continue
                key = (r[0] or "").strip()
                if not key:
                    continue
                val = r[1] if len(r) > 1 else ""
                out[key] = _coerce_setting(key, val)
            return out

    # B) Header + en rad värden
    header = [h.strip() for h in values[0]]
    valrow = values[1] if len(values) > 1 else []
    for i, h in enumerate(header):
        if not h:
            continue
        v = valrow[i] if i < len(valrow) else ""
        out[h] = _coerce_setting(h, v)
    return out

def _settings_candidates(profile: str) -> List[str]:
    # Stöd flera varianter för bakåtkompatibilitet
    return [f"Settings - {profile}", f"{profile}__settings", profile]

def read_profile_settings(profile: str) -> Dict[str, Any]:
    """
    Läs inställningar för en profil. Sök i ordning:
      1) 'Settings - {profile}'
      2) '{profile}__settings'
      3) '{profile}'
    """
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
    """
    Spara inställningar som enkel 2-kolumners nyckel/värde i 'Settings - {profile}'.
    Datums skrivs som ISO (YYYY-MM-DD), tid som HH:MM:SS.
    """
    ss = _open_spreadsheet()
    title = _settings_candidates(profile)[0]  # 'Settings - {profile}'
    ws = _get_ws_by_title(ss, title)
    if ws is None:
        ws = ss.add_worksheet(title=title, rows=2, cols=2)

    def _to_writable(v: Any) -> Any:
        # date/time → str
        try:
            import datetime as _dt
            if isinstance(v, _dt.date) and not isinstance(v, _dt.datetime):
                return v.isoformat()
            if isinstance(v, _dt.time):
                return v.strftime("%H:%M:%S")
        except Exception:
            pass
        return v

    # Gör en stabil lista av (key, value)
    rows = []
    for k, v in cfg.items():
        rows.append([k, _to_writable(v)])

    # Töm och skriv
    ws.clear()
    if rows:
        ws.update(f"A1", rows)

# =============================
# Data – läsa & skriva
# =============================

def _records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # Försök tolka numeriska kolumner om möjligt
    for col in df.columns:
        # hoppa över rena textfält
        if df[col].dtype == object:
            # försök numeriskt
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass
    return df

def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läs alla rader för profil från:
      1) 'Data - {profile}' (primär) om den finns
      2) annars '{profile}__data'
    Returnerar en DataFrame (kan vara tom).
    """
    ss = _open_spreadsheet()

    ws = _find_existing_data_ws(ss, profile)
    if ws is None:
        return pd.DataFrame()

    try:
        records = ws.get_all_records(default_blank="")
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa data för '{profile}': {e}")

    return _records_to_dataframe(records)

def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """
    Lägg till en rad i profilens **befintliga** databladsark.
    - Om 'Data - {profile}' finns → append där
    - Annars om '{profile}__data' finns → append där
    - Annars skapa 'Data - {profile}' och lägg till header + rad
    """
    ss = _open_spreadsheet()
    ws = _get_or_create_data_ws(ss, profile)

    # Läs befintlig header (om någon)
    try:
        existing = ws.get_all_values()
    except APIError as e:
        raise RuntimeError(f"Kunde inte läsa befintliga värden för '{ws.title}': {e}")

    if not existing:
        # tomt blad → skriv header + rad
        headers = list(row.keys())
        values = [row.get(h, "") for h in headers]
        ws.update("A1", [headers, values])
        return

    # Det finns något – anta första raden = header
    headers = existing[0] if existing else []
    if not headers:
        # Om första raden råkat vara tom – skriv header i A1
        headers = list(row.keys())
        ws.update("A1", [headers])
    # Bygg rad i header-ordning
    values = [row.get(h, "") for h in headers]
    ws.append_row(values, value_input_option="USER_ENTERED")
