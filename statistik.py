def compute_stats(rows):
    total_rows = len(rows)
    total_men = sum(int(r.get("Totalt Män", 0)) for r in rows)
    total_fitta = sum(int(r.get("Fitta", 0)) for r in rows)
    total_alskar = sum(int(r.get("Älskar", 0)) for r in rows)
    total_sover = sum(int(r.get("Sover med", 0)) for r in rows)

    return {
        "Antal scener": total_rows,
        "Totalt antal män": total_men,
        "Total fitta": total_fitta,
        "Totalt älskar": total_alskar,
        "Totalt sover med": total_sover,
        "Andel älskar": f"{(total_alskar / total_rows * 100):.1f}%" if total_rows else "-",
        "Andel sover med": f"{(total_sover / total_rows * 100):.1f}%" if total_rows else "-",
    }
