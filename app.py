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
# LÓGICA DE NEGOCIO Y AUTO-REPARACIÓN
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

# --- FUNCIÓN DE AUTO-REPARACIÓN (LO QUE FALTABA) ---
def check_and_seed_data():
    """Verifica si existen los datos base (ID=1) y si no, los crea."""
    try:
        # Intentamos leer la configuración de admin
        df = get_data("SELECT id FROM config_admin WHERE id=1")
        if df.empty:
            # Si está vacío, INYECTAMOS los datos por defecto
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO config_admin (id, salario_base, p_prestaciones, num_empleados) VALUES (1, 5000, 41.83, 3) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_ventas (id, salario_base, p_prestaciones, num_empleados) VALUES (1, 3500, 41.83, 2) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_mod (id, salario_base, p_prestaciones, num_operarios, horas_mes) VALUES (1, 4252.28, 41.83, 2, 176) ON CONFLICT DO NOTHING"))
                conn.execute(text("INSERT INTO config_global (id, unidades_promedio_mes) VALUES (1, 5000) ON CONFLICT DO NOTHING"))
                conn.commit()
            print("✅ Datos base restaurados automáticamente.")
    except Exception as e:
        st.warning(f"⚠️ Aviso de sistema: {e}")

# EJECUTAMOS LA VERIFICACIÓN AL INICIO
check_and_seed_data()

# ==============================================================================
# INTERFAZ
# ==============================================================================
st.title("☁️ ERP Perfumería")

tabs = st.tabs(["👥 Nóminas", "💰 Costos Fijos", "🌿 Materias Primas", "📦 Fábrica (Prod)", "🔎 Ficha Técnica"])

# ------------------------------------------------------------------
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

