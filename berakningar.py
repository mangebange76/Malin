# berakningar.py
import pandas as pd
import random
from datetime import datetime, timedelta
from konstanter import COLUMNS

def process_lägg_till_rader(df, inst, f):
    idag = datetime.today().strftime("%Y-%m-%d")
    typ = f["Typ"]

    if typ == "Scen":
        ny_rad = skapa_scenrad(f, idag)
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)

    elif typ == "Vila inspelningsplats":
        dagar = int(f.get("Antal vilodagar", 0))
        for _ in range(dagar):
            ny_rad = skapa_vilarad(idag)
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)

    elif typ == "Vilovecka hemma":
        startdatum = datetime.today()
        for i in range(7):
            dag = startdatum + timedelta(days=i)
            ny_rad = skapa_vilovecka_hemma(dag)
            df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)

    df = df.reindex(columns=COLUMNS, fill_value=0)
    return df

def skapa_scenrad(f, datum):
    total_tid = f["Scenens längd (h)"] * 3600
    dt_tid_total = f["DT tid per man (sek)"] * (
        f["Kompisar"] + f["Pappans vänner"] + f["Nils vänner"] + f["Nils familj"]
    )

    minuter_per_kille = 0
    antal_killar = (
        f["Enkel vaginal"] + f["Enkel anal"] +
        2 * (f["DP"] + f["DPP"] + f["DAP"]) +
        3 * (f["TPP"] + f["TPA"] + f["TAP"]) +
        f["Kompisar"] + f["Pappans vänner"] + f["Nils vänner"] + f["Nils familj"]
    )
    if antal_killar > 0:
        minuter_per_kille = (total_tid + dt_tid_total) / 60 / antal_killar

    return {
        "Datum": datum,
        **{k: f.get(k, 0) for k in COLUMNS if k not in ["Datum", "Minuter per kille", "Total tid (h)", "Total tid (sek)", "DT total tid (sek)"]},
        "DT total tid (sek)": dt_tid_total,
        "Total tid (sek)": total_tid + dt_tid_total,
        "Total tid (h)": (total_tid + dt_tid_total) / 3600,
        "Minuter per kille": round(minuter_per_kille, 2),
    }

def skapa_vilarad(datum):
    return {
        "Datum": datum,
        "Typ": "Vila inspelningsplats",
        "Antal vilodagar": 1,
        "Kvinnans lön ($)": 0,
        "Minuter per kille": 0,
        "Total tid (h)": 0,
        "Total tid (sek)": 0,
        "DT total tid (sek)": 0
    }

def skapa_vilovecka_hemma(datum):
    nils_sex = 0
    rand = random.random()
    if rand < 0.1:
        nils_sex = 2
    elif rand < 0.6:
        nils_sex = 1

    return {
        "Datum": datum.strftime("%Y-%m-%d"),
        "Typ": "Vilovecka hemma",
        "Antal vilodagar": 0,
        "Sover med": 1 if datum.weekday() == 6 else 0,
        "Nils sex": nils_sex,
        "Kvinnans lön ($)": 0,
        "Minuter per kille": 0,
        "Total tid (h)": 0,
        "Total tid (sek)": 0,
        "DT total tid (sek)": 0
    }

def beräkna_tid_per_kille(f):
    total_tid = f["Scenens längd (h)"] * 3600
    dt_tid_total = f["DT tid per man (sek)"] * (
        f["Kompisar"] + f["Pappans vänner"] + f["Nils vänner"] + f["Nils familj"]
    )

    antal_killar = (
        f["Enkel vaginal"] + f["Enkel anal"] +
        2 * (f["DP"] + f["DPP"] + f["DAP"]) +
        3 * (f["TPP"] + f["TPA"] + f["TAP"]) +
        f["Kompisar"] + f["Pappans vänner"] + f["Nils vänner"] + f["Nils familj"]
    )
    minuter_per_kille = ((total_tid + dt_tid_total) / 60 / antal_killar) if antal_killar > 0 else 0
    total_tid_h = (total_tid + dt_tid_total) / 3600
    return minuter_per_kille, total_tid_h
