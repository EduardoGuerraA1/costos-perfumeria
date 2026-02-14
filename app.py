import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import urllib.parse

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ERP Perfumería - Supabase", layout="wide")

# ==============================================================================
# 🔐 CONEXIÓN A BASE DE DATOS (CONFIGURACIÓN POOLER)
# ==============================================================================

# 1. TUS NUEVOS DATOS (Copiados de lo que me enviaste)
DB_HOST = "aws-1-us-east-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.nzlysybivtiumentgpvi"  # <--- Fíjate que el usuario cambió
DB_PORT = "6543"
DB_PASS = ".pJUb+(3pnYqBH1yhM"  # <--- ⚠️ IMPORTANTE: BORRA ESTO Y PON TU CONTRASEÑA REAL

# 2. CONSTRUCCIÓN DE LA URL BLINDADA
try:
    # Codificamos la contraseña para evitar errores con símbolos (@, #, etc.)
    encoded_password = urllib.parse.quote_plus(DB_PASS)
    
    # URL de conexión específica para PostgreSQL + Psycopg2
    DB_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

    @st.cache_resource
    def get_engine():
        # pool_pre_ping=True ayuda a reconectar si Supabase cierra la conexión
        return create_engine(DB_URL, pool_pre_ping=True)

    # Test de conexión al iniciar
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    st.sidebar.success("✅ Conectado a Nube")

except Exception as e:
    st.error("❌ Error Crítico de Conexión")
    st.error("Por favor revisa que tu contraseña sea correcta en el código.")
    st.code(f"Detalle del error: {e}")
    st.stop()

# ==============================================================================
# LÓGICA DE NEGOCIO (QUERIES)
# ==============================================================================

def run_query(query, params=None):
    with engine.connect() as conn:
        if params:
            conn.execute(text(query), params)
        else:
            conn.execute(text(query))
        conn.commit()

