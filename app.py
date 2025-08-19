import streamlit as st
from datetime import datetime
import json

# OBS: Dessa import kräver att du lagt till gspread + google-auth i requirements.txt:
# gspread==5.9.0
# google-auth==2.29.0
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Sheets-diagnostik", layout="centered")
st.title("🧪 Google Sheets – Diagnostik")

# -----------------------------------------------------
# 1) Visa vilka secrets som finns
# -----------------------------------------------------
st.subheader("Steg 1: Finns secrets i appen?")
has_creds = "GOOGLE_CREDENTIALS" in st.secrets
has_id    = "GOOGLE_SHEET_ID" in st.secrets
has_url   = "SHEET_URL" in st.secrets
tab_name  = st.secrets.get("GOOGLE_SHEET_TAB", "Data")

c1, c2, c3 = st.columns(3)
with c1: st.metric("GOOGLE_CREDENTIALS", "✔️" if has_creds else "❌")
with c2: st.metric("GOOGLE_SHEET_ID", "✔️" if has_id else "❌")
with c3: st.metric("SHEET_URL", "✔️" if has_url else "❌")

st.write("Flik (tab) som används:", f"**{tab_name}**")

if not has_creds:
    st.error("Saknar `GOOGLE_CREDENTIALS` i Secrets. Lägg in service account-nyckeln (TOML-tabell eller JSON-sträng).")
    st.stop()

if not (has_id or has_url):
    st.warning("Varken `GOOGLE_SHEET_ID` eller `SHEET_URL` finns i Secrets. Minst en av dem krävs.")
    # vi fortsätter inte, för nästa steg behöver ett ID eller URL
    st.stop()

# -----------------------------------------------------
# 2) Bygg klient (auth) – robust mot TOML-tabell eller JSON-sträng
# -----------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_client():
    raw = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(raw, dict):
        cred_info = dict(raw)
    else:
        # kan vara JSON-sträng i secrets
        try:
            cred_info = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"GOOGLE_CREDENTIALS kunde inte tolkas som JSON: {e}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(cred_info, scopes=scopes)
    return gspread.authorize(creds)

# -----------------------------------------------------
# 3) Öppna spreadsheet via ID eller URL
# -----------------------------------------------------
@st.cache_resource(show_spinner=False)
def resolve_spreadsheet(_client):
    if has_id:
        sid = st.secrets["GOOGLE_SHEET_ID"].strip()
        if sid:
            return _client.open_by_key(sid)
    if has_url:
        url = st.secrets["SHEET_URL"].strip()
        if url:
            return _client.open_by_url(url)
    raise RuntimeError("Varken GOOGLE_SHEET_ID eller SHEET_URL gav något värde.")

# -----------------------------------------------------
# 4) Hämta worksheet
# -----------------------------------------------------
def get_worksheet(spreadsheet, title: str):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        # föreslå att skapa?
        return None

# -----------------------------------------------------
# UI – kör tester
# -----------------------------------------------------
st.subheader("Steg 2: Testa anslutning")

auth_ok = False
ss_ok = False
ws_ok = False

try:
    client = get_client()
    auth_ok = True
    st.success("✅ Autentisering OK (service account).")
except Exception as e:
    st.exception(RuntimeError(f"Autentisering misslyckades: {e}"))
    st.stop()

try:
    ss = resolve_spreadsheet(client)
    ss_ok = True
    st.success(f"✅ Spreadsheet öppnat: **{ss.title}**")
except Exception as e:
    st.exception(RuntimeError(f"Kunde inte öppna spreadsheet: {e}"))
    st.stop()

# Lista flikar
try:
    sheets = [ws.title for ws in ss.worksheets()]
    st.write("Tillgängliga flikar:", ", ".join(sheets) if sheets else "(inga)")
except Exception as e:
    st.warning(f"Kunde inte lista flikar: {e}")

# Förvald flik
ws = get_worksheet(ss, tab_name)
if ws is None:
    st.error(f"Fliken **{tab_name}** finns inte. Skapa fliken i Google Sheets (eller ange rätt namn i `GOOGLE_SHEET_TAB`).")
else:
    ws_ok = True
    st.success(f"✅ Hittade fliken: **{tab_name}**")

# -----------------------------------------------------
# 5) Läs topp 5 rader
# -----------------------------------------------------
if ws_ok:
    st.subheader("Steg 3: Läs topp 5 rader")
    try:
        vals = ws.get_all_values()
        if not vals:
            st.info("Arket är tomt (inga celler).")
        else:
            # visa max 6 rader (inkl. header)
            show = vals[:6]
            st.dataframe(show)
    except Exception as e:
        st.warning(f"Kunde inte läsa rader: {e}")

# -----------------------------------------------------
# 6) Skriv en testrad
# -----------------------------------------------------
st.subheader("Steg 4: Skriv en testrad")
st.caption("Skriver en enkel testrad längst ned i fliken. Ta bort den manuellt vid behov.")

colA, colB = st.columns(2)
with colA:
    do_write = st.button("✍️ Skriv testrad")
with colB:
    do_create_tab = st.button(f"➕ Skapa fliken '{tab_name}' (om saknas)")

if do_create_tab and ss_ok:
    try:
        ws2 = get_worksheet(ss, tab_name)
        if ws2 is None:
            ws2 = ss.add_worksheet(title=tab_name, rows=2000, cols=80)
            ws2.update("A1:C1", [["Skapad", "Användare", "Meddelande"]])
            st.success(f"✅ Fliken '{tab_name}' skapad med en enkel header.")
        else:
            st.info(f"Fliken '{tab_name}' finns redan.")
    except Exception as e:
        st.exception(RuntimeError(f"Kunde inte skapa flik: {e}"))

if do_write:
    if not ws_ok:
        st.error("Kan inte skriva – fliken saknas.")
    else:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [now, st.secrets.get("APP_USER", "streamlit-user"), "Testrad från diagnostik-appen"]
            ws.append_row(row)
            st.success("✅ Testrad skriven! Kolla i Google Sheets.")
        except Exception as e:
            st.exception(RuntimeError(f"Misslyckades att skriva testrad: {e}"))

st.markdown("---")
st.caption("Klart. När alla steg är gröna fungerar secrets och Sheets-åtkomst. Flytta sedan över samma auth/resolve-kod till din riktiga app.")
