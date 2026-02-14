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
    """Calcula el costo unitario basado en la conversión de unidades."""
    df_mp = get_data("SELECT costo_unitario, unidad_medida FROM materias_primas WHERE id=:id", {'id': mp_id})
    if df_mp.empty: return 0.0
    
    costo_base = float(df_mp.iloc[0]['costo_unitario'])
    unidad_base = df_mp.iloc[0]['unidad_medida']
    
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

# ==============================================================================
# INTERFAZ
# ==============================================================================
st.title("☁️ ERP Perfumería")

tabs = st.tabs(["👥 Nóminas", "💰 Costos Fijos", "🌿 Materias Primas", "📦 Fábrica (Prod)", "🔎 Ficha Técnica", "⚙️ Ajustes"])

# --- TAB 1: NÓMINAS ---
with tabs[0]:
    st.header("Configuración de Personal")
    c1, c2, c3 = st.columns(3)
    def render_nomina_form(titulo, tabla, key_prefix):
        with st.container(border=True):
            st.subheader(titulo)
            try:
                col_emp = "num_operarios" if tabla == 'config_mod' else "num_empleados"
                df = get_data(f"SELECT * FROM {tabla} WHERE id=1")
                if not df.empty:
                    data = df.iloc[0]
                    with st.form(f"form_{key_prefix}"):
                        s = st.number_input("Salario", value=float(data['salario_base']))
                        p = st.number_input("% Prestaciones", value=float(data['p_prestaciones']))
                        n = st.number_input("Nº Personas", value=int(data[col_emp]))
                        if st.form_submit_button("Guardar"):
                            run_query(f"UPDATE {tabla} SET salario_base=:s, p_prestaciones=:p, {col_emp}=:n WHERE id=1", {'s':s, 'p':p, 'n':n})
                            st.rerun()
            except: pass
    with c1: render_nomina_form("🏢 Admin", "config_admin", "adm")
    with c2: render_nomina_form("🛍️ Ventas", "config_ventas", "ven")
    with c3: render_nomina_form("🏭 Producción", "config_mod", "mod")

