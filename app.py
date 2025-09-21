import streamlit as st
import os
import pandas as pd
from io import BytesIO
import sqlite3, json, os
DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")

def ensure_tables():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
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
    con.commit()
    con.close()

# Crear tablas al inicio de la app
ensure_tables()

def ensure_user(username: str):
    if not username:
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO users(username) VALUES(?)", (username,))
    con.commit()
    con.close()

def save_scenario(username: str, sport: str, label: str, resumen_df):
    if not username:
        return False
    payload = resumen_df.to_json(orient="records", force_ascii=False)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""INSERT INTO scenarios(username, sport, label, payload_json)
                   VALUES(?,?,?,?)""", (username, sport, label, payload))
    con.commit()
    con.close()
    return True

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
    "🗂️ Administrar Templates"
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
    st.markdown("O **sube tu propio CSV** con el esquema indicado.")
    file = st.file_uploader("Sube CSV base (DATA)", type=["csv"], key="uploader_data")
    if "dataframes" not in st.session_state:
        st.session_state["dataframes"] = {}
    if file:
        df = pd.read_csv(file)
        # Validar esquema
        expected_cols = FREE_SCHEMAS.get(sport) or FREE_SCHEMAS.get(sport.replace(' ',''))
        if expected_cols and not set(expected_cols).issubset(df.columns):
            st.error(f"El archivo no tiene el esquema correcto. Se esperaban las columnas: {', '.join(expected_cols)}. Columnas encontradas: {', '.join(df.columns)}")
        else:
            st.session_state["dataframes"][sport] = df
            st.success(f"{len(df)} filas cargadas para {sport}.")
            st.dataframe(df.head(50), use_container_width=True)

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
    df = st.session_state.get("dataframes",{}).get(sport)
    if df is None:
        st.info("Carga un CSV en la pestaña 'Demo & Datos'.")
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
    st.subheader("Proyecciones (simula con tus propias plantillas)")
    st.markdown("1) **Descarga la plantilla de proyección** del deporte elegido.\n\n2) **Rellénala** con tus supuestos.\n\n3) **Súbela** aquí para recalcular tablas con esos escenarios.")
    proj_paths = _proj_template_paths()
    if sport in proj_paths:
        st.download_button(
            "Descargar plantilla de proyección "+sport,
            open(proj_paths[sport],"rb"),
            file_name=f"plantilla_proyecciones_{sport.lower().replace(' ','_')}.csv"
        )
    else:
        st.warning(f"No hay plantilla de proyección disponible para {sport}.")
    proj_file = st.file_uploader("Sube CSV de PROYECCIONES", type=["csv"], key="uploader_proj")
    df = st.session_state.get("dataframes",{}).get(sport)
    if df is None:
        st.info("Primero carga tu CSV base en 'Demo & Datos'.")
    elif proj_file is None:
        st.warning("Sube tu archivo de proyecciones para simular.")
    else:
        df_proj = pd.read_csv(proj_file)
        # Validate schemas
        miss_base, _, _ = validate_schema(df, sport)
        miss_proj, _, _ = validate_schema(df_proj, sport)
        if miss_base:
            st.error(f"Base inválida. Faltan columnas: {miss_base}")
        elif miss_proj:
            st.error(f"Proyección inválida. Faltan columnas: {miss_proj}")
        else:
            if sport=="La Liga":
                sim_df = merge_laliga_with_projections(df, df_proj)
                table = compute_standings_laliga(sim_df)
                st.success("Simulación aplicada: resultados actualizados con tus proyecciones.")
                st.dataframe(table, use_container_width=True)
                st.bar_chart(table.set_index('Equipo')["PTS"])
            elif sport=="F1":
                sim_df = merge_concat(df, df_proj)
                drv, cons = compute_f1_points(sim_df)
                st.success("Simulación aplicada a pilotos y constructores (concat de proyecciones).")
                col1,col2 = st.columns(2)
                with col1:
                    st.dataframe(drv, use_container_width=True)
                    st.bar_chart(drv.set_index("Piloto")["Puntos"])
                with col2:
                    st.dataframe(cons, use_container_width=True)
                    st.bar_chart(cons.set_index("Equipo")["Puntos"])
            elif sport=="MLB":
                sim_df = merge_concat(df, df_proj)
                summ = compute_mlb_summary(sim_df)
                st.success("Simulación aplicada (concat de proyecciones).")
                st.dataframe(summ, use_container_width=True)
                st.bar_chart(summ.set_index("Equipo")["R"])
            elif sport=="NFL":
                sim_df = merge_concat(df, df_proj)
                tbl = compute_nfl_table(sim_df)
                st.success("Simulación aplicada (concat de proyecciones).")
                st.dataframe(tbl, use_container_width=True)
                st.bar_chart(tbl.set_index("Equipo")["W"])

            # Offer to download a Simulator Excel with DATA + PROYECCIONES + RESUMEN
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="DATA")
                df_proj.to_excel(writer, index=False, sheet_name="PROYECCIONES")
                # summaries
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
                "⬇️ Descargar Excel Simulador (DATA + PROYECCIONES + RESUMEN)",
                data=buffer.getvalue(),
                file_name=f"simulador_{sport.lower().replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

with tabs[3]:
    st.subheader("Generar Excel (Plantilla Freemium)")
    df = st.session_state.get("dataframes",{}).get(sport)
    if df is None:
        st.info("Carga un CSV en la pestaña 'Demo & Datos'.")
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
                    "Esta plantilla Freemium usa datos ficticios con esquema real.",
                    "Reemplaza la hoja DATA con tus datos respetando las columnas esperadas.",
                    "Para simulación, usa la pestaña 'Proyecciones (simula)' y descarga el Excel Simulador.",
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
            st.success("Plantilla Excel generada.")


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
    if sport_s not in st.session_state["escenarios"]:
        st.session_state["escenarios"][sport_s] = {}

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
