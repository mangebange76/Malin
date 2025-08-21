# sheets_utils.py
from __future__ import annotations
import json, re
from typing import Any, Dict, List, Optional
import streamlit as st

# ===================== Interna hjälpare =====================

def _load_service_account_from_secrets() -> dict:
    if "GOOGLE_CREDENTIALS" not in st.secrets:
        raise RuntimeError("Saknar secret GOOGLE_CREDENTIALS.")
    raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(raw, str):
        return json.loads(raw)
    return json.loads(json.dumps(dict(raw)))

def _open_spreadsheet():
    if "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar secret SHEET_URL.")
    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_info = _load_service_account_from_secrets()
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["SHEET_URL"])

def _normalize_header(names: List[str]) -> List[str]:
    seen, out = set(), []
    for n in names or []:
        k = (n or "").strip()
        if k and k not in seen:
            out.append(k); seen.add(k)
    return out

def _ws_titles(ss) -> List[str]:
    return [ws.title for ws in ss.worksheets()]

# ===================== Offentliga: öppna/ensure =====================

def get_client():
    """Historiskt namn – returnerar Spreadsheet-objektet (inte bara klienten)."""
    return _open_spreadsheet()

def get_spreadsheet():
    return _open_spreadsheet()

def open_spreadsheet():
    return _open_spreadsheet()

def ensure_ws(ss, title: str, rows: int = 4000, cols: int = 80):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def ensure_worksheet(ss, title: str, rows: int = 4000, cols: int = 80):
    return ensure_ws(ss, title, rows, cols)

# ===================== Profiler: lista/inställningar =====================

def read_profile_list(ss=None) -> List[str]:
    if ss is None: ss = _open_spreadsheet()
    try:
        ws = ensure_ws(ss, "Profil", rows=200, cols=4)
        vals = ws.col_values(1)
        return [v.strip() for v in vals if (v or "").strip()]
    except Exception as e:
        st.error(f"Kunde inte läsa profiler: {e}")
        return []

def _kv_rows_to_dict(rows: List[List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for r in rows:
        if not r: continue
        k = (r[0] if len(r) > 0 else "").strip()
        v = (r[1] if len(r) > 1 else "").strip()
        if not k: continue
        if re.fullmatch(r"-?\d+", v or ""):
            out[k] = int(v)
        else:
            try:
                out[k] = float(v)
            except Exception:
                # lämna som str (ev. datum i YYYY-MM-DD)
                out[k] = v
    return out

def read_profile_cfg(profile: str, ss=None) -> Dict[str, Any]:
    if ss is None: ss = _open_spreadsheet()
    try:
        ws = ensure_ws(ss, profile)
    except Exception as e:
        st.warning(f"Profilblad '{profile}' saknas: {e}")
        return {}
    values = ws.get_all_values()
    if values:
        hdr = [c.strip().lower() for c in (values[0] or [])]
        if ("key" in hdr and "value" in hdr) or ("nyckel" in hdr and "värde" in hdr):
            return _kv_rows_to_dict(values[1:])
    try:
        recs = ws.get_all_records()
        if recs:
            if {"Key","Value"}.issubset(recs[0].keys()):
                rows = [[r.get("Key",""), r.get("Value","")] for r in recs]
                return _kv_rows_to_dict(rows)
            if {"Nyckel","Värde"}.issubset(recs[0].keys()):
                rows = [[r.get("Nyckel",""), r.get("Värde","")] for r in recs]
                return _kv_rows_to_dict(rows)
            return recs[0]  # första raden som dict
    except Exception:
        pass
    return {}

def write_profile_cfg(profile: str, cfg: Dict[str, Any], ss=None) -> None:
    if ss is None: ss = _open_spreadsheet()
    ws = ensure_ws(ss, profile, rows=400, cols=4)
    ws.clear()
    ws.update("A1", [["Key","Value"]])
    rows = []
    for k, v in cfg.items():
        if hasattr(v, "strftime"):
            v = v.strftime("%Y-%m-%d")
        rows.append([str(k), str(v)])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

# alias
save_profile_cfg = write_profile_cfg
read_profile_cfg_dict = read_profile_cfg
read_profiles = read_profile_list

# ===================== Profilspecifik DATA =====================

def _candidate_data_titles(profile: str) -> List[str]:
    p = profile
    return [
        f"Data__{p}",
        f"Data_{p}",
        f"{p}__Data",
        f"{p}_Data",
        f"Data - {p}",
        f"{p} - Data",
        f"DATA__{p}",
        f"DATA_{p}",
    ]

def find_profile_data_worksheet(ss, profile: str):
    titles = _ws_titles(ss)
    for t in _candidate_data_titles(profile):
        if t in titles:
            return ss.worksheet(t)
    pl = profile.lower()
    for t in titles:
        if "data" in t.lower() and pl in t.lower():
            return ss.worksheet(t)
    return None

def ensure_profile_data_sheet(ss, profile: str, header: List[str]):
    ws = find_profile_data_worksheet(ss, profile)
    if ws is None:
        title = f"Data__{profile}"
        ws = ensure_ws(ss, title, rows=4000, cols=max(80, len(header)+5))
        header = _normalize_header(header)
        if header: ws.update("A1", [header])
    else:
        existing = ws.row_values(1)
        union = _normalize_header((existing or []) + (header or []))
        if union and union != existing:
            ws.update("A1", [union])
    return ws

def read_profile_data(profile: str, ss=None) -> List[Dict[str, Any]]:
    if ss is None: ss = _open_spreadsheet()
    ws = find_profile_data_worksheet(ss, profile)
    if ws is None:
        return []
    try:
        return ws.get_all_records() or []
    except Exception:
        return []

def read_profile_data_df(profile: str, ss=None):
    import pandas as pd
    return pd.DataFrame(read_profile_data(profile, ss=ss))

def append_profile_row(profile: str, row_dict: Dict[str, Any], ss=None) -> None:
    if ss is None: ss = _open_spreadsheet()
    row = dict(row_dict)
    row.setdefault("Profil", profile)
    ws = ensure_profile_data_sheet(ss, profile, list(row.keys()))
    current_header = ws.row_values(1)
    union = _normalize_header((current_header or []) + list(row.keys()))
    if union != current_header:
        ws.update("A1", [union])
        current_header = union
    values = [row.get(col, "") for col in current_header]
    ws.append_row(values)

# ===================== Kompatibilitets-API (gamla namn) =====================

# Apparnas gamla interna hjälpare
def _get_gspread_client():
    """Historiskt: brukar returnera Spreadsheet-objekt i våra appar."""
    return _open_spreadsheet()

def _ensure_ws(ss, title, rows=4000, cols=80):
    return ensure_ws(ss, title, rows, cols)

# “Spara till Sheets” – gammal variant som skrev till en global flik
def save_to_sheets(row_dict: Dict[str, Any], sheet_title: str = "Data", profile: Optional[str] = None) -> None:
    """
    Bakåtkompatibel: om profile anges → skriv i profilens data-blad,
    annars skriv i (globala) 'Data'.
    """
    ss = _open_spreadsheet()
    if profile:
        append_profile_row(profile, row_dict, ss=ss)
        return
    ws = ensure_ws(ss, sheet_title)
    header = ws.row_values(1)
    if not header:
        header = list(row_dict.keys())
        ws.update("A1", [header])
    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values)

# Fler alias så import-rader inte spricker
open_ss = get_spreadsheet
get_ss = get_spreadsheet
ensure_sheet = ensure_ws
ensure_data_sheet = ensure_profile_data_sheet
append_row_to_profile_data = append_profile_row
