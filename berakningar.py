# berakningar.py
from __future__ import annotations
from datetime import datetime, timedelta, date, time

# =========================
# Hjälpfunktioner (rena)
# =========================
def _safe_int(x, default=0):
    try:
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _calc_u(rad_in: dict) -> int:
    """
    U = Känner = Pappans vänner + Grannar + Nils vänner + Nils familj.
    """
    return (
        _safe_int(rad_in.get("Pappans vänner", 0)) +
        _safe_int(rad_in.get("Grannar", 0)) +
        _safe_int(rad_in.get("Nils vänner", 0)) +
        _safe_int(rad_in.get("Nils familj", 0))
    )

def _hm_str_from_seconds(q_sec: int) -> str:
    """Returnera t.ex. '4h 49 min' från sekunder (avrundar minuter)."""
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    """Returnera 'Xm Ys' från sekunder (minuter & sekunder)."""
    if sec < 0: sec = 0
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _age_on_date(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


# =========================================
# Huvudberäkning (används av app.py)
# =========================================
def berakna_radvarden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    """
    - U (Känner) ingår i Summa S/D/TP/Vila.
    - Älskar → +30 min per st (1800 s), Sover med (0/1) → +60 min (3600 s).
    - Suger_total (sek) = 60% av (Summa D + Summa TP).
    - Suger per kille (sek) = Suger_total / Z.
    - Tid per kille (sek) = (S/Z) + 2*(D/Z) + 3*(TP/Z) + (Suger_total/Z), Z = Män + Känner.
    - 'Tid kille' (min) = 'Tid per kille (sek)' / 60.
    - Summa tid returneras i sek och 'xh y min'. Klockan formateras HH:MM från starttid + (3h + q + 1h).
    - Ekonomi enligt tidigare överenskommelser (Hångel, Prenumeranter, Lön, Vinst m.m.).
    """

    # Indata (säkerställ int)
    c = _safe_int(rad_in.get("Män", 0))
    d = _safe_int(rad_in.get("Fitta", 0))
    e = _safe_int(rad_in.get("Rumpa", 0))
    f = _safe_int(rad_in.get("DP", 0))
    g = _safe_int(rad_in.get("DPP", 0))
    h = _safe_int(rad_in.get("DAP", 0))
    i = _safe_int(rad_in.get("TAP", 0))

    j = _safe_int(rad_in.get("Tid S", 0))  # sek
    k = _safe_int(rad_in.get("Tid D", 0))  # sek
    l = _safe_int(rad_in.get("Vila", 0))   # sek

    alskar    = _safe_int(rad_in.get("Älskar", 0))     # 30 min/st
    sover_med = _safe_int(rad_in.get("Sover med", 0))  # 0/1 → 60 min/st
    if sover_med < 0: sover_med = 0
    if sover_med > 1: sover_med = 1

    # U = Känner
    u = _calc_u(rad_in)

    # Summor – inkluderar U (sekunder)
    m = (c + d + e + u) * j                 # Summa S
    n = (f + g + h + u) * k                 # Summa D
    o = (i + u) * k                         # Summa TP
    p = (c + d + e + f + g + h + i + u) * l # Summa Vila

    # Extra tid från Älskar & Sover med
    extra_alskar_sec    = alskar * 1800     # 30 min/st
    extra_sover_med_sec = sover_med * 3600  # 60 min/st

    # Totaltid (sek + text)
    q_sec = int(m + n + o + p + extra_alskar_sec + extra_sover_med_sec)
    q_hours = q_sec / 3600.0
    summa_tid_str = _hm_str_from_seconds(q_sec)

    # Klockan (utifrån starttid)
    klockan_str = (
        datetime.combine(rad_datum, starttid)
        + timedelta(hours=3)
        + timedelta(hours=q_hours)
        + timedelta(hours=1)
    ).strftime("%H:%M")

    # Totalt män Z = Män + Känner (exkl. älskar/sover med)
    z = int(c + u)
    z_safe = z if z > 0 else 1

    # ===== Suger_total, Suger per kille & Tid per kille =====
    # Suger_total (sek, total) = 60% av (D + TP)
    suger_total_sec = int(round(0.60 * (n + o)))
    # per kille
    suger_per_kille_sec = int(round(suger_total_sec / z)) if z > 0 else 0

    # Tid per kille (sek) = (m/z) + 2*(n/z) + 3*(o/z) + (suger_total_sec / z)
    if z > 0:
        tid_per_kille_sec = int(round(
            (m / z) + 2 * (n / z) + 3 * (o / z) + (suger_total_sec / z)
        ))
    else:
        tid_per_kille_sec = 0

    tid_per_kille_str = _ms_str_from_seconds(tid_per_kille_sec)

    # ----- Ekonomi -----
    ac = 10800 / max(c, 1)   # Hångel (sek/kille)
    ae = (c + d + e + f + g + h + i + u)  # Prenumeranter (med U)
    af = 15
    ag = ae * af
    ah = c * 120

    # Lön Malin – åldersfaktor
    ålder = (rad_datum.year - födelsedatum.year
             - ((rad_datum.month, rad_datum.day) < (födelsedatum.month, födelsedatum.day)))
    if ålder < 18:
        raise ValueError("Ålder < 18 — spärrad rad.")
    if   18 <= ålder <= 25: faktor = 1.20
    elif 26 <= ålder <= 30: faktor = 1.10
    elif 31 <= ålder <= 40: faktor = 1.00
    else:                    faktor = 0.90
    aj_base = max(150, min(800, ae * 0.10))
    aj = max(150, min(800, aj_base * faktor))  # Lön Malin

    ai = (aj + 120) * u        # Intäkt Känner
    ak = ag * 0.20             # Intäkt Företaget
    al = ag - ah - ai - aj - ak# Vinst
    hårdhet = (2 if f > 0 else 0) + (3 if g > 0 else 0) + (5 if h > 0 else 0) + (7 if i > 0 else 0)

    # Returnera komplett resultatrad
    return {
        **rad_in,
        "Känner": u,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Tid Älskar (sek)": extra_alskar_sec,
        "Tid Älskar": _hm_str_from_seconds(extra_alskar_sec),
        "Tid Sover med (sek)": extra_sover_med_sec,
        "Tid Sover med": _hm_str_from_seconds(extra_sover_med_sec),
        "Summa tid (sek)": q_sec,
        "Summa tid": summa_tid_str,
        "Klockan": klockan_str,
        "Totalt Män": z,
        # Suger = TOTAL sekunder (60% av (D+TP)) + per kille
        "Suger": suger_total_sec,
        "Suger per kille (sek)": suger_per_kille_sec,
        # Tid per kille (sek och text) + "Tid kille" i minuter
        "Tid per kille (sek)": tid_per_kille_sec,
        "Tid per kille": tid_per_kille_str,  # min:sek
        "Tid kille": tid_per_kille_sec / 60,
        # Ekonomi
        "Hångel": ac,
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": aj,
        "Intäkt Företaget": ak,
        "Vinst": al,
        "Känner Sammanlagt": u,
        "Hårdhet": hårdhet
    }

# Alias med prickar (om någon importerar det namnet).
beräkna_radvärden = berakna_radvarden
