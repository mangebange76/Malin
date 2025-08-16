import pandas as pd
import random

# ---------------------------------------------------------
# Hjälpfunktioner
# ---------------------------------------------------------

def slumpa_vilovecka_nils(rad_index: int) -> int:
    """Slumpar värde för Nils vid vilovecka hemma.
    Dag 7 = alltid 0.
    Dag 1–6: 50% chans för 0, 45% chans för 1, 5% chans för totalt två ettor under veckan.
    """
    if rad_index == 6:  # dag 7
        return 0
    slump = random.random()
    if slump < 0.5:
        return 0
    elif slump < 0.95:
        return 1
    else:
        return 2

# ---------------------------------------------------------
# Beräkningar på radnivå
# ---------------------------------------------------------

def beräkna_radvärden(rad, sidopanel):
    """Beräknar automatiska värden för en rad i databasen."""
    
    män = int(rad.get("Män", 0) or 0)
    svarta = int(rad.get("Svarta", 0) or 0)
    totalt_män = män + svarta

    # Prenumeranter (svarta räknas dubbelt)
    rad["Prenumeranter"] = män + (svarta * 2)

    # Hårdhet (svarta ger +3)
    hårdhet = int(rad.get("Hårdhet", 0) or 0)
    if svarta > 0:
        hårdhet += 3
    rad["Hårdhet"] = hårdhet

    # Tid kille (per minut)
    minuter_per_kille = int(rad.get("Minuter per kille", 0) or 0)
    rad["Tid kille"] = totalt_män * minuter_per_kille

    # Intäkter/kostnader
    intäkt_känner = float(rad.get("Intäkt känner", 0) or 0)
    kostnad_företag = float(rad.get("Kostnad företag", 0) or 0)
    rad["Vinst"] = intäkt_känner - kostnad_företag

    # Malins lön: 10% av prenumeranter, minst 150, max 800
    pren = rad.get("Prenumeranter", 0)
    malins_lön = max(150, min(800, pren * 0.10))
    rad["Lön Malin"] = malins_lön

    return rad

# ---------------------------------------------------------
# Statistiska sammanställningar
# ---------------------------------------------------------

def beräkna_statistik(df: pd.DataFrame, sidopanel: dict):
    """Beräknar statistik för hela databasen."""
    stats = {}

    # Antal scener (män > 0)
    scener_df = df[(df["Män"] > 0) | (df["Svarta"] > 0)]
    antal_scener = len(scener_df)
    stats["Antal scener"] = antal_scener

    # Privat GB (män = 0, känner > 0)
    privat_gb_df = df[(df["Män"] == 0) & (df["Svarta"] == 0) & (df["Känner"] > 0)]
    stats["Privat GB"] = len(privat_gb_df)

    # Totalt antal män
    stats["Totalt antal män"] = (df["Män"].sum() + df["Svarta"].sum())

    # Andel svarta (% av män)
    tot_män = df["Män"].sum() + df["Svarta"].sum()
    stats["Andel svarta (%)"] = (df["Svarta"].sum() / tot_män * 100) if tot_män > 0 else 0

    # Summeringar
    stats["Summa älskar"] = df["Älskar"].sum()
    stats["Summa sover med"] = df["Sover med"].sum()
    stats["Summa Nils"] = df["Nils"].sum()

    # Snitt älskar (delat med maxvärden i sidopanel)
    max_älskar = sidopanel.get("Nils familj", 1) + sidopanel.get("Nils vänner", 1) + sidopanel.get("Grannar", 1) + sidopanel.get("Pappans vänner", 1)
    stats["Snitt älskar"] = df["Älskar"].sum() / max_älskar if max_älskar > 0 else 0

    # Snitt sover med
    max_sov = sidopanel.get("Nils familj", 1)
    stats["Snitt sover med"] = df["Sover med"].sum() / max_sov if max_sov > 0 else 0

    # Snitt tid per scen (exkl älskar/sover med-tid)
    if antal_scener > 0:
        stats["Snitt tid kille per scen (min)"] = scener_df["Tid kille"].sum() / antal_scener
        stats["Snitt tid timmar per scen"] = (scener_df["Tid kille"].sum() / 60) / antal_scener
    else:
        stats["Snitt tid kille per scen (min)"] = 0
        stats["Snitt tid timmar per scen"] = 0

    # Summeringar av intäkter/kostnader
    stats["Totalt intäkt känner"] = df["Intäkt känner"].sum()
    stats["Totalt kostnad företag"] = df["Kostnad företag"].sum()
    stats["Totalt vinst"] = df["Vinst"].sum()
    stats["Totalt lön Malin"] = df["Lön Malin"].sum()

    # Snitt intäkt per maxvärden
    max_sum = sum(sidopanel.values())
    if max_sum > 0:
        stats["Snitt intäkt/känner+företag+vinst"] = (
            df["Intäkt känner"].sum() + df["Kostnad företag"].sum() + df["Vinst"].sum()
        ) / max_sum
    else:
        stats["Snitt intäkt/känner+företag+vinst"] = 0

    # Snitt Malins lön (delat på totalt antal män + älskar + sover med)
    total_divisor = stats["Totalt antal män"] + stats["Summa älskar"] + stats["Summa sover med"]
    if total_divisor > 0:
        stats["Snitt lön Malin"] = stats["Totalt lön Malin"] / total_divisor
    else:
        stats["Snitt lön Malin"] = 0

    return stats