# --- TAB 2: COSTOS FIJOS ---
with tabs[1]:
    st.header("Matriz de Costos Fijos")
    try:
        df_man = get_data("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos ORDER BY id")
        df_show = df_man.copy()
        ed_df = st.data_editor(df_show, disabled=["id"], num_rows="dynamic", key="cf_ed")
        if st.button("💾 Guardar Matriz"):
            # Lógica de guardado simplificada para brevedad
            for _, r in ed_df.iterrows():
                if pd.isna(r['id']): run_query("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (:c, :t, :pa, :pv, :pp)", {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod']})
                else: run_query("UPDATE costos_fijos SET concepto=:c, total_mensual=:t, p_admin=:pa, p_ventas=:pv, p_prod=:pp WHERE id=:id", {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod'], 'id':r['id']})
            st.rerun()
    except: pass

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

# --- TAB 4: FÁBRICA (RECETAS) ---
with tabs[3]:
    st.header("Gestión de Producción")
    prods = get_data("SELECT codigo_barras, nombre FROM productos")
    if not prods.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            sel_p = st.selectbox("Seleccione Producto:", prods['nombre'].tolist())
            pid = prods[prods['nombre']==sel_p]['codigo_barras'].values[0]
            
            with st.expander("👯 Duplicar Receta"):
                dest = st.selectbox("Copiar receta a:", prods['nombre'].tolist(), key="copy_dest")
                if st.button("Ejecutar Clonación"):
                    c_dest = prods[prods['nombre']==dest]['codigo_barras'].values[0]
                    run_query("DELETE FROM recetas WHERE producto_id=:d", {'d':c_dest})
                    run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) SELECT :d, mp_id, cantidad, unidad_uso FROM recetas WHERE producto_id=:o", {'d':c_dest, 'o':pid})
                    st.success("Clonado")

        with c2:
            st.subheader(f"Editor de Receta: {sel_p}")
            mps = get_data("SELECT id, nombre, unidad_medida FROM materias_primas ORDER BY nombre")
            with st.form("add_mp_receta"):
                ca, cb, cc = st.columns([3,1,1])
                mp_n = ca.selectbox("Materia Prima", mps['nombre'].tolist())
                mp_row = mps[mps['nombre']==mp_n].iloc[0]
                cant = cb.number_input("Cant.", format="%.4f")
                u_uso = cc.text_input("Unidad Uso", value=mp_row['unidad_medida'])
                if st.form_submit_button("➕ Añadir"):
                    run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) VALUES (:pid, :mid, :c, :u)", 
                              {'pid':pid, 'mid':int(mp_row['id']), 'c':cant, 'u':u_uso})
                    st.rerun()
            
            receta_act = get_data("SELECT r.id, m.nombre, r.cantidad, r.unidad_uso FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
            st.dataframe(receta_act, hide_index=True, use_container_width=True)
            if st.button("🗑️ Limpiar Receta"):
                run_query("DELETE FROM recetas WHERE producto_id=:pid", {'pid':pid})
                st.rerun()

# --- TAB 5: FICHA TÉCNICA (DETALLE EXCEL) ---
with tabs[4]:
    st.header("🔎 Ficha Técnica de Costeo")
    prods_f = get_data("SELECT codigo_barras, nombre, precio_venta_sugerido, unidades_por_lote, tipo_produccion FROM productos")
    sel_f = st.selectbox("Ver Ficha de:", [""] + prods_f['nombre'].tolist())
    
    if sel_f:
        p_info = prods_f[prods_f['nombre']==sel_f].iloc[0]
        cod_p = p_info['codigo_barras']
        
        # Recuperar receta
        rec_det = get_data("""
            SELECT m.nombre, m.categoria, r.cantidad, r.unidad_uso, m.id as mid 
            FROM recetas r JOIN materias_primas m ON r.mp_id=m.id 
            WHERE r.producto_id=:c""", {'c':cod_p})
        
        # Separación Categorías
        df_frag = rec_det[rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        df_otros = rec_det[~rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        
        st.markdown(f"### {p_info['nombre']}")
        c_frag, c_pack = st.columns(2)
        
        total_mp = 0
        with c_frag:
            st.write("**🧪 FRAGANCIA / FÓRMULA**")
            sub_f = 0
            for _, r in df_frag.iterrows():
                cost_u = obtener_costo_convertido(r['mid'], r['unidad_uso'])
                linea = r['cantidad'] * cost_u
                sub_f += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"Subtotal Fórmula: Q{sub_f:.4f}")
            total_mp += sub_f

        with c_pack:
            st.write("**📦 MATERIA PRIMA / EMPAQUE**")
            sub_o = 0
            for _, r in df_otros.iterrows():
                cost_u = obtener_costo_convertido(r['mid'], r['unidad_uso'])
                linea = r['cantidad'] * cost_u
                sub_o += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"Subtotal Empaque: Q{sub_o:.4f}")
            total_mp += sub_o

        # Costos Indirectos (CIF)
        u_prom = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
        cif_tot = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos").iloc[0,0] or 0
        cif_u = float(cif_tot) / u_prom
        
        st.divider()
        res1, res2, res3 = st.columns(3)
        u_div = p_info['unidades_por_lote'] if p_info['tipo_produccion'] == 'Lote' else 1
        costo_final = (total_mp / u_div) + cif_u
        
        res1.metric("Costo Total Unitario", f"Q{costo_final:.2f}")
        res2.metric("Precio de Venta", f"Q{p_info['precio_venta_sugerido']:.2f}")
        utilidad = p_info['precio_venta_sugerido'] - costo_final
        res3.metric("Utilidad por Unidad", f"Q{utilidad:.2f}", f"{(utilidad/p_info['precio_venta_sugerido']*100):.1f}%")

# --- TAB 6: AJUSTES (CONVERSIONES) ---
with tabs[5]:
    st.header("⚙️ Editor de Medidas y Conversiones")
    st.write("Configura aquí cuánto equivale una unidad de compra en unidades de receta.")
    
    with st.form("nueva_conv"):
        c1, c2, c3 = st.columns(3)
        ori = c1.text_input("Unidad Compra", placeholder="Galon")
        des = c2.text_input("Unidad Receta", placeholder="Oz")
        fac = c3.number_input("Factor (Ej: 1 Galon = 128 Oz)", value=1.0, format="%.4f")
        if st.form_submit_button("Registrar Regla"):
            run_query("INSERT INTO conversiones (unidad_origen, unidad_destino, factor_multiplicador) VALUES (:o, :d, :f) ON CONFLICT (unidad_origen, unidad_destino) DO UPDATE SET factor_multiplicador=:f", 
                      {'o':ori, 'd':des, 'f':fac})
            st.rerun()
    
    st.subheader("Reglas Activas")
    df_c = get_data("SELECT id, unidad_origen, unidad_destino, factor_multiplicador FROM conversiones")
    st.dataframe(df_c, use_container_width=True)
