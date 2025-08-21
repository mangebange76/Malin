# sheets_utils.py
# Hjälpfunktioner för Google Sheets med profilstöd
#
# Förutsätter st.secrets:
#   - GOOGLE_CREDENTIALS  (service account JSON eller dict)
#   - SHEET_URL           (URL till Google Sheet-dokumentet)

from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, datetime

import streamlit as st

# --- Lazy imports (för att slippa tunga beroenden vid import) ---
def _gspread_bundle():
    from google.oauth2.service_account import Credentials
    import gspread
    return Credentials, gspread


# ---------- Verktyg för värde-parse ----------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _parse_value(v: str) -> Any:
    if v is None:
        return ""
    s = str(v).strip()

    # tom str -> tomt
    if s == "":
        return ""

    # bool
    sl = s.lower()
    if sl in ("true", "false"):
        return sl == "true"

    # datum
    if _DATE_RE.match(s):
        try:
            y, m, d = [int(x) for x in s.split("-")]
            return date(y, m, d)
        except Exception:
            pass

    # int/float
    try:
        if re.match(r"^[+-]?\d+$", s):
            return int(s)
        if re.match(r"^[+-]?\d+\.\d+$", s):
            return float(s)
    except Exception:
        pass

    # fallback
    return s


def _to_str_for_sheet(v: Any) -> str:
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)


# ---------- Koppling / klient ----------

def get_client() -> Tuple[Any, Any]:
    """Returnerar (gspread_client, spreadsheet)."""
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar secrets GOOGLE_CREDENTIALS och/eller SHEET_URL.")

    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    Credentials, gspread = _gspread_bundle()
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return client, ss


def ensure_ws(ss, title: str, rows: int = 4000, cols: int = 80):
    """Hämta eller skapa ett worksheet med angivet namn."""
    _, gspread = _gspread_bundle()
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)


# ---------- Profil-hantering ----------

PROFILES_SHEET = "Profil"               # kolumn A = profilnamn
PROFILE_SETTINGS_PREFIX = "Inställningar - "   # inställningar per profil
PROFILE_DATA_PREFIX = "Data - "                # data per profil

def list_profiles() -> List[str]:
    """Returnerar en lista med profiler från bladet 'Profil' (kolumn A)."""
    _, ss = get_client()
    ws = ensure_ws(ss, PROFILES_SHEET, rows=200, cols=3)
    values = ws.col_values(1) or []
    # rensa tomma + rubriker
    out = []
    for v in values:
        name = (v or "").strip()
        if name and name.lower() != "profil":
            out.append(name)
    return out


# ---------- Läs & skriv inställningar för en profil ----------

def read_profile_settings(profile: str) -> Dict[str, Any]:
    """
    Läser inställningar från 'Inställningar - <profil>'.
    Om det bladet saknas försöker den med ett blad som heter exakt profilnamnet.
    Format: 2 kolumner: Key | Value (valfritt huvud).
    """
    _, ss = get_client()

    # Primärt: Inställningar - <profil>
    title_primary = f"{PROFILE_SETTINGS_PREFIX}{profile}"
    # Fallback (kompatibilitet): blad med exakt profilnamn
    title_fallback = profile

    for title in (title_primary, title_fallback):
        try:
            ws = ss.worksheet(title)
            values = ws.get_all_values()
            if not values:
                return {}
            # hoppa eventuellt header
            start_row = 0
            if len(values[0]) >= 2 and values[0][0].strip().lower() in ("key", "nyckel"):
                start_row = 1

            out = {}
            for r in values[start_row:]:
                if not r or len(r) < 2:
                    continue
                k = (r[0] or "").strip()
                if not k:
                    continue
                out[k] = _parse_value(r[1])
            return out
        except Exception:
            continue

    return {}


def write_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """
    Skriver *hela* cfg som två kolumner (Key, Value) till 'Inställningar - <profil>'.
    """
    _, ss = get_client()
    ws = ensure_ws(ss, f"{PROFILE_SETTINGS_PREFIX}{profile}", rows=400, cols=4)
    rows = [["Key", "Value"]]
    for k, v in cfg.items():
        rows.append([k, _to_str_for_sheet(v)])
    ws.clear()
    ws.update("A1", rows)


# ---------- Läs & spara profildata (scener) ----------

def _header(ws) -> List[str]:
    row1 = ws.row_values(1) or []
    return [h.strip() for h in row1]


def _set_header(ws, header: List[str]) -> None:
    if not header:
        return
    ws.update("A1", [header])


def _extend_header(ws, header: List[str], extra_keys: List[str]) -> List[str]:
    """Lägg till nya kolumnnamn i headern om row_dict innehåller okända nycklar."""
    new_cols = [k for k in extra_keys if k not in header]
    if not new_cols:
        return header
    header = header + new_cols
    _set_header(ws, header)
    return header


def read_profile_data(profile: str) -> List[Dict[str, Any]]:
    """
    Läser alla rader för profilen från bladet 'Data - <profil>'.
    Returnerar list[dict] (tom lista om inget finns).
    """
    _, ss = get_client()
    title = f"{PROFILE_DATA_PREFIX}{profile}"
    ws = ensure_ws(ss, title, rows=6000, cols=120)

    vals = ws.get_all_values()
    if not vals or len(vals) < 2:
        return []

    header = [h.strip() for h in vals[0]]
    out = []
    for row in vals[1:]:
        if not any(c.strip() for c in row):
            continue
        rec = {}
        for i, col in enumerate(header):
            val = row[i] if i < len(row) else ""
            rec[col] = _parse_value(val)
        out.append(rec)
    return out


def save_row_for_profile(profile: str, row_dict: Dict[str, Any]) -> None:
    """
    Append: spara en scenrad i bladet 'Data - <profil>'.
    Om nya nycklar tillkommer expanderas rubriken.
    """
    _, ss = get_client()
    title = f"{PROFILE_DATA_PREFIX}{profile}"
    ws = ensure_ws(ss, title, rows=6000, cols=120)

    header = _header(ws)
    if not header:
        header = list(row_dict.keys())
        _set_header(ws, header)

    # Expandera header för nya fält
    header = _extend_header(ws, header, list(row_dict.keys()))

    # Mappa radvärden i header-ordning
    values = [_to_str_for_sheet(row_dict.get(col, "")) for col in header]
    ws.append_row(values)
