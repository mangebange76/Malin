# sheets_utils.py
import re
import json
import datetime as dt
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Vi använder Streamlit-secrets och gspread
import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

# ---------------------------
# Helpers: Spreadsheet access
# ---------------------------
def _open_spreadsheet():
    if "GOOGLE_CREDENTIALS" not in st.secrets or "SHEET_URL" not in st.secrets:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS och/eller SHEET_URL i st.secrets.")

    creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_raw, str):
        creds_info = json.loads(creds_raw)
    else:
        # toml -> dict -> json -> dict (för att få ren str->dict)
        creds_info = json.loads(json.dumps(dict(creds_raw)))

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open_by_url(st.secrets["SHEET_URL"])
    return ss

def _ensure_ws(ss, title: str, rows: int = 4000, cols: int = 100):
    """Hämta blad eller skapa om det saknas."""
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

# ---------------------------
# Helpers: text & typing
# ---------------------------
def _norm(s: str) -> str:
    """Normalisera titel för jämförelser: små bokstäver utan extra whitespace/underscore."""
    return re.sub(r"[_\s]+", " ", str(s or "")).strip().lower()

def _candidate_titles_for_data(profile: str) -> List[str]:
    """Möjliga titlar för profildata-blad."""
    p = profile.strip()
    return [
        f"Data_{p}",
        f"Data {p}",
        f"{p} Data",
        f"{p}_Data",
    ]

def _parse_date(val: str) -> Optional[dt.date]:
    """Försök tolka datumsträng."""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(val.strip(), fmt).date()
        except Exception:
            pass
    return None

def _auto_cast(key: str, val: str):
    """Automatisk typning från str -> bool/int/float/date/str."""
    if val is None:
        return None
    s = str(val).strip()

    # Bool
    if _norm(s) in ("true", "ja", "yes", "1"):
        return True
    if _norm(s) in ("false", "nej", "no", "0"):
        return False

    # Datum för nycklar som brukar vara datum
    if key in ("startdatum", "fodelsedatum"):
        d = _parse_date(s)
        if d:
            return d

    # Heltal / flyttal
    try:
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s)
        # tillåt komma som decimaltecken
        s2 = s.replace(",", ".")
        if re.fullmatch(r"[+-]?\d+\.\d+", s2):
            return float(s2)
    except Exception:
        pass

    return s

def _records_to_df(header: List[str], rows: List[List[str]]) -> pd.DataFrame:
    # kapa trailing tomma kolumner
    last_nonempty = 0
    for i, name in enumerate(header, start=1):
        if str(name).strip():
            last_nonempty = i
    header = header[:last_nonempty] if last_nonempty > 0 else header
    trimmed = []
    for r in rows:
        trimmed.append(r[: len(header)])
    df = pd.DataFrame(trimmed, columns=header if header else None)
    # släng helt tomma rader
    if not df.empty:
        df = df.dropna(how="all")
    return df

# ---------------------------
# Publika API: Profiler
# ---------------------------
def list_profiles() -> List[str]:
    """Hämtar profiler från bladet 'Profil' (kolumn A)."""
    ss = _open_spreadsheet()
    try:
        ws = ss.worksheet("Profil")
    except gspread.WorksheetNotFound:
        return []

    vals = ws.col_values(1)  # kolumn A
    profiles = []
    for v in vals:
        name = str(v).strip()
        if not name:
            continue
        # ignorera rubriker typ 'Namn'
        if _norm(name) in ("namn", "profil", "profiler"):
            continue
        profiles.append(name)

    # unika, stabil ordning
    seen = set()
    uniq = []
    for p in profiles:
        k = p.lower()
        if k not in seen:
            uniq.append(p)
            seen.add(k)
    return uniq

def read_profile_settings(profile: str) -> Dict:
    """Läs inställningar från blad med samma namn som profilen.
       Förväntar 2 kolumner (Key, Value) – men funkar även utan rubrikrad.
    """
    if not profile:
        return {}

    ss = _open_spreadsheet()
    # hitta bladet case-insensitivt
    target = None
    for ws in ss.worksheets():
        if _norm(ws.title) == _norm(profile):
            target = ws
            break
    if target is None:
        # inget blad -> inga inställningar
        return {}

    vals = target.get_all_values()
    if not vals:
        return {}

    # Om första rad har >=2 celler och innehåller 'key', 'value' använd rader efter header
    start_row = 0
    if len(vals[0]) >= 2:
        h0 = _norm(vals[0][0])
        h1 = _norm(vals[0][1])
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
        casted = _auto_cast(k, v)
        cfg[k] = casted

    # säkerställ HEIGHT_CM (cm)
    if "HEIGHT_CM" in cfg:
        try:
            cfg["HEIGHT_CM"] = int(str(cfg["HEIGHT_CM"]).replace(",", "."))
        except Exception:
            pass
    return cfg