def get_data(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

def get_unidades_promedio():
    try:
        df = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1")
        return df.iloc[0,0] if not df.empty else 1
    except: return 1

def get_nomina_config(table_name):
    # Definimos las columnas según la tabla para evitar el error de nombres
    if table_name == 'config_mod':
        # TRUCO: Renombramos 'num_operarios' a 'num_empleados' en la consulta
        query = f"SELECT salario_base, p_prestaciones, num_operarios as num_empleados, horas_mes FROM {table_name} WHERE id=1"
    else:
        # En admin y ventas ya se llama 'num_empleados'
        query = f"SELECT salario_base, p_prestaciones, num_empleados FROM {table_name} WHERE id=1"
    
    try:
        df = get_data(query)
        if not df.empty: 
            return df.iloc[0]
    except Exception as e:
        pass
    return None

# ==============================================================================
# INTERFAZ DE USUARIO
# ==============================================================================
st.title("☁️ ERP Perfumería (Versión Nube)")

tabs = st.tabs(["👥 Nóminas", "💰 Costos Fijos", "🌿 Materias Primas", "📦 Fábrica", "🔎 Ficha Técnica"])

# ------------------------------------------------------------------
# TAB 1: NÓMINAS
# ------------------------------------------------------------------
with tabs[0]:
    st.header("Configuración de Personal")
    c1, c2, c3 = st.columns(3)
    
    # ADMIN
    with c1:
        st.subheader("🏢 Admin Central")
        adm = get_nomina_config('config_admin')
        if adm is not None:
            with st.form("f_adm"):
                s = st.number_input("Salario", value=float(adm['salario_base']))
                p = st.number_input("% Prestaciones", value=float(adm['p_prestaciones']))
                n = st.number_input("Nº Empleados", value=int(adm['num_empleados']))
                if st.form_submit_button("Guardar Admin"):
                    run_query("UPDATE config_admin SET salario_base=:s, p_prestaciones=:p, num_empleados=:n WHERE id=1", {'s':s, 'p':p, 'n':n})
                    st.rerun()
        else: st.warning("Configurando DB...")

    # VENTAS
    with c2:
        st.subheader("🛍️ Sala Ventas")
        ven = get_nomina_config('config_ventas')
        if ven is not None:
            with st.form("f_ven"):
                s = st.number_input("Salario", value=float(ven['salario_base']))
                p = st.number_input("% Prestaciones", value=float(ven['p_prestaciones']))
                n = st.number_input("Nº Empleados", value=int(ven['num_empleados']))
                if st.form_submit_button("Guardar Ventas"):
                    run_query("UPDATE config_ventas SET salario_base=:s, p_prestaciones=:p, num_empleados=:n WHERE id=1", {'s':s, 'p':p, 'n':n})
                    st.rerun()

    # MOD
    with c3:
        st.subheader("🏭 Producción")
        mod = get_nomina_config('config_mod')
        if mod is not None:
            with st.form("f_mod"):
                s = st.number_input("Salario", value=float(mod['salario_base']))
                p = st.number_input("% Prestaciones", value=float(mod['p_prestaciones']))
                n = st.number_input("Nº Ops", value=int(mod['num_empleados'])) 
                h = st.number_input("Horas/Mes", value=float(mod['horas_mes']))
                if st.form_submit_button("Guardar MOD"):
                    run_query("UPDATE config_mod SET salario_base=:s, p_prestaciones=:p, num_operarios=:n, horas_mes=:h WHERE id=1", {'s':s, 'p':p, 'n':n, 'h':h})
                    st.rerun()

# # ------------------------------------------------------------------
# TAB 2: MATRIZ COSTOS (CORREGIDO CON TOTALES)
# ------------------------------------------------------------------
with tabs[1]:
    st.header("Matriz de Costos Fijos")
    
    # Carga CSV
    with st.expander("📂 Cargar Gastos (CSV)"):
        f = st.file_uploader("CSV: concepto,total_mensual,p_admin,p_ventas,p_prod", type="csv")
        if f:
            try:
                df_csv = pd.read_csv(f)
                for _, r in df_csv.iterrows():
                    run_query("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (:c, :t, :pa, :pv, :pp)",
                              {'c':r['concepto'], 't':r['total_mensual'], 'pa':r['p_admin'], 'pv':r['p_ventas'], 'pp':r['p_prod']})
                st.success("Cargado"); st.rerun()
            except Exception as e: st.error(e)

    # 1. Datos Manuales
    df_man = get_data("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos ORDER BY id")
    
    # 2. Datos Automáticos (Nóminas)
    adm = get_nomina_config('config_admin')
    ven = get_nomina_config('config_ventas')
    
    filas_auto = []
    if adm is not None:
        t_sal_adm = float(adm['salario_base'] * adm['num_empleados'])
        t_pre_adm = float(t_sal_adm * (adm['p_prestaciones'] / 100))
        filas_auto.append({'id': -1, 'concepto': '⚡ Nómina: Salarios Admin', 'total_mensual': t_sal_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})
        filas_auto.append({'id': -2, 'concepto': '⚡ Nómina: Prestaciones Admin', 'total_mensual': t_pre_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})
    
    if ven is not None:
        t_sal_ven = float(ven['salario_base'] * ven['num_empleados'])
        t_pre_ven = float(t_sal_ven * (ven['p_prestaciones'] / 100))
        filas_auto.append({'id': -3, 'concepto': '⚡ Nómina: Salarios Ventas', 'total_mensual': t_sal_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})
        filas_auto.append({'id': -4, 'concepto': '⚡ Nómina: Prestaciones Ventas', 'total_mensual': t_pre_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})

    df_show = pd.concat([df_man, pd.DataFrame(filas_auto)], ignore_index=True)
    
    # EDITOR
    ed_df = st.data_editor(df_show, disabled=["id"], num_rows="dynamic", key="cf_ed", column_config={"total_mensual": st.column_config.NumberColumn(format="Q%.2f")})
    
    # BOTÓN GUARDAR
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
        
        # Eliminar
        ids_old = set(df_man['id'].tolist())
        to_del = list(ids_old - ids_now)
        if to_del:
            todel_str = tuple(to_del)
            if len(to_del) == 1: todel_str = f"({to_del[0]})"
            run_query(f"DELETE FROM costos_fijos WHERE id IN {todel_str}")
        
        st.success("Guardado"); st.rerun()

    # --- CÁLCULO DE TOTALES (AQUÍ ESTÁ LO QUE FALTABA) ---
    # Calculamos los montos reales en memoria para mostrar
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
    
    # UNIDADES BASE
    u_prom = st.number_input("Unidades Base", value=get_unidades_promedio())
    if u_prom != get_unidades_promedio():
        run_query("UPDATE config_global SET unidades_promedio_mes=:u WHERE id=1", {'u':u_prom})
        st.rerun()
    
    # CIF UNITARIO
    cif_unit = ed_df['M_Prod'].sum() / u_prom if u_prom > 0 else 0
    st.success(f"🎯 CIF Unitario: **Q{cif_unit:,.2f}**")

# ------------------------------------------------------------------
# TAB 3: MATERIAS PRIMAS
# ------------------------------------------------------------------
with tabs[2]:
    st.header("Inventario MP")
    with st.expander("Subir CSV"):
        f = st.file_uploader("CSV MP", type="csv", key="csv_mp")
        if f:
            try: 
                df_mp = pd.read_csv(f)
                for _, r in df_mp.iterrows():
                    run_query("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (:n, :c, :u, :p)",
                              {'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario']})
                st.success("Ok"); st.rerun()
            except: st.error("Error CSV")

    df = get_data("SELECT * FROM materias_primas ORDER BY nombre")
    ed = st.data_editor(df, num_rows="dynamic", key="mp_ed", column_config={"costo_unitario": st.column_config.NumberColumn(format="Q%.4f")})
    
    if st.button("💾 Guardar MP"):
        ids_now = set()
        for _, r in ed.iterrows():
            if pd.notna(r['id']):
                ids_now.add(r['id'])
                run_query("UPDATE materias_primas SET nombre=:n, categoria=:c, unidad_medida=:u, costo_unitario=:p WHERE id=:id",
                          {'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario'], 'id':r['id']})
            else:
                run_query("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (:n, :c, :u, :p)",
                          {'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario']})
        
        ids_old = set(df['id'].tolist())
        to_del = list(ids_old - ids_now)
        if to_del:
            todel_str = tuple(to_del)
            if len(to_del) == 1: todel_str = f"({to_del[0]})"
            run_query(f"DELETE FROM materias_primas WHERE id IN {todel_str}")
        
        st.success("Guardado"); st.rerun()

