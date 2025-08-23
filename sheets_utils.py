# sheets_utils.py  (Basversion 250822 – robust Google Sheets-hantering)
from __future__ import annotations

import json
import time
from datetime import datetime, date, time as dtime
from typing import Dict, Any, List, Optional

import gspread
import pandas as pd
import streamlit as st


# =========================
# Hjälpfunktioner – datum/tid & numerik
# =========================
def _parse_date(x: Any) -> Optional[date]:
    """Försöker tolka datum i vanliga format: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, etc."""
    if x is None or x == "":
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    s = str(x).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    # ISO-ish?
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _parse_time(x: Any) -> Optional[dtime]:
    """Försöker tolka tid: HH:MM eller HH:MM:SS."""
    if x is None or x == "":
        return None
    if isinstance(x, dtime):
        return x
    s = str(x).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass
    # ISO-ish?
    try:
        return datetime.fromisoformat(s).time()
    except Exception:
        return None


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(float(str(x).replace(",", ".").strip()))
    except Exception:
        return None


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None


def _clean_header_row(vals: List[List[Any]]) -> List[str]:
    """Tar första raden som header och standardiserar kolumnnamn."""
    if not vals:
        return []
    headers = vals[0]
    fixed = []
    for h in headers:
        hs = str(h).strip()
        fixed.append(hs if hs else "")
    return fixed


# =========================
# Google-klient & Spreadsheet med backoff
# =========================
def _get_gspread_client() -> Optional[gspread.Client]:
    """
    Bygger en gspread-klient från st.secrets["GOOGLE_CREDENTIALS"].
    Stöder både JSON-sträng och dict. Returnerar None vid fel.
    """
    try:
        creds_blob = st.secrets.get("GOOGLE_CREDENTIALS")
        if isinstance(creds_blob, str):
            creds_info = json.loads(creds_blob)
        elif isinstance(creds_blob, dict):
            creds_info = creds_blob
        else:
            st.warning("GOOGLE_CREDENTIALS saknas eller har fel format i st.secrets.")
            return None
        return gspread.service_account_from_dict(creds_info)
    except Exception as e:
        st.warning(f"Kunde inte skapa Google-klient: {e}")
        return None


def _open_spreadsheet(max_retries: int = 5, backoff_s: float = 0.8, raise_on_fail: bool = False) -> Optional[gspread.Spreadsheet]:
    """
    Öppnar kalkylarket med exponential backoff. Returnerar None vid fel (default).
    Sätt raise_on_fail=True om du vill bubbla upp felet.
    """
    url = st.secrets.get("SHEET_URL")
    if not url:
        st.warning("SHEET_URL saknas i st.secrets.")
        return None

    client = _get_gspread_client()
    if client is None:
        return None

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            ss = client.open_by_url(url)
            return ss
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_s * (2 ** (attempt - 1)))
            else:
                msg = f"Kunde inte öppna kalkylarket efter {max_retries} försök: {last_err}"
                if raise_on_fail:
                    raise RuntimeError(msg)
                else:
                    st.warning(msg)
                    return None
    return None


def _get_ws(ss: gspread.Spreadsheet, title: str, create_if_missing: bool = False) -> Optional[gspread.Worksheet]:
    """Hämtar ett blad med namn 'title'. Skapar vid behov om flaggat."""
    try:
        return ss.worksheet(title)
    except Exception:
        if not create_if_missing:
            return None
        try:
            return ss.add_worksheet(title=title, rows=2000, cols=40)
        except Exception as e:
            st.warning(f"Kunde inte skapa blad '{title}': {e}")
            return None


