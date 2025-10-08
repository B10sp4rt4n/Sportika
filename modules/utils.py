# utils.py - Módulo mínimo para evitar errores de importación
import pandas as pd

FREE_SCHEMAS = {
    "La Liga": ["Local", "Visitante", "Goles_Local", "Goles_Visitante"],
    "F1": ["Piloto", "Equipo", "Puntos"],
    "MLB": ["Equipo_Local", "Equipo_Visitante", "HR_Local", "HR_Visitante"],
    "NFL": ["Local", "Visitante", "Puntos_Local", "Puntos_Visitante"]
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
    """Calcula la tabla de posiciones de La Liga basada en resultados"""
    equipos = set(df["Local"].tolist() + df["Visitante"].tolist())
    standings = []
    
    for equipo in equipos:
        # Partidos como local
        local_games = df[df["Local"] == equipo]
        # Partidos como visitante
        away_games = df[df["Visitante"] == equipo]
        
        # Calcular estadísticas
        partidos = len(local_games) + len(away_games)
        goles_favor = (local_games["Goles_Local"].sum() + 
                      away_games["Goles_Visitante"].sum())
        goles_contra = (local_games["Goles_Visitante"].sum() + 
                       away_games["Goles_Local"].sum())
        
        # Calcular victorias, empates, derrotas
        victorias = len(local_games[local_games["Goles_Local"] > local_games["Goles_Visitante"]])
        victorias += len(away_games[away_games["Goles_Visitante"] > away_games["Goles_Local"]])
        
        empates = len(local_games[local_games["Goles_Local"] == local_games["Goles_Visitante"]])
        empates += len(away_games[away_games["Goles_Visitante"] == away_games["Goles_Local"]])
        
        derrotas = partidos - victorias - empates
        
        # Puntos (3 por victoria, 1 por empate)
        puntos = victorias * 3 + empates * 1
        
        standings.append({
            "Pos": 0,  # Se calculará después del ordenamiento
            "Equipo": equipo,
            "PJ": partidos,
            "G": victorias,
            "E": empates,
            "P": derrotas,
            "GF": int(goles_favor),
            "GC": int(goles_contra),
            "DG": int(goles_favor - goles_contra),
            "PTS": puntos
        })
    
    # Crear DataFrame y ordenar
    standings_df = pd.DataFrame(standings)
    standings_df = standings_df.sort_values(["PTS", "DG", "GF"], ascending=[False, False, False])
    standings_df["Pos"] = range(1, len(standings_df) + 1)
    
    return standings_df[["Pos", "Equipo", "PJ", "G", "E", "P", "GF", "GC", "DG", "PTS"]]

def compute_f1_points(df):
    """Calcula puntos de pilotos y constructores en F1"""
    # Agrupar por piloto
    drivers = df.groupby("Piloto")["Puntos"].sum().reset_index()
    drivers = drivers.sort_values("Puntos", ascending=False)
    drivers["Pos"] = range(1, len(drivers) + 1)
    drivers = drivers[["Pos", "Piloto", "Puntos"]]
    
    # Agrupar por constructor/equipo
    constructors = df.groupby("Equipo")["Puntos"].sum().reset_index()
    constructors = constructors.sort_values("Puntos", ascending=False)
    constructors["Pos"] = range(1, len(constructors) + 1)
    constructors = constructors[["Pos", "Equipo", "Puntos"]]
    
    return drivers, constructors

def compute_mlb_summary(df):
    """Calcula resumen de estadísticas MLB por equipo"""
    equipos = set(df["Equipo_Local"].tolist() + df["Equipo_Visitante"].tolist())
    summary = []
    
    for equipo in equipos:
        # Juegos como local
        local_games = df[df["Equipo_Local"] == equipo]
        # Juegos como visitante
        away_games = df[df["Equipo_Visitante"] == equipo]
        
        # Calcular estadísticas
        juegos = len(local_games) + len(away_games)
        hr_total = (local_games["HR_Local"].sum() + away_games["HR_Visitante"].sum())
        hr_contra = (local_games["HR_Visitante"].sum() + away_games["HR_Local"].sum())
        
        # Calcular victorias (asumiendo que más HR = victoria, simplificado)
        victorias_local = len(local_games[local_games["HR_Local"] > local_games["HR_Visitante"]])
        victorias_away = len(away_games[away_games["HR_Visitante"] > away_games["HR_Local"]])
        victorias = victorias_local + victorias_away
        
        derrotas = juegos - victorias
        avg = victorias / juegos if juegos > 0 else 0
        
        summary.append({
            "Pos": 0,  # Se calculará después
            "Equipo": equipo,
            "J": juegos,
            "G": victorias,
            "P": derrotas,
            "AVG": round(avg, 3),
            "HR": int(hr_total),
            "R": int(hr_total)  # Simplificado: R = HR para este ejemplo
        })
    
    # Crear DataFrame y ordenar
    summary_df = pd.DataFrame(summary)
    summary_df = summary_df.sort_values(["G", "HR"], ascending=[False, False])
    summary_df["Pos"] = range(1, len(summary_df) + 1)
    
    return summary_df[["Pos", "Equipo", "J", "G", "P", "AVG", "HR", "R"]]

def compute_nfl_table(df):
    """Calcula tabla de posiciones NFL basada en puntos"""
    equipos = set(df["Local"].tolist() + df["Visitante"].tolist())
    standings = []
    
    for equipo in equipos:
        # Juegos como local
        local_games = df[df["Local"] == equipo]
        # Juegos como visitante
        away_games = df[df["Visitante"] == equipo]
        
        # Calcular estadísticas
        juegos = len(local_games) + len(away_games)
        puntos_favor = (local_games["Puntos_Local"].sum() + 
                       away_games["Puntos_Visitante"].sum())
        puntos_contra = (local_games["Puntos_Visitante"].sum() + 
                        away_games["Puntos_Local"].sum())
        
        # Calcular victorias y derrotas
        victorias = len(local_games[local_games["Puntos_Local"] > local_games["Puntos_Visitante"]])
        victorias += len(away_games[away_games["Puntos_Visitante"] > away_games["Puntos_Local"]])
        
        empates = len(local_games[local_games["Puntos_Local"] == local_games["Puntos_Visitante"]])
        empates += len(away_games[away_games["Puntos_Visitante"] == away_games["Puntos_Local"]])
        
        derrotas = juegos - victorias - empates
        
        win_pct = victorias / juegos if juegos > 0 else 0
        
        standings.append({
            "Pos": 0,  # Se calculará después
            "Equipo": equipo,
            "J": juegos,
            "W": victorias,
            "L": derrotas,
            "T": empates,
            "PCT": round(win_pct, 3),
            "PF": int(puntos_favor),
            "PA": int(puntos_contra),
            "DIFF": int(puntos_favor - puntos_contra)
        })
    
    # Crear DataFrame y ordenar
    standings_df = pd.DataFrame(standings)
    standings_df = standings_df.sort_values(["W", "PCT", "DIFF"], ascending=[False, False, False])
    standings_df["Pos"] = range(1, len(standings_df) + 1)
    
    return standings_df[["Pos", "Equipo", "J", "W", "L", "T", "PCT", "PF", "PA", "DIFF"]]

def merge_laliga_with_projections(df1, df2):
    """Combina datos base de La Liga con proyecciones"""
    return pd.concat([df1, df2], ignore_index=True)

def merge_concat(df1, df2):
    """Concatena dos DataFrames"""
    return pd.concat([df1, df2], ignore_index=True)
