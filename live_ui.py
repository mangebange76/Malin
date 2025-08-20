# live_ui.py
import streamlit as st
from statistik import compute_stats

def render_live_and_preview(cfg, rows_df):
    """Visar livevärden och preview (inkl statistik)."""
    st.header("🔴 Live & Preview")

    # Visa inställningar
    with st.expander("⚙️ Aktiva inställningar"):
        for k, v in cfg.items():
            st.write(f"**{k}**: {v}")

    # Statistik
    st.subheader("📊 Statistik")
    try:
        stats = compute_stats(rows_df, cfg)
        for k, v in stats.items():
            st.write(f"**{k}**: {v}")
    except Exception as e:
        st.error(f"Kunde inte beräkna statistik: {e}")

    # Förhandsgranskning
    st.subheader("🔍 Förhandsvisning (senaste 5 rader)")
    if not rows_df.empty:
        st.dataframe(rows_df.tail(5))
    else:
        st.info("Ingen data att visa.")
