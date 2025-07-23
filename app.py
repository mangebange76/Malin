def main():
    init_sheet("Data", DATA_COLUMNS)
    init_inställningar()

    inst = läs_inställningar()
    df = ladda_data()

    st.title("🎬 Malin Filmproduktion")

    with st.sidebar:
        st.header("Inställningar")
        with st.form("spara_inställningar"):
            namn = st.text_input("Kvinnans namn", value=str(inst.get("Kvinnans namn", "")))
            född = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "1984-03-26")))
            startdatum = st.date_input("Startdatum (första scen)", value=pd.to_datetime(inst.get("Startdatum", "2014-03-26")))

            inst_inputs = {}
            for fält in ["Kompisar", "Pappans vänner", "Nils vänner", "Nils familj"]:
                inst_inputs[fält] = st.number_input(fält, value=float(inst.get(fält, 0)), min_value=0.0, step=1.0)

            spara = st.form_submit_button("Spara inställningar")

        if spara:
            spara_inställning("Kvinnans namn", namn)
            spara_inställning("Födelsedatum", född.strftime("%Y-%m-%d"))
            spara_inställning("Startdatum", startdatum.strftime("%Y-%m-%d"))
            for nyckel, värde in inst_inputs.items():
                spara_inställning(nyckel, värde)
            st.success("Inställningar sparade!")

    # Formulär och beräkning
    scenformulär(df, inst)

    # Tillfälligt utkommenterad:
    # df = beräkna_fält(df)

    # Visa tabell
    st.subheader("Alla scener och vilodagar")
    st.dataframe(df, use_container_width=True)