# =========================
# Offentliga funktioner (används av appen)
# =========================
def list_profiles() -> List[str]:
    """
    Hämtar profiler från bladet 'Profil' (kolumn A). Returnerar tom lista vid fel.
    Hoppar över tomma rader och vanliga rubrikord.
    """
    ss = _open_spreadsheet()
    if ss is None:
        return []

    try:
        ws = _get_ws(ss, "Profil")
        if ws is None:
            return []
        values = ws.col_values(1)  # kolumn A
    except Exception:
        return []

    profs = []
    for v in values:
        name = str(v).strip()
        if not name:
            continue
        low = name.lower()
        if low in ("profil", "profiles", "namn", "name"):
            continue
        profs.append(name)

    # unika i ordning
    seen = set()
    uniq = []
    for p in profs:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def read_profile_settings(profile: str) -> Dict[str, Any]:
    """
    Läser profilens inställningar från ett blad med titel = profile.
    Förväntar K/V-layout: kolumn A = nyckel, kolumn B = värde.
    Returnerar dict med typade värden (datum/tid/int/float) när möjligt.
    Vid fel returneras {}.
    """
    ss = _open_spreadsheet()
    if ss is None:
        return {}

    ws = _get_ws(ss, profile)
    if ws is None:
        # Saknar inställningsblad -> inget att uppdatera
        return {}

    try:
        vals = ws.get_all_values()  # lista av rader
    except Exception:
        return {}

    out: Dict[str, Any] = {}
    # För enkelhet: läs första två kolumner som nyckel/värde
    for row in vals:
        if not row:
            continue
        key = str(row[0]).strip() if len(row) >= 1 else ""
        val = row[1] if len(row) >= 2 else ""
        if not key:
            continue

        k = key  # behåll original-nyckeln som i appen
        # Datatyper enligt kända fält i appens CFG
        if k in ("startdatum", "Startdatum"):
            d = _parse_date(val)
            if d:
                out["startdatum"] = d
        elif k in ("starttid", "Starttid"):
            t = _parse_time(val)
            if t:
                out["starttid"] = t
        elif k in ("fodelsedatum", "Födelsedatum"):
            d = _parse_date(val)
            if d:
                out["fodelsedatum"] = d
        elif k in ("avgift_usd", "Avgift (USD)", "Avgift per prenumerant (USD)"):
            f = _as_float(val)
            if f is not None:
                out["avgift_usd"] = f
        elif k in ("PROD_STAFF", "Totalt antal personal"):
            i = _as_int(val)
            if i is not None:
                out["PROD_STAFF"] = i
        elif k in ("BONUS_AVAILABLE", "Bonus killar kvar"):
            i = _as_int(val)
            if i is not None:
                out["BONUS_AVAILABLE"] = i
        elif k in ("BONUS_PCT", "Bonus %"):
            f = _as_float(val)
            if f is not None:
                out["BONUS_PCT"] = f
        elif k in ("SUPER_BONUS_PCT", "Super-bonus %"):
            f = _as_float(val)
            if f is not None:
                out["SUPER_BONUS_PCT"] = f
        elif k in ("BMI_GOAL", "BM mål"):
            f = _as_float(val)
            if f is not None:
                out["BMI_GOAL"] = f
        elif k in ("HEIGHT_CM", "Längd (cm)"):
            i = _as_int(val)
            if i is not None:
                out["HEIGHT_CM"] = i
        elif k in ("ESK_MIN", "Eskilstuna min"):
            i = _as_int(val)
            if i is not None:
                out["ESK_MIN"] = i
        elif k in ("ESK_MAX", "Eskilstuna max"):
            i = _as_int(val)
            if i is not None:
                out["ESK_MAX"] = i
        elif k in ("MAX_PAPPAN", "MAX Pappans vänner"):
            i = _as_int(val)
            if i is not None:
                out["MAX_PAPPAN"] = i
        elif k in ("MAX_GRANNAR", "MAX Grannar"):
            i = _as_int(val)
            if i is not None:
                out["MAX_GRANNAR"] = i
        elif k in ("MAX_NILS_VANNER", "MAX Nils vänner"):
            i = _as_int(val)
            if i is not None:
                out["MAX_NILS_VANNER"] = i
        elif k in ("MAX_NILS_FAMILJ", "MAX Nils familj"):
            i = _as_int(val)
            if i is not None:
                out["MAX_NILS_FAMILJ"] = i
        elif k in ("MAX_BEKANTA", "MAX Bekanta"):
            i = _as_int(val)
            if i is not None:
                out["MAX_BEKANTA"] = i
        elif k in ("LBL_PAPPAN", "Etikett Pappans vänner"):
            if str(val).strip():
                out["LBL_PAPPAN"] = str(val).strip()
        elif k in ("LBL_GRANNAR", "Etikett Grannar"):
            if str(val).strip():
                out["LBL_GRANNAR"] = str(val).strip()
        elif k in ("LBL_NILS_VANNER", "Etikett Nils vänner"):
            if str(val).strip():
                out["LBL_NILS_VANNER"] = str(val).strip()
        elif k in ("LBL_NILS_FAMILJ", "Etikett Nils familj"):
            if str(val).strip():
                out["LBL_NILS_FAMILJ"] = str(val).strip()
        elif k in ("LBL_BEKANTA", "Etikett Bekanta"):
            if str(val).strip():
                out["LBL_BEKANTA"] = str(val).strip()
        elif k in ("LBL_ESK", "Etikett Eskilstuna killar"):
            if str(val).strip():
                out["LBL_ESK"] = str(val).strip()
        elif k in ("Sömn (h)", "Sömn timmar", "Sömn"):
            f = _as_float(val)
            if f is not None:
                out["SÖMN (h)"] = f  # appen läser denna till CFG[EXTRA_SLEEP_KEY] via update

        # Annars: okänt fält – hoppa över tyst
    return out


