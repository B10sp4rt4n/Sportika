# utils.py - Módulo mínimo para evitar errores de importación

FREE_SCHEMAS = {
    "LaLiga": ["Equipo", "Puntos", "Partidos", "Goles"],
    "F1": ["Piloto", "Puntos", "Carreras"],
    "MLB": ["Equipo", "Victorias", "Derrotas"],
    "NFL": ["Equipo", "Victorias", "Derrotas", "Empates"]
}

def validate_schema(df, schema):
    return set(schema).issubset(df.columns)

def compute_standings_laliga(df):
    return df.sort_values("Puntos", ascending=False)

def compute_f1_points(df):
    return df.sort_values("Puntos", ascending=False)

def compute_mlb_summary(df):
    return df

def compute_nfl_table(df):
    return df

def merge_laliga_with_projections(df1, df2):
    return df1

def merge_concat(df1, df2):
    return df1.append(df2, ignore_index=True)
