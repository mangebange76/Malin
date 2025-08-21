# sheets_utils.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# ========== INTERN HJÄLP ==========
def _load_service_account_from_secrets():
    """
    Läser GOOGLE_CREDENTIALS (json/dict) ur st.secrets och returnerar en dict.
    """
    if "GOOGLE_CREDENTIALS" not in st.secrets:
        raise RuntimeError("Saknar secret GOOGLE_CREDENTIALS.")
    raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(raw, str):
        return json.loads(raw)
    # AttrDict/dict → str → dict
    return json.loads(json.dumps(dict(raw)))


def _open_spreadsheet():
    """
    Öppnar Google Sheet via URL i secret SHEET_URL.
    Returnerar gspread Spreadsheet-objektet.
    """
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
    # Trimma och ta bort dubbletter med stabil ordning.
    seen = set()
    out = []
    for n in names:
        k = (n or "").strip()
        if k and k not in seen:
            out.append(k)
            seen.add(k)
    return out


def _ws_titles(ss) -> List[str]:
    return [ws.title for ws in ss.worksheets()]


# ========== OFFENTLIGA FUNKTIONER (generösa alias) ==========
# -- klient/öppna
def get_client():
    """Behåller kompatibilitet – returnerar Spreadsheet (ej rena klienten)."""
    return _open_spreadsheet()


def get_spreadsheet():
    """Alias: öppnar och returnerar Spreadsheet."""
    return _open_spreadsheet()


def open_spreadsheet():
    """Alias: öppnar och returnerar Spreadsheet."""
    return _open_spreadsheet()


# -- worksheet helper
def ensure_ws(ss, title: str, rows: int = 4000, cols: int = 80):
    """
    Säkerställ att bladet 'title' finns, annars skapa det.
    Returnerar Worksheet.
    """
    import gspread

    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)


def ensure_worksheet(ss, title: str, rows: int = 4000, cols: int = 80):
    """Alias till ensure_ws."""
    return ensure_ws(ss, title, rows, cols)


# -- PROFIL: lista, inställningar, data
def read_profile_list(ss=None) -> List[str]:
    """
    Läser flik 'Profil', kolumn A (alla rader). Returnerar en ren lista (utan tomma).
    """
    if ss is None:
        ss = _open_spreadsheet()
    try:
        ws = ensure_ws(ss, "Profil", rows=200, cols=4)
        vals = ws.col_values(1)
        return [v.strip() for v in vals if (v or "").strip()]
    except Exception as e:
        st.error(f"Kunde inte läsa profiler: {e}")
        return []


def _kv_rows_to_dict(rows: List[List[str]]) -> Dict[str, Any]:
    """
    Hjälp: om inställningsbladet är Key/Value eller Nyckel/Värde.
    """
    out: Dict[str, Any] = {}
    for r in rows:
        if not r:
            continue
        if len(r) == 1:
            k, v = r[0], ""
        else:
            k, v = r[0], r[1]
        k = (k or "").strip()
        if not k:
            continue
        v = (v or "").strip()
        # auto-typning
        if re.fullmatch(r"-?\d+", v or ""):
            out[k] = int(v)
        else:
            try:
                out[k] = float(v)
            except Exception:
                # försök datum YYYY-MM-DD
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                    out[k] = v  # app.py kan själv casta till date om den vill
                else:
                    out[k] = v
    return out


def read_profile_cfg(profile: str, ss=None) -> Dict[str, Any]:
    """
    Läser inställningar från BLADET som heter exakt 'profile'.
    Hanterar både (Key,Value)-tabell och “tabell med rubriker” (get_all_records).
    """
    if ss is None:
        ss = _open_spreadsheet()

    try:
        ws = ensure_ws(ss, profile)
    except Exception as e:
        st.warning(f"Profilblad '{profile}' saknas: {e}")
        return {}

    # Försök 1: tvåkolumn (A/B)
    values = ws.get_all_values()
    if values:
        # Om första raden ser ut som rubriker “Key,Value” eller “Nyckel,Värde”
        hdr = [c.strip().lower() for c in (values[0] if values else [])]
        if ("key" in hdr and "value" in hdr) or ("nyckel" in hdr and "värde" in hdr):
            # hoppa headern
            return _kv_rows_to_dict(values[1:])

    # Försök 2: get_all_records (tabell med rubriker där första kolumn är Nyckel/Key, andra Värde)
    try:
        recs = ws.get_all_records()
        if recs:
            # Om bladet är struktur (Key/Value som kolumnrubriker)
            if {"Key", "Value"}.issubset(recs[0].keys()):
                rows = [[r.get("Key", ""), r.get("Value", "")] for r in recs]
                return _kv_rows_to_dict(rows)
            elif {"Nyckel", "Värde"}.issubset(recs[0].keys()):
                rows = [[r.get("Nyckel", ""), r.get("Värde", "")] for r in recs]
                return _kv_rows_to_dict(rows)
            else:
                # Om någon lagt inställningar i form av en bred tabell – returnera första raden som dict
                return recs[0]
    except Exception:
        pass

    return {}


