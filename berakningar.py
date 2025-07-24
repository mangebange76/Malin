import pandas as pd

def process_lägg_till_rader(df, inst, f):
    ny_rad = {col: f.get(col, 0) for col in df.columns}
    return pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)

def konvertera_typer(df):
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except:
                pass
    return df
