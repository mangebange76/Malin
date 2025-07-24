from datetime import datetime, timedelta
import random

def beräkna_tid_per_kille(f):
    scen_tid = f.get("Scenens längd (h)", 0) * 3600
    dt_tid_per_man = f.get("DT tid per man (sek)", 0)

    dt_antal_män = (
        f.get("Övriga män", 0)
        + f.get("Kompisar", 0)
        + f.get("Pappans vänner", 0)
        + f.get("Nils vänner", 0)
        + f.get("Nils familj", 0)
    )

    multipla_akter = {
        "DP": 2, "DPP": 2, "DAP": 2,
        "TPP": 3, "TPA": 3, "TAP": 3
    }

    scen_tid_extra = 0
    multipla_män = 0
    for nyckel, multipel in multipla_akter.items():
        antal = f.get(nyckel, 0)
        scen_tid_extra += antal * 120 * multipel
        multipla_män += antal * multipel

    total_tid = scen_tid + dt_tid_per_man * dt_antal_män + scen_tid_extra
    totala_män = dt_antal_män + multipla_män

    tid_per_kille_min = total_tid / 60 / totala_män if totala_män else 0
    total_tid_h = total_tid / 3600

    return tid_per_kille_min, total_tid_h

def process_lägg_till_rader(df, inst, f):
    rows = []
    datum = datetime.today()

    def lägg_till_beräkningar(rad):
        tid_per_kille_min, total_tid_h = beräkna_tid_per_kille(rad)
        rad["Total tid (h)"] = round(total_tid_h, 2)
        rad["Total tid (sek)"] = round(total_tid_h * 3600, 2)
        rad["Minuter per kille"] = round(tid_per_kille_min, 2)
        rad["DT total tid (sek)"] = rad.get("DT tid per man (sek)", 0) * (
            rad.get("Övriga män", 0)
            + rad.get("Kompisar", 0)
            + rad.get("Pappans vänner", 0)
            + rad.get("Nils vänner", 0)
            + rad.get("Nils familj", 0)
        )

    if f["Typ"] == "Vilovecka hemma":
        for i in range(7):
            ny = f.copy()
            ny["Datum"] = (datum + timedelta(days=i)).strftime("%Y-%m-%d")
            ny["Typ"] = "Vilovecka hemma"
            ny["Kvinnans lön ($)"] = 0

            if i == 6:
                ny["Sover med"] = 1
                ny["Nils sex"] = 0
            else:
                slump = random.random()
                if slump < 0.10:
                    ny["Nils sex"] = 2
                elif slump < 0.60:
                    ny["Nils sex"] = 1
                else:
                    ny["Nils sex"] = 0
                ny["Sover med"] = 0

            lägg_till_beräkningar(ny)
            rows.append(ny)

    elif f["Typ"] == "Vila inspelningsplats":
        for _ in range(2):
            ny = f.copy()
            ny["Datum"] = datum.strftime("%Y-%m-%d")
            ny["Kvinnans lön ($)"] = 0
            lägg_till_beräkningar(ny)
            rows.append(ny)

    else:
        f["Datum"] = datum.strftime("%Y-%m-%d")
        lägg_till_beräkningar(f)
        rows.append(f)

    return df._append(rows, ignore_index=True)
