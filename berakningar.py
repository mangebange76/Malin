# berakningar.py
from datetime import datetime, date, time, timedelta

__all__ = ["beräkna_radvärden"]

# ---- Hjälpfunktioner ----
def _ålder_vid_datum(rad_datum: date, född: date) -> int:
    return rad_datum.year - född.year - ((rad_datum.month, rad_datum.day) < (född.month, född.day))

def _lönefaktor(ålder: int):
    if ålder < 18: return None
    if 18 <= ålder <= 25: return 1.20
    if 26 <= ålder <= 30: return 1.10
    if 31 <= ålder <= 40: return 1.00
    return 0.90  # >40

def _klockan_str(rad_datum: date, starttid: time, q_timmar: float) -> str:
    start_dt = datetime.combine(rad_datum, starttid)
    slut_dt = start_dt + timedelta(hours=3) + timedelta(hours=q_timmar) + timedelta(hours=1)
    return slut_dt.strftime("%H:%M")

# ---- Huvudfunktion ----
def beräkna_radvärden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    # Läs defensivt
    c = int(rad_in.get("Män",0)); d = int(rad_in.get("Fitta",0)); e = int(rad_in.get("Rumpa",0))
    f = int(rad_in.get("DP",0)); g = int(rad_in.get("DPP",0)); h = int(rad_in.get("DAP",0)); i = int(rad_in.get("TAP",0))
    j = int(rad_in.get("Tid S",0)); k = int(rad_in.get("Tid D",0)); l = int(rad_in.get("Vila",0))
    pv = int(rad_in.get("Pappans vänner",0)); gr = int(rad_in.get("Grannar",0))
    nv = int(rad_in.get("Nils vänner",0)); nf = int(rad_in.get("Nils familj",0))

    # Bas-summor (sekunder)
    m = (c+d+e) * j
    n = (f+g+h) * k
    o = i * k
    p = (c+d+e+f+g+h+i) * l

    # Timmar med 1 decimal + klockslag HH:MM
    q_hours = round((m+n+o+p) / 3600.0, 1)
    klockan = _klockan_str(rad_datum, starttid, q_hours)

    # Känner & totalt
    u = pv + gr + nv + nf
    z = u + c
    z_safe = z if z > 0 else 1

    # Övrigt
    ac = 10800 / max(c, 1)         # sek per kille
    ad = (n * 0.65) / z_safe
    ae = (c+d+e+f+g+h+i)
    af = 15
    ag = ae * af
    ah = c * 120

    # Lön Malin med åldersfaktor
    ålder = _ålder_vid_datum(rad_datum, födelsedatum)
    faktor = _lönefaktor(ålder)
    if faktor is None:
        raise ValueError("Ålder < 18 — spärrad rad.")
    aj_bas = max(150, min(800, ae * 0.10))
    aj = max(150, min(800, aj_bas * faktor))

    ai = (aj + 120) * u
    ak = ag * 0.20
    al = ag - ah - ai - aj - ak
    hårdhet = (2 if f>0 else 0) + (3 if g>0 else 0) + (5 if h>0 else 0) + (7 if i>0 else 0)

    return {
        **rad_in,
        "Summa S": m, "Summa D": n, "Summa TP": o, "Summa Vila": p,
        "Summa tid": q_hours,         # timmar, 1 decimal
        "Klockan": klockan,           # "HH:MM"
        "Känner": u, "Totalt Män": z,
        "Tid kille": ((m/z_safe)+(n/z_safe)+(o/z_safe)+ad)/60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag,
        "Intäkt män": ah, "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak,
        "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hårdhet
    }
