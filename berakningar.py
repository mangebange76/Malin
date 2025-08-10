# berakningar.py

def beräkna_radvärden(rad_in: dict) -> dict:
    """
    Tar in bas-fält (Veckodag, Scen, Män, Fitta, Rumpa, DP, DPP, DAP, TAP,
    Tid S, Tid D, Vila, Älskar, Sover med, Pappans vänner, Grannar,
    Nils vänner, Nils familj, Nils) och returnerar samma dict
    + alla beräknade kolumner i appens KOLUMNER.
    """

    # Plocka ut (med defensiva default)
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
    s = int(rad_in.get("Älskar", 0))
    t = int(rad_in.get("Sover med", 0))
    pv = int(rad_in.get("Pappans vänner", 0))
    gr = int(rad_in.get("Grannar", 0))
    nv = int(rad_in.get("Nils vänner", 0))
    nf = int(rad_in.get("Nils familj", 0))
    ab = int(rad_in.get("Nils", 0))

    # --- Beräkningar ---
    m = (c + d + e) * j                  # Summa S
    n = (f + g + h) * k                  # Summa D
    o = i * k                            # Summa TP
    p = (c + d + e + f + g + h + i) * l  # Summa Vila

    # timmar
    q = (m + n + o + p) / 3600.0         # Summa tid
    r = 7 + 3 + q + 1                    # Klockan (enligt din formel)

    u = pv + gr + nv + nf                # Känner
    z = u + c                            # Totalt Män (enligt dina kolumner)

    # Undvik 0-delning
    z_safe = z if z > 0 else 1
    c_safe = c if c > 0 else 1

    # Tider per kille och övrigt
    ac = 10800 / c_safe                  # Hångel
    ad = (n * 0.65) / z_safe             # Suger

    # Prenumeranter (antalet nya = summan av alla aktioner denna rad)
    ae = (c + d + e + f + g + h + i)
    af = 15                              # Avgift (USD)
    ag = ae * af                         # Intäkter
    ah = c * 120                         # Intäkt män
    aj = max(150, min(800, ae * 0.10))   # Lön Malin (min 150, max 800, 10% av nya prenumeranter)
    ai = (aj + 120) * u                  # Intäkt Känner
    ak = ag * 0.20                       # Intäkt Företaget
    al = ag - ah - ai - aj - ak          # Vinst
    am = u                               # Känner Sammanlagt

    # Hårdhetspoäng
    hårdhet = (2 if f > 0 else 0) + (3 if g > 0 else 0) + (5 if h > 0 else 0) + (7 if i > 0 else 0)

    # Tid kille enligt din formel
    tid_kille = ((m / z_safe) + (n / z_safe) + (o / z_safe) + ad) / 60.0

    # Svar: vi returnerar ett dict med samma nycklar som appen förväntar sig
    return {
        **rad_in,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Summa tid": q,
        "Klockan": r,
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
        "Känner Sammanlagt": am,
        "Hårdhet": hårdhet,
    }
