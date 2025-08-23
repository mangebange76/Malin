# sheets_utils.py
from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, List, Optional
from collections.abc import Mapping

import pandas as pd
import streamlit as st

import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials


# =========================
# Konstanter
# =========================
DEFAULT_PROFILES_SHEET_NAMES = ["Profil", "Profiles", "Profiler"]
SETTINGS_CANDIDATES = [
    "{profile}__settings",
    "{profile}_settings",
    "{profile} settings",
    "Inställningar - {profile}",
    # Sista fallback: själva profilsheeten (om det är key/value-format)
    "{profile}",
]
DATA_CANDIDATES = [
    "{profile}__data",
    "{profile}_data",
    "{profile} data",
    "Data - {profile}",
    # Sista fallback: själva profilsheeten (om det är tabell med många kolumner)
    "{profile}",
]

# =========================
# Hjälpare – credentials
# =========================
def _load_google_credentials_dict() -> dict:
    """
    Laddar service account-credar från st.secrets eller env.
    Stödjer:
      - st.secrets["GOOGLE_CREDENTIALS"] som dict/Mapping, SecretValue eller JSON-sträng
      - st.secrets["gcp_service_account"] (Streamlit-exemplet)
      - os.environ["GOOGLE_CREDENTIALS"] (JSON-sträng)
    Fixar även '\\n' -> '\n' i private_key.
    """
    raw = None

    if "GOOGLE_CREDENTIALS" in st.secrets:
        raw = st.secrets["GOOGLE_CREDENTIALS"]
    elif "gcp_service_account" in st.secrets:
        raw = st.secrets["gcp_service_account"]
    elif os.environ.get("GOOGLE_CREDENTIALS"):
        raw = os.environ["GOOGLE_CREDENTIALS"]

    if raw is None:
        raise RuntimeError("GOOGLE_CREDENTIALS saknas i secrets/ENV.")

    # 1) Mapping (dict/SecretDict osv)
    if isinstance(raw, Mapping):
        creds_dict = dict(raw)

    # 2) Sträng/bytes (JSON)
    elif isinstance(raw, (str, bytes)):
        s = raw if isinstance(raw, str) else raw.decode("utf-8", "ignore")
        s = s.strip()
        try:
            creds_dict = json.loads(s)
        except Exception as e:
            raise RuntimeError("GOOGLE_CREDENTIALS är en sträng men inte giltig JSON.") from e

    # 3) Övriga specialtyper – försök tolka via str() som JSON, annars dict()
    else:
        try:
            s = str(raw).strip()
            creds_dict = json.loads(s)
        except Exception:
            try:
                creds_dict = dict(raw)  # kan kasta TypeError
            except Exception as e:
                raise RuntimeError(
                    f"GOOGLE_CREDENTIALS okänt format (typ {type(raw).__name__}). "
                    "Spara som JSON-sträng, dict eller 'gcp_service_account'."
                ) from e

    # Normalisera private_key
    pk = creds_dict.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        creds_dict["private_key"] = pk.replace("\\n", "\n")

    for k in ("type", "client_email", "private_key"):
        if not creds_dict.get(k):
            raise RuntimeError(f"GOOGLE_CREDENTIALS saknar fältet '{k}'.")

    return creds_dict


def _get_gspread_client() -> gspread.Client:
    creds_dict = _load_google_credentials_dict()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)


def _open_spreadsheet(max_attempts: int = 4, base_delay: float = 0.8) -> gspread.Spreadsheet:
    """Öppnar kalkylarket med retry/backoff och tydliga fel."""
    if "SHEET_URL" not in st.secrets or not st.secrets["SHEET_URL"]:
        raise RuntimeError("SHEET_URL saknas i st.secrets.")
    url = st.secrets["SHEET_URL"]

    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            client = _get_gspread_client()
            return client.open_by_url(url)
        except APIError as e:
            last_err = e
            # Retry på 5xx och rate-limit
            status = getattr(e.response, "status_code", None)
            text = getattr(e.response, "text", "")
            transient = (status and 500 <= status < 600) or ("rateLimitExceeded" in text)
            if attempt == max_attempts or not transient:
                break
            time.sleep(base_delay * (2 ** (attempt - 1)))
        except Exception as e:
            last_err = e
            if attempt == max_attempts:
                break
            time.sleep(base_delay * (2 ** (attempt - 1)))

    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")


def _try_get_ws(ss: gspread.Spreadsheet, names: List[str]) -> Optional[gspread.Worksheet]:
    for name in names:
        try:
            return ss.worksheet(name)
        except WorksheetNotFound:
            continue
    return None