def write_profile_cfg(profile: str, cfg: Dict[str, Any], ss=None) -> None:
    """
    Skriver om inställningar för profilen (två kolumner Key/Value).
    """
    if ss is None:
        ss = _open_spreadsheet()
    ws = ensure_ws(ss, profile, rows=400, cols=4)
    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    rows = []
    for k, v in cfg.items():
        if hasattr(v, "strftime"):
            v = v.strftime("%Y-%m-%d")
        rows.append([str(k), str(v)])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)


# alias
save_profile_cfg = write_profile_cfg


def _candidate_data_titles(profile: str) -> List[str]:
    """
    Möjliga namn för ett profilspecifikt Data-blad.
    """
    p = profile
    candidates = [
        f"Data__{p}",
        f"Data_{p}",
        f"{p}__Data",
        f"{p}_Data",
        f"Data - {p}",
        f"{p} - Data",
        f"DATA__{p}",
        f"DATA_{p}",
    ]
    return candidates


def find_profile_data_worksheet(ss, profile: str):
    """
    Försök hitta blad för profilens data.
    1) Exakta varianter (Data__Profil, Data_Profil, …)
    2) Om ej träff: kolla alla blad och hitta första som innehåller profilnamnet och 'data'
    3) Om ej träff: returnera None
    """
    titles = _ws_titles(ss)
    # steg 1
    for t in _candidate_data_titles(profile):
        if t in titles:
            return ss.worksheet(t)
    # steg 2: contains
    pname = profile.lower()
    for t in titles:
        if "data" in t.lower() and pname in t.lower():
            return ss.worksheet(t)
    return None


def ensure_profile_data_sheet(ss, profile: str, header: List[str]) -> Any:
    """
    Säkerställ profilspecifikt data-blad.
    Skapar om det saknas och lägger header på rad 1.
    """
    ws = find_profile_data_worksheet(ss, profile)
    if ws is None:
        # välj “snyggaste” standardnamn
        title = f"Data__{profile}"
        ws = ensure_ws(ss, title, rows=4000, cols=max(80, len(header) + 5))
        # sätt header
        header = _normalize_header(header)
        if header:
            ws.update("A1", [header])
    else:
        # se till att headern innehåller alla kolumner (union)
        existing = ws.row_values(1)
        union = _normalize_header((existing or []) + (header or []))
        if union and union != existing:
            ws.update("A1", [union])
    return ws


def read_profile_data(profile: str, ss=None) -> List[Dict[str, Any]]:
    """
    Läser alla rader från profilens data-blad (enligt find_profile_data_worksheet).
    Returnerar list[dict]. Tom lista om blad saknas.
    """
    if ss is None:
        ss = _open_spreadsheet()

    ws = find_profile_data_worksheet(ss, profile)
    if ws is None:
        return []
    try:
        return ws.get_all_records() or []
    except Exception:
        return []


def read_profile_data_df(profile: str, ss=None):
    """
    Som read_profile_data, men returnerar pandas.DataFrame (kan vara tom).
    """
    import pandas as pd

    rows = read_profile_data(profile, ss=ss)
    return pd.DataFrame(rows)


def append_profile_row(profile: str, row_dict: Dict[str, Any], ss=None) -> None:
    """
    Appendar en rad i profilens data-blad. Om blad saknas skapas det.
    Header uppdateras med union av existerande + row_dict.keys().
    """
    if ss is None:
        ss = _open_spreadsheet()

    # slå in profilnamnet i raden också (robusthet/felsökning)
    row_with_profile = dict(row_dict)
    row_with_profile.setdefault("Profil", profile)

    # säkerställ blad
    header = list(row_with_profile.keys())
    ws = ensure_profile_data_sheet(ss, profile, header)

    # uppdatera header (union) och mappa values i samma ordning
    current_header = ws.row_values(1)
    union = _normalize_header((current_header or []) + list(row_with_profile.keys()))
    if union != current_header:
        ws.update("A1", [union])
        current_header = union

    values = [row_with_profile.get(col, "") for col in current_header]
    ws.append_row(values)


# ------------- EXTRA ALIAS (för kompatibilitet med olika app-varianter) -------------
# (så ditt app.py inte klagar oavsett vilken variant du råkade använda tidigare)

open_ss = get_spreadsheet
get_ss = get_spreadsheet
ensure_sheet = ensure_ws
ensure_data_sheet = ensure_profile_data_sheet
append_row_to_profile_data = append_profile_row
read_profile_cfg_dict = read_profile_cfg
read_profiles = read_profile_list
