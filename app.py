import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import urllib.parse

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ERP Perfumería - Final", layout="wide")

# ==============================================================================
# 🔐 CONEXIÓN A BASE DE DATOS (VIA TRANSACTION POOLER - PUERTO 6543)
# ==============================================================================

# 1. CREDENCIALES EXACTAS PARA EL POOLER
# Nota: Si el host 'aws-0' no funciona, cámbialo a 'aws-1' según lo que diga Supabase
DB_HOST = "aws-1-us-east-1.pooler.supabase.com" 
DB_NAME = "postgres"
DB_USER = "postgres.nzlysybivtiumentgpvi" # <--- Usuario especial del pooler
DB_PORT = "6543" 
DB_PASS = ".pJUb+(3pnYqBH1yhM" # <--- ¡La que creaste recientemente!

# 2. CONSTRUCCIÓN DE URL SEGURA
try:
    encoded_password = urllib.parse.quote_plus(DB_PASS)
    # Importante: Usamos postgresql+psycopg2 y sslmode require
    DB_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

    @st.cache_resource
    def get_engine():
        # pool_pre_ping ayuda a detectar si la conexión se cerró por inactividad
        return create_engine(DB_URL, pool_pre_ping=True)

    engine = get_engine()
    
    # Test de conexión
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    st.sidebar.success("✅ Conectado a la Nube (Puerto 6543)")

except Exception as e:
    st.error("❌ Error de Conexión")
    if "Circuit breaker open" in str(e):
        st.warning("⚠️ Supabase bloqueó el acceso temporalmente por demasiados errores. Espera 15 minutos sin intentar conectar.")
    else:
        st.info("Asegúrate de haber seleccionado 'Transaction Pooler' en Supabase y que la contraseña sea correcta.")
    st.code(str(e))
    st.stop()
# ==============================================================================
# LÓGICA DE NEGOCIO Y CONVERSIONES
# ==============================================================================
def run_query(query, params=None):
    with engine.connect() as conn:
        if params: conn.execute(text(query), params)
        else: conn.execute(text(query))
        conn.commit()