def read_profile_data(profile: str) -> pd.DataFrame:
    """
    Läser hela Data-bladet som DataFrame. Om kolumnen 'Profil' finns filtreras på angivet profile.
    Returnerar tom DataFrame vid fel.
    """
    ss = _open_spreadsheet()
    if ss is None:
        return pd.DataFrame()

    ws = _get_ws(ss, "Data")
    if ws is None:
        return pd.DataFrame()

    try:
        vals = ws.get_all_values()
    except Exception:
        return pd.DataFrame()

    if not vals:
        return pd.DataFrame()

    headers = _clean_header_row(vals)
    rows = vals[1:] if len(vals) > 1 else []
    if not headers:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=headers)

    # Om 'Profil' finns -> filtrera
    if "Profil" in df.columns:
        df = df[df["Profil"].astype(str).str.strip() == str(profile).strip()]

    # Försök kasta kända numeriska kolumner till numeric
    numeric_cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","Vila","DT tid (sek/kille)","DT vila (sek/kille)",
        "Älskar","Sover med",
        "Bonus deltagit","Personal deltagit","Händer aktiv","Nils",
        "Summa tid (sek)","Hångel (sek/kille)","Suger per kille (sek)","Händer per kille (sek)",
        "Tid Älskar (sek)",
        "Totalt Män","Prenumeranter","Intäkter","Kostnad män","Intäkt Känner",
        "Intäkt företag","Lön Malin","Vinst",
        "BM mål","Mål vikt (kg)","Super bonus ack"
    ]
    # Lägg även till etiketter som kan vara omdöpta
    extra_sources = ["Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta","Eskilstuna killar"]
    for col in numeric_cols + extra_sources:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

    # Datum/tid
    if "Datum" in df.columns:
        # Behåll som str – appen konverterar själv där det behövs
        pass

    return df.reset_index(drop=True)


def save_profile_settings(profile: str, cfg: Dict[str, Any]) -> None:
    """
    Sparar (skriver över) profilens inställningar till bladet med titel = profile.
    Lagrar som två kolumner: Nyckel | Värde
    """
    ss = _open_spreadsheet()
    if ss is None:
        st.warning("Kan inte spara – inget kalkylark.")
        return

    ws = _get_ws(ss, profile, create_if_missing=True)
    if ws is None:
        st.warning(f"Kan inte spara – kunde inte öppna/skapa blad '{profile}'.")
        return

    # Nycklar vi bryr oss om att spara (samma som appen använder)
    keys_order = [
        "startdatum","starttid","fodelsedatum",
        "avgift_usd","PROD_STAFF",
        "BONUS_AVAILABLE","BONUS_PCT",
        "SUPER_BONUS_PCT",
        "BMI_GOAL","HEIGHT_CM",
        "ESK_MIN","ESK_MAX",
        "MAX_PAPPAN","MAX_GRANNAR","MAX_NILS_VANNER","MAX_NILS_FAMILJ","MAX_BEKANTA",
        "LBL_PAPPAN","LBL_GRANNAR","LBL_NILS_VANNER","LBL_NILS_FAMILJ","LBL_BEKANTA","LBL_ESK",
        "SÖMN (h)"
    ]

    rows = [["Nyckel","Värde"]]
    for k in keys_order:
        if k not in cfg:
            continue
        v = cfg[k]
        if isinstance(v, date) and not isinstance(v, datetime):
            sval = v.isoformat()
        elif isinstance(v, dtime):
            sval = v.strftime("%H:%M")
        else:
            sval = str(v)
        rows.append([k, sval])

    try:
        ws.clear()
        ws.update(rows)
    except Exception as e:
        st.warning(f"Kunde inte spara inställningar: {e}")


def append_row_to_profile_data(profile: str, row_dict: Dict[str, Any]) -> None:
    """
    Appendar en rad till Data-bladet. Skapar bladet om det saknas.
    Säkrar att header finns (union av befintlig header och nya fältnamn).
    """
    ss = _open_spreadsheet()
    if ss is None:
        st.warning("Kan inte spara data – inget kalkylark.")
        return

    ws = _get_ws(ss, "Data", create_if_missing=True)
    if ws is None:
        st.warning("Kan inte spara data – kunde inte öppna/skapa blad 'Data'.")
        return

    try:
        vals = ws.get_all_values()
    except Exception as e:
        st.warning(f"Kunde inte läsa 'Data' för uppdatering: {e}")
        return

    # Befintlig header
    if vals:
        headers = _clean_header_row(vals)
        data_rows = vals[1:]
    else:
        headers = []
        data_rows = []

    # Union av headers + nya fält
    new_keys = list(row_dict.keys())
    for k in new_keys:
        if k not in headers:
            headers.append(k)

    # Bygg rad i header-ordning
    def _fmt_cell(v: Any) -> str:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, dtime):
            return v.strftime("%H:%M")
        if v is None:
            return ""
        return str(v)

    new_row = [_fmt_cell(row_dict.get(h, "")) for h in headers]

    # Skriv tillbaka
    try:
        if not vals:
            # Första gången: skriv header + första rad
            ws.update([headers, new_row])
        else:
            # Om headern växer med nya kolumner -> uppdatera header först
            if len(headers) != len(vals[0]):
                # utöka alla befintliga rader till nya header-längden
                widened = [headers]
                for r in data_rows:
                    widened.append(r + [""] * (len(headers) - len(r)))
                widened.append(new_row)
                ws.clear()
                ws.update(widened)
            else:
                # vanlig append
                ws.append_row(new_row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.warning(f"Kunde inte appenda rad till 'Data': {e}")
