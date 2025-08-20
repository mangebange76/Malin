import streamlit as st
import json

PROFIL_KEY = "VALD_PROFIL"
PROFILER_KEY = "ALLA_PROFILER"

def ladda_profiler():
    profiler_raw = st.secrets.get("PROFILER_JSON", "{}")
    try:
        profiler = json.loads(profiler_raw)
        st.session_state[PROFILER_KEY] = profiler
    except Exception:
        st.session_state[PROFILER_KEY] = {}

def visa_profilval():
    profiler = st.session_state.get(PROFILER_KEY, {})
    if not profiler:
        st.warning("Inga profiler tillgängliga.")
        return None

    profillista = list(profiler.keys())
    if profillista:
        vald = st.selectbox("🧍 Välj profil", profillista, key="profil_selector")
        st.session_state[PROFIL_KEY] = vald
        st.session_state[CFG_KEY].update(profiler[vald])
        st.success(f"Profil '{vald}' laddad!")
        return vald
    return None
