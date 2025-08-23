# sheets_utils.py  (basversion 250823)

from __future__ import annotations
import json
import time as _time
from typing import Any, Dict, List, Optional

import streamlit as st
import gspread
from google.oauth2 import service_account
import pandas as pd


# -----------------------------
# Secrets & klient
# -----------------------------
_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _load_google_credentials_dict() -> Dict[str, Any]:
    if "GOOGLE_CREDENTIALS" not in st.secrets:
        raise RuntimeError("GOOGLE_CREDENTIALS saknas i st.secrets.")
    raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        s = raw.strip()
        # Tillåt antingen JSON-text eller TOML-yaml-liknande med enkla citattecken
        try:
            return json.loads(s)
        except Exception as e:
            raise RuntimeError("GOOGLE_CREDENTIALS måste vara JSON-sträng eller dict.") from e
    raise RuntimeError(f"GOOGLE_CREDENTIALS hade oväntad typ: {type(raw)}")


def _get_gspread_client() -> gspread.Client:
    creds_dict = _load_google_credentials_dict()
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=_SHEETS_SCOPES
    )
    return gspread.authorize(creds)


def _open_spreadsheet(retries: int = 3, delay_sec: float = 0.8) -> gspread.Spreadsheet:
    if "SHEET_URL" not in st.secrets:
        raise RuntimeError("SHEET_URL saknas i st.secrets.")
    url = st.secrets["SHEET_URL"]
    last_err: Optional[Exception] = None
    client = _get_gspread_client()
    for _ in range(max(1, retries)):
        try:
            return client.open_by_url(url)
        except Exception as e:
            last_err = e
            _time.sleep(delay_sec)
    raise RuntimeError(f"Kunde inte öppna kalkylarket efter flera försök: {last_err}")


# -----------------------------
# Hjälpare för ark/blad
# -----------------------------
def _get_ws_by_title(ss: gspread.Spreadsheet, title: str) -> Optional[gspread.Worksheet]:
    try:
        return ss.worksheet(title)
    except Exception:
        return None


def _infer_existing_data_ws(ss: gspread.Spreadsheet, profile: str) -> Optional[gspread.Worksheet]:
    """Hitta ett befintligt data-ark för profilen (utan att skapa nytt)."""
    preferred = f"Data - {profile}"
    ws = _get_ws_by_title(ss, preferred)
    if ws:
        return ws
    # Fallback-varianter
    candidates = [
        f"{profile} - Data",
        f"DATA - {profile}",
        f"Data–{profile}",
        f"Data_{profile}",
    ]
    for name in candidates:
        ws = _get_ws_by_title(ss, name)
        if ws:
            return ws
    # Sista chans: hitta blad som verkar vara data (har rubriker som Datum/Män)
    for w in ss.worksheets():
        try:
            vals = w.get_values("A1:Z1")
            headers = [h.strip() for h in (vals[0] if vals else [])]
            if any(h.lower() == "datum" for h in headers) and any(h.lower() in ("män", "man") for h in headers):
                return w
        except Exception:
            pass
    return None


def _ensure_data_ws(ss: gspread.Spreadsheet, profile: str, header: List[str]) -> gspread.Worksheet:
    """Returnera data-ark. Skapar 'Data - {profile}' ENDAST om inget data-ark finns."""
    ws = _infer_existing_data_ws(ss, profile)
    if ws:
        # Se till att header finns (behåller befintlig ordning om den redan finns)
        vals = ws.get_values("A1:Z1")
        current = list(vals[0]) if vals else []
        if not current:
            ws.update("A1", [header])
        return ws
    # Skapa nytt data-ark
    ws = ss.add_worksheet(title=f"Data - {profile}", rows=1000, cols=max(26, len(header)))
    ws.update("A1", [header])
    return ws


def _read_sheet_as_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    headers = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=headers)


def _kv_sheet_to_dict(ws: gspread.Worksheet) -> Dict[str, Any]:
    """Läs ett nyckel/värde-blad (två kolumner: Nyckel | Värde) till dict."""
    df = _read_sheet_as_df(ws)
    out: Dict[str, Any] = {}
    if df.empty:
        return out
    # Anta första kolumn = nyckel, andra = värde
    for _, row in df.iterrows():
        key = str(row.iloc[0]).strip()
        val = row.iloc[1] if len(row) > 1 else ""
        out[key] = val
    return out


def _parse_settings_from_ws(ws: gspread.Worksheet) -> Dict[str, Any]:
    """Försök A1 JSON, annars nyckel/värde-tabell."""
    try:
        a1 = ws.acell("A1").value
        if a1:
            s = a1.strip()
            if s.startswith("{") and s.endswith("}"):
                return json.loads(s)
    except Exception:
        pass
    # Fallback: nyckel/värde-rader
    return _kv_sheet_to_dict(ws)


