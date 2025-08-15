# berakningar.py
from datetime import datetime, date, time, timedelta

__all__ = ["beräkna_radvärden", "beräkna_radvärden_kompatibel"]

# ---- Hjälpfunktioner ----
def ålder_vid_datum(rad_datum: date, född: date) -> int:
    """Returnerar ålder i hela år på rad_datum."""
    return rad_datum.year - född.year - (
        (rad_datum.month, rad_datum.day) < (född.month, född.day)
    )

def lönefaktor_för_ålder(ålder: int):
    """Åldersbaserad faktor. Returnerar None om <18 (spärr)."""
    if ålder < 18:
        return None
    if 18 <= ålder <= 25:
        return 1.20
    if 26 <= ålder <= 30:
        return 1.10
    if 31 <= ålder <= 40:
        return 1.00
    return 0.90  # > 40

def beräkna_klockan_str(rad_datum: date, starttid: time, q_timmar: float) -> str:
    """
    Klockan = starttid + 3h (Hångel) + q (Summa tid, timmar) + 1h (vila),
    returnerad som HH:MM.
    """
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt = start_dt + timedelta(hours=3) + timedelta(hours=q_timmar) + timedelta(hours=1)
    return slut_dt.strftime("%H:%M")

# ---- Huvudfunktion ----
def beräkna_radvärden(
    rad_in: dict,
    rad_datum: date,
    födelsedatum: date,
    starttid: time,
) -> dict:
    """
    Tar in grundvärdena för raden + rad_datum, födelsedatum och starttid
    och returnerar en dict med samtliga beräknade kolumner:
    - Summa S, Summa D, Summa TP, Summa Vila, Summa tid (timmar, float)
    - Klockan (HH:MM), Känner, Totalt Män, Tid kille, Hångel, Suger
    - Prenumeranter, Avgift, Intäkter, Intäkt män, Intäkt Känner
    - Lön Malin (med åldersfaktor), Intäkt Företaget, Vinst
    - Känner Sammanlagt, Hårdhet
    """

    # Läs & defensiva default
    c = int(rad_in.get("Män", 0))
    d = int(rad_in.get("Fitta", 0))
    e = int(rad_in.get("Rumpa", 0))
    f = int(rad_in.get("DP", 0))
    g = int(rad_in.get("DPP", 0))
    h = int(rad_in.get("DAP", 0))
    i = int(rad_in.get("TAP", 0))
    j = int(rad_in.get("Tid S", 0))
    k = int(rad_in.get("Tid D", 0))
    l = int(rad_in.get("Vila", 0))
    pv = int(rad_in.get("Pappans vänner", 0))
    gr = int(rad_in.get("Grannar", 0))
    nv = int(rad_in.get("Nils vänner", 0))
    nf = int(rad_in.get("Nils familj", 0))

    # Bas-summor
    m = (c + d + e) * j                 # Summa S (sek)
    n = (f + g + h) * k                 # Summa D (sek)
    o = i * k                           # Summa TP (sek)
    p = (c + d + e + f + g + h + i) * l # Summa Vila (sek)

    # Total tid i timmar
    q = (m + n + o + p) / 3600.0        # Summa tid (timmar, float)

    # Klockslag HH:MM
    klockan_str = beräkna_klockan_str(rad_datum, starttid, q)

    # Känner & Totalt Män
    u = pv + gr + nv + nf               # Känner
    z = u + c                           # Totalt Män
    z_safe = z if z > 0 else 1

    # Övriga härledda fält
    ac = 10800 / max(c, 1)              # Hångel (sek per kille)
    ad = (n * 0.65) / z_safe            # Suger (sek per man totalt)
    ae = (c + d + e + f + g + h + i)    # Prenumeranter (nya på raden)
    af = 15                             # Avgift (USD)
    ag = ae * af                        # Intäkter (USD)
    ah = c * 120                        # Intäkt män (USD)

    # Lön Malin med åldersfaktor
    ålder = ålder_vid_datum(rad_datum, födelsedatum)
    faktor = lönefaktor_för_ålder(ålder)
    if faktor is None:
        raise ValueError("Ålder < 18 — spärrad rad.")

    aj_bas = max(150, min(800, ae * 0.10))
    aj = max(150, min(800, aj_bas * faktor))  # Lön Malin (USD)

    ai = (aj + 120) * u                 # Intäkt Känner (USD)
    ak = ag * 0.20                      # Intäkt Företaget (USD)
    al = ag - ah - ai - aj - ak         # Vinst (USD)

    # Hårdhet
    hårdhet = (2 if f > 0 else 0) + (3 if g > 0 else 0) + (5 if h > 0 else 0) + (7 if i > 0 else 0)

    # Tid kille (minuter)
    tid_kille = ((m / z_safe) + (n / z_safe) + (o / z_safe) + ad) / 60.0

    return {
        **rad_in,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Summa tid": q,             # timmar (float)
        "Klockan": klockan_str,     # HH:MM
        "Känner": u,
        "Totalt Män": z,
        "Tid kille": tid_kille,
        "Hångel": ac,
        "Suger": ad,
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": aj,
        "Intäkt Företaget": ak,
        "Vinst": al,
        "Känner Sammanlagt": u,
        "Hårdhet": hårdhet,
    }

# ---- Bakåtkompatibel wrapper (om appen råkar kalla utan nya parametrar) ----
def beräkna_radvärden_kompatibel(rad_in: dict) -> dict:
    """
    Fallback för äldre anrop som bara skickar rad_in.
    Använder dagens datum, starttid 07:00 och ett default-födelsedatum.
    (Rekommenderas att uppdatera appen att kalla huvudfunktionen med alla parametrar.)
    """
    return beräkna_radvärden(
        rad_in=rad_in,
        rad_datum=date.today(),
        födelsedatum=date(1999, 1, 1),
        starttid=time(7, 0),
    )
