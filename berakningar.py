import random

# Hjälpfunktion för att konvertera säkert
def _safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Konvertera sekunder till "h:mm"-format
def _hm_str_from_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}:{m:02d}"

def beräkna_radvärden(row, inställningar):
    """Beräknar alla automatiska fält för en rad baserat på inmatningar och inställningar."""

    män = _safe_int(row.get("Män", 0))
    svarta = _safe_int(row.get("Svarta", 0))
    bekanta = _safe_int(row.get("Bekanta", 0))
    eskilstuna = _safe_int(row.get("Eskilstuna killar", 0))
    älskar = _safe_int(row.get("Älskar", 0))
    sover_med = _safe_int(row.get("Sover med", 0))

    # Summor för total män
    totalt_män = män + svarta + bekanta + eskilstuna

    # DT tid (per man, default 60s) & DT vila (per man, default 3s)
    dt_tid = _safe_int(row.get("DT tid", inställningar.get("DT tid standard", 60)))
    dt_vila = _safe_int(row.get("DT vila", inställningar.get("DT vila standard", 3)))

    # Total tid
    summa_tid = _safe_int(row.get("Summa tid", 0))
    summa_tid += totalt_män * dt_tid  # DT tid på tid kille
    summa_vila = _safe_int(row.get("Summa vila", 0))
    summa_vila += totalt_män * dt_vila  # DT vila på vila

    row["Tid kille (min)"] = round((män * dt_tid) / 60, 2)  # män ger kostnad
    row["Summa tid"] = summa_tid
    row["Summa vila"] = summa_vila
    row["Klockan"] = _hm_str_from_seconds(7 * 3600 + summa_tid + summa_vila)

    # Prenumeranter: Svarta ger dubbel effekt
    pren = män + bekanta + eskilstuna + (svarta * 2)
    row["Prenumeranter"] = pren

    # Hårdhet: +3 om det finns svarta
    hårdhet = _safe_int(row.get("Hårdhet", 0))
    if svarta > 0:
        hårdhet += 3
    row["Hårdhet"] = hårdhet

    # Hångel påverkas av alla
    hångel = män + svarta + bekanta + eskilstuna
    row["Hångel"] = hångel

    # Intäkter
    pris = 39.99
    filmer = män + svarta + bekanta + eskilstuna
    intakt_filmer = filmer * pris
    intakt_känner = (män + svarta + bekanta + eskilstuna) * pris

    # Företagets kostnad
    intakt_företag = - (män * 5)  # ex: kostnad per man

    vinst = intakt_filmer + intakt_känner + intakt_företag
    row["Intäkt filmer"] = intakt_filmer
    row["Intäkt känner"] = intakt_känner
    row["Intäkt företag"] = intakt_företag
    row["Vinst"] = vinst

    # Malins lön
    total_intakt = intakt_känner + intakt_företag + vinst
    divisor_snitt_lon = (
        totalt_män + älskar + sover_med
    )
    snitt_lon = total_intakt / divisor_snitt_lon if divisor_snitt_lon > 0 else 0
    row["Lön Malin"] = max(150, min(800, snitt_lon))

    return row


def slumpa_vila_rad(typ, inställningar):
    """Genererar slumpvärden för rader vid vila hemma eller vila på inspelningsplatsen."""
    rad = {}

    # Alla maxvärden slumpas 40–60 %
    for key in ["Jobb", "Grannar", "Nils vänner", "Nils familj", "Bekanta"]:
        maxv = inställningar.get(f"Max {key}", 0)
        if maxv > 0:
            val = int(random.randint(40, 60) * maxv / 100)
            rad[key] = val
        else:
            rad[key] = 0

    # Eskilstuna killar: 20–40, med viktad chans
    if random.random() < 0.7:  # 70% chans > 30
        rad["Eskilstuna killar"] = random.randint(31, 40)
    else:  # 30% chans <= 30
        rad["Eskilstuna killar"] = random.randint(20, 30)

    # Män & Svarta slumpas som 0 vid vila
    rad["Män"] = 0
    rad["Svarta"] = 0

    return rad
