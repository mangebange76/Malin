import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# -------------------------
# Grundinställningar
# -------------------------
st.set_page_config(page_title="Malin-produktionsapp", layout="wide")

# Viktiga nycklar i session_state
DATA_KEY = "data"
ROW_COUNT_KEY = "row_count"
INST_KEY = "inställningar"

# -------------------------
# Initiera session_state
# -------------------------
if DATA_KEY not in st.session_state:
    st.session_state[DATA_KEY] = pd.DataFrame()

if ROW_COUNT_KEY not in st.session_state:
    st.session_state[ROW_COUNT_KEY] = 0

if INST_KEY not in st.session_state:
    st.session_state[INST_KEY] = {
        "Startdatum": datetime.today().date(),
        "Kvinnans namn": "Malin",
        "Födelsedatum": "1995-01-01",
        "Totalt personal": 10,
        "Totalt bonus killar": 500
    }

# -------------------------
# Sidopanel - Inställningar
# -------------------------
with st.sidebar:
    st.header("Inställningar")

    st.session_state[INST_KEY]["Kvinnans namn"] = st.text_input(
        "Kvinnans namn",
        st.session_state[INST_KEY]["Kvinnans namn"]
    )

    st.session_state[INST_KEY]["Födelsedatum"] = st.date_input(
        "Kvinnans födelsedatum",
        pd.to_datetime(st.session_state[INST_KEY]["Födelsedatum"]).date()
    )

    st.session_state[INST_KEY]["Startdatum"] = st.date_input(
        "Startdatum",
        st.session_state[INST_KEY]["Startdatum"]
    )

    st.session_state[INST_KEY]["Totalt personal"] = st.number_input(
        "Totalt antal personal",
        min_value=0,
        value=st.session_state[INST_KEY]["Totalt personal"]
    )

    st.session_state[INST_KEY]["Totalt bonus killar"] = st.number_input(
        "Totalt antal bonus killar",
        min_value=0,
        value=st.session_state[INST_KEY]["Totalt bonus killar"]
    )

    st.markdown("---")
    st.subheader("Tillgängligt just nu")
    st.write(f"👨‍💼 Personal totalt: **{st.session_state[INST_KEY]['Totalt personal']}**")
    st.write(f"👨 Bonus killar totalt: **{st.session_state[INST_KEY]['Totalt bonus killar']}**")

# -------------------------
# Scenformulär
# -------------------------
st.header("Lägg till scen")

with st.form("scen_form"):
    col1, col2 = st.columns(2)

    with col1:
        scen_typ = st.selectbox("Typ av händelse", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        minuter_per_kille = st.number_input("Minuter per kille", min_value=0, value=30, step=5)
        bonus_deltagit = st.number_input(
            f"Bonus killar deltagit (Tillgängligt: {st.session_state[INST_KEY]['Totalt bonus killar']})",
            min_value=0, max_value=st.session_state[INST_KEY]["Totalt bonus killar"], value=0
        )

    with col2:
        personal_deltagit = st.number_input(
            f"Personal deltagit (Tillgängligt: {st.session_state[INST_KEY]['Totalt personal']})",
            min_value=0, max_value=st.session_state[INST_KEY]["Totalt personal"], value=0
        )
        kvinnans_lon = st.number_input("Kvinnans lön (USD)", min_value=0, value=0)
        vilodagar = st.number_input("Antal vilodagar (endast om Vila)", min_value=0, value=0)

    # Skicka in
    submitted = st.form_submit_button("Spara rad")

if submitted:
    ny_rad = {
        "Datum": bestäm_datum(),
        "Typ": scen_typ,
        "Bonus deltagit": bonus_deltagit,
        "Personal deltagit": personal_deltagit,
        "Minuter per kille": minuter_per_kille,
        "Kvinnans lön": kvinnans_lon,
        "Vilodagar": vilodagar,
    }

    # Lägg till raden i session_state
    st.session_state[DATA_KEY] = pd.concat([st.session_state[DATA_KEY], pd.DataFrame([ny_rad])], ignore_index=True)

    st.success("Ny rad tillagd ✅")

# -------------------------------
# Del 4 – Scenformulär & Input
# -------------------------------

def scenformulär():
    st.subheader("Lägg till scen")

    with st.form("scenform"):
        col1, col2, col3 = st.columns(3)

        with col1:
            scen_typ = st.selectbox("Typ av scen", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
            antal_män = st.number_input("Antal män i scenen", min_value=0, value=0)
            minuter_per_kille = st.number_input("Minuter per kille", min_value=0, value=0)

        with col2:
            bonus_totalt = st.session_state.get("bonus_totalt", 0)
            bonus_deltagit = st.number_input(f"Bonus deltagit (Tillgängliga: {bonus_totalt})", min_value=0, value=0)
            bonus_nya = st.number_input("Bonus tillkommer i denna scen", min_value=0, value=0)

        with col3:
            personal_deltagit = st.number_input("Personal deltagit", min_value=0, value=0)

        submitted = st.form_submit_button("Lägg till rad")

        if submitted:
            # Uppdatera bonuskillar
            st.session_state["bonus_totalt"] = max(0, bonus_totalt - bonus_deltagit + bonus_nya)

            ny_rad = {
                "Typ": scen_typ,
                "Antal män": antal_män,
                "Minuter per kille": minuter_per_kille,
                "Bonus deltagit": bonus_deltagit,
                "Bonus tillkommer": bonus_nya,
                "Bonus tillgängliga efter scen": st.session_state["bonus_totalt"],
                "Personal deltagit": personal_deltagit
            }

            st.session_state["data"].append(ny_rad)
            st.success("Scen tillagd!")

# -------------------------------
# Del 5 – Huvudprogram
# -------------------------------

def main():
    st.title("Malin – Produktionsapp")

    # Initiera session state
    if "data" not in st.session_state:
        st.session_state["data"] = []
    if "bonus_totalt" not in st.session_state:
        st.session_state["bonus_totalt"] = 0  # Startvärde kan anges i sidopanel

    # Sidopanel – inställningar
    st.sidebar.header("Inställningar")
    start_bonus = st.sidebar.number_input("Start antal bonuskillar", min_value=0, value=st.session_state["bonus_totalt"])
    st.session_state["bonus_totalt"] = start_bonus

    personal_total = st.sidebar.number_input("Totalt antal personal", min_value=0, value=0)

    # Formulär
    scenformulär()

    # Visa data
    if st.session_state["data"]:
        st.subheader("Inmatade rader")
        df = pd.DataFrame(st.session_state["data"])
        st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
