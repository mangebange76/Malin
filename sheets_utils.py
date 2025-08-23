# sheets_utils.py
# =========================
# Google Sheets-hjälpare för Malin-appen
# - Robust klient + retrys
# - Profiler (lista från blad "Profil", kolumn A)
# - Profilinställningar (key/value-blad)
# - Profildata (rader + dynamiska headers på blad med samma namn som profilen)
# =========================

import json
import time
from typing import Dict, List, Optional, Tuple

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials as SA_Credentials

# Scopes
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ===== Interna util-funktioner =====

def _get_gspread_client() -> gspread.Client:
    creds_blob = st.secrets.get("GOOGLE_CREDENTIALS")
    if not creds_blob:
        raise RuntimeError("Saknar GOOGLE_CREDENTIALS i st.secrets.")
    try:
        info = json.loads(creds_blob) if isinstance(creds_blob, str) else dict(creds_blob)
        creds = SA_Credentials.from_service_account_info(info, scopes=_SCOPES)
    except Exception as e:
        raise RuntimeError(f"Fel i GOOGLE_CREDENTIALS: {e}")
    return gspread.authorize(creds)

def _open_spreadsheet() -> gspread.Spreadsheet:
    """Öppna arket med retrys (429/5xx) + bättre fel vid 403/404."""
    url = st.secrets.get("SHEET_URL")
    if not url:
        raise RuntimeError("Saknar SHEET_URL i st.secrets.")
    client = _get_gspread_client()

    backoff = 0.6
    last_err = None
    for attempt in range(5):
        try:
            return client.open_by_url(url)
        except gspread.exceptions.APIError as e:
            code = getattr(e.response, "status_code", None)
            # Retrybara fel
            if code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff *= 2
                last_err = e
                continue
            # Åtkomst/URL-fel
            if code in (403, 404):
                raise RuntimeError(
                    f"Åtkomst nekad eller ark saknas ({code}). "
                    f"Dela arket med servicekontots e-post och kontrollera SHEET_URL."
                ) from e
            raise
        except Exception as e:
            last_err = e
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")

def _gs_retry(fn, *args, **kwargs):
    """Enkel retry-wrapper för enstaka worksheet-anrop."""
    backoff = 0.5
    last = None
    for _ in range(5):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            code = getattr(e.response, "status_code", None)
            if code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff *= 2
                last = e
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(backoff)
            backoff *= 2
    raise last

def _get_ws_by_title(ss: gspread.Spreadsheet, title: str) -> Optional[gspread.Worksheet]:
    try:
        return _gs_retry(ss.worksheet, title)
    except gspread.WorksheetNotFound:
        return None

def _get_or_create_ws(ss: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    ws = _get_ws_by_title(ss, title)
    if ws is not None:
        return ws
    # Skapa nytt blad
    return _gs_retry(ss.add_worksheet, title=title, rows=1000, cols=200)

# ===== Offentliga funktioner som appen använder =====

def list_profiles() -> List[str]:
    """
    Läs lista av profilnamn från bladet 'Profil' (kolumn A).
    Rad 1 antas vara rubrik och hoppas över om den inte ser ut som ett namn.
    """
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, "Profil")
    if ws is None:
        return []

    values = _gs_retry(ws.col_values, 1)  # kolumn A
    out = []
    for i, v in enumerate(values):
        name = (v or "").strip()
        if not name:
            continue
        # hoppa ev. rubrik i första raden
        if i == 0 and name.lower() in ("profil", "namn", "profiles"):
            continue
        out.append(name)
    # ta bort dubbletter men behåll ordning
    seen = set()
    uniq = []
    for n in out:
        if n not in seen:
            uniq.append(n)
            seen.add(n)
    return uniq

def read_profile_settings(profile: str) -> Dict:
    """
    Läser profilens inställningar som key/value-tabell.
    Bladsökordning:
      1) f"{profile}__settings"
      2) f"{profile}_settings"
      3) "Inställningar"
      4) "Settings"
    Struktur: kolumn A = Nyckel, kolumn B = Värde.
    Returnerar en dict med strängvärden (appen typ-säkrar själv).
    """
    ss = _open_spreadsheet()
    cand_titles = [
        f"{profile}__settings",
        f"{profile}_settings",
        "Inställningar",
        "Settings",
    ]
    ws = None
    for t in cand_titles:
        ws = _get_ws_by_title(ss, t)
        if ws:
            break
    if ws is None:
        return {}

    rows = _gs_retry(ws.get_all_values)
    out = {}
    for r in rows:
        if not r:
            continue
        if len(r) == 1:
            key = (r[0] or "").strip()
            if key:
                out[key] = ""
            continue
        key = (r[0] or "").strip()
        val = (r[1] or "").strip()
        if key:
            out[key] = val
    return out

