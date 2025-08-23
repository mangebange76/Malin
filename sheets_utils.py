# sheets_utils.py
# Basversion 250823 – robusta secrets, stabil klient, strikt append till befintlig flik,
# profiler i fliken "Profil" (kol A), profil-inställningar som JSON i kol B.

from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import time
import json
import re
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# ---- Google scopes ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# =========================
# Helpers: secrets & creds
# =========================
def _load_google_credentials_dict() -> Dict[str, Any]:
    if "GOOGLE_CREDENTIALS" not in st.secrets:
        raise RuntimeError("GOOGLE_CREDENTIALS saknas i st.secrets.")
    raw = st.secrets["GOOGLE_CREDENTIALS"]

    # Dict direkt
    if isinstance(raw, dict):
        return raw

    # JSON-sträng (ev. via env)
    if isinstance(raw, str):
        s = raw.strip()

        # Om det är ett env-var-namn: försök läsa det också
        if not s.startswith("{") and s.upper() in os.environ:
            s_env = os.environ.get(s.upper(), "").strip()
            if s_env:
                try:
                    return json.loads(s_env)
                except Exception as e:
                    raise RuntimeError(f"Env-var '{s}' innehåller ogiltig JSON: {e}")

        # Försök tolka som JSON direkt
        try:
            return json.loads(s)
        except Exception as e:
            raise RuntimeError(f"GOOGLE_CREDENTIALS-strängen är inte giltig JSON: {e}")

    raise RuntimeError(f"GOOGLE_CREDENTIALS hade oväntad typ: {type(raw)}")


def _get_gspread_client() -> gspread.Client:
    # Cacha klienten i sessionen så den inte tappas i onödan
    cache_key = "_GSPREAD_CLIENT"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    creds_dict = _load_google_credentials_dict()
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    st.session_state[cache_key] = client
    return client


def _open_spreadsheet(retries: int = 4, base_delay: float = 0.6) -> gspread.Spreadsheet:
    if "SHEET_URL" not in st.secrets:
        raise RuntimeError("SHEET_URL saknas i st.secrets.")
    url = st.secrets["SHEET_URL"]

    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            client = _get_gspread_client()
            return client.open_by_url(url)
        except Exception as e:
            last_err = e
            time.sleep(base_delay * (2 ** i))
    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")


# =========================
# Helpers: worksheet-lookup
# =========================
def _find_ws_by_title_relaxed(ss: gspread.Spreadsheet, wanted_title: str) -> Optional[gspread.Worksheet]:
    """
    Case/whitespace-okänslig match av fliknamn. Skapar aldrig nytt blad.
    """
    if not wanted_title:
        return None
    wanted = wanted_title.strip().lower()
    for ws in ss.worksheets():
        if ws.title.strip().lower() == wanted:
            return ws
    return None


# =========================
# Profiler (fliken "Profil")
# =========================
def _get_profiles_ws(ss: gspread.Spreadsheet) -> gspread.Worksheet:
    """
    Hämta/Skapa fliken 'Profil'. Vi skapar den om den saknas
    (endast denna flik får auto-skapas).
    """
    ws = _find_ws_by_title_relaxed(ss, "Profil")
    if ws is None:
        # Skapa en tom med rimliga headers
        ws = ss.add_worksheet(title="Profil", rows=100, cols=2)
        ws.update("A1:B1", [["Profil", "SettingsJSON"]])
    return ws


def list_profiles() -> List[str]:
    """
    Läser profilnamn från fliken 'Profil', kolumn A (första kolumnen), hoppar över header.
    Tomma rader filtreras bort.
    """
    ss = _open_spreadsheet()
    ws = _get_profiles_ws(ss)
    vals = ws.col_values(1)  # kol A
    if not vals:
        return []
    # hoppa över headern
    profs = [v.strip() for v in vals[1:] if v and v.strip()]
    return profs


# =========================
# Profil-inställningar i "Profil" (JSON i kol B)
# =========================
_DATE_KEYS = {"startdatum", "fodelsedatum"}
_TIME_KEYS = {"starttid"}

def _normalize_settings_types(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gör om ISO-strängar till date/time-objekt för de kända nycklarna.
    Övriga lämnas som de är.
    """
    from datetime import date, time, datetime

    out = dict(d)

    def _parse_date(v: Any):
        if v is None or v == "":
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v).date()
            except Exception:
                # tillåt även "YYYY-MM-DD" enklare
                try:
                    return datetime.strptime(v, "%Y-%m-%d").date()
                except Exception:
                    return v
        return v

    def _parse_time(v: Any):
        if v is None or v == "":
            return None
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            # tillåt "HH:MM" eller "HH:MM:SS"
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(v, fmt).time()
                except Exception:
                    pass
            return v
        return v

    for k in list(out.keys()):
        lk = str(k).lower()
        if lk in _DATE_KEYS:
            out[k] = _parse_date(out[k])
        elif lk in _TIME_KEYS:
            out[k] = _parse_time(out[k])

    return out


def read_profile_settings(profile_title: str) -> Dict[str, Any]:
    """
    Hämtar JSON-inställningar för profil ur fliken 'Profil':
    - Kol A: Profilnamn
    - Kol B: SettingsJSON (valfritt)
    """
    ss = _open_spreadsheet()
    ws = _get_profiles_ws(ss)
    vals = ws.get_all_values()
    if not vals:
        return {}

    headers = [h.strip().lower() for h in vals[0]] if vals else []
    # hitta settings-kolumn (default kol 2)
    settings_col_idx = 1  # 0-baserat: B-kolumn
    for i, h in enumerate(headers):
        if h in ("settingsjson", "inställningar", "installningar", "settings", "config", "cfg"):
            settings_col_idx = i
            break

    wanted = (profile_title or "").strip().lower()
    for row in vals[1:]:
        if not row:
            continue
        name = (row[0] if len(row) > 0 else "").strip().lower()
        if name == wanted:
            js = (row[settings_col_idx] if len(row) > settings_col_idx else "").strip()
            if not js:
                return {}
            try:
                data = json.loads(js)
            except Exception:
                return {}
            return _normalize_settings_types(data)

    return {}


def save_profile_settings(profile_title: str, cfg: Dict[str, Any]) -> None:
    """
    Sparar profilens inställningar som JSON i fliken 'Profil', kol B.
    Skapar raden om den saknas.
    """
    ss = _open_spreadsheet()
    ws = _get_profiles_ws(ss)

    # Gör cfg JSON-säker (date/time -> iso-strängar)
    from datetime import date, time
    json_ready = {}
    for k, v in (cfg or {}).items():
        if isinstance(v, (date,)):
            json_ready[k] = v.isoformat()
        elif isinstance(v, time):
            json_ready[k] = v.strftime("%H:%M:%S")
        else:
            json_ready[k] = v

    payload = json.dumps(json_ready, ensure_ascii=False)

    vals = ws.get_all_values()
    if not vals:
        ws.update("A1:B1", [["Profil", "SettingsJSON"]])
        vals = ws.get_all_values()

    # Finns profilraden?
    profs = [r[0].strip() if r else "" for r in vals[1:]]
    try:
        idx = [p.lower() for p in profs].index((profile_title or "").strip().lower())
        row_no = idx + 2  # pga header
        ws.update_cell(row_no, 2, payload)
    except ValueError:
        # Lägg till ny rad
        ws.append_row([profile_title, payload], value_input_option="USER_ENTERED")