# =========================
# Profiler
# =========================
def list_profiles() -> List[str]:
    """Returnerar listan av profiler från bladet 'Profil' (eller fallback-namn)."""
    ss = _open_spreadsheet()
    ws = _try_get_ws(ss, DEFAULT_PROFILES_SHEET_NAMES)
    if ws is None:
        # Inga profiler hittade – returnera tom lista
        return []

    # Läs kolumn A (alla rader)
    vals = ws.col_values(1)
    # Filtrera bort header-rader och tomma
    profs = []
    for v in vals:
        v = (v or "").strip()
        if not v:
            continue
        if v.lower() in ("profil", "profiles", "profiler"):
            continue
        if v not in profs:
            profs.append(v)
    return profs


# =========================
# Inställningar – läs/spara
# =========================
def _read_key_value_worksheet(ws: gspread.Worksheet) -> Dict[str, Any]:
    """Läser ett key/value-blad. Första kolumn = key, andra = value."""
    rows = ws.get_all_values()
    if not rows:
        return {}

    # Hoppa över eventuell header om den liknar "key,value"
    start_idx = 0
    if rows and len(rows[0]) >= 2:
        h0 = (rows[0][0] or "").strip().lower()
        h1 = (rows[0][1] or "").strip().lower()
        if h0 in ("key", "nyckel") and h1 in ("value", "värde", "varde"):
            start_idx = 1

    data: Dict[str, Any] = {}
    for r in rows[start_idx:]:
        if not r:
            continue
        k = (r[0] or "").strip()
        if not k:
            continue
        v = (r[1] if len(r) > 1 else "").strip()
        data[k] = _parse_value_auto(v)
    return data


def _parse_value_auto(s: str) -> Any:
    """Försöker konvertera text från ark -> bool/int/float/date/time, annars lämna str."""
    if s is None:
        return ""
    s2 = str(s).strip()
    if s2 == "":
        return ""

    # True/False
    low = s2.lower()
    if low in ("true", "false", "ja", "nej"):
        return low in ("true", "ja")

    # Int
    try:
        if s2.isdigit() or (s2.startswith("-") and s2[1:].isdigit()):
            return int(s2)
    except Exception:
        pass

    # Float
    try:
        # Byt ev. komma mot punkt
        s3 = s2.replace(",", ".")
        f = float(s3)
        return f
    except Exception:
        pass

    # Date (YYYY-MM-DD)
    from datetime import date, time as _time
    try:
        if len(s2) == 10 and s2[4] == "-" and s2[7] == "-":
            y, m, d = s2.split("-")
            return date(int(y), int(m), int(d))
    except Exception:
        pass

    # Time (HH:MM[:SS])
    try:
        parts = s2.split(":")
        if len(parts) >= 2:
            hh = int(parts[0]); mm = int(parts[1]); ss = int(parts[2]) if len(parts) >= 3 else 0
            return _time(hh, mm, ss)
    except Exception:
        pass

    # JSON?
    try:
        return json.loads(s2)
    except Exception:
        pass

    return s  # original sträng


def _serialize_value(v: Any) -> str:
    """Serialiserar Python-värde -> str för sheets."""
    from datetime import date, time as _time, datetime as _dt
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, date) and not isinstance(v, _dt):
        return v.isoformat()
    if isinstance(v, _time):
        return v.strftime("%H:%M")
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return ""
    return str(v)


def read_profile_settings(profile: str) -> Dict[str, Any]:
    """Läser inställningar (key-value) för given profil. Testar flera möjliga blad."""
    ss = _open_spreadsheet()
    candidates = [name.format(profile=profile) for name in SETTINGS_CANDIDATES]

    # Hitta första blad som ser ut som key/value
    for name in candidates:
        try:
            ws = ss.worksheet(name)
            # Kontrollera om detta verkligen är key/value (<=2 kolumner eller header "key/value")
            rows = ws.get_all_values()
            if not rows:
                continue
            col_count = max((len(r) for r in rows), default=0)
            if col_count <= 2:
                return _read_key_value_worksheet(ws)
            # Om första raden ser ut som "key/value" trots fler kolumner, prova ändå:
            h0 = (rows[0][0] or "").strip().lower() if rows and rows[0] else ""
            h1 = (rows[0][1] or "").strip().lower() if rows and len(rows[0]) > 1 else ""
            if h0 in ("key", "nyckel") and h1 in ("value", "värde", "varde"):
                return _read_key_value_worksheet(ws)
            # annars är detta troligen ett databladsformat – fortsätt leta
        except WorksheetNotFound:
            continue

    # Inga inställningar funna
    return {}


