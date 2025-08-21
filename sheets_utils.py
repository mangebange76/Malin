# sheets_utils.py
import re
import json
import datetime as dt
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

# ---------------------------
# Spreadsheet access
# ---------------------------
def _open_spreadsheet():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS och/eller SHEET_URL i st.secrets.")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["SHEET_URL"])

def _ensure_ws(ss, title: str, rows: int = 4000, cols: int = 120):
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

# ---------------------------
# Helpers: text & typing
# ---------------------------
def _norm(s: str) -> str:
    return re.sub(r"[_\s]+", " ", str(s or "")).strip().lower()

def _candidate_titles_for_data(profile: str) -> List[str]:
    p = str(profile).strip()
    return [f"Data_{p}", f"Data {p}", f"{p} Data", f"{p}_Data"]

def _parse_date(val: str) -> Optional[dt.date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(val.strip(), fmt).date()
        except Exception:
            pass
    return None

def _auto_cast(key: str, val):
    if val is None:
        return None
    s = str(val).strip()

    # Bool
    if _norm(s) in ("true", "ja", "yes", "1"):
        return True
    if _norm(s) in ("false", "nej", "no", "0"):
        return False

    # Datum (kända fält)
    if key in ("startdatum", "fodelsedatum"):
        d = _parse_date(s)
        if d:
            return d

    # Heltal / flyttal (tillåt komma som decimal)
    try:
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s)
        s2 = s.replace(",", ".")
        if re.fullmatch(r"[+-]?\d+\.\d+", s2):
            return float(s2)
    except Exception:
        pass
    return s

def _trim_header_and_rows(header: List[str], rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
    # ta bort helt tomma rader i början
    while rows and all((str(c).strip() == "" for c in rows[0])):
        rows.pop(0)

    # om header är tom eller ser tom ut: använd första icke-tomma raden som header
    if not header or all(str(h).strip() == "" for h in header):
        if rows:
            header = rows[0]
            rows = rows[1:]

    # ta bort tomma kolumner i slutet
    last_nonempty = 0
    for i, name in enumerate(header, start=1):
        if str(name).strip():
            last_nonempty = i
    header = header[: last_nonempty] if last_nonempty > 0 else header
    trimmed_rows = [r[: len(header)] for r in rows]

    return header, trimmed_rows

def _to_dataframe(header: List[str], rows: List[List[str]]) -> pd.DataFrame:
    header, rows = _trim_header_and_rows(header, rows)
    df = pd.DataFrame(rows, columns=header if header else None)
    if not df.empty:
        df = df.dropna(how="all")
    return df

# ---------------------------
# Publika API
# ---------------------------
def list_profiles() -> List[str]:
    ss = _open_spreadsheet()
    try:
        ws = ss.worksheet("Profil")
    except gspread.WorksheetNotFound:
        return []

    vals = ws.col_values(1)  # kolumn A
    out = []
    for v in vals:
        name = str(v).strip()
        if not name:
            continue
        if _norm(name) in ("namn", "profil", "profiler"):
            continue
        out.append(name)

    # unika i stabil ordning
    seen, uniq = set(), []
    for p in out:
        k = p.lower()
        if k not in seen:
            uniq.append(p); seen.add(k)
    return uniq

def read_profile_settings(profile: str) -> Dict:
    if not profile:
        return {}
    ss = _open_spreadsheet()
    target = None
    for ws in ss.worksheets():
        if _norm(ws.title) == _norm(profile):
            target = ws
            break
    if target is None:
        return {}

    vals = target.get_all_values()
    if not vals:
        return {}

    # upptäck header (Key/Value) om den finns
    start_row = 0
    if len(vals[0]) >= 2:
        h0 = _norm(vals[0][0]); h1 = _norm(vals[0][1])
        if h0 in ("key", "nyckel") and h1 in ("value", "värde", "varde"):
            start_row = 1

    cfg = {}
    for row in vals[start_row:]:
        if len(row) < 2:
            continue
        k = str(row[0]).strip()
        v = row[1]
        if not k:
            continue
        cfg[k] = _auto_cast(k, v)

    # säkerställ cm om angivet
    if "HEIGHT_CM" in cfg:
        try:
            cfg["HEIGHT_CM"] = int(str(cfg["HEIGHT_CM"]).replace(",", "."))
        except Exception:
            pass
    return cfg

def _find_profile_data_ws(ss, profile: str) -> Optional[gspread.Worksheet]:
    # 1) exakta kandidater
    cand = { _norm(t): t for t in _candidate_titles_for_data(profile) }
    for ws in ss.worksheets():
        if _norm(ws.title) in cand:
            return ws

    # 2) heuristik: titel börjar med "data" och innehåller profilen
    nprof = _norm(profile)
    for ws in ss.worksheets():
        t = _norm(ws.title)
        if t.startswith("data") and nprof in t:
            return ws
    return None

def read_profile_data(profile: str) -> pd.DataFrame:
    if not profile:
        return pd.DataFrame()

    ss = _open_spreadsheet()

    # Försök dedikerat datablad
    ws = _find_profile_data_ws(ss, profile)
    if ws is not None:
        vals = ws.get_all_values()
        if not vals:
            return pd.DataFrame()
        header = vals[0] if vals else []
        rows   = vals[1:] if len(vals) > 1 else []
        df = _to_dataframe(header, rows)
        return df

    # Fallback: globalt Data + filtrera Profil
    try:
        ws_data = ss.worksheet("Data")
    except gspread.WorksheetNotFound:
        return pd.DataFrame()

    vals = ws_data.get_all_values()
    if not vals:
        return pd.DataFrame()
    header = vals[0]; rows = vals[1:]
    df = _to_dataframe(header, rows)
    if df.empty:
        return df

    # hitta "Profil"-kolumn (case-insensitivt)
    prof_col = None
    for c in df.columns:
        if _norm(c) == "profil":
            prof_col = c; break
    if prof_col is None:
        return pd.DataFrame()  # kan inte filtrera

    mask = df[prof_col].astype(str).str.strip().str.lower() == profile.strip().lower()
    return df.loc[mask].copy()

def save_profile_settings(profile: str, cfg: Dict):
    if not profile:
        raise ValueError("Profilnamn saknas.")
    ss = _open_spreadsheet()
    ws = _ensure_ws(ss, profile)

    out_rows = []
    for k, v in cfg.items():
        if isinstance(v, (dt.date, dt.datetime)):
            v = v.strftime("%Y-%m-%d")
        out_rows.append([str(k), str(v)])

    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if out_rows:
        ws.update(f"A2:B{len(out_rows)+1}", out_rows)

def append_row_to_profile_data(profile: str, row: Dict):
    if not profile:
        raise ValueError("Profilnamn saknas.")

    ss = _open_spreadsheet()
    ws = _find_profile_data_ws(ss, profile)
    if ws is None:
        ws = _ensure_ws(ss, f"Data_{profile}")

    # säkra header
    header = ws.row_values(1)
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])

    values = [row.get(col, "") for col in header]
    ws.append_row(values)