def save_profile_settings(profile: str, cfg: Dict) -> None:
    """
    Sparar en stor del av appens CFG till ett dedikerat settings-blad för profilen:
    f"{profile}__settings" (skapas om det saknas).

    Värden serialiseras som str (datum/tid som ISO).
    """
    ss = _open_spreadsheet()
    ws = _get_or_create_ws(ss, f"{profile}__settings")

    # Välj vilka nycklar som är meningsfulla att lagra
    keys_to_save = [
        "startdatum","starttid","fodelsedatum",
        "avgift_usd","PROD_STAFF",
        "BONUS_AVAILABLE","BONUS_PCT",
        "SUPER_BONUS_PCT","SUPER_BONUS_ACC",
        "BMI_GOAL","HEIGHT_CM",
        "ESK_MIN","ESK_MAX",
        "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA",
        "LBL_PAPPAN","LBL_GRANNAR","LBL_NILS_VANNER","LBL_NILS_FAMILJ","LBL_BEKANTA","LBL_ESK",
        "EXTRA_SLEEP_H",
    ]

    # Serialisering
    def _as_str(v):
        from datetime import date, time, datetime
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, date) and not isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
        if isinstance(v, datetime):
            return v.isoformat(timespec="seconds")
        if isinstance(v, bool):
            return "1" if v else "0"
        return "" if v is None else str(v)

    rows = [["Nyckel", "Värde"]]
    for k in keys_to_save:
        rows.append([k, _as_str(cfg.get(k))])

    # rensa och skriv
    _gs_retry(ws.clear)
    _gs_retry(ws.update, "A1", rows)

def _read_table_to_df(ws: gspread.Worksheet):
    import pandas as pd
    values = _gs_retry(ws.get_all_values)
    if not values:
        return pd.DataFrame()
    header = values[0]
    data = values[1:] if len(values) > 1 else []
    # Fyll upp rader som är kortare än header
    data_norm = [row + [""]*(len(header)-len(row)) for row in data]
    df = pd.DataFrame(data_norm, columns=header)
    return df

def read_profile_data(profile: str):
    """
    Läser profildata från ett blad som heter exakt som profilen.
    Finns inte bladet returneras en tom DataFrame.
    """
    import pandas as pd
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, profile)
    if ws is None:
        # skapa tomt blad med en minimal header?
        # Vi returnerar tom DF (appen hanterar tom lista).
        return pd.DataFrame()
    return _read_table_to_df(ws)

def _sync_header(ws: gspread.Worksheet, new_keys: List[str]) -> List[str]:
    """Säkerställ att alla keys finns i headern (rad 1). Returnerar uppdaterad header."""
    values = _gs_retry(ws.get_all_values)
    header = values[0] if values else []
    # Om bladet är helt tomt – skapa headeren från new_keys (sorteras stabilt)
    if not header:
        header = list(new_keys)
        _gs_retry(ws.update, "A1", [header])
        return header

    # Lägg till saknade kolumner längst till höger
    missing = [k for k in new_keys if k not in header]
    if missing:
        updated = header + missing
        # uppdatera header-raden
        _gs_retry(ws.update, f"A1", [updated])
        return updated
    return header

def _row_order_from_header(header: List[str], row_dict: Dict) -> List[str]:
    """Returnera värdelista i header-ordning (okända keys ignoreras)."""
    out = []
    for col in header:
        val = row_dict.get(col, "")
        # streamlit skickar ofta numbers; vi konverterar varsamt till str för Sheets
        if isinstance(val, float):
            # undvik 1.0 -> "1.0" ifall col verkligen är heltal? Låt appen sköta typerna vid läsning.
            out.append(str(val))
        else:
            out.append(str(val))
    return out

def append_row_to_profile_data(profile: str, row_dict: Dict) -> None:
    """
    Appenda en rad till ett blad med samma namn som profilen.
    Saknas bladet skapas det. Headern synkas dynamiskt mot row_dicts nycklar.
    """
    ss = _open_spreadsheet()
    ws = _get_or_create_ws(ss, profile)

    # säkerställ header
    header = _sync_header(ws, list(row_dict.keys()))
    # ordna värdena i header-ordning
    values = _row_order_from_header(header, row_dict)
    # hitta nästa rad
    # get_all_values kan vara tungt; använd ws.row_count och counta bef. rader snabbt via find?
    # Vi kör enkel append_row via API (gspread hanterar nästa rad).
    _gs_retry(ws.append_row, values, value_input_option="USER_ENTERED")