def _find_profile_data_ws(ss, profile: str) -> Tuple[Optional[gspread.Worksheet], str]:
    """Försök hitta profildata-blad. Returnerar (worksheet, titel-strategi).
       Strategier:
        1) Data_<Profil>, Data <Profil>, <Profil> Data, <Profil>_Data (case/space-agnostiskt)
        2) första blad vars title börjar med 'data' och innehåller profilen
        3) None (faller tillbaka till global 'Data' i read_profile_data)
    """
    norm_profile = _norm(profile)
    candidates = _candidate_titles_for_data(profile)

    # 1) direkta träffar
    titles = { _norm(t): t for t in candidates }
    for ws in ss.worksheets():
        if _norm(ws.title) in titles:
            return ws, "direct"

    # 2) heuristik: titel börjar med 'data' och innehåller profil
    for ws in ss.worksheets():
        t = _norm(ws.title)
        if t.startswith("data") and norm_profile in t:
            return ws, "heuristic"

    return None, "missing"

def read_profile_data(profile: str) -> pd.DataFrame:
    """Läser profildata från Data_<Profil> (med flera varianter).
       Om inget specifikt blad hittas: läs 'Data' och filtrera på kolumnen 'Profil' == profile.
       Returnerar alltid en DataFrame (kan vara tom).
    """
    if not profile:
        return pd.DataFrame()

    ss = _open_spreadsheet()

    # 1) Försök hitta ett dedikerat datablad för profilen
    ws, how = _find_profile_data_ws(ss, profile)
    if ws is not None:
        vals = ws.get_all_values()
        if not vals:
            return pd.DataFrame()
        header = vals[0]
        rows = vals[1:]
        df = _records_to_df(header, rows)
        # släng helt tomma rader
        if not df.empty:
            df = df.dropna(how="all")
        return df

    # 2) Fallback: globalt Data + filtrera Profil == profile
    try:
        data_ws = ss.worksheet("Data")
    except gspread.WorksheetNotFound:
        return pd.DataFrame()

    vals = data_ws.get_all_values()
    if not vals:
        return pd.DataFrame()
    header = vals[0]
    rows = vals[1:]
    df = _records_to_df(header, rows)
    if df.empty:
        return df

    # Kräver kolumnen 'Profil'
    prof_col = None
    for c in df.columns:
        if _norm(c) == "profil":
            prof_col = c
            break
    if prof_col is None:
        # ingen profilkolumn -> kan inte filtrera
        return pd.DataFrame()

    mask = df[prof_col].astype(str).str.strip().str.lower() == profile.strip().lower()
    return df.loc[mask].copy()

def save_profile_settings(profile: str, cfg: Dict):
    """Skriv hela cfg (key/value) till profilens inställningsblad (ersätter innehåll)."""
    if not profile:
        raise ValueError("Profilnamn saknas.")

    ss = _open_spreadsheet()
    ws = _ensure_ws(ss, profile)

    # skriv key/value
    rows = []
    for k, v in cfg.items():
        if isinstance(v, (dt.date, dt.datetime)):
            v = v.strftime("%Y-%m-%d")
        rows.append([str(k), str(v)])

    ws.clear()
    ws.update("A1", [["Key", "Value"]])
    if rows:
        ws.update(f"A2:B{len(rows)+1}", rows)

def append_row_to_profile_data(profile: str, row: Dict):
    """Appendar en rad till profildata-blad.
       Prioriterar samma namngivning som read_profile_data söker:
       Data_<Profil> -> Data <Profil> -> <Profil> Data -> <Profil>_Data.
       Skapar om det saknas. Sätter headerrad om tomt.
    """
    if not profile:
        raise ValueError("Profilnamn saknas.")

    ss = _open_spreadsheet()

    # välj första befintliga eller skapa Data_<Profil>
    ws, how = _find_profile_data_ws(ss, profile)
    title_to_use = None
    if ws is None:
        # skapa Data_<Profil>
        title_to_use = f"Data_{profile}"
        ws = _ensure_ws(ss, title_to_use)
    else:
        title_to_use = ws.title

    # Säkra header
    header = ws.row_values(1)
    if not header:
        header = list(row.keys())
        ws.update("A1", [header])

    # Synka ordning
    values = [row.get(col, "") for col in header]
    ws.append_row(values)

    # Om global Data ska spegla allt också (valfritt): kommenterat ut
    # try:
    #     ws_global = _ensure_ws(ss, "Data")
    #     hdr_g = ws_global.row_values(1)
    #     if not hdr_g:
    #         ws_global.update("A1", [header + (["Profil"] if "Profil" not in header else [])])
    #         hdr_g = ws_global.row_values(1)
    #     # bygg rad i global ordning
    #     row_global = dict(row)
    #     if "Profil" not in row_global:
    #         row_global["Profil"] = profile
    #     values_g = [row_global.get(col, "") for col in hdr_g]
    #     ws_global.append_row(values_g)
    # except Exception:
    #     pass
