# sheets_utils.py
# Basversion 250822 – uppdaterad för robust auth + flexibla inställningar + säkra läs/skriv
from __future__ import annotations

import os
import time
import json
import math
from typing import Dict, List, Any, Optional
from datetime import date, time as dtime, datetime

import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials

# =========================================================
#  Auth & Spreadsheet
# =========================================================

def _load_google_credentials_dict() -> dict:
    """
    Laddar service account-credar från st.secrets eller env.
    Stödjer:
      - st.secrets["GOOGLE_CREDENTIALS"] som dict ELLER JSON-sträng
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

    # Dict direkt?
    if isinstance(raw, dict):
        creds_dict = dict(raw)
    # Sträng → försök JSON
    elif isinstance(raw, str):
        s = raw.strip()
        try:
            creds_dict = json.loads(s)
        except Exception as e:
            raise RuntimeError("GOOGLE_CREDENTIALS är en sträng men inte giltig JSON.") from e
    else:
        raise RuntimeError(f"GOOGLE_CREDENTIALS hade oväntad typ: {type(raw)}")

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


def _open_spreadsheet(retries: int = 3, base_delay: float = 0.8):
    """
    Öppnar arket från SHEET_URL (i secrets eller ENV) med exponential backoff.
    """
    sheet_url = st.secrets.get("SHEET_URL") or os.environ.get("SHEET_URL")
    if not sheet_url:
        raise RuntimeError("SHEET_URL saknas i secrets/ENV.")

    client = _get_gspread_client()
    last_err = None
    for i in range(retries):
        try:
            return client.open_by_url(sheet_url)
        except APIError as e:
            last_err = e
            time.sleep(base_delay * (2 ** i))
    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")


# =========================================================
#  Worksheet helpers
# =========================================================

def _get_worksheet_by_title(ss, title: str):
    try:
        return ss.worksheet(title)
    except WorksheetNotFound:
        return None

def _get_or_create_worksheet(ss, title: str, rows: int = 1000, cols: int = 50):
    ws = _get_worksheet_by_title(ss, title)
    if ws is None:
        ws = ss.add_worksheet(title=title, rows=rows, cols=cols)
    return ws

def _with_retry(fn, *args, retries: int = 3, base_delay: float = 0.6, **kwargs):
    last_err = None
    for i in range(retries):
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            last_err = e
            time.sleep(base_delay * (2 ** i))
    if last_err:
        raise last_err
    raise RuntimeError("Operation misslyckades utan APIError.")

# =========================================================
#  Profiler – lista/profilblad
# =========================================================

def list_profiles() -> List[str]:
    """
    Läser bladet 'Profil' och returnerar alla namn i kolumn A (exkl. header/tomma).
    """
    ss = _open_spreadsheet()
    ws = _get_worksheet_by_title(ss, "Profil")
    if ws is None:
        return []
    vals = _with_retry(ws.col_values, 1)  # kolumn A
    out: List[str] = []
    for i, v in enumerate(vals):
        v = (v or "").strip()
        if not v:
            continue
        # hoppa ev. rubrikrad
        if i == 0 and v.lower() in ("profil", "profiles", "namn", "name"):
            continue
        out.append(v)
    # unika i ordning
    seen = set()
    uniq = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq

# =========================================================
#  Inställningar – läs/spara
# =========================================================

def _coerce_cfg_types(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Säkerställ att startdatum/fodelsedatum/starttid konverteras till rätt typer om de är strängar.
    """
    out = dict(cfg)

    def _to_date(v):
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str) and v:
            try:
                return datetime.fromisoformat(v).date()
            except Exception:
                try:
                    return datetime.strptime(v, "%Y-%m-%d").date()
                except Exception:
                    return out.get("startdatum", date(1990,1,1))
        return out.get("startdatum", date(1990,1,1))

    def _to_time(v):
        if isinstance(v, dtime):
            return v
        if isinstance(v, datetime):
            return v.time().replace(microsecond=0)
        if isinstance(v, str) and v:
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(v, fmt).time()
                except Exception:
                    pass
        # fallback
        return dtime(7, 0)

    if "startdatum" in out:
        out["startdatum"] = _to_date(out["startdatum"])
    if "fodelsedatum" in out:
        out["fodelsedatum"] = _to_date(out["fodelsedatum"])
    if "starttid" in out:
        out["starttid"] = _to_time(out["starttid"])
    return out


