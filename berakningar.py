# berakningar.py
from datetime import datetime, date, time, timedelta

__all__ = ["beräkna_radvärden"]

# ---------- Hjälp ----------
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

def _format_tid_från_sek(sek: float) -> str:
    """Returnerar 'xh yy min' från sekunder (avrundar minuter)."""
    h = int(sek // 3600)
    m = int(round((sek % 3600) / 60.0))
    # rulla över 60 min till 1h
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m} min"

# ---------- Huvud ----------
def beräkna_radvärden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    # Defensiva inputs
    c = int(rad_in.get("Män",0)); d = int(rad_in.get("Fitta",0)); e = int(rad_in.get("Rumpa",0))
    f = int(rad_in.get("DP",0)); g = int(rad_in.get("DPP",0)); h = int(rad_in.get("DAP",0)); i = int(rad_in.get("TAP",0))
    j = int(rad_in.get("Tid S",0)); k = int(rad_in.get("Tid D",0)); l = int(rad_in.get("Vila",0))
    pv = int(rad_in.get("Pappans vänner",0)); gr = int(rad_in.get("Grannar",0))
    nv = int(rad_in.get("Nils vänner",0)); nf = int(rad_in.get("Nils familj",0))

    # Summor (sekunder)
    m = (c+d+e) * j
    n = (f+g+h) * k
    o = i * k
    p = (c+d+e+f+g+h+i) * l
    q_sec = m + n + o + p                    # total sekunder
    q_hours = q_sec / 3600.0                 # timmar som flyttal (för klockslag)
    klockan = _klockan_str(rad_datum, starttid, q_hours)
    summa_tid_str = _format_tid_från_sek(q_sec)

    # Känner & totalt
    u = pv + gr + nv + nf
    z = u + c
    z_safe = z if z > 0 else 1

    # Övriga fält
    ac = 10800 / max(c, 1)
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
        "Summa tid": summa_tid_str,     # <-- 'xh yy min'
        "Klockan": klockan,             # <-- 'HH:MM'
        "Känner": u, "Totalt Män": z,
        "Tid kille": ((m/z_safe)+(n/z_safe)+(o/z_safe)+ad)/60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag,
        "Intäkt män": ah, "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak,
        "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hårdhet
    }