# --- TAB 3: MATERIAS PRIMAS ---
with tabs[2]:
    st.header("Inventario Materia Prima")
    df_mp = get_data("SELECT id, codigo_interno, nombre, categoria, unidad_medida, costo_unitario FROM materias_primas ORDER BY nombre")
    ed_mp = st.data_editor(df_mp, num_rows="dynamic", key="mp_editor_final", disabled=["id"])
    if st.button("💾 Guardar Cambios MP"):
        for _, r in ed_mp.iterrows():
            if pd.notna(r['id']): run_query("UPDATE materias_primas SET codigo_interno=:cod, nombre=:n, categoria=:c, unidad_medida=:u, costo_unitario=:p WHERE id=:id", {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario'], 'id':r['id']})
            else: run_query("INSERT INTO materias_primas (codigo_interno, nombre, categoria, unidad_medida, costo_unitario) VALUES (:cod, :n, :c, :u, :p)", {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario']})
        st.rerun()

# --- TAB 4: FÁBRICA (PRODUCTOS Y RECETAS) ---
with tabs[3]:
    st.header("Gestión de Producción")
    c_izq, c_der = st.columns([1, 2])
    
    with c_izq:
        st.subheader("Productos")
        prods = get_data("SELECT codigo_barras, nombre, tipo_produccion, unidades_por_lote FROM productos")
        st.dataframe(prods, hide_index=True)
        
        with st.expander("👯 Duplicar Receta"):
            orig = st.selectbox("Copiar de:", prods['nombre'].tolist())
            dest = st.selectbox("Pegar en:", prods['nombre'].tolist())
            if st.button("Ejecutar Clonación"):
                c_orig = prods[prods['nombre']==orig]['codigo_barras'].values[0]
                c_dest = prods[prods['nombre']==dest]['codigo_barras'].values[0]
                run_query("DELETE FROM recetas WHERE producto_id=:d", {'d':c_dest})
                run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) SELECT :d, mp_id, cantidad, unidad_uso FROM recetas WHERE producto_id=:o", {'d':c_dest, 'o':c_orig})
                st.success("Receta duplicada con éxito")

    with c_der:
        st.subheader("Editor de Receta")
        sel_p = st.selectbox("Seleccione Producto para editar receta:", prods['nombre'].tolist())
        if sel_p:
            pid = prods[prods['nombre']==sel_p]['codigo_barras'].values[0]
            mps = get_data("SELECT id, nombre, unidad_medida FROM materias_primas")
            with st.form("add_mp_receta"):
                c1, c2, c3 = st.columns([3,1,1])
                mp_n = c1.selectbox("Materia Prima", mps['nombre'].tolist())
                mp_id = mps[mps['nombre']==mp_n]['id'].values[0]
                mp_u_base = mps[mps['nombre']==mp_n]['unidad_medida'].values[0]
                
                cant = c2.number_input("Cant.", format="%.4f")
                u_uso = c3.text_input("Unidad Uso", value=mp_u_base)
                if st.form_submit_button("Añadir a Receta"):
                    run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) VALUES (:pid, :mid, :c, :u)", 
                              {'pid':pid, 'mid':mp_id, 'c':cant, 'u':u_uso})
                    st.rerun()
            
            receta_act = get_data("SELECT r.id, m.nombre, r.cantidad, r.unidad_uso FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
            st.dataframe(receta_act, hide_index=True)
            if st.button("🗑️ Limpiar Receta"):
                run_query("DELETE FROM recetas WHERE producto_id=:pid", {'pid':pid})
                st.rerun()

# --- TAB 5: FICHA TÉCNICA DETALLADA ---
with tabs[4]:
    st.header("🔎 Ficha Técnica de Costeo")
    prods_list = get_data("SELECT codigo_barras, nombre FROM productos")
    sel_f = st.selectbox("Ver Ficha de:", [""] + prods_list['nombre'].tolist())
    
    if sel_f != "":
        cod_p = prods_list[prods_list['nombre']==sel_f]['codigo_barras'].values[0]
        p_info = get_data("SELECT * FROM productos WHERE codigo_barras=:c", {'c':cod_p}).iloc[0]
        
        # Detalle Receta con Conversión
        rec_det = get_data("""
            SELECT m.nombre, m.categoria, r.cantidad, r.unidad_uso, m.id as mid 
            FROM recetas r JOIN materias_primas m ON r.mp_id=m.id 
            WHERE r.producto_id=:c""", {'c':cod_p})
        
        st.markdown(f"### {p_info['nombre']} (Cód: {cod_p})")
        
        # Clasificación
        df_frag = rec_det[rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        df_otros = rec_det[~rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        
        col_a, col_b = st.columns(2)
        
        total_receta = 0
        with col_a:
            st.subheader("🧪 Fórmula / Fragancia")
            sub_f = 0
            for _, r in df_frag.iterrows():
                cost_u = obtener_costo_convertido(r['mid'], r['unidad_uso'])
                linea = r['cantidad'] * cost_u
                sub_f += linea
                st.write(f"• {r['nombre']}: {r['cantidad']} {r['unidad_uso']} -> Q{linea:.4f}")
            st.warning(f"Subtotal Fragancia: Q{sub_f:.4f}")
            total_receta += sub_f

        with col_b:
            st.subheader("📦 Empaque y Otros")
            sub_o = 0
            for _, r in df_otros.iterrows():
                cost_u = obtener_costo_convertido(r['mid'], r['unidad_uso'])
                linea = r['cantidad'] * cost_u
                sub_o += linea
                st.write(f"• {r['nombre']}: {r['cantidad']} {r['unidad_uso']} -> Q{linea:.4f}")
            st.warning(f"Subtotal Otros: Q{sub_o:.4f}")
            total_receta += sub_o

        # Totales Finales
        st.divider()
        u_lote = p_info['unidades_por_lote'] if p_info['tipo_produccion'] == 'Lote' else 1
        costo_mp_u = total_receta / u_lote
        
        # MOD y CIF (Cálculo simplificado del bloque anterior)
        u_prom = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
        cif_tot = get_data("SELECT SUM(total_mensual * (p_prod/100)) as cif FROM costos_fijos").iloc[0,0] or 0
        c_cif_u = float(cif_tot) / u_prom
        
        costo_final = costo_mp_u + c_cif_u # + MOD (Añadir aquí tu lógica de MOD si usas minutos)
        
        res1, res2, res3 = st.columns(3)
        res1.metric("Costo Unitario Total", f"Q{costo_final:.2f}")
        res2.metric("Precio Venta", f"Q{p_info['precio_venta_sugerido']:.2f}")
        margen = p_info['precio_venta_sugerido'] - costo_final
        res3.metric("Margen Q", f"Q{margen:.2f}", f"{(margen/p_info['precio_venta_sugerido']*100):.1f}%")

# --- TAB 6: AJUSTES (CONVERSIONES) ---
with tabs[5]:
    st.header("⚙️ Editor de Medidas y Conversiones")
    st.info("Define aquí cuántas unidades de uso hay en una unidad de compra. Ej: 1 Galón -> 128 Oz")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("nueva_conv"):
            ori = st.text_input("Unidad Compra (Origen)", placeholder="Galon")
            des = st.text_input("Unidad Receta (Destino)", placeholder="Oz")
            fac = st.number_input("Factor Multiplicador", value=1.0, format="%.4f")
            if st.form_submit_button("Registrar Conversión"):
                run_query("INSERT INTO conversiones (unidad_origen, unidad_destino, factor_multiplicador) VALUES (:o, :d, :f) ON CONFLICT (unidad_origen, unidad_destino) DO UPDATE SET factor_multiplicador=:f", 
                          {'o':ori, 'd':des, 'f':fac})
                st.rerun()
    
    with col2:
        df_c = get_data("SELECT id, unidad_origen, unidad_destino, factor_multiplicador FROM conversiones")
        ed_c = st.data_editor(df_c, num_rows="dynamic", key="editor_conv")
        if st.button("Eliminar Seleccionados"):
            # Lógica para borrar si es necesario
            pass
