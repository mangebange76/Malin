from datetime import datetime

def beräkna_radvärden(data):
    # Beräkna kvinnans ålder vid startdatum
    födelsedatum = datetime.strptime(data["Födelsedatum"], "%Y-%m-%d")
    startdatum = datetime.strptime(data["Startdatum"], "%Y-%m-%d")
    ålder = startdatum.year - födelsedatum.year - ((startdatum.month, startdatum.day) < (födelsedatum.month, födelsedatum.day))

    # Räkna ut Malins lön baserat på ålder
    grundlön = 150
    ålderstillägg = max(0, min(ålder - 18, 30)) * 10  # Exempel: 10 kr per år mellan 18–48
    malins_lön = min(grundlön + ålderstillägg, 800)

    return {
        "Aktivitet": data["Aktivitet"],
        "Antal män": data["Antal män"],
        "Hångel": data["Hångel"],
        "Summa tid": data["Summa tid"],
        "Vila": data["Vila"],
        "Kvinnonamn": data["Kvinnonamn"],
        "Födelsedatum": data["Födelsedatum"],
        "Startdatum": data["Startdatum"],
        "Ålder": ålder,
        "Malins lön": malins_lön
    }