def _coerce_cfg_types(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Fixar kända fält-typer som appen förväntar sig."""
    out = dict(cfg)
    # Datum
    from datetime import date, time as dtime, datetime
    def _to_date(x):
        if isinstance(x, date) and not isinstance(x, datetime):
            return x
        if isinstance(x, str):
            try:
                return datetime.fromisoformat(x).date()
            except Exception:
                pass
        return out.get("startdatum")
    def _to_time(x):
        if isinstance(x, dtime):
            return x
        if isinstance(x, str):
            try:
                return dtime.fromisoformat(x)
            except Exception:
                # Stöd "HH:MM" utan sek
                try:
                    hh, mm = x.split(":")[:2]
                    return dtime(hour=int(hh), minute=int(mm))
                except Exception:
                    pass
        return out.get("starttid")

    if "startdatum" in out:
        out["startdatum"] = _to_date(out["startdatum"])
    if "fodelsedatum" in out:
        try:
            if isinstance(out["fodelsedatum"], str):
                out["fodelsedatum"] = datetime.fromisoformat(out["fodelsedatum"]).date()
        except Exception:
            pass
    if "starttid" in out:
        out["starttid"] = _to_time(out["starttid"])

    # Numeriska fält som kan vara str
    for key in [
        "avgift_usd","PROD_STAFF","BONUS_AVAILABLE","BONUS_PCT",
        "SUPER_BONUS_PCT","BMI_GOAL","HEIGHT_CM",
        "ESK_MIN","ESK_MAX",
        "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA",
        "SUPER_BONUS_ACC",
        "EXTRA_SLEEP_H",
    ]:
        if key in out:
            try:
                # int om heltal, annars float
                v = out[key]
                if isinstance(v, str) and v.strip() == "":
                    continue
                fv = float(v)
                iv = int(fv)
                out[key] = iv if fv.is_integer() else fv
            except Exception:
                pass
    return out


# -----------------------------
# Publika funktioner
# -----------------------------
def list_profiles() -> List[str]:
    """Läs profiler från bladet 'Profil' (kolumn A)."""
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, "Profil")
    if not ws:
        # Fallback: härleda profiler från data-bladens namn
        profs = []
        for w in ss.worksheets():
            t = w.title
            if t.startswith("Data - "):
                profs.append(t.replace("Data - ", "", 1))
        return sorted(list(dict.fromkeys(profs)))
    col = ws.col_values(1)
    profs = [c.strip() for c in col if c and c.strip().lower() not in ("profil", "namn")]
    return profs


def read_profile_settings(profile: str) -> Dict[str, Any]:
    """Läs profilens inställningar. Stöd flera möjliga bladnamn/format."""
    ss = _open_spreadsheet()
    # Företräde
    ws = _get_ws_by_title(ss, f"{profile} - Inställningar")
    if not ws:
        # Fallback: blad med exakt profilnamn
        ws = _get_ws_by_title(ss, profile)
    if not ws:
        return {}
    raw = _parse_settings_from_ws(ws)
    return _coerce_cfg_types(raw)


def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """Spara inställningar som JSON i A1 på '{profile} - Inställningar' (skapas om saknas)."""
    ss = _open_spreadsheet()
    ws = _get_ws_by_title(ss, f"{profile} - Inställningar")
    if not ws:
        # Skapa nytt inställningsblad
        ws = ss.add_worksheet(title=f"{profile} - Inställningar", rows=50, cols=4)
    # Skriv JSON i A1
    try:
        payload = json.dumps(cfg, ensure_ascii=False)
    except Exception:
        # sista utväg: konvertera till str
        payload = json.dumps({k: str(v) for k, v in cfg.items()}, ensure_ascii=False)
    ws.update_acell("A1", payload)


def read_profile_data(profile: str) -> pd.DataFrame:
    """Läs profilens data som DataFrame. Returnerar tom DF om inget data-ark finns."""
    ss = _open_spreadsheet()
    ws = _infer_existing_data_ws(ss, profile)
    if not ws:
        return pd.DataFrame()
    return _read_sheet_as_df(ws)


def append_row_to_profile_data(profile: str, row_dict: Dict[str, Any]) -> None:
    """Append till befintligt data-ark. Skapar 'Data - {profile}' om inget data-ark hittas."""
    ss = _open_spreadsheet()

    # Hämta/Skapa data-ark med stabil rubrik
    header = list(row_dict.keys())
    ws = _ensure_data_ws(ss, profile, header)

    # Läs befintlig header (behåll befintlig ordning om den finns)
    vals = ws.get_values("A1:Z1")
    current_header = list(vals[0]) if vals else []
    if not current_header:
        current_header = header
        ws.update("A1", [current_header])

    # Bygg rad enligt current_header
    def _cellify(v: Any) -> Any:
        # gspread kräver enkla typer
        if v is None:
            return ""
        if isinstance(v, (int, float, str)):
            return v
        # datum/tid
        try:
            import datetime as _dt
            if isinstance(v, _dt.date) and not isinstance(v, _dt.datetime):
                return v.isoformat()
            if isinstance(v, _dt.time):
                return v.strftime("%H:%M:%S")
            if isinstance(v, _dt.datetime):
                return v.isoformat(sep=" ")
        except Exception:
            pass
        # fall back till str
        try:
            return str(v)
        except Exception:
            return ""

    row_out = [_cellify(row_dict.get(col, "")) for col in current_header]
    ws.append_row(row_out, value_input_option="USER_ENTERED")


# -----------------------------
# (Valfritt) Hjälpare för debug
# -----------------------------
def _debug_sheet_titles() -> List[str]:
    ss = _open_spreadsheet()
    return [w.title for w in ss.worksheets()]