# ------------------------------------------------------------------
# TAB 4: FABRICA
# ------------------------------------------------------------------
with tabs[3]:
    st.header("Productos y Recetas")
    c_izq, c_der = st.columns([1, 2])
    
    with c_izq:
        st.subheader("Crear Producto")
        cats = get_data("SELECT nombre FROM categorias_producto")
        lista_cats = cats['nombre'].tolist() if not cats.empty else ['General']
        
        n_cat = st.text_input("Nueva Categoría (Enter)")
        if n_cat:
            try: run_query("INSERT INTO categorias_producto (nombre) VALUES (:n)", {'n':n_cat}); st.rerun()
            except: pass

        with st.form("new_p"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            cat = st.selectbox("Línea", lista_cats)
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            u_lote = st.number_input("Uds/Lote", 1)
            m_total = st.number_input("Minutos Totales", 0.0)
            precio = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("Guardar"):
                m_unit = m_total / u_lote if tipo == "Lote" else m_total
                q = """
                INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                VALUES (:c, :n, :l, :t, :ul, :ml, :mu, :p)
                ON CONFLICT (codigo_barras) DO UPDATE SET 
                nombre=:n, linea=:l, tipo_produccion=:t, unidades_por_lote=:ul, minutos_por_lote=:ml, minutos_por_unidad=:mu, precio_venta_sugerido=:p
                """
                run_query(q, {'c':cod, 'n':nom, 'l':cat, 't':tipo, 'ul':u_lote, 'ml':m_total, 'mu':m_unit, 'p':precio})
                st.success("Guardado"); st.rerun()

    with c_der:
        st.subheader("Recetas")
        prods = get_data("SELECT codigo_barras, nombre FROM productos")
        d_prods = {f"{r['nombre']}": r['codigo_barras'] for _, r in prods.iterrows()}
        
        sel = st.selectbox("Producto:", list(d_prods.keys()) if d_prods else [])
        
        if sel:
            pid = d_prods[sel]
            
            with st.expander("Herramientas: Clonar"):
                src = st.selectbox("Desde:", ["..."] + list(d_prods.keys()))
                if st.button("Clonar") and src != "...":
                    src_id = d_prods[src]
                    run_query("DELETE FROM recetas WHERE producto_id=:pid", {'pid':pid})
                    run_query("""
                        INSERT INTO recetas (producto_id, mp_id, cantidad)
                        SELECT :pid, mp_id, cantidad FROM recetas WHERE producto_id=:src
                    """, {'pid':pid, 'src':src_id})
                    st.success("Clonado!"); st.rerun()

            c1, c2, c3 = st.columns([3,2,1])
            mps = get_data("SELECT id, nombre FROM materias_primas")
            d_mps = {f"{r['nombre']}": r['id'] for _, r in mps.iterrows()}
            
            m_sel = c1.selectbox("MP", list(d_mps.keys()) if d_mps else [])
            cant = c2.number_input("Cant", 0.0, step=0.1)
            if c3.button("➕"):
                run_query("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (:pid, :mid, :c)", 
                          {'pid':pid, 'mid':d_mps[m_sel], 'c':cant})
                st.rerun()
            
            rec = get_data("""
                SELECT r.id, m.nombre, r.cantidad, m.costo_unitario, (r.cantidad*m.costo_unitario) as subtotal 
                FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid
            """, {'pid':pid})
            st.dataframe(rec, hide_index=True)
            
            if not rec.empty:
                del_id = st.selectbox("Borrar ID", rec['id'].tolist())
                if st.button("🗑️"):
                    run_query("DELETE FROM recetas WHERE id=:id", {'id':del_id}); st.rerun()

# ------------------------------------------------------------------
# TAB 5: FICHA TÉCNICA
# ------------------------------------------------------------------
with tabs[4]:
    st.header("Buscador y Costeo")
    prods = get_data("SELECT codigo_barras, nombre, linea FROM productos")
    lista = [f"{r['nombre']} | {r['codigo_barras']}" for _, r in prods.iterrows()]
    
    sel = st.selectbox("Buscar", [""] + lista)
    if sel:
        cod = sel.split(" | ")[-1]
        p_dat = get_data("SELECT * FROM productos WHERE codigo_barras=:c", {'c':cod}).iloc[0]
        
        c_mat = get_data("SELECT SUM(r.cantidad * m.costo_unitario) FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:c", {'c':cod}).iloc[0,0] or 0
        div_lote = p_dat['unidades_por_lote'] if p_dat['tipo_produccion'] == 'Lote' else 1
        c_mat_u = float(c_mat) / div_lote
        
        mod_cfg = get_nomina_config('config_mod')
        mod_money = float(mod_cfg['salario_base'] * mod_cfg['num_empleados'] * (1+mod_cfg['p_prestaciones']/100))
        mod_hrs = float(mod_cfg['horas_mes'] * mod_cfg['num_empleados'])
        c_min = mod_money / mod_hrs / 60 if mod_hrs > 0 else 0
        
        if float(p_dat['minutos_por_unidad']) > 0:
            c_mod_u = float(p_dat['minutos_por_unidad']) * c_min
        else:
            c_mod_u = mod_money / u_prom if u_prom > 0 else 0
            
        cif_df = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos WHERE id > 0")
        cif_total = float(cif_df.iloc[0,0]) if not cif_df.empty and cif_df.iloc[0,0] else 0
        c_cif_u = cif_total / u_prom if u_prom > 0 else 0
        
        c_tot = c_mat_u + c_mod_u + c_cif_u
        
        st.markdown(f"## {p_dat['nombre']}")
        k1, k2, k3 = st.columns(3)
        k1.metric("Costo Unitario", f"Q{c_tot:.2f}")
        k2.metric("Precio Venta", f"Q{p_dat['precio_venta_sugerido']:.2f}")
        margen = p_dat['precio_venta_sugerido'] - c_tot
        k3.metric("Margen", f"Q{margen:.2f}")