def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """Sparar inställningar (key/value) till ett dedikerat {profile}__settings-blad."""
    ss = _open_spreadsheet()
    ws_name = f"{profile}__settings"
    try:
        ws = ss.worksheet(ws_name)
        ws.clear()
    except WorksheetNotFound:
        ws = ss.add_worksheet(title=ws_name, rows=200, cols=2)

    rows = [["key", "value"]]
    for k, v in cfg.items():
        rows.append([k, _serialize_value(v)])

    ws.update("A1", rows, value_input_option="RAW")


# =========================
# Data – läs/append
# =========================
def _worksheet_looks_like_settings(ws: gspread.Worksheet) -> bool:
    """Heuristik: 2 kolumner (eller key/value-header) => inställningsblad."""
    vals = ws.get_all_values()
    if not vals:
        return True
    col_count = max((len(r) for r in vals), default=0)
    if col_count <= 2:
        return True
    if vals:
        h0 = (vals[0][0] or "").strip().lower()
        h1 = (vals[0][1] or "").strip().lower() if len(vals[0]) > 1 else ""
        if h0 in ("key", "nyckel") and h1 in ("value", "värde", "varde"):
            return True
    return False


def _worksheet_looks_like_table(ws: gspread.Worksheet) -> bool:
    """Heuristik: tabell med >= 3 kolumner i första raden."""
    vals = ws.get_all_values()
    if not vals:
        return False
    return len(vals[0]) >= 3


def _values_to_dataframe(vals: List[List[Any]]) -> pd.DataFrame:
    if not vals:
        return pd.DataFrame()
    header = [str(h) if h is not None else "" for h in vals[0]]
    rows = vals[1:] if len(vals) > 1 else []
    df = pd.DataFrame(rows, columns=header)
    # Försök konvertera numeriska kolumner
    for c in df.columns:
        # behåll str om blandat
        try:
            # Om helt tom: hoppa
            if df[c].dropna().eq("").all():
                continue
            # prova numeriskt
            df[c] = pd.to_numeric(df[c], errors="ignore")
        except Exception:
            pass
    return df


def read_profile_data(profile: str) -> pd.DataFrame:
    """Läser data-tabellen för en profil. Testar flera bladnamn."""
    ss = _open_spreadsheet()
    for name in [n.format(profile=profile) for n in DATA_CANDIDATES]:
        try:
            ws = ss.worksheet(name)
        except WorksheetNotFound:
            continue

        # Om detta ser ut som settings-blad – hoppa
        if _worksheet_looks_like_settings(ws):
            continue
        # Om det ser ut som tabell – returnera som DF
        if _worksheet_looks_like_table(ws):
            vals = ws.get_all_values()
            return _values_to_dataframe(vals)

    # Inget databladsformat hittat – returnera tom DF
    return pd.DataFrame()


def _ensure_header(ws: gspread.Worksheet, header: List[str]) -> List[str]:
    """Säkerställ att headern i bladet innehåller minst 'header'. Lägg till nya kolumner vid behov."""
    vals = ws.get_all_values()
    if not vals:
        ws.update("A1", [header], value_input_option="RAW")
        return header

    existing = vals[0]
    need_add = [h for h in header if h not in existing]
    if not need_add:
        return existing

    new_header = existing + need_add
    ws.update("A1", [new_header], value_input_option="RAW")
    return new_header


def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """Append: skapar {profile}__data vid behov, synkar header och appendar värden."""
    ss = _open_spreadsheet()
    # Försök öppna primär dataflik
    ws = _try_get_ws(ss, [f"{profile}__data"])
    if ws is None:
        # Skapa nytt data-blad
        ws = ss.add_worksheet(title=f"{profile}__data", rows=2, cols=max(2, len(row)))
        # initial header
        ws.update("A1", [[*row.keys()]], value_input_option="RAW")

    # Säkerställ header (lägg till nya fält vid behov)
    header = _ensure_header(ws, list(row.keys()))

    # Bygg rad i rätt ordning
    def ser(v: Any) -> str:
        # serialisera delar – reuse settings-serializer men bevara tal när det går
        s = _serialize_value(v)
        return s

    values = [ser(row.get(col, "")) for col in header]
    ws.append_row(values, value_input_option="USER_ENTERED")
