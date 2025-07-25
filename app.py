import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from konstanter import COLUMNS, säkerställ_kolumner
from berakningar import process_lägg_till_rader  # dummyfunktion just nu

gc = gspread.service_account_from_dict(st.secrets["GOOGLE_CREDENTIALS"])
SHEET_URL = st.secrets["GOOGLE_CREDENTIALS"]["SHEET_URL"]
sh = gc.open_by_url(SHEET_URL)
inst_sheet = sh.worksheet("Inställningar")
data_sheet = sh.worksheet("Data")


def hämta_inställningar():
    try:
        df = pd.DataFrame(inst_sheet.get_all_records())
        return df.set_index("Fält")["Värde"].to_dict()
    except Exception as e:
        st.error(f"Kunde inte läsa inställningar: {e}")
        return {}


def spara_inställningar(nydata):
    df = pd.DataFrame(list(nydata.items()), columns=["Fält", "Värde"])
    inst_sheet.clear()
    inst_sheet.update([df.columns.values.tolist()] + df.values.tolist())


def rensa_databasen():
    data_sheet.clear()
    data_sheet.update([COLUMNS])  # lägg till kolumnrubriker


def hämta_datan():
    try:
        data = data_sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df = säkerställ_kolumner(df)
        return df
    except Exception as e:
        st.error(f"Fel vid hämtning av data: {e}")
        return pd.DataFrame(columns=COLUMNS)


def bestäm_datum(df, inställningar):
    if df.empty:
        startdatum = inställningar.get("Startdatum", datetime.today().strftime("%Y-%m-%d"))
        return datetime.strptime(startdatum, "%Y-%m-%d").date()
    else:
        senaste_datum = pd.to_datetime(df["Datum"]).max()
        return (senaste_datum + timedelta(days=1)).date()


def scenformulär(df, inställningar):
    st.header("Lägg till scen")
    datum = bestäm_datum(df, inställningar)
    st.info(f"Dagens datum för nästa rad: **{datum}**")

    with st.form("scenformulär", clear_on_submit=False):
        typ = st.selectbox("Typ", ["Scen", "Vila inspelningsplats", "Vilovecka hemma"])
        antal_vilodagar = st.number_input("Antal vilodagar", min_value=0, step=1)
        nya_män = st.number_input("Nya män", min_value=0, step=1)
        enkel_vaginal = st.number_input("Enkel vaginal", min_value=0, step=1)
        enkel_anal = st.number_input("Enkel anal", min_value=0, step=1)
        dp = st.number_input("DP", min_value=0, step=1)
        dpp = st.number_input("DPP", min_value=0, step=1)
        dap = st.number_input("DAP", min_value=0, step=1)
        tpp = st.number_input("TPP", min_value=0, step=1)
        tpa = st.number_input("TPA", min_value=0, step=1)
        tap = st.number_input("TAP", min_value=0, step=1)
        tid_enkel = st.number_input("Tid enkel (sek)", min_value=0, step=1)
        tid_dubbel = st.number_input("Tid dubbel (sek)", min_value=0, step=1)
        tid_trippel = st.number_input("Tid trippel (sek)", min_value=0, step=1)
        vila = st.number_input("Vila (sek mellan varv)", min_value=0, step=1)

        # Begränsade fält enligt inställningar
        kompisar = st.number_input(
            f"Kompisar (max {inställningar.get('Kompisar', 0)})",
            min_value=0, max_value=int(inställningar.get("Kompisar", 0)), step=1
        )
        pappans_vänner = st.number_input(
            f"Pappans vänner (max {inställningar.get('Pappans vänner', 0)})",
            min_value=0, max_value=int(inställningar.get("Pappans vänner", 0)), step=1
        )
        nils_vänner = st.number_input(
            f"Nils vänner (max {inställningar.get('Nils vänner', 0)})",
            min_value=0, max_value=int(inställningar.get("Nils vänner", 0)), step=1
        )
        nils_familj = st.number_input(
            f"Nils familj (max {inställningar.get('Nils familj', 0)})",
            min_value=0, max_value=int(inställningar.get("Nils familj", 0)), step=1
        )

        dt_tid_per_man = st.number_input("DT tid per man", min_value=0, step=1)
        antal_varv = st.number_input("Antal varv", min_value=0, step=1)
        älskar_med = st.number_input("Älskar med", min_value=0, step=1)
        sover_med = st.number_input("Sover med", min_value=0, step=1)
        nils_sex = st.number_input("Nils sex", min_value=0, step=1)
        prenumeranter = st.number_input("Prenumeranter", min_value=0, step=1)
        kvinnans_lön = st.number_input("Kvinnans lön ($)", min_value=0.0, step=1.0)
        mäns_lön = st.number_input("Mäns lön ($)", min_value=0.0, step=1.0)
        kompisars_lön = st.number_input("Kompisars lön ($)", min_value=0.0, step=1.0)

        minuter_per_kille = st.number_input("Minuter per kille", min_value=0.0, step=1.0)

        confirm = st.checkbox("Bekräfta att du vill lägga till raden")
        submitted = st.form_submit_button("Lägg till rad")

    if submitted:
        if not confirm:
            st.warning("Du måste bekräfta innan raden kan läggas till.")
            return df

        rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Typ": typ,
            "Antal vilodagar": antal_vilodagar,
            "Nya män": nya_män,
            "Enkel vaginal": enkel_vaginal,
            "Enkel anal": enkel_anal,
            "DP": dp,
            "DPP": dpp,
            "DAP": dap,
            "TPP": tpp,
            "TPA": tpa,
            "TAP": tap,
            "Tid enkel": tid_enkel,
            "Tid dubbel": tid_dubbel,
            "Tid trippel": tid_trippel,
            "Vila": vila,
            "Kompisar": kompisar,
            "Pappans vänner": pappans_vänner,
            "Nils vänner": nils_vänner,
            "Nils familj": nils_familj,
            "DT tid per man": dt_tid_per_man,
            "Antal varv": antal_varv,
            "Älskar med": älskar_med,
            "Sover med": sover_med,
            "Nils sex": nils_sex,
            "Prenumeranter": prenumeranter,
            "Intäkt ($)": 0.0,  # ej beräknat ännu
            "Kvinnans lön ($)": kvinnans_lön,
            "Mäns lön ($)": mäns_lön,
            "Kompisars lön ($)": kompisars_lön,
            "DT total tid (sek)": 0,
            "Total tid (sek)": 0,
            "Total tid (h)": 0.0,
            "Minuter per kille": minuter_per_kille,
        }

        rad = process_lägg_till_rader(rad)  # dummyfunktion
        df = pd.concat([df, pd.DataFrame([rad])], ignore_index=True)
        säkerställ_kolumner(df)
        data_sheet.update([df.columns.tolist()] + df.fillna("").astype(str).values.tolist())
        st.success("Rad tillagd!")

    return df