def get_data(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

def calcular_sin_iva(monto, tiene_iva):
    return monto / 1.12 if (tiene_iva and monto > 0) else monto

def obtener_costo_convertido(mp_id, unidad_destino):
    """Calcula el costo neto (sin IVA) y aplica conversiones de unidad."""
    df_mp = get_data("SELECT costo_unitario, unidad_medida, tiene_iva FROM materias_primas WHERE id=:id", {'id': mp_id})
    if df_mp.empty: return 0.0
    
    # 1. Obtenemos el costo base
    costo_base = float(df_mp.iloc[0]['costo_unitario'])
    unidad_base = df_mp.iloc[0]['unidad_medida']
    tiene_iva = bool(df_mp.iloc[0]['tiene_iva'])
    
    # 2. APLICAMOS LÓGICA DE IVA (Si tiene, lo quitamos: Q / 1.12)
    if tiene_iva:
        costo_base = costo_base / 1.12
    
    # Si la unidad es la misma, no hay conversión
    if unidad_base == unidad_destino or unidad_destino is None:
        return costo_base
    
    # Buscar factor en tabla conversiones
    conv = get_data("SELECT factor_multiplicador FROM conversiones WHERE unidad_origen=:u1 AND unidad_destino=:u2", 
                    {'u1': unidad_base, 'u2': unidad_destino})
    
    if not conv.empty:
        return costo_base / float(conv.iloc[0]['factor_multiplicador'])
    
    return costo_base

def check_and_seed_data():
    try:
        df = get_data("SELECT id FROM config_admin WHERE id=1")
        if df.empty:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO config_admin (id, salario_base, p_prestaciones, num_empleados) VALUES (1, 5000, 41.83, 3) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_ventas (id, salario_base, p_prestaciones, num_empleados) VALUES (1, 3500, 41.83, 2) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_mod (id, salario_base, p_prestaciones, num_operarios, horas_mes) VALUES (1, 4252.28, 41.83, 2, 176) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_global (id, unidades_promedio_mes) VALUES (1, 5000) ON CONFLICT DO NOTHING"))
                conn.commit()
    except Exception as e:
        pass

check_and_seed_data()

def obtener_volumen_referencia():
    """Retorna la producción real del mes o el promedio manual si no hay registros."""
    mes_act = pd.to_datetime("today").month
    anio_act = pd.to_datetime("today").year
    real = get_data("SELECT SUM(cantidad_producida) FROM registro_produccion WHERE EXTRACT(MONTH FROM fecha) = :m AND EXTRACT(YEAR FROM fecha) = :a", {'m': mes_act, 'a': anio_act}).iloc[0,0]
    
    if real and real > 0:
        return float(real), "Real (Mes Actual)"
    manual = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
    return float(manual), "Teórico (Promedio)"
# ==============================================================================
# INTERFAZ
# ==============================================================================
st.title("☁️ ERP Perfumería")

tabs = st.tabs(["👥 Nóminas", "💰 Costos Fijos", "🌿 Materias Primas", "📦 Fábrica (Prod)", "🔎 Ficha Técnica", "⚙️ Ajustes", "🚀 Producción Diaria"])
# TAB 1: NÓMINAS

# ------------------------------------------------------------------

with tabs[0]:

    st.header("Configuración de Personal")

    c1, c2, c3 = st.columns(3)

    

    def render_nomina_form(titulo, tabla, key_prefix):

        with st.container(border=True):

            st.subheader(titulo)

            try:

                # Query seguro

                col_emp = "num_operarios" if tabla == 'config_mod' else "num_empleados"

                cols = f"salario_base, p_prestaciones, {col_emp}"

                if tabla == 'config_mod': cols += ", horas_mes"

                

                df = get_data(f"SELECT {cols} FROM {tabla} WHERE id=1")

                

                if not df.empty:

                    data = df.iloc[0]

                    with st.form(f"form_{key_prefix}"):

                        s = st.number_input("Salario", value=float(data['salario_base']))

                        p = st.number_input("% Prestaciones", value=float(data['p_prestaciones']))

                        n = st.number_input("Nº Personas", value=int(data[col_emp]))

                        

                        h = 0.0

                        if tabla == 'config_mod':

                            h = st.number_input("Horas/Mes", value=float(data['horas_mes']))



                        if st.form_submit_button("Guardar"):

                            if tabla == 'config_mod':

                                run_query(f"UPDATE {tabla} SET salario_base=:s, p_prestaciones=:p, num_operarios=:n, horas_mes=:h WHERE id=1", {'s':s, 'p':p, 'n':n, 'h':h})

                            else:

                                run_query(f"UPDATE {tabla} SET salario_base=:s, p_prestaciones=:p, num_empleados=:n WHERE id=1", {'s':s, 'p':p, 'n':n})

                            st.rerun()

                else:

                    st.warning("⚠️ Datos vacíos. Recarga la página para auto-reparar.")

            except Exception as e: st.error(f"Error DB: {e}")



    with c1: render_nomina_form("🏢 Admin", "config_admin", "adm")

    with c2: render_nomina_form("🛍️ Ventas", "config_ventas", "ven")

    with c3: render_nomina_form("🏭 Producción", "config_mod", "mod")



# --- TAB 2: COSTOS FIJOS (RESTAURADO CON TOTALES) ---

with tabs[1]:

    st.header("Matriz de Costos Fijos")

    

    with st.expander("📂 Cargar Gastos (CSV)"):

        with st.form("csv_cf", clear_on_submit=True):

            f = st.file_uploader("CSV", type="csv")

            borrar = st.checkbox("Borrar tabla antes de cargar", value=False)

            if st.form_submit_button("Cargar") and f:

                if borrar: run_query("TRUNCATE TABLE costos_fijos RESTART IDENTITY")

                df = pd.read_csv(f)

                for _, r in df.iterrows():

                    run_query("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (:c, :t, :pa, :pv, :pp)",

                              {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod']})

                st.success("Cargado"); st.rerun()



    try:

        df_man = get_data("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos ORDER BY id")

        

        # Lógica de Filas Auto de Nóminas

        filas_auto = []

        adm = get_data("SELECT salario_base, p_prestaciones, num_empleados FROM config_admin WHERE id=1").iloc[0]

        t_adm = float(adm['salario_base'] * adm['num_empleados'])

        filas_auto.append({'id': -1, 'concepto': '⚡ Nómina: Salarios Admin', 'total_mensual': t_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})

        filas_auto.append({'id': -2, 'concepto': '⚡ Nómina: Prestaciones Admin', 'total_mensual': t_adm*(adm['p_prestaciones']/100), 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})

        

        ven = get_data("SELECT salario_base, p_prestaciones, num_empleados FROM config_ventas WHERE id=1").iloc[0]

        t_ven = float(ven['salario_base'] * ven['num_empleados'])

        filas_auto.append({'id': -3, 'concepto': '⚡ Nómina: Salarios Ventas', 'total_mensual': t_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})

        filas_auto.append({'id': -4, 'concepto': '⚡ Nómina: Prestaciones Ventas', 'total_mensual': t_ven*(ven['p_prestaciones']/100), 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})



        df_show = pd.concat([df_man, pd.DataFrame(filas_auto)], ignore_index=True)

        ed_df = st.data_editor(df_show, disabled=["id"], num_rows="dynamic", key="cf_ed", column_config={"total_mensual": st.column_config.NumberColumn(format="Q%.2f")})

        

        if st.button("💾 Guardar Matriz"):

            ids_now = set()

            for _, r in ed_df.iterrows():

                if r['id'] >= 0:

                    ids_now.add(r['id'])

                    run_query("UPDATE costos_fijos SET concepto=:c, total_mensual=:t, p_admin=:pa, p_ventas=:pv, p_prod=:pp WHERE id=:id",

                            {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod'], 'id':r['id']})

                elif pd.isna(r['id']):

                    run_query("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (:c, :t, :pa, :pv, :pp)",

                            {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod']})

            

            ids_old = set(df_man['id'].tolist())

            to_del = list(ids_old - ids_now)

            if to_del:

                todel = tuple(to_del)

                if len(to_del)==1: todel = f"({to_del[0]})"

                run_query(f"DELETE FROM costos_fijos WHERE id IN {todel}")

            st.success("Guardado"); st.rerun()



        # --- SECCIÓN DE TOTALES RESTAURADA ---

        ed_df['M_Admin'] = ed_df['total_mensual'] * (ed_df['p_admin']/100)

        ed_df['M_Ventas'] = ed_df['total_mensual'] * (ed_df['p_ventas']/100)

        ed_df['M_Prod'] = ed_df['total_mensual'] * (ed_df['p_prod']/100)

        

        st.divider()

        st.subheader("📊 Resumen Mensual")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("TOTAL GASTOS", f"Q{ed_df['total_mensual'].sum():,.2f}")

        c2.metric("Total Admin", f"Q{ed_df['M_Admin'].sum():,.2f}")

        c3.metric("Total Ventas", f"Q{ed_df['M_Ventas'].sum():,.2f}")

        c4.metric("Total Prod (CIF)", f"Q{ed_df['M_Prod'].sum():,.2f}")

        

        st.write("---")

        u_prom = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]

        u_base = st.number_input("Unidades Base", value=int(u_prom))

        if u_base != u_prom:

            run_query("UPDATE config_global SET unidades_promedio_mes=:u WHERE id=1", {'u':u_base})

            st.rerun()

            

        cif_unit = ed_df['M_Prod'].sum() / u_base if u_base > 0 else 0

        st.success(f"🎯 CIF Unitario: **Q{cif_unit:,.2f}**")



    except Exception as e: st.error(f"Error cargando matriz: {e}")
# --- TAB 3: MATERIAS PRIMAS (CON IVA Y ELIMINACIÓN) ---
with tabs[2]:
    st.header("🌿 Inventario Materia Prima")
    
    # 1. BUSCADOR DINÁMICO
    busqueda = st.text_input("🔍 Buscar por código o nombre:", placeholder="Ej: REPH... o Alcohol")
    
    # Recuperamos los datos de la DB (Añadimos 'tiene_iva')
    query_base = "SELECT id, codigo_interno, nombre, categoria, unidad_medida, costo_unitario, tiene_iva FROM materias_primas"
    df_mps = get_data(f"{query_base} ORDER BY nombre")
    ids_antes = set(df_mps['id'].dropna().unique()) # Guardamos los IDs actuales
    
    if busqueda:
        df_filtrado = df_mps[
            df_mps['nombre'].str.contains(busqueda, case=False, na=False) | 
            df_mps['codigo_interno'].str.contains(busqueda, case=False, na=False)
        ]
    else:
        df_filtrado = df_mps

    # 2. EDITOR DE DATOS
    # Configuramos la columna IVA para que sea un checkbox
    ed_mp = st.data_editor(
        df_filtrado, 
        num_rows="dynamic", 
        key="mp_ed_v3", 
        disabled=["id"],
        use_container_width=True,
        column_config={
            "tiene_iva": st.column_config.CheckboxColumn("¿Tiene IVA?", default=False),
            "costo_unitario": st.column_config.NumberColumn("Costo (Q)", format="%.4f")
        }
    )
    
    # 3. LOGICA DE ACTUALIZACIÓN Y ELIMINACIÓN
    st.write("---")
    col_save, col_check = st.columns([1, 2])
    
    with col_check:
        confirmar = st.checkbox("✅ Confirmo que los precios (sin IVA si aplica) y datos son correctos.")
    
    with col_save:
        if st.button("💾 Sincronizar Cambios", disabled=not confirmar, type="primary"):
            try:
                # A. Detectar y eliminar filas borradas
                ids_ahora = set(ed_mp['id'].dropna().unique())
                ids_a_eliminar = ids_antes - ids_ahora
                
                if ids_a_eliminar:
                    for id_del in ids_a_eliminar:
                        run_query("DELETE FROM materias_primas WHERE id = :id", {'id': id_del})

                # B. Actualizar o Insertar filas
                for _, r in ed_mp.iterrows():
                    id_actual = r.get('id')
                    
                    # Lógica de IVA: Si tiene IVA, lo guardamos ya neto (Costo / 1.12)
                    # Opcional: Puedes elegir guardar el bruto y calcularlo solo al ver recetas.
                    # Aquí lo guardaremos bruto pero con el flag para procesarlo después.
                    costo = float(r['costo_unitario'])
                    t_iva = bool(r['tiene_iva'])
                    
                    if pd.notna(id_actual): 
                        run_query("""UPDATE materias_primas SET codigo_interno=:cod, nombre=:n, 
                                     categoria=:c, unidad_medida=:u, costo_unitario=:p, tiene_iva=:iva 
                                     WHERE id=:id""", 
                                  {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 
                                   'u':r['unidad_medida'], 'p':costo, 'iva':t_iva, 'id':id_actual})
                    else: 
                        run_query("""INSERT INTO materias_primas (codigo_interno, nombre, categoria, unidad_medida, costo_unitario, tiene_iva) 
                                     VALUES (:cod, :n, :c, :u, :p, :iva)""", 
                                  {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 
                                   'u':r['unidad_medida'], 'p':costo, 'iva':t_iva})
                
                st.success("¡Base de datos sincronizada y limpia!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al sincronizar: {e}")
# --- TAB 4: FÁBRICA (PRODUCTOS Y RECETAS) ---
# --- TAB 4: FÁBRICA (PRODUCTOS Y RECETAS) ---
with tabs[3]:
    st.header("Gestión de Producción")
    
    # --- 1. RECUPERAR LÍNEAS OFICIALES ---
    try:
        df_lineas_oficiales = get_data("SELECT nombre FROM lineas_produccion ORDER BY nombre")
        lista_lineas = df_lineas_oficiales['nombre'].tolist() if not df_lineas_oficiales.empty else ['General']
    except:
        lista_lineas = ['General']

    # --- VISUALIZACIÓN DE COSTO POR MINUTO ---
    try:
        mod_cfg = get_data("SELECT salario_base, p_prestaciones, num_operarios, horas_mes FROM config_mod WHERE id=1").iloc[0]
        t_mod_mensual = float(mod_cfg['salario_base'] * mod_cfg['num_operarios'] * (1 + mod_cfg['p_prestaciones']/100))
        minutos_disponibles = float(mod_cfg['horas_mes'] * mod_cfg['num_operarios'] * 60)
        costo_minuto = t_mod_mensual / minutos_disponibles if minutos_disponibles > 0 else 0
        st.info(f"⏱️ **Costo de Mano de Obra por Minuto:** Q{costo_minuto:,.4f}")
    except:
        st.warning("Configure la nómina de producción para calcular el costo por minuto.")
    
    # --- CARGA MASIVA MEJORADA (Detección automática de separador) ---
    with st.expander("📂 Carga Masiva de Productos (CSV)"):
        st.write("Columnas requeridas: `codigo, nombre, tipo, unidades_lote, tiempo_ciclo, precio, linea`")
        with st.form("csv_p_f", clear_on_submit=True):
            f_p = st.file_uploader("Subir CSV Productos", type="csv")
            if st.form_submit_button("Procesar Productos") and f_p:
                try:
                    # sep=None con engine='python' detecta automáticamente si es coma o punto y coma
                    df_p = pd.read_csv(f_p, sep=None, engine='python')
                    
                    for _, r in df_p.iterrows():
                        # Si la línea del CSV no existe en la DB, se crea automáticamente
                        linea_csv = str(r['linea']).strip()
                        run_query("INSERT INTO lineas_produccion (nombre) VALUES (:n) ON CONFLICT DO NOTHING", {'n': linea_csv})
                        
                        run_query("""
                            INSERT INTO productos (codigo_barras, nombre, tipo_produccion, unidades_por_lote, minutos_por_unidad, precio_venta_sugerido, linea)
                            VALUES (:c, :n, :t, :u, :m, :p, :l)
                            ON CONFLICT (codigo_barras) DO UPDATE SET 
                            nombre=:n, tipo_produccion=:t, unidades_por_lote=:u, minutos_por_unidad=:m, precio_venta_sugerido=:p, linea=:l
                        """, {
                            'c': str(r['codigo']), 'n': r['nombre'], 't': r['tipo'], 
                            'u': r['unidades_lote'], 'm': float(r['tiempo_ciclo']),
                            'p': r['precio'], 'l': linea_csv
                        })
                    st.success("Productos actualizados con éxito.")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Error en el formato del CSV: {e}")

    c_left, c_right = st.columns([1, 2])

    # --- CREACIÓN INDIVIDUAL CON SELECTOR DE LÍNEA ---
    with c_left:
        st.subheader("🆕 Crear Individual")
        with st.form("new_p_safe"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            # Cambio de campo de texto a selector basado en el catálogo oficial
            lin = st.selectbox("Línea de Producción", options=lista_lineas)
            tip = st.selectbox("Tipo", ["Unidad", "Lote"])
            uds = st.number_input("Uds/Lote", 1)
            ciclo = st.number_input("Tiempo de ciclo (Min por unidad)", value=5.0, step=0.1)
            prc = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("💾 Guardar"):
                run_query("""
                    INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_unidad, precio_venta_sugerido) 
                    VALUES (:c, :n, :l, :t, :u, :m, :p)
                    ON CONFLICT (codigo_barras) DO UPDATE SET 
                    nombre=:n, linea=:l, tipo_produccion=:t, unidades_por_lote=:u, minutos_por_unidad=:m, precio_venta_sugerido=:p
                """, {'c':cod, 'n':nom, 'l':lin, 't':tip, 'u':uds, 'm':ciclo, 'p':prc})
                st.success(f"Producto {nom} guardado.")
                st.rerun()

        # --- GESTOR DE LÍNEAS (CREADOR RÁPIDO) ---
        with st.expander("🛠️ Editor de Líneas"):
            nueva_lin = st.text_input("Nombre de nueva línea")
            if st.button("Añadir Línea"):
                if nueva_lin:
                    run_query("INSERT INTO lineas_produccion (nombre) VALUES (:n) ON CONFLICT DO NOTHING", {'n': nueva_lin})
                    st.rerun()

    # --- EDITOR DE RECETAS Y VISTA PREVIA ---
    with c_right:
        prods_list = get_data("SELECT codigo_barras, nombre, linea FROM productos ORDER BY nombre")
        if not prods_list.empty:
            sel_options = [f"{r['nombre']} | {r['linea']}" for _, r in prods_list.iterrows()]
            sel_p = st.selectbox("Editar Receta de:", sel_options)
            
            p_nombre_clean = sel_p.split(" | ")[0]
            pid = prods_list[prods_list['nombre']==p_nombre_clean]['codigo_barras'].values[0]
            
            mps_list = get_data("SELECT id, nombre, unidad_medida FROM materias_primas ORDER BY nombre")
            unidades_db = get_data("SELECT DISTINCT unidad_medida FROM materias_primas WHERE unidad_medida IS NOT NULL")
            opciones_u = unidades_db['unidad_medida'].tolist() if not unidades_db.empty else []
            if "Nueva unidad..." not in opciones_u:
                opciones_u.append("Nueva unidad...")

            with st.form("add_rec_f"):
                st.subheader(f"🛠️ Editor: {p_nombre_clean}")
                c1, c2, c3 = st.columns([3,1,1])
                m_n = c1.selectbox("MP", mps_list['nombre'].tolist())
                m_r = mps_list[mps_list['nombre']==m_n].iloc[0]
                can = c2.number_input("Cant.", format="%.4f")
                u_sel = c3.selectbox("Unidad Uso", opciones_u, index=opciones_u.index(m_r['unidad_medida']) if m_r['unidad_medida'] in opciones_u else 0)
                nueva_u = st.text_input("Escribe la nueva unidad (solo si seleccionaste 'Nueva unidad...' arriba)", placeholder="Ej: Mililitros")
                
                if st.form_submit_button("➕ Añadir Ingrediente"):
                    unidad_final = nueva_u if u_sel == "Nueva unidad..." else u_sel
                    if u_sel == "Nueva unidad..." and not nueva_u:
                        st.error("Por favor, escribe el nombre de la nueva unidad.")
                    else:
                        run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) VALUES (:pid, :mid, :c, :u)", 
                                  {'pid':pid, 'mid':int(m_r['id']), 'c':can, 'u':unidad_final})
                        st.rerun()
            
            curr_rec = get_data("SELECT r.id, m.nombre, r.cantidad, r.unidad_uso FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
            st.dataframe(curr_rec, use_container_width=True, hide_index=True)

            if st.button("👁️ Vista Previa del Costo"):
                with st.spinner("Calculando..."):
                    rec_p = get_data("SELECT r.cantidad, r.unidad_uso, m.id as mid FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
                    costo_mat = sum(row['cantidad'] * obtener_costo_convertido(row['mid'], row['unidad_uso']) for _, row in rec_p.iterrows())
                    p_p = get_data("SELECT unidades_por_lote, tipo_produccion, minutos_por_unidad FROM productos WHERE codigo_barras=:pid", {'pid':pid}).iloc[0]
                    u_div = p_p['unidades_por_lote'] if p_p['tipo_produccion'] == 'Lote' else 1
                    mod_p = float(p_p['minutos_por_unidad']) * costo_minuto
                    u_prom_p = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
                    cif_tot_p = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos").iloc[0,0] or 0
                    cif_p = float(cif_tot_p) / u_prom_p if u_prom_p > 0 else 0
                    total_p = (costo_mat / u_div) + mod_p + cif_p
                st.success(f"**Costo Unitario Estimado: Q{total_p:,.2f}**")
                st.caption(f"Materiales: Q{(costo_mat/u_div):.2f} | MOD: Q{mod_p:.2f} | CIF: Q{cif_p:.2f}")

            if not curr_rec.empty:
                with st.expander("🗑️ Quitar un ingrediente"):
                    dict_borrar = {f"{row['nombre']} ({row['cantidad']} {row['unidad_uso']})": row['id'] for _, row in curr_rec.iterrows()}
                    item_sel = st.selectbox("Seleccione para eliminar:", options=list(dict_borrar.keys()), key="del_local")
                    if st.button("Confirmar Eliminación", type="primary", key="btn_del_local"):
                        run_query("DELETE FROM recetas WHERE id = :rid", {"rid": dict_borrar[item_sel]})
                        st.rerun()
# --- TAB 5: FICHA TÉCNICA (ACTUALIZADA CON COSTOS REALES Y SEMÁFORO) ---
with tabs[4]:
    st.header("🔎 Ficha Técnica de Costeo")
    prods_f = get_data("SELECT * FROM productos ORDER BY nombre")
    sel_f = st.selectbox("Ver Ficha de:", [""] + prods_f['nombre'].tolist())
    
    if sel_f:
        p_info = prods_f[prods_f['nombre']==sel_f].iloc[0]
        cod_p = p_info['codigo_barras']
        
        # Recuperar receta
        rec_det = get_data("SELECT m.nombre, m.categoria, r.cantidad, r.unidad_uso, m.id as mid FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:c", {'c':cod_p})
        df_frag = rec_det[rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        df_otros = rec_det[~rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        
        st.markdown(f"### {p_info['nombre']}")
        
        # Botón de Exportación
        if st.button("📥 Generar Reporte PDF"):
            st.info("Función de exportación PDF seleccionada. Preparando estructura de datos...")

        c_f, c_o = st.columns(2)
        tot_formula = 0
        tot_empaque = 0
        
        with c_f:
            st.write("**🧪 FRAGANCIA / FÓRMULA**")
            sub_f = 0
            for _, r in df_frag.iterrows():
                linea = r['cantidad'] * obtener_costo_convertido(r['mid'], r['unidad_uso'])
                sub_f += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"SUB-TOTAL FORMULA: Q{sub_f:.4f}")
            tot_formula = sub_f

        with c_o:
            st.write("**📦 MATERIA PRIMA / EMPAQUE**")
            sub_o = 0
            for _, r in df_otros.iterrows():
                linea = r['cantidad'] * obtener_costo_convertido(r['mid'], r['unidad_uso'])
                sub_o += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"SUB-TOTAL MATERIA PRIMA: Q{sub_o:.4f}")
            tot_empaque = sub_o
        
        st.divider()

        # --- CÁLCULOS TÉCNICOS CON VOLUMEN REAL ---
        u_div = p_info['unidades_por_lote'] if p_info['tipo_produccion'] == 'Lote' else 1
        
        # Llamada a la función dinámica para obtener volumen real vs teórico
        u_volumen, tipo_vol = obtener_volumen_referencia()
        
        costo_variable_u = (tot_formula + tot_empaque) / u_div
        mod_cfg = get_data("SELECT salario_base, p_prestaciones, num_operarios, horas_mes FROM config_mod WHERE id=1").iloc[0]
        t_mod_mensual = float(mod_cfg['salario_base'] * mod_cfg['num_operarios'] * (1 + mod_cfg['p_prestaciones']/100))
        minutos_disponibles = float(mod_cfg['horas_mes'] * mod_cfg['num_operarios'] * 60)
        costo_minuto = t_mod_mensual / minutos_disponibles if minutos_disponibles > 0 else 0
        
        tiempo_ciclo = float(p_info.get('minutos_por_unidad', 5.0)) 
        mod_u = tiempo_ciclo * costo_minuto
        
        cif_tot = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos").iloc[0,0] or 0
        c_fijos_u = float(cif_tot) / u_volumen
        
        gasto_op_tot = get_data("SELECT SUM(total_mensual * ((p_admin + p_ventas)/100)) FROM costos_fijos").iloc[0,0] or 0
        gasto_op_u = float(gasto_op_tot) / u_volumen
        
        # --- TOTALES FINALES ---
        costo_total_u = costo_variable_u + mod_u + c_fijos_u
        total_costos_gastos = costo_total_u + gasto_op_u
        precio_venta = float(p_info['precio_venta_sugerido'])
        utilidad = precio_venta - total_costos_gastos
        margen = (utilidad / precio_venta * 100) if precio_venta > 0 else 0

        # --- TABLA DE RESULTADOS ---
        st.subheader("📊 Desglose Final de Costos y Utilidad")
        st.caption(f"ℹ️ Cálculos basados en volumen **{tipo_vol}**: {u_volumen:,.0f} unidades.")
        
        res_cols = st.columns(2)
        with res_cols[0]:
            st.write(f"**COSTO VARIABLE UNITARIO:** Q{costo_variable_u:,.2f}")
            st.write(f"**MANO DE OBRA DIRECTA (MOD):** Q{mod_u:,.2f}")
            st.write(f"**COSTOS FIJOS UNITARIOS:** Q{c_fijos_u:,.2f}")
            st.markdown(f"### **COSTO TOTAL UNITARIO:** Q{costo_total_u:,.2f}")
            st.write(f"**Tiempo de ciclo:** {tiempo_ciclo} min")
            
        with res_cols[1]:
            st.write(f"**Gasto total Unitario (operativo promedio):** Q{gasto_op_u:,.2f}")
            st.markdown(f"### **Total de costos y gastos:** Q{total_costos_gastos:,.2f}")
            st.write(f"**PRECIO DE VENTA:** Q{precio_venta:,.2f}")
            
        st.divider()
        
        # --- SEMÁFORO DE UTILIDAD ---
        if utilidad > 0.01:
            color_res = "green"
            st.success(f"**💰 GANANCIA Detectada para este producto.**")
        elif utilidad < -0.01:
            color_res = "red"
            st.error(f"**⚠️ PÉRDIDA: El costo total supera al precio de venta.**")
        else:
            color_res = "gray"
            st.warning("**⚖️ NEUTRAL: El producto está en punto de equilibrio.**")

        # KPIs Visuales
        st.markdown(f"""
            <div style="display: flex; justify-content: space-around; padding: 10px; border-radius: 10px; background-color: #f0f2f6;">
                <div style="text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #555;">UTILIDAD POR UNIDAD</p>
                    <h2 style="margin: 0; color: {color_res};">Q{utilidad:,.2f}</h2>
                </div>
                <div style="text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #555;">MARGEN DE GANANCIA</p>
                    <h2 style="margin: 0; color: {color_res};">{margen:.2f}%</h2>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.metric("PUNTO DE EQUILIBRIO (Est.)", f"{int(total_costos_gastos / (precio_venta - costo_variable_u) * u_volumen) if precio_venta > costo_variable_u else 0} uds")
# --- TAB 6: AJUSTES (CONVERSIONES) ---
with tabs[5]:
    st.header("⚙️ Ajustes y Conversiones")
    with st.form("new_conv"):
        c1, c2, c3 = st.columns(3)
        o = c1.text_input("Unidad Compra")
        d = c2.text_input("Unidad Receta")
        f = c3.number_input("Factor (Ej: 1 Gal = 128 Oz)", value=1.0)
        if st.form_submit_button("Registrar"):
            run_query("INSERT INTO conversiones (unidad_origen, unidad_destino, factor_multiplicador) VALUES (:o, :d, :f) ON CONFLICT (unidad_origen, unidad_destino) DO UPDATE SET factor_multiplicador=:f", {'o':o, 'd':d, 'f':f})
            st.rerun()
    st.dataframe(get_data("SELECT * FROM conversiones"), use_container_width=True)
# --- TAB 7: REGISTRO DE PRODUCCIÓN (CARGA MASIVA POR LÍNEA Y ANULACIÓN) ---
with tabs[6]:
    st.header("🚀 Panel de Producción Diaria")
    
    col_entrada, col_hist_prod = st.columns([1.2, 1])
    
    with col_entrada:
        st.subheader("📥 Registro Masivo por Línea")
        
        # 1. Configuración de la sesión
        c_f1, c_f2 = st.columns(2)
        fecha_registro = c_f1.date_input("Fecha de Trabajo", value=pd.to_datetime("today"))
        
        # Obtenemos las líneas oficiales del catálogo
        lineas_db = get_data("SELECT nombre FROM lineas_produccion ORDER BY nombre")
        linea_sel = c_f2.selectbox("Seleccione Línea para trabajar:", lineas_db['nombre'].tolist() if not lineas_db.empty else ["General"])

        # 2. FILTRADO REAL: Solo productos que pertenezcan a la línea seleccionada
        prods_de_linea = get_data("SELECT codigo_barras, nombre FROM productos WHERE linea = :l ORDER BY nombre", {'l': linea_sel})
        
        if not prods_de_linea.empty:
            st.info(f"📋 Completando producción para: **{linea_sel}**")
            
            # Preparamos la tabla de carga (vaciamos cantidades a 0)
            df_carga = prods_de_linea.copy()
            df_carga['cantidad'] = 0 
            
            # EDITOR MASIVO: Permite llenar múltiples productos a la vez
            ed_carga = st.data_editor(
                df_carga,
                hide_index=True,
                use_container_width=True,
                disabled=["codigo_barras", "nombre"], # Solo editamos la columna 'cantidad'
                column_config={
                    "cantidad": st.column_config.NumberColumn("Unidades Producidas", min_value=0, step=1, format="%d")
                },
                key=f"editor_v3_{linea_sel}" # Key dinámica para limpiar al cambiar de línea
            )
            
            if st.button("💾 Guardar Producción de la Línea", type="primary"):
                # Procesamos solo filas donde se ingresó producción
                a_registrar = ed_carga[ed_carga['cantidad'] > 0]
                
                if not a_registrar.empty:
                    try:
                        for _, r in a_registrar.iterrows():
                            run_query("""
                                INSERT INTO registro_produccion (fecha, linea_nombre, producto_codigo, cantidad_producida)
                                VALUES (:f, :l, :c, :q)
                            """, {
                                'f': fecha_registro, 'l': linea_sel, 
                                'c': r['codigo_barras'], 'q': int(r['cantidad'])
                            })
                        st.success(f"✅ Registrados {len(a_registrar)} productos de la línea {linea_sel}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error técnico al guardar: {e}")
                else:
                    st.warning("No has ingresado cantidades mayores a cero todavía.")
        else:
            # Si la línea no tiene productos, mostramos advertencia clara
            st.warning(f"⚠️ La línea '{linea_sel}' no tiene productos asociados en el catálogo.")

    with col_hist_prod:
        st.subheader("📋 Historial y Anulaciones")
        
        # Filtro de fecha para auditar
        f_ver = st.date_input("Ver producción del día:", value=fecha_registro)
        
        historial_dia = get_data("""
            SELECT r.id, p.nombre as producto, r.cantidad_producida as cantidad, r.linea_nombre as linea
            FROM registro_produccion r
            JOIN productos p ON r.producto_codigo = p.codigo_barras
            WHERE r.fecha = :f
            ORDER BY r.id DESC
        """, {'f': f_ver})
        
        if not historial_dia.empty:
            st.dataframe(historial_dia, use_container_width=True, hide_index=True)
            
            # --- MÓDULO DE ANULACIÓN ---
            with st.expander("🗑️ Anular un registro (Solo administradores)"):
                # Creamos lista para elegir qué registro borrar del historial
                opciones_del = {f"{row['producto']} ({row['cantidad']} uds) - ID: {row['id']}": row['id'] 
                               for _, row in historial_dia.iterrows()}
                
                a_eliminar = st.selectbox("Seleccione el registro a anular:", options=list(opciones_del.keys()))
                
                if st.button("Confirmar Eliminación", type="primary"):
                    run_query("DELETE FROM registro_produccion WHERE id = :id", {'id': opciones_del[a_eliminar]})
                    st.success("Registro eliminado del historial diario.")
                    st.rerun()
        else:
            st.write("No se encontró producción registrada en esta fecha.")
