import streamlit as st

st.title("🔍 Debug: Kontrollera st.secrets")

# Visa alla nycklar
st.subheader("Tillgängliga nycklar i st.secrets:")
st.write(list(st.secrets.keys()))

# Visa GOOGLE_CREDENTIALS
if "GOOGLE_CREDENTIALS" in st.secrets:
    st.subheader("GOOGLE_CREDENTIALS:")
    st.json(st.secrets["GOOGLE_CREDENTIALS"])
else:
    st.error("❌ Nyckeln GOOGLE_CREDENTIALS saknas!")

# Visa SHEET_URL
if "SHEET_URL" in st.secrets:
    st.subheader("SHEET_URL:")
    st.success(st.secrets["SHEET_URL"])
else:
    st.error("❌ Nyckeln SHEET_URL saknas!")
