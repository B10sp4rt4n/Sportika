# utils.py - Módulo mínimo para evitar errores de importación

FREE_SCHEMAS = {
    "LaLiga": ["Equipo", "Puntos", "Partidos", "Goles"],
    "F1": ["Piloto", "Puntos", "Carreras"],
    "MLB": ["Equipo", "Victorias", "Derrotas"],
    "NFL": ["Equipo", "Victorias", "Derrotas", "Empates"]
}

def validate_schema(df, schema):
    # schema puede ser una lista de columnas o el nombre del deporte
    if isinstance(schema, str):
        expected = FREE_SCHEMAS.get(schema) or FREE_SCHEMAS.get(schema.replace(' ',''))
    else:
        expected = schema
    expected = list(expected) if expected else []
    cols = set(df.columns)
    expected_set = set(expected)
    missing = [col for col in expected if col not in cols]
    extra = [col for col in df.columns if col not in expected_set]
    return missing, extra, expected

def compute_standings_laliga(df):
    return df.sort_values("Puntos", ascending=False)

def compute_f1_points(df):
    # Retorna dos valores: el DataFrame ordenado y un DataFrame vacío como placeholder
    return df.sort_values("Puntos", ascending=False), pd.DataFrame()

def compute_mlb_summary(df):
    return df

def compute_nfl_table(df):
    return df

def merge_laliga_with_projections(df1, df2):
    return df1

def merge_concat(df1, df2):
    return df1.append(df2, ignore_index=True)
