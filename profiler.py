import pandas as pd
import streamlit as st
from sheets_utils import skapa_koppling


def hamta_profiler():
    """Returnerar listan med tillgängliga profiler från fliken 'Profil'."""
    try:
        sheet = skapa_koppling()
        profiler = sheet.worksheet("Profil").col_values(1)
        return [p.strip() for p in profiler if p.strip()]
    except Exception as e:
        st.error(f"Kunde inte läsa profiler: {e}")
        return []


def hamta_profil_data(namn):
    """Hämtar inställningar för vald profil från dess blad."""
    try:
        df = skapa_koppling().worksheet(namn).get_all_records()
        return pd.DataFrame(df)
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar för profilen '{namn}': {e}")
        return pd.DataFrame()


def skapa_cfg_dict(profil_df):
    """Konverterar inställningsrader från profilens blad till CFG-dict."""
    cfg = {}
    for _, row in profil_df.iterrows():
        nyckel = str(row.get("Nyckel", "")).strip()
        värde = str(row.get("Värde", "")).strip()
        if not nyckel:
            continue
        # Försök konvertera till rätt typ
        if värde.isdigit():
            cfg[nyckel] = int(värde)
        else:
            try:
                cfg[nyckel] = float(värde)
            except:
                cfg[nyckel] = värde
    return cfg


def hamta_scen_data(namn):
    """Hämtar sparade scenrader för vald profil från fliken 'Data'."""
    try:
        df = skapa_koppling().worksheet("Data").get_all_records()
        df = pd.DataFrame(df)
        return df[df["Profil"] == namn].copy() if "Profil" in df.columns else df
    except Exception as e:
        st.error(f"Kunde inte läsa scen-data för profilen '{namn}': {e}")
        return pd.DataFrame()