def inställningsformulär():
    st.header("Inställningar")
    inst = hämta_inställningar()
    with st.form("instform"):
        namn = st.text_input("Namn", value=inst.get("Namn", ""))
        födelsedatum = st.date_input("Födelsedatum", value=pd.to_datetime(inst.get("Födelsedatum", "2000-01-01")), min_value=datetime(1970, 1, 1))
        startdatum = st.date_input("Startdatum", value=pd.to_datetime(inst.get("Startdatum", datetime.today())), min_value=datetime(1990, 1, 1))
        kompisar = st.number_input("Kompisar", min_value=0, step=1, value=int(inst.get("Kompisar", 0)))
        pappans_vänner = st.number_input("Pappans vänner", min_value=0, step=1, value=int(inst.get("Pappans vänner", 0)))
        nils_vänner = st.number_input("Nils vänner", min_value=0, step=1, value=int(inst.get("Nils vänner", 0)))
        nils_familj = st.number_input("Nils familj", min_value=0, step=1, value=int(inst.get("Nils familj", 0)))
        sparaknapp = st.form_submit_button("Spara inställningar")

    if sparaknapp:
        nydata = {
            "Namn": namn,
            "Födelsedatum": födelsedatum.strftime("%Y-%m-%d"),
            "Startdatum": startdatum.strftime("%Y-%m-%d"),
            "Kompisar": kompisar,
            "Pappans vänner": pappans_vänner,
            "Nils vänner": nils_vänner,
            "Nils familj": nils_familj,
        }
        spara_inställningar(nydata)
        st.success("Inställningar sparade!")


def main():
    st.title("Malin-produktionsapp")

    meny = st.sidebar.selectbox("Välj vy", ["Lägg till scen", "Inställningar", "Rensa databasen"])
    inställningar = hämta_inställningar()
    df = hämta_datan()

    if meny == "Lägg till scen":
        df = scenformulär(df, inställningar)

    elif meny == "Inställningar":
        inställningsformulär()

    elif meny == "Rensa databasen":
        if st.button("Rensa hela databasen (inkl. rubriker)"):
            rensa_databasen()
            st.success("Databasen är nu tom (förutom rubriker).")


if __name__ == "__main__":
    main()
