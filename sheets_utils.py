# sheets_utils.py
from __future__ import annotations
import json
from datetime import date, datetime
from typing import Dict, List, Tuple, Any

import pandas as pd

# --- Google auth / gspread helpers ---

def _get_spreadsheet():
    """Returnerar ett öppnat Spreadsheet-objekt via st.secrets (anropas från app.py)."""
    import streamlit as st
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS eller SHEET_URL i secrets.")
    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        creds_info = json.loads(json.dumps(dict(creds_raw)))
    from google.oauth2.service_account import Credentials
    import gspread
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def _get_ws(ss, title: str, create: bool = False):
    import gspread
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        if create:
            return ss.add_worksheet(title=title, rows=4000, cols=80)
        raise

# --- Casting / parsing ---

def _cast_scalar(v: str) -> Any:
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    # date YYYY-MM-DD?
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            y, m, d = [int(x) for x in s.split("-")]
            return date(y, m, d)
    except Exception:
        pass
    # int
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass
    # float
    try:
        return float(s)
    except Exception:
        return s

# --- Profil-lista ---

def list_profiles() -> List[str]:
    """Hämtar listan med profiler från fliken 'Profil' (kolumn A, skippar header)."""
    ss = _get_spreadsheet()
    try:
        ws = _get_ws(ss, "Profil", create=False)
    except Exception:
        return []
    vals = ws.col_values(1) or []
    # hoppa header (första raden), trimma och ta bort tomma
    out = []
    for i, v in enumerate(vals, start=1):
        if i == 1:
            continue
        v = (v or "").strip()
        if v:
            out.append(v)
    return out

# --- Inställningar för profil ---

def read_profile_settings(profile: str) -> Dict[str, Any]:
    """
    Läser profilens inställningar från ett blad som heter exakt 'profile'.
    Antas vara 2 kolumner: (Key|Nyckel), (Value|Värde).
    """
    ss = _get_spreadsheet()
    try:
        ws = _get_ws(ss, profile, create=False)
    except Exception:
        return {}
    rows = ws.get_all_values()
    if not rows:
        return {}
    # hitta kolumnindex för key/value om det finns header, annars använd första två
    header = [c.strip() for c in rows[0]] if rows else []
    k_idx = 0
    v_idx = 1
    # Om header säger något, försök hitta
    for idx, h in enumerate(header):
        hlow = h.lower()
        if hlow in ("key", "nyckel"):
            k_idx = idx
        if hlow in ("value", "värde", "varde"):
            v_idx = idx
    out = {}
    # iterera från rad 2
    for r in rows[1:]:
        if not r or len(r) <= k_idx:
            continue
        key = (r[k_idx] or "").strip()
        if not key:
            continue
        val = r[v_idx] if len(r) > v_idx else ""
        out[key] = _cast_scalar(val)
    return out

# --- Data för profil ---

def _find_profile_data_sheet_title(ss, profile: str) -> str | None:
    """
    Leta efter dedikerat data-blad för profilen.
    Prioritet: Data_<Profil>, <Profil>_Data, <Profil> Data (case-sensitive).
    Om ej hittas -> None.
    """
    candidates = [f"Data_{profile}", f"{profile}_Data", f"{profile} Data"]
    titles = [w.title for w in ss.worksheets()]
    for c in candidates:
        if c in titles:
            return c
    return None

def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läser profilens data:
      1) Försök dedikerat data-blad (Data_<Profil> / <Profil>_Data / <Profil> Data).
      2) Annars läs globalt 'Data' och filtrera på kolumnen 'Profil' == profile.
    Returnerar alltid en DataFrame (kan vara tom).
    """
    ss = _get_spreadsheet()
    # 1: dedikerat blad
    title = _find_profile_data_sheet_title(ss, profile)
    if title:
        ws = _get_ws(ss, title, create=False)
        recs = ws.get_all_records()  # list[dict]
        return pd.DataFrame(recs)

    # 2: global Data
    try:
        ws = _get_ws(ss, "Data", create=False)
    except Exception:
        return pd.DataFrame()  # inget att läsa
    recs = ws.get_all_records()
    df = pd.DataFrame(recs)
    if "Profil" in df.columns:
        df = df[df["Profil"].astype(str) == str(profile)]
    return df.reset_index(drop=True)

# --- Spara ---

def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """Skriv om hela profilbladet <profile> med två kolumner (Key, Value)."""
    ss = _get_spreadsheet()
    ws = _get_ws(ss, profile, create=True)
    rows = []
    for k, v in cfg.items():
        if isinstance(v, (date, datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([k, str(v)])
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """
    Lägger till en rad i profilens data.
    Föredrar globalt 'Data' med kolumnen 'Profil' (skapar den om saknas).
    Om ingen global Data finns skapas ett dedikerat 'Data_<Profil>'.
    """
    from gspread.utils import rowcol_to_a1

    ss = _get_spreadsheet()

    # Försök globalt 'Data' först
    try:
        ws = _get_ws(ss, "Data", create=False)
        use_global = True
    except Exception:
        ws = None
        use_global = False

    if use_global:
        # säkerställ profilkolumn
        header = ws.row_values(1) or []
        if not header:
            header = list(row.keys())
            if "Profil" not in header:
                header.insert(0, "Profil")
            a1_end = rowcol_to_a1(1, len(header))
            ws.update(f"A1:{a1_end}", [header])

        # union mellan befintlig header och row-keys
        header = ws.row_values(1)
        add_cols = [k for k in row.keys() if k not in header]
        if add_cols:
            # bredda header
            new_header = header + add_cols
            a1_end = rowcol_to_a1(1, len(new_header))
            ws.update(f"A1:{a1_end}", [new_header])
            header = new_header

        # bygg values i header-ordning och prepend Profil
        row_to_write = dict(row)
        row_to_write["Profil"] = profile
        values = [row_to_write.get(col, "") for col in header]
        ws.append_row(values, value_input_option="USER_ENTERED")
        return

    # annars dedikerat Data_<Profil>
    title = _find_profile_data_sheet_title(ss, profile) or f"Data_{profile}"
    ws = _get_ws(ss, title, create=True)
    header = ws.row_values(1) or []
    if not header:
        header = list(row.keys())
        a1_end = rowcol_to_a1(1, len(header))
        ws.update(f"A1:{a1_end}", [header])
    header = ws.row_values(1)
    add_cols = [k for k in row.keys() if k not in header]
    if add_cols:
        new_header = header + add_cols
        a1_end = rowcol_to_a1(1, len(new_header))
        ws.update(f"A1:{a1_end}", [new_header])
        header = new_header
    values = [row.get(col, "") for col in header]
    ws.append_row(values, value_input_option="USER_ENTERED")