def _read_settings_from_ws(ws) -> Dict[str, Any]:
    """
    Förväntar sig antingen:
      - A1="JSON", A2=<json-sträng>
      - eller en key/value-tabell med två kolumner (key i kol A, value i kol B)
    """
    try:
        a1 = _with_retry(ws.acell, "A1").value or ""
    except Exception:
        a1 = ""
    a1 = a1.strip().upper()

    # JSON-varianten
    if a1 == "JSON":
        raw = _with_retry(ws.acell, "A2").value or ""
        raw = raw.strip()
        if raw:
            try:
                cfg = json.loads(raw)
                return cfg if isinstance(cfg, dict) else {}
            except Exception:
                pass

    # key/value-variant
    rows = _with_retry(ws.get_all_values)
    cfg: Dict[str, Any] = {}
    for r in rows:
        if len(r) < 2:
            continue
        key = (r[0] or "").strip()
        val = r[1]
        if not key:
            continue
        # försök typa enkla tal/bool
        v = val
        if isinstance(val, str):
            s = val.strip()
            if s.lower() in ("true", "false"):
                v = (s.lower() == "true")
            else:
                try:
                    if "." in s.replace(",", "."):
                        v = float(s.replace(",", "."))
                    else:
                        v = int(s)
                except Exception:
                    v = val
        cfg[key] = v
    return cfg


def read_profile_settings(profile: str) -> Dict[str, Any]:
    """
    Läser inställningar för en profil.
    Primärt från bladet '<profil>__settings'. Om saknas, försöker ett par alternativ och till sist tom dict.
    Konverterar datum/tid till rätt typer.
    """
    ss = _open_spreadsheet()
    # Kandidat-namn (kompatibilitet)
    candidates = [
        f"{profile}__settings",
        f"{profile}__cfg",
        f"{profile}_settings",
        f"{profile}__inst",
        f"{profile}__inställningar",
    ]
    ws = None
    for name in candidates:
        ws = _get_worksheet_by_title(ss, name)
        if ws:
            break

    cfg: Dict[str, Any] = {}
    if ws:
        try:
            cfg = _read_settings_from_ws(ws)
        except Exception:
            cfg = {}

    # Slutlig typning för kritiska fält
    cfg = _coerce_cfg_types(cfg)
    return cfg


def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """
    Sparar inställningar för profilen i blad '<profil>__settings' som JSON (A1='JSON', A2='<json>').
    Datum/tid konverteras till ISO-strängar.
    """
    ss = _open_spreadsheet()
    ws = _get_or_create_worksheet(ss, f"{profile}__settings")

    # Konvertera datum/tid till isoformat i en sanerad kopia
    def _ser(v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, dtime):
            return v.strftime("%H:%M:%S")
        return v

    to_save = {k: _ser(v) for k, v in cfg.items()}

    # Töm blad och skriv om
    _with_retry(ws.clear)
    _with_retry(ws.update, "A1", [["JSON"], [json.dumps(to_save, ensure_ascii=False)]])


# =========================================================
#  Profildata – läs/append
# =========================================================

def _ensure_headers(ws, desired_headers: List[str]) -> List[str]:
    """
    Ser till att headerraden innehåller minst desired_headers, i given ordning + ev. bef. kolumner.
    Returnerar den slutliga headerlistan.
    """
    try:
        current = _with_retry(ws.row_values, 1)
    except Exception:
        current = []

    current = [c for c in current if c]  # rensa tomma i slutet
    if not current:
        # lägg första headern
        _with_retry(ws.update, "A1", [desired_headers])
        return desired_headers

    # union – bevara befintlig ordning, lägg till nya sist
    cur_set = set(current)
    new_cols = [h for h in desired_headers if h not in cur_set]
    final = current + new_cols
    if new_cols:
        _with_retry(ws.update, "A1", [final])
    return final


def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läser hela data-bladet för profilen -> DataFrame.
    Om blad saknas returneras tom DF.
    """
    ss = _open_spreadsheet()
    ws = _get_worksheet_by_title(ss, profile)
    if ws is None:
        return pd.DataFrame()

    # Använd get_all_records (första raden = headers)
    records: List[Dict[str, Any]] = _with_retry(ws.get_all_records, expected_headers=None, head=1, default_blank="")
    return pd.DataFrame(records)


def append_row_to_profile_data(profile: str, row: Dict[str, Any]) -> None:
    """
    Appendar en rad till profilens datablad.
    Skapar bladet och headerraden om de saknas. Säkerställer att alla nycklar finns i headern.
    """
    ss = _open_spreadsheet()
    ws = _get_or_create_worksheet(ss, profile)

    # Säkerställ headers
    headers = list(row.keys())
    headers = _ensure_headers(ws, headers)

    # Bygg radlist i headerordning
    def _ser_cell(v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, dtime):
            return v.strftime("%H:%M:%S")
        if isinstance(v, float):
            # undvik NaN/inf i Sheets
            if math.isfinite(v):
                return v
            return ""
        return v

    values = [_ser_cell(row.get(h, "")) for h in headers]

    # Append
    _with_retry(ws.append_row, values, value_input_option="USER_ENTERED")
