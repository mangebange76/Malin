def beräkna_radvärden(data):
    c = data["Män"]
    d = data["Fitta"]
    e = data["Rumpa"]
    f = data["DP"]
    g = data["DPP"]
    h = data["DAP"]
    i = data["TAP"]
    j = data["Tid S"]
    k = data["Tid D"]
    l = data["Vila"]
    v = data["Pappans vänner"]
    w = data["Grannar"]
    x = data["Nils vänner"]
    y = data["Nils familj"]
    s = data["Älskar"]
    t = data["Sover med"]
    ab = data["Nils"]

    # Summeringar
    m = (c + d + e) * j
    n = (f + g + h) * k
    o = i * k
    p = (c + d + e + f + g + h + i) * l
    q = (m + n + o + p) / 3600  # timmar
    r = 7 + 3 + q + 1           # klockan
    u = v + w + x + y
    z = u + c

    try:
        ac = 10800 / c if c > 0 else 0  # Hångel
    except:
        ac = 0

    try:
        ad = (n * 0.65) / z if z > 0 else 0  # Suger
    except:
        ad = 0

    an = 1  # Prenumeranter per manuell enhet, justerbar
    ae = (c + d + e + f + g + h + i) * an
    af = 15
    ag = ae * af
    ah = c * 120
    aj = max(150, min(800, ae * 0.10))  # Malins lön
    ai = (aj + 120) * u
    ak = ag * 0.20
    al = ag - ah - ai - aj - ak
    am = u

    # Hårdhetspoäng
    hårdhet = 0
    if f > 0:
        hårdhet += 2
    if g > 0:
        hårdhet += 3
    if h > 0:
        hårdhet += 5
    if i > 0:
        hårdhet += 7

    return {
        **data,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Summa tid": q,
        "Klockan": r,
        "Känner": u,
        "Totalt Män": z,
        "Tid kille": ((m / z) + (n / z) + (o / z) + ad) / 60 if z > 0 else 0,
        "Hångel": ac,
        "Suger": ad,
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": aj,
        "intäkt Företaget": ak,
        "Vinst": al,
        "Känner Sammanlagt": am,
        "Hårdhet": hårdhet
    }
