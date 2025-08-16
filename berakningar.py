import pandas as pd

def beräkna_radvärden(rad, pris_prenumeration):
    """Beräknar värden för en enskild rad innan sparning."""
    män = int(rad.get("Män", 0))
    känner = int(rad.get("Känner", 0))
    prenumeranter = int(rad.get("Prenumeranter", 0))

    # Intäkter
    rad["Intäkt Känner"] = känner * pris_prenumeration
    rad["Intäkt Företag"] = män * 39.99
    rad["Vinst"] = rad["Intäkt Känner"] + rad["Intäkt Företag"] - rad.get("Kostnad män", 0)

    # Malins lön (min 150, max 800, 10% av nya prenumeranter)
    rad["Malins lön"] = max(150, min(800, prenumeranter * 0.10))

    return rad


def beräkna_statistik(df, max_pappans_vänner, max_grannar, max_nils_vänner, max_nils_familj):
    """Beräknar all statistik för Statistik-vyn."""
    statistik = {}

    # Antal scener (män > 0)
    scener = df[df["Män"] > 0]
    statistik["Antal scener"] = len(scener)

    # Privat GB (män == 0 men känner > 0)
    privat_gb = df[(df["Män"] == 0) & (df["Känner"] > 0)]
    statistik["Privat GB"] = len(privat_gb)

    # Totalt antal män
    statistik["Totalt antal män"] = df[df["Män"] > 0]["Män"].sum()

    # Snitt scener (män > 0 + känner på dessa rader)
    if len(scener) > 0:
        statistik["Snitt Scener"] = (scener["Män"] + scener["Känner"]).mean()
    else:
        statistik["Snitt Scener"] = 0

    # Snitt Privat GB (känner vid män==0 / antal Privat GB)
    if len(privat_gb) > 0:
        statistik["Snitt Privat GB"] = privat_gb["Känner"].sum() / len(privat_gb)
    else:
        statistik["Snitt Privat GB"] = 0

    # Prenumeranter
    statistik["Prenumeranter"] = df["Prenumeranter"].sum()

    # Intäkter och vinst
    statistik["Intäkt Känner"] = df["Intäkt Känner"].sum()
    statistik["Intäkt Företag"] = df["Intäkt Företag"].sum()
    statistik["Vinst"] = df["Vinst"].sum()
    statistik["Malins lön"] = df["Malins lön"].sum()

    # Snitt intäkt känner (alla intäkter / (maxvärden))
    total_intäkter = statistik["Intäkt Känner"] + statistik["Intäkt Företag"] + statistik["Vinst"]
    max_total = max_pappans_vänner + max_grannar + max_nils_vänner + max_nils_familj
    statistik["Snitt intäkt känner"] = total_intäkter / max_total if max_total > 0 else 0

    # Snitt lön Malin
    totala_män_älskar_sover = (
        statistik["Totalt antal män"] +
        df["Älskar"].sum() +
        df["Sover med"].sum()
    )
    if totala_män_älskar_sover > 0:
        statistik["Snitt lön Malin"] = statistik["Malins lön"] / totala_män_älskar_sover
    else:
        statistik["Snitt lön Malin"] = 0

    # DP/DPP/DAP/TAP snitt
    for kol in ["DP","DPP","DAP","TAP"]:
        if kol in df.columns and len(scener) > 0:
            statistik[f"Snitt {kol}"] = df[df[kol] > 0][kol].sum() / len(scener)
        else:
            statistik[f"Snitt {kol}"] = 0

    # Snitt hångel
    if "Hångel (sek/kille)" in df.columns and len(scener) > 0:
        statistik["Snitt Hångel"] = df["Hångel (sek/kille)"].sum() / len(scener)
    else:
        statistik["Snitt Hångel"] = 0

    # Älskar och Sover med
    total_max = max_pappans_vänner + max_grannar + max_nils_vänner + max_nils_familj
    statistik["Snitt Älskar"] = df["Älskar"].sum() / total_max if total_max > 0 else 0
    statistik["Summa Älskar per dag"] = df["Älskar"].sum() / len(df) if len(df) > 0 else 0
    statistik["Snitt Sover med"] = df["Sover med"].sum() / max_nils_familj if max_nils_familj > 0 else 0

    # Nils
    statistik["Summa Nils"] = df["Nils"].sum()

    # Tid
    if len(scener) > 0:
        statistik["Snitt Tid kille per scen"] = scener["Tid kille (min)"].sum() / len(scener)
        # Tid utan extra älskar/sover med-timmar (hångel 3h + vila 1h) → i timmar
        extra_tid = (df["Älskar"].sum() * 0 + df["Sover med"].sum() * 0)  # 0 tills vi specificerar exakt logik
        total_tid = scener["Tid kille (min)"].sum() - extra_tid
        statistik["Snitt Tid timmar per scen"] = (total_tid / 60) / len(scener)
    else:
        statistik["Snitt Tid kille per scen"] = 0
        statistik["Snitt Tid timmar per scen"] = 0

    # Snittar per maxgrupp
    grupper = {
        "Pappans vänner": (df["Pappans vänner"].sum(), max_pappans_vänner),
        "Grannar": (df["Grannar"].sum(), max_grannar),
        "Nils vänner": (df["Nils vänner"].sum(), max_nils_vänner),
        "Nils familj": (df["Nils familj"].sum(), max_nils_familj)
    }
    for namn, (summa, maxv) in grupper.items():
        if maxv > 0:
            statistik[f"Snitt {namn}"] = summa / maxv
        else:
            statistik[f"Snitt {namn}"] = 0

        if namn == "Nils familj":
            statistik[f"Totalt antal {namn}"] = statistik[f"Snitt {namn}"] + statistik["Snitt Älskar"] + statistik["Snitt Sover med"]
        else:
            statistik[f"Totalt antal {namn}"] = statistik[f"Snitt {namn}"] + statistik["Snitt Älskar"]

    return statistik
