# Daglig Registreringsapp

En Streamlit-app för att registrera och analysera dagliga värden relaterade till relationer, tid, ekonomi och känslor.

## Funktioner
- Registrering av ny dag
- Dynamisk summering (malin, känner, snitt m.m.)
- Redigering och radering av data
- Google Sheets-integrerad databas
- Mobilvänlig layout

## Starta appen i Streamlit Cloud
1. Skapa ett nytt projekt på Streamlit Cloud
2. Ladda upp alla dessa filer
3. Gå till `secrets.toml` och lägg in din `GOOGLE_CREDENTIALS` (se nedan)

## secrets.toml (instruktion)
```toml
GOOGLE_CREDENTIALS = """{...ditt JSON-innehåll här...}"""
