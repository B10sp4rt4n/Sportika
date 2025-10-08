import streamlit as st
import os
import pandas as pd
from io import BytesIO
import sqlite3
import json
DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")

def ensure_tables():
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        
        # Tablas existentes
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            sport TEXT,
            label TEXT,
            payload_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS entitlements (
            username TEXT PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Nuevas tablas para datos deportivos
        cur.execute('''CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            sport TEXT,
            name TEXT,
            is_projection INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Tabla para partidos de fútbol (La Liga, NFL)
        cur.execute('''CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            local TEXT,
            visitante TEXT,
            goles_local INTEGER DEFAULT 0,
            goles_visitante INTEGER DEFAULT 0,
            puntos_local INTEGER DEFAULT 0,
            puntos_visitante INTEGER DEFAULT 0,
            FOREIGN KEY (dataset_id) REFERENCES datasets (id)
        )''')
        
        # Tabla para carreras de F1
        cur.execute('''CREATE TABLE IF NOT EXISTS f1_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            piloto TEXT,
            equipo TEXT,
            puntos INTEGER DEFAULT 0,
            carrera TEXT DEFAULT '',
            FOREIGN KEY (dataset_id) REFERENCES datasets (id)
        )''')
        
        # Tabla para juegos de MLB
        cur.execute('''CREATE TABLE IF NOT EXISTS mlb_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            equipo_local TEXT,
            equipo_visitante TEXT,
            hr_local INTEGER DEFAULT 0,
            hr_visitante INTEGER DEFAULT 0,
            runs_local INTEGER DEFAULT 0,
            runs_visitante INTEGER DEFAULT 0,
            FOREIGN KEY (dataset_id) REFERENCES datasets (id)
        )''')
        
        con.commit()
        con.close()
    except Exception as e:
        st.error(f"Error al inicializar la base de datos: {str(e)}")

# Crear tablas al inicio de la app
ensure_tables()

def ensure_user(username: str):
    if not username:
        return
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("INSERT OR IGNORE INTO users(username) VALUES(?)", (username,))
        con.commit()
        con.close()
    except Exception as e:
        st.error(f"Error al registrar usuario: {str(e)}")

def save_scenario(username: str, sport: str, label: str, resumen_df):
    if not username:
        return False
    try:
        payload = resumen_df.to_json(orient="records", force_ascii=False)
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("""INSERT INTO scenarios(username, sport, label, payload_json)
                       VALUES(?,?,?,?)""", (username, sport, label, payload))
        con.commit()
        con.close()
        return True
    except Exception as e:
        st.error(f"Error al guardar escenario: {str(e)}")
        return False

def load_scenarios(username: str, sport: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT label, payload_json, created_at FROM scenarios WHERE username=? AND sport=? ORDER BY created_at DESC", (username, sport))
    rows = cur.fetchall()
    con.close()
    # return dict label -> DataFrame (latest per label)
    out = {}
    for label, payload, created_at in rows:
        try:
            df = pd.read_json(payload)
            out.setdefault(label, df)  # keep first occurrence (latest due to ORDER BY DESC)
        except Exception:
            continue
    return out


def set_premium(username: str, flag: bool):
    if not username:
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO entitlements(username, is_premium) VALUES(?, ?) ON CONFLICT(username) DO UPDATE SET is_premium=excluded.is_premium, updated_at=CURRENT_TIMESTAMP", (username, 1 if flag else 0))
    con.commit()
    con.close()

def is_premium(username: str) -> bool:
    if not username:
        return False
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT is_premium FROM entitlements WHERE username=?", (username,))
    row = cur.fetchone()
    con.close()
    return bool(row[0]) if row else False

# Funciones para gestión de datasets deportivos
def create_dataset(username: str, sport: str, name: str, is_projection: bool = False) -> int:
    """Crea un nuevo dataset y retorna su ID"""
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("INSERT INTO datasets (username, sport, name, is_projection) VALUES (?, ?, ?, ?)",
                   (username, sport, name, 1 if is_projection else 0))
        dataset_id = cur.lastrowid
        con.commit()
        con.close()
        return dataset_id
    except Exception as e:
        st.error(f"Error al crear dataset: {str(e)}")
        return None

def get_datasets(username: str, sport: str = None):
    """Obtiene los datasets del usuario"""
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        if sport:
            cur.execute("SELECT id, sport, name, is_projection, created_at FROM datasets WHERE username=? AND sport=? ORDER BY created_at DESC", 
                       (username, sport))
        else:
            cur.execute("SELECT id, sport, name, is_projection, created_at FROM datasets WHERE username=? ORDER BY created_at DESC", 
                       (username,))
        datasets = cur.fetchall()
        con.close()
        return datasets
    except Exception as e:
        st.error(f"Error al obtener datasets: {str(e)}")
        return []

def delete_dataset(dataset_id: int):
    """Elimina un dataset y todos sus datos relacionados"""
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("DELETE FROM matches WHERE dataset_id=?", (dataset_id,))
        cur.execute("DELETE FROM f1_results WHERE dataset_id=?", (dataset_id,))
        cur.execute("DELETE FROM mlb_games WHERE dataset_id=?", (dataset_id,))
        cur.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
        con.commit()
        con.close()
        return True
    except Exception as e:
        st.error(f"Error al eliminar dataset: {str(e)}")
        return False

def import_csv_to_dataset(df, dataset_id: int, sport: str):
    """Importa datos de un DataFrame CSV a las tablas SQLite"""
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        
        if sport == "La Liga":
            for _, row in df.iterrows():
                cur.execute("""INSERT INTO matches (dataset_id, local, visitante, goles_local, goles_visitante) 
                              VALUES (?, ?, ?, ?, ?)""", 
                           (dataset_id, row['Local'], row['Visitante'], 
                            row['Goles_Local'], row['Goles_Visitante']))
        
        elif sport == "F1":
            for _, row in df.iterrows():
                cur.execute("""INSERT INTO f1_results (dataset_id, piloto, equipo, puntos) 
                              VALUES (?, ?, ?, ?)""", 
                           (dataset_id, row['Piloto'], row['Equipo'], row['Puntos']))
        
        elif sport == "MLB":
            for _, row in df.iterrows():
                cur.execute("""INSERT INTO mlb_games (dataset_id, equipo_local, equipo_visitante, hr_local, hr_visitante) 
                              VALUES (?, ?, ?, ?, ?)""", 
                           (dataset_id, row['Equipo_Local'], row['Equipo_Visitante'], 
                            row['HR_Local'], row['HR_Visitante']))
        
        elif sport == "NFL":
            for _, row in df.iterrows():
                cur.execute("""INSERT INTO matches (dataset_id, local, visitante, puntos_local, puntos_visitante) 
                              VALUES (?, ?, ?, ?, ?)""", 
                           (dataset_id, row['Local'], row['Visitante'], 
                            row['Puntos_Local'], row['Puntos_Visitante']))
        
        con.commit()
        con.close()
        return True
    except Exception as e:
        st.error(f"Error al importar datos: {str(e)}")
        return False

def get_dataset_data(dataset_id: int, sport: str):
    """Obtiene los datos de un dataset como DataFrame"""
    try:
        con = sqlite3.connect(DB_PATH)
        
        if sport == "La Liga":
            df = pd.read_sql_query("""SELECT local AS Local, visitante AS Visitante, 
                                     goles_local AS Goles_Local, goles_visitante AS Goles_Visitante 
                                     FROM matches WHERE dataset_id=?""", con, params=(dataset_id,))
        elif sport == "F1":
            df = pd.read_sql_query("""SELECT piloto AS Piloto, equipo AS Equipo, puntos AS Puntos 
                                     FROM f1_results WHERE dataset_id=?""", con, params=(dataset_id,))
        elif sport == "MLB":
            df = pd.read_sql_query("""SELECT equipo_local AS Equipo_Local, equipo_visitante AS Equipo_Visitante,
                                     hr_local AS HR_Local, hr_visitante AS HR_Visitante 
                                     FROM mlb_games WHERE dataset_id=?""", con, params=(dataset_id,))
        elif sport == "NFL":
            df = pd.read_sql_query("""SELECT local AS Local, visitante AS Visitante,
                                     puntos_local AS Puntos_Local, puntos_visitante AS Puntos_Visitante 
                                     FROM matches WHERE dataset_id=?""", con, params=(dataset_id,))
        else:
            df = pd.DataFrame()
        
        con.close()
        return df
    except Exception as e:
        st.error(f"Error al obtener datos del dataset: {str(e)}")
        return pd.DataFrame()

from modules.utils import FREE_SCHEMAS, validate_schema, compute_standings_laliga, compute_f1_points, compute_mlb_summary, compute_nfl_table, merge_laliga_with_projections, merge_concat

st.set_page_config(page_title="Sports Templates Freemium", page_icon="🏟️", layout="wide")

st.title("🏟️ Sports Templates Freemium — Excel Digestor")
st.caption("Carga datos *ficticios o propios* con **esquemas reales**, genera Excel y **simula con tus proyecciones**.")

# ---- Simple login (username-only) ----
if "username" not in st.session_state:
    st.session_state["username"] = ""

with st.sidebar:
    st.header("👤 Usuario")
    st.session_state["username"] = st.text_input("Username (temporal)", value=st.session_state["username"] or "salvador")
    if st.session_state["username"]:
        st.success(f"Conectado como: {st.session_state['username']}")
    else:
        st.warning("Ingresa un username para guardar escenarios.")

    # Billing shortcut
    with st.expander("💳 Suscripción (Stripe)"):
        st.caption("Define STRIPE_* como variables de entorno al desplegar.")
        # Admin/local helper to marcar Premium (para demos)
        if os.getenv('ENABLE_LOCAL_PREMIUM_SWITCH','false').lower() in ('1','true','yes','on'):
            if st.button('Marcar usuario como PREMIUM (local)'):
                set_premium(st.session_state.get('username',''), True)
                st.success('Usuario marcado como PREMIUM en SQLite.')
        try:
            from billing.stripe_helpers import get_checkout_session_url
            if st.button("Ir a Checkout"):
                url = get_checkout_session_url(st.session_state["username"] or "anon")
                st.markdown(f"[Abrir Checkout]({url})")
        except Exception as e:
            st.error(f"No se pudo preparar Stripe: {e}")


with st.sidebar:
    # Premium status & demo override
    demo_env = os.getenv("DEMO_PREMIUM", "false").lower() in ("1","true","yes","on")
    st.header("🔐 Plan")
    # Compute effective premium
    _user = st.session_state.get("username","")
    premium_flag = is_premium(_user) or demo_env
    st.session_state["__premium_flag"] = premium_flag
    if premium_flag and demo_env and not is_premium(_user):
        st.info("Premium DEMO activo por entorno (DEMO_PREMIUM).")
    st.markdown(f"**Estado:** {'✅ Premium' if premium_flag else '🆓 Free'}")
    st.divider()

    st.header("🏁 Elegir deporte")
    sport = st.selectbox("Liga/Deporte", list(FREE_SCHEMAS.keys()))
    st.markdown("**Esquema esperado:**")
    st.code(", ".join(FREE_SCHEMAS[sport]), language="text")
    st.divider()
    st.caption("Tip: Descarga los CSV de ejemplo en la pestaña 'Demo & Datos'.")

tabs = st.tabs([
    "🏟️ Demo & Datos",
    "📈 Visualización básica", 
    "🧪 Proyecciones (simula)",
    "📥 Generar Excel",
    "🔒 Zona Premium",
    "🗂️ Administrar Templates",
    "🗄️ Gestión Datasets"
])

def _demo_paths():
    return {
        "La Liga":"data/la_liga_demo.csv",
        "F1":"data/f1_demo.csv",
        "MLB":"data/mlb_demo.csv",
        "NFL":"data/nfl_demo.csv",
    }

def _proj_template_paths():
    return {
        "La Liga":"data/plantilla_proyecciones_la_liga.csv",
        "F1":"data/plantilla_proyecciones_f1.csv",
        "MLB":"data/plantilla_proyecciones_mlb.csv",
        "NFL":"data/plantilla_proyecciones_nfl.csv",
    }

with tabs[0]:
    st.subheader("Demo & Datos")
    demo_paths = _demo_paths()
    st.markdown("Descarga un **CSV de ejemplo** con datos ficticios:")
    demo_file_path = demo_paths.get(sport)
    if demo_file_path and os.path.exists(demo_file_path):
        st.download_button(
            "Descargar CSV demo "+sport,
            open(demo_file_path,"rb"),
            file_name=f"{sport.lower().replace(' ','_')}_demo.csv"
        )
    else:
        st.warning(f"No hay demo disponible para {sport}.")
    
    st.markdown("### Gestión de Datasets")
    st.markdown("Carga y gestiona tus datos directamente en la base de datos SQLite.")
    
    # Selector de dataset existente
    username = st.session_state.get("username", "")
    datasets = get_datasets(username, sport)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        if datasets:
            dataset_options = {f"{d[2]} ({'Proyección' if d[3] else 'Base'}) - {d[4][:10]}": d[0] 
                             for d in datasets}
            selected_dataset_name = st.selectbox("Dataset activo", list(dataset_options.keys()))
            selected_dataset_id = dataset_options.get(selected_dataset_name)
            st.session_state["selected_dataset_id"] = selected_dataset_id
        else:
            st.info("No hay datasets para este deporte. Crea uno nuevo subiendo un CSV.")
            st.session_state["selected_dataset_id"] = None
    
    with col2:
        if datasets and st.button("🗑️ Eliminar Dataset"):
            if delete_dataset(st.session_state.get("selected_dataset_id")):
                st.success("Dataset eliminado correctamente")
                st.rerun()
    
    # Carga de nuevo CSV
    st.markdown("### Subir nuevo CSV")
    dataset_name = st.text_input("Nombre del dataset", value=f"{sport} - {pd.Timestamp.now().strftime('%Y%m%d_%H%M')}")
    is_projection = st.checkbox("Es una proyección (datos futuros)")
    file = st.file_uploader("Sube CSV", type=["csv"], key="uploader_data")
    
    if file and dataset_name:
        try:
            df = pd.read_csv(file)
            # Validar esquema
            expected_cols = FREE_SCHEMAS.get(sport) or FREE_SCHEMAS.get(sport.replace(' ',''))
            if expected_cols and not set(expected_cols).issubset(df.columns):
                st.error(f"El archivo no tiene el esquema correcto. Se esperaban las columnas: {', '.join(expected_cols)}. Columnas encontradas: {', '.join(df.columns)}")
            else:
                # Crear dataset y guardar datos
                dataset_id = create_dataset(username, sport, dataset_name, is_projection)
                if dataset_id and import_csv_to_dataset(df, dataset_id, sport):
                    st.success(f"Dataset '{dataset_name}' creado con {len(df)} filas.")
                    st.session_state["selected_dataset_id"] = dataset_id
                    st.rerun()
        except Exception as e:
            st.error(f"Error al cargar el archivo CSV: {str(e)}")
            st.info("Asegúrate de que el archivo esté en formato CSV válido.")
    
    # Mostrar datos del dataset seleccionado
    if st.session_state.get("selected_dataset_id"):
        dataset_data = get_dataset_data(st.session_state["selected_dataset_id"], sport)
        if not dataset_data.empty:
            st.markdown("### Vista previa de datos")
            st.dataframe(dataset_data.head(50), use_container_width=True)
            st.caption(f"Mostrando primeras 50 filas de {len(dataset_data)} total")

    # Sección pública para descargar templates base
    st.markdown("---")
    st.markdown("### Descarga directa de templates base (encabezados)")
    for key, cols in FREE_SCHEMAS.items():
        template_path = os.path.join("data", "templates", key, f"template_{key.lower().replace(' ','_')}_base.csv")
        if os.path.exists(template_path):
            with open(template_path, "rb") as f:
                st.download_button(
                    f"Descargar template base {key}",
                    f,
                    file_name=f"template_{key.lower().replace(' ','_')}_base.csv",
                    key=f"dl_base_{key}"
                )
        else:
            st.info(f"No hay template base disponible para {key}.")

with tabs[1]:
    st.subheader("Visualización básica")
    dataset_id = st.session_state.get("selected_dataset_id")
    
    if not dataset_id:
        st.info("Selecciona un dataset en la pestaña 'Demo & Datos'.")
    else:
        df = get_dataset_data(dataset_id, sport)
        if df.empty:
            st.warning("El dataset seleccionado no tiene datos.")
        else:
            missing, extra, expected = validate_schema(df, sport)
            if missing:
                st.error(f"Columnas faltantes: {missing}")
            else:
                if sport=="La Liga":
                    table = compute_standings_laliga(df)
                    st.markdown("**Tabla de posiciones (regla 3-1-0):**")
                    st.dataframe(table, use_container_width=True)
                    st.bar_chart(table.set_index("Equipo")["PTS"])
                elif sport=="F1":
                    drv, cons = compute_f1_points(df)
                    col1,col2 = st.columns(2)
                    with col1:
                        st.markdown("**Pilotos:**")
                        st.dataframe(drv, use_container_width=True)
                        st.bar_chart(drv.set_index("Piloto")["Puntos"])
                    with col2:
                        st.markdown("**Constructores:**")
                        st.dataframe(cons, use_container_width=True)
                        st.bar_chart(cons.set_index("Equipo")["Puntos"])
                elif sport=="MLB":
                    summ = compute_mlb_summary(df)
                    st.markdown("**Resumen por equipo (ficticio):**")
                    st.dataframe(summ, use_container_width=True)
                    st.bar_chart(summ.set_index("Equipo")["R"])
                elif sport=="NFL":
                    tbl = compute_nfl_table(df)
                    st.markdown("**Tabla NFL (ficticia):**")
                    st.dataframe(tbl, use_container_width=True)
                    st.bar_chart(tbl.set_index("Equipo")["W"])

with tabs[2]:
    st.subheader("Proyecciones (simula con datasets combinados)")
    st.markdown("1) **Selecciona un dataset base** (datos reales)\n\n2) **Selecciona un dataset de proyección** (escenarios futuros)\n\n3) **Combína ambos** para ver resultados simulados")
    
    username = st.session_state.get("username", "")
    datasets = get_datasets(username, sport)
    
    # Separar datasets base y proyecciones
    base_datasets = [(d[0], d[2], d[4]) for d in datasets if not d[3]]  # is_projection = 0
    proj_datasets = [(d[0], d[2], d[4]) for d in datasets if d[3]]      # is_projection = 1
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Dataset Base (datos reales):**")
        if base_datasets:
            base_options = {f"{name} - {date[:10]}": id for id, name, date in base_datasets}
            selected_base = st.selectbox("Selecciona dataset base", list(base_options.keys()))
            base_dataset_id = base_options.get(selected_base)
        else:
            st.warning("No hay datasets base disponibles")
            base_dataset_id = None
    
    with col2:
        st.markdown("**Dataset Proyección (escenarios):**")
        if proj_datasets:
            proj_options = {f"{name} - {date[:10]}": id for id, name, date in proj_datasets}
            selected_proj = st.selectbox("Selecciona dataset proyección", list(proj_options.keys()))
            proj_dataset_id = proj_options.get(selected_proj)
        else:
            st.warning("No hay datasets de proyección disponibles")
            proj_dataset_id = None
    
    # Descargar plantilla de proyección
    proj_paths = _proj_template_paths()
    if sport in proj_paths:
        st.download_button(
            "📥 Descargar plantilla de proyección " + sport,
            open(proj_paths[sport],"rb"),
            file_name=f"plantilla_proyecciones_{sport.lower().replace(' ','_')}.csv"
        )
    
    # Procesar simulación si ambos datasets están seleccionados
    if base_dataset_id and proj_dataset_id:
        df_base = get_dataset_data(base_dataset_id, sport)
        df_proj = get_dataset_data(proj_dataset_id, sport)
        
        if df_base.empty or df_proj.empty:
            st.error("Uno de los datasets seleccionados está vacío.")
        else:
            # Validar esquemas
            miss_base, _, _ = validate_schema(df_base, sport)
            miss_proj, _, _ = validate_schema(df_proj, sport)
            
            if miss_base:
                st.error(f"Dataset base inválido. Faltan columnas: {miss_base}")
            elif miss_proj:
                st.error(f"Dataset proyección inválido. Faltan columnas: {miss_proj}")
            else:
                # Combinar datos y calcular resultados
                if sport=="La Liga":
                    sim_df = merge_laliga_with_projections(df_base, df_proj)
                    table = compute_standings_laliga(sim_df)
                    st.success("✅ Simulación aplicada: resultados actualizados con proyecciones.")
                    st.dataframe(table, use_container_width=True)
                    st.bar_chart(table.set_index('Equipo')["PTS"])
                elif sport=="F1":
                    sim_df = merge_concat(df_base, df_proj)
                    drv, cons = compute_f1_points(sim_df)
                    st.success("✅ Simulación aplicada a pilotos y constructores.")
                    col1,col2 = st.columns(2)
                    with col1:
                        st.dataframe(drv, use_container_width=True)
                        st.bar_chart(drv.set_index("Piloto")["Puntos"])
                    with col2:
                        st.dataframe(cons, use_container_width=True)
                        st.bar_chart(cons.set_index("Equipo")["Puntos"])
                elif sport=="MLB":
                    sim_df = merge_concat(df_base, df_proj)
                    summ = compute_mlb_summary(sim_df)
                    st.success("✅ Simulación aplicada.")
                    st.dataframe(summ, use_container_width=True)
                    st.bar_chart(summ.set_index("Equipo")["R"])
                elif sport=="NFL":
                    sim_df = merge_concat(df_base, df_proj)
                    tbl = compute_nfl_table(sim_df)
                    st.success("✅ Simulación aplicada.")
                    st.dataframe(tbl, use_container_width=True)
                    st.bar_chart(tbl.set_index("Equipo")["W"])

                # Opción para descargar Excel simulador
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df_base.to_excel(writer, index=False, sheet_name="DATA_BASE")
                    df_proj.to_excel(writer, index=False, sheet_name="PROYECCIONES")
                    # Resúmenes
                    if sport=="La Liga":
                        compute_standings_laliga(sim_df).to_excel(writer, index=False, sheet_name="TABLA_SIM")
                    elif sport=="F1":
                        d,c = compute_f1_points(sim_df)
                        d.to_excel(writer, index=False, sheet_name="PILOTOS_SIM")
                        c.to_excel(writer, index=False, sheet_name="CONSTRUCTORES_SIM")
                    elif sport=="MLB":
                        compute_mlb_summary(sim_df).to_excel(writer, index=False, sheet_name="RESUMEN_SIM")
                    elif sport=="NFL":
                        compute_nfl_table(sim_df).to_excel(writer, index=False, sheet_name="RESUMEN_SIM")
                
                st.download_button(
                    "⬇️ Descargar Excel Simulador (BASE + PROYECCIONES + RESUMEN)",
                    data=buffer.getvalue(),
                    file_name=f"simulador_{sport.lower().replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    else:
        st.info("Selecciona ambos datasets (base y proyección) para ver la simulación.")
        st.markdown("💡 **Tip:** Crea datasets de proyección marcando la casilla 'Es una proyección' al subir un CSV.")

with tabs[3]:
    st.subheader("Generar Excel (Plantilla Freemium)")
    dataset_id = st.session_state.get("selected_dataset_id")
    
    if not dataset_id:
        st.info("Selecciona un dataset en la pestaña 'Demo & Datos'.")
    else:
        df = get_dataset_data(dataset_id, sport)
        if df.empty:
            st.warning("El dataset seleccionado no tiene datos.")
        else:
            missing, extra, expected = validate_schema(df, sport)
            if missing:
                st.error(f"Columnas faltantes: {missing}")
            else:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="DATA")
                    if sport=="La Liga":
                        compute_standings_laliga(df).to_excel(writer, index=False, sheet_name="TABLA")
                    elif sport=="F1":
                        drv, cons = compute_f1_points(df)
                        drv.to_excel(writer, index=False, sheet_name="PILOTOS")
                        cons.to_excel(writer, index=False, sheet_name="CONSTRUCTORES")
                    elif sport=="MLB":
                        compute_mlb_summary(df).to_excel(writer, index=False, sheet_name="RESUMEN")
                    elif sport=="NFL":
                        compute_nfl_table(df).to_excel(writer, index=False, sheet_name="RESUMEN")
                    notes = pd.DataFrame({"Nota":[
                        "Esta plantilla Freemium usa datos almacenados en SQLite.",
                        "Los datos se gestionan directamente en la aplicación.",
                        "Para simulación, usa la pestaña 'Proyecciones' con datasets combinados.",
                        "Desbloquea Premium para simuladores y dashboards enriquecidos."
                    ]})
                    notes.to_excel(writer, index=False, sheet_name="INSTRUCCIONES")
                st.download_button(
                    "⬇️ Descargar Excel Freemium",
                    data=buffer.getvalue(),
                    file_name=f"plantilla_{sport.lower().replace(' ','_')}_freemium.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("Plantilla Excel generada desde datos SQLite.")


with tabs[4]:
    st.subheader("Zona Premium (demo visual)")
    st.markdown("""
    Aquí aparecerán **simuladores**, **dashboards con slicers** y actualización automática.
    Este bloque se muestra con sombreado para generar el *WOW effect* y conversión.
    """)
    if not st.session_state.get('__premium_flag', False):
        st.warning("Estás en modo Free. Cambia a 'Premium (demo)' en la barra lateral para ver un mockup.")
    else:
        st.success("Premium habilitado.")
        st.markdown("- **Carga masiva de jornadas/carreras** y escenarios múltiples guardados.")
        st.markdown("- **Slicers y estilos** tipo app dentro del Excel (Power Query / Macros).")
        st.info("Versión comercial: macros + auto-actualización + pagos.")

# ---------- NEW PREMIUM TAB: Escenarios & Sensibilidad ----------
premium_tabs = st.tabs(["🅿️ Premium: Escenarios A/B/C","🅿️ Premium: Sensibilidad"])

with premium_tabs[0]:
    st.subheader("Escenarios A/B/C — compara proyecciones")
    st.markdown("Guarda hasta **3 escenarios** con tus proyecciones y compáralos lado a lado.")
    if "escenarios" not in st.session_state:
        st.session_state["escenarios"] = {}

    col_sel, col_label = st.columns([2,1])
    with col_sel:
        sport_s = st.selectbox("Deporte del escenario", list(FREE_SCHEMAS.keys()), key="esc_sport")
    with col_label:
        label = st.selectbox("Etiqueta de escenario", ["A","B","C"], key="esc_label")

    base_df = st.session_state.get("dataframes",{}).get(sport_s)
    proj_file = st.file_uploader("Sube CSV de PROYECCIONES para este escenario", type=["csv"], key=f"proj_{sport_s}_{label}")
    if base_df is None:
        st.info("Primero carga tu CSV base en 'Demo & Datos'.")
    else:
        if proj_file:
            df_proj = pd.read_csv(proj_file)
            miss_base, _, _ = validate_schema(base_df, sport_s)
            miss_proj, _, _ = validate_schema(df_proj, sport_s)
            if miss_base:
                st.error(f"Base inválida. Faltan columnas: {miss_base}")
            elif miss_proj:
                st.error(f"Proyección inválida. Faltan columnas: {miss_proj}")
            else:
                # build simulated df per sport
                if sport_s=="La Liga":
                    sim_df = merge_laliga_with_projections(base_df, df_proj)
                    resumen = compute_standings_laliga(sim_df).rename(columns={"PTS":"PTS_"+label})
                elif sport_s=="F1":
                    sim_df = merge_concat(base_df, df_proj)
                    resumen, cons = compute_f1_points(sim_df)
                    resumen = resumen.rename(columns={"Puntos":"PTS_"+label})
                elif sport_s=="MLB":
                    sim_df = merge_concat(base_df, df_proj)
                    resumen = compute_mlb_summary(sim_df).rename(columns={"R":"R_"+label})
                elif sport_s=="NFL":
                    sim_df = merge_concat(base_df, df_proj)
                    resumen = compute_nfl_table(sim_df).rename(columns={"W":"W_"+label})

                # save scenario
                ensure_user(st.session_state.get('username',''))
                st.session_state["escenarios"].setdefault(sport_s, {})
                st.session_state["escenarios"][sport_s][label] = resumen
                save_scenario(st.session_state.get('username',''), sport_s, label, resumen)
                st.success(f"Escenario {label} guardado para {sport_s} (y persistido).")

    # Comparison if two or more scenarios exist
    persisted = load_scenarios(st.session_state.get('username',''), sport_s)
    st.session_state.setdefault('escenarios',{})
    st.session_state['escenarios'].setdefault(sport_s,{})
    st.session_state['escenarios'][sport_s].update(persisted)
    esc = st.session_state.get("escenarios",{}).get(sport_s, {})
    if len(esc)>=2:
        st.markdown("### Comparativa")
        # merge on entity column
        if sport_s in ["La Liga","NFL","MLB"]:
            # Ensure same "Equipo" key
            combined = None
            for lab,res in esc.items():
                dfk = res.copy()
                key = "Equipo" if "Equipo" in dfk.columns else ("Equipo" if sport_s!="F1" else "Piloto")
                if combined is None:
                    combined = dfk.set_index(key)
                else:
                    combined = combined.join(dfk.set_index(key)[[c for c in dfk.columns if c not in ["Pos"]]], how="outer")
            st.dataframe(combined.fillna(0), use_container_width=True)
            # Choose a metric to chart
            metric = None
            if sport_s=="La Liga":
                metric = [c for c in combined.columns if c.startswith("PTS_")]
            elif sport_s=="MLB":
                metric = [c for c in combined.columns if c.startswith("R_")]
            elif sport_s=="NFL":
                metric = [c for c in combined.columns if c.startswith("W_")]
            if metric:
                st.bar_chart(combined[metric])
        else:  # F1 (Pilotos)
            combined = None
            for lab,res in esc.items():
                dfk = res.copy()  # columns Pos, Piloto, Equipo, PTS_label
                dfk = dfk.set_index("Piloto")
                if combined is None:
                    combined = dfk
                else:
                    combined = combined.join(dfk[[c for c in dfk.columns if c.startswith("PTS_")]], how="outer")
            st.dataframe(combined.fillna(0), use_container_width=True)
            st.bar_chart(combined[[c for c in combined.columns if c.startswith("PTS_")]])

with premium_tabs[1]:
    st.subheader("Análisis de Sensibilidad — ajusta y observa el impacto")
    st.markdown("Aplica un **ajuste incremental** y observa la variación en el ranking/resumen.")

    sport_x = st.selectbox("Deporte", list(FREE_SCHEMAS.keys()), key="sens_sport")
    base_df = st.session_state.get("dataframes",{}).get(sport_x)
    if base_df is None:
        st.info("Primero carga tu CSV base en 'Demo & Datos'.")
    else:
        if sport_x=="La Liga":
            equipo = st.text_input("Equipo a ajustar (exacto como aparece en DATA)", value="Real Madrid")
            delta = st.slider("Goles a sumar por partido (hipotético)", -2, 2, 1)
            sim = base_df.copy()
            mask_home = sim["Local"]==equipo
            mask_away = sim["Visitante"]==equipo
            sim.loc[mask_home,"Goles_Local"] = sim.loc[mask_home,"Goles_Local"] + delta
            sim.loc[mask_away,"Goles_Visitante"] = sim.loc[mask_away,"Goles_Visitante"] + delta
            table = compute_standings_laliga(sim)
            st.dataframe(table, use_container_width=True)
            st.bar_chart(table.set_index("Equipo")["PTS"])
        elif sport_x=="F1":
            piloto = st.text_input("Piloto a ajustar", value="Max Perez")
            delta = st.slider("Puntos a sumar por carrera", -5, 5, 2)
            sim = base_df.copy()
            sim.loc[sim["Piloto"]==piloto,"Puntos"] = sim.loc[sim["Piloto"]==piloto,"Puntos"] + delta
            drv, cons = compute_f1_points(sim)
            col1,col2 = st.columns(2)
            with col1:
                st.dataframe(drv, use_container_width=True)
                st.bar_chart(drv.set_index("Piloto")["Puntos"])
            with col2:
                st.dataframe(cons, use_container_width=True)
                st.bar_chart(cons.set_index("Equipo")["Puntos"])
        elif sport_x=="MLB":
            equipo = st.text_input("Equipo a ajustar", value="Yankees")
            delta = st.slider("Home Runs a sumar por juego", -2, 2, 1)
            sim = base_df.copy()
            sim.loc[sim["Equipo_Local"]==equipo,"HR_Local"] = sim.loc[sim["Equipo_Local"]==equipo,"HR_Local"] + delta
            sim.loc[sim["Equipo_Visitante"]==equipo,"HR_Visitante"] = sim.loc[sim["Equipo_Visitante"]==equipo,"HR_Visitante"] + delta
            summ = compute_mlb_summary(sim)
            st.dataframe(summ, use_container_width=True)
            st.bar_chart(summ.set_index("Equipo")["HR"])
        elif sport_x=="NFL":
            equipo = st.text_input("Equipo a ajustar", value="Cowboys")
            delta = st.slider("Puntos a sumar por juego", -7, 7, 3)
            sim = base_df.copy()
            sim.loc[sim["Local"]==equipo,"Puntos_Local"] = sim.loc[sim["Local"]==equipo,"Puntos_Local"] + delta
            sim.loc[sim["Visitante"]==equipo,"Puntos_Visitante"] = sim.loc[sim["Visitante"]==equipo,"Puntos_Visitante"] + delta
            tbl = compute_nfl_table(sim)
            st.dataframe(tbl, use_container_width=True)
            st.bar_chart(tbl.set_index("Equipo")["W"])

with tabs[5]:
    st.subheader("🗂️ Administrar Templates personalizados")
    st.markdown("Sube, descarga o elimina tus propios templates (CSV) para cada deporte.")
    sport_sel = st.selectbox("Deporte para template", list(FREE_SCHEMAS.keys()), key="template_sport")
    template_dir = os.path.join("data", "templates", sport_sel)
    os.makedirs(template_dir, exist_ok=True)

    # Subir template
    uploaded_template = st.file_uploader("Sube un template CSV", type=["csv"], key="uploader_template")
    if uploaded_template:
        save_path = os.path.join(template_dir, uploaded_template.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_template.read())
        st.success(f"Template '{uploaded_template.name}' guardado para {sport_sel}.")

    # Listar y descargar templates
    templates = [f for f in os.listdir(template_dir) if f.endswith('.csv')]
    if templates:
        st.markdown("### Templates disponibles:")
        for tfile in templates:
            tpath = os.path.join(template_dir, tfile)
            col1, col2 = st.columns([3,1])
            with col1:
                st.markdown(f"- {tfile}")
            with col2:
                with open(tpath, "rb") as f:
                    st.download_button("Descargar", f, file_name=tfile, key=f"dl_{tfile}")
                if st.button("Eliminar", key=f"del_{tfile}"):
                    os.remove(tpath)
                    st.warning(f"Template '{tfile}' eliminado.")
    else:
        st.info("No hay templates personalizados para este deporte.")
        # Generar template base con encabezados
        import io
        base_csv = io.StringIO()
        pd.DataFrame(columns=FREE_SCHEMAS[sport_sel]).to_csv(base_csv, index=False)
        st.download_button(
            "Descargar template base (encabezados)",
            base_csv.getvalue(),
            file_name=f"template_{sport_sel.lower().replace(' ','_')}_base.csv",
            mime="text/csv",
            key=f"dl_base_{sport_sel}"
        )
with tabs[6]:
    st.subheader("🗄️ Gestión Avanzada de Datasets")
    st.markdown("Visualiza y gestiona todos tus datasets almacenados en SQLite.")
    
    username = st.session_state.get("username", "")
    if not username:
        st.warning("Inicia sesión para gestionar datasets.")
    else:
        # Mostrar todos los datasets del usuario
        all_datasets = get_datasets(username)
        
        if not all_datasets:
            st.info("No tienes datasets creados aún.")
        else:
            st.markdown("### Todos tus datasets")
            
            # Crear DataFrame para mostrar datasets
            datasets_df = pd.DataFrame(all_datasets, columns=["ID", "Deporte", "Nombre", "Es_Proyección", "Fecha_Creación"])
            datasets_df["Tipo"] = datasets_df["Es_Proyección"].apply(lambda x: "Proyección" if x else "Base")
            datasets_df["Fecha"] = pd.to_datetime(datasets_df["Fecha_Creación"]).dt.strftime("%Y-%m-%d %H:%M")
            
            display_df = datasets_df[["ID", "Deporte", "Nombre", "Tipo", "Fecha"]].copy()
            st.dataframe(display_df, use_container_width=True)
            
            # Gestión individual de datasets
            st.markdown("### Acciones en Dataset")
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                dataset_to_manage = st.selectbox(
                    "Seleccionar dataset", 
                    options=[(row["ID"], f"{row['Nombre']} ({row['Deporte']}) - {row['Tipo']}") 
                            for _, row in datasets_df.iterrows()],
                    format_func=lambda x: x[1]
                )
                selected_id = dataset_to_manage[0] if dataset_to_manage else None
            
            with col2:
                if st.button("👁️ Ver Datos") and selected_id:
                    dataset_info = datasets_df[datasets_df["ID"] == selected_id].iloc[0]
                    dataset_data = get_dataset_data(selected_id, dataset_info["Deporte"])
                    st.markdown(f"#### Datos del dataset: {dataset_info['Nombre']}")
                    st.dataframe(dataset_data, use_container_width=True)
            
            with col3:
                if st.button("🗑️ Eliminar") and selected_id:
                    if delete_dataset(selected_id):
                        st.success("Dataset eliminado correctamente")
                        st.rerun()
            
            # Estadísticas generales
            st.markdown("### Estadísticas")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Datasets", len(all_datasets))
            with col2:
                base_count = sum(1 for d in all_datasets if not d[3])
                st.metric("Datasets Base", base_count)
            with col3:
                proj_count = sum(1 for d in all_datasets if d[3])
                st.metric("Proyecciones", proj_count)
            with col4:
                sports_count = len(set(d[1] for d in all_datasets))
                st.metric("Deportes", sports_count)