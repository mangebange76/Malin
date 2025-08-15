import pandas as pd

def format_h_m(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

def format_m_s(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"

def berakna_radvarden(row):
    # Hämta indata (0 om ej angivet)
    summa_s = pd.to_numeric(row.get("Summa S (sek)", 0), errors="coerce") or 0
    summa_d = pd.to_numeric(row.get("Summa D (sek)", 0), errors="coerce") or 0
    summa_t = pd.to_numeric(row.get("Summa T (sek)", 0), errors="coerce") or 0
    känner = pd.to_numeric(row.get("Känner", 0), errors="coerce") or 0
    män = pd.to_numeric(row.get("Män", 0), errors="coerce") or 0
    älskar = pd.to_numeric(row.get("Älskar", 0), errors="coerce") or 0
    sover_med = pd.to_numeric(row.get("Sover med", 0), errors="coerce") or 0

    # Totalt antal män för tid per kille (män + känner, ej älskar/sover med)
    totalt_män = män + känner

    # Tid från älskar (30 min per älskar)
    tid_alskar = älskar * 30 * 60

    # Tid från sover med (1h per rad med värde 1)
    tid_sover = sover_med * 60 * 60

    # Summa total tid (sek)
    total_tid_sec = summa_s + summa_d + summa_t + tid_alskar + tid_sover

    # Tid per kille (sek)
    tid_per_kille_sec = 0
    if totalt_män > 0:
        tid_per_kille_sec = (summa_s / totalt_män) + (summa_d / (totalt_män * 2)) + (summa_t / (totalt_män * 3))

    # Spara beräknade fält
    row["Totalt Män"] = totalt_män
    row["Summa tid (sek)"] = total_tid_sec
    row["Summa tid"] = format_h_m(total_tid_sec)
    row["Tid per kille (sek)"] = tid_per_kille_sec
    row["Tid per kille"] = format_m_s(tid_per_kille_sec)

    return row
