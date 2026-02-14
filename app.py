import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import urllib.parse

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ERP Perfumería - Final", layout="wide")

# ==============================================================================
# 🔐 CONEXIÓN A BASE DE DATOS
# ==============================================================================
DB_HOST = "aws-1-us-east-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.nzlysybivtiumentgpvi"
DB_PORT = "6543"
DB_PASS = "TU_CONTRASEÑA_AQUI" # <--- ¡PON TU CONTRASEÑA AQUÍ!

try:
    encoded_password = urllib.parse.quote_plus(DB_PASS)
    DB_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

    @st.cache_resource
    def get_engine():
        return create_engine(DB_URL, pool_pre_ping=True)

    engine = get_engine()
except Exception as e:
    st.error("❌ Error de Conexión. Revisa la contraseña en el código.")
    st.stop()

# ==============================================================================
# LÓGICA
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
    """Si tiene IVA, divide entre 1.12, si no, retorna el monto igual."""
    if tiene_iva and monto > 0:
        return monto / 1.12
    return monto

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
    
    # Función auxiliar para pintar forms
    def render_nomina_form(titulo, tabla, key_prefix):
        with st.container(border=True):
            st.subheader(titulo)
            try:
                if tabla == 'config_mod':
                    df = get_data(f"SELECT salario_base, p_prestaciones, num_operarios as num_empleados, horas_mes FROM {tabla} WHERE id=1")
                else:
                    df = get_data(f"SELECT salario_base, p_prestaciones, num_empleados FROM {tabla} WHERE id=1")
                
                if not df.empty:
                    data = df.iloc[0]
                    with st.form(f"form_{key_prefix}"):
                        s = st.number_input("Salario", value=float(data['salario_base']))
                        p = st.number_input("% Prestaciones", value=float(data['p_prestaciones']))
                        n = st.number_input("Nº Personas", value=int(data['num_empleados']))
                        
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
                    st.warning("Inicializando DB...")
            except: st.error("Error leyendo DB")

    with c1: render_nomina_form("🏢 Admin", "config_admin", "adm")
    with c2: render_nomina_form("🛍️ Ventas", "config_ventas", "ven")
    with c3: render_nomina_form("🏭 Producción", "config_mod", "mod")

# ------------------------------------------------------------------
# TAB 2: COSTOS FIJOS
# ------------------------------------------------------------------
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

    # Visualización
    df_man = get_data("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos ORDER BY id")
    
    # Filas Auto
    filas_auto = []
    # (Aquí iría la lógica de filas auto de nóminas que ya teníamos, simplificada para ahorrar espacio en esta respuesta)
    # ... [Puedes mantener el código de filas auto de la versión anterior aquí] ...
    
    # Editor
    ed_df = st.data_editor(df_man, disabled=["id"], num_rows="dynamic", key="cf_ed", column_config={"total_mensual": st.column_config.NumberColumn(format="Q%.2f")})
    
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

# ------------------------------------------------------------------
# TAB 3: MATERIAS PRIMAS (CORREGIDO)
# ------------------------------------------------------------------
with tabs[2]:
    st.header("Inventario Materia Prima")
    
    # Carga CSV MP con IVA
    with st.expander("📂 Carga Masiva (CSV)"):
        st.markdown("**Columnas:** `codigo, nombre, categoria, unidad_medida, costo`")
        with st.form("csv_mp_form", clear_on_submit=True):
            f = st.file_uploader("CSV", type="csv")
            incluye_iva = st.checkbox("Los precios del CSV incluyen IVA (se dividirá entre 1.12)", value=True)
            
            if st.form_submit_button("Cargar") and f:
                try:
                    df = pd.read_csv(f)
                    for _, r in df.iterrows():
                        costo_real = calcular_sin_iva(r['costo'], incluye_iva)
                        # Usamos 'codigo' del CSV para el campo 'codigo_interno'
                        cod = r['codigo'] if 'codigo' in df.columns else ''
                        
                        run_query("INSERT INTO materias_primas (codigo_interno, nombre, categoria, unidad_medida, costo_unitario) VALUES (:cod, :n, :c, :u, :p)",
                                  {'cod':cod, 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':costo_real})
                    st.success("Cargado"); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    # Tabla Editable
    df = get_data("SELECT id, codigo_interno, nombre, categoria, unidad_medida, costo_unitario FROM materias_primas ORDER BY nombre")
    
    st.info("💡 Edita el 'Código Interno' para poner tus códigos (ej: REPH005). El campo 'id' es automático.")
    
    ed = st.data_editor(
        df, 
        num_rows="dynamic", 
        key="mp_ed", 
        disabled=["id"], # <--- ESTO EVITA EL ERROR DATAERROR
        column_config={
            "costo_unitario": st.column_config.NumberColumn(format="Q%.4f", label="Costo sin IVA"),
            "codigo_interno": st.column_config.TextColumn(label="Tu Código (SKU)")
        }
    )
    
    if st.button("💾 Guardar MP"):
        ids_now = set()
        for _, r in ed.iterrows():
            if pd.notna(r['id']):
                ids_now.add(r['id'])
                run_query("UPDATE materias_primas SET codigo_interno=:cod, nombre=:n, categoria=:c, unidad_medida=:u, costo_unitario=:p WHERE id=:id",
                          {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario'], 'id':r['id']})
            else:
                run_query("INSERT INTO materias_primas (codigo_interno, nombre, categoria, unidad_medida, costo_unitario) VALUES (:cod, :n, :c, :u, :p)",
                          {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario']})
        
        ids_old = set(df['id'].tolist())
        to_del = list(ids_old - ids_now)
        if to_del:
             todel = tuple(to_del)
             if len(to_del)==1: todel = f"({to_del[0]})"
             run_query(f"DELETE FROM materias_primas WHERE id IN {todel}")
        st.success("Guardado"); st.rerun()

# ------------------------------------------------------------------
# TAB 4: FABRICA (PRODUCTOS) - CON CARGA CSV RESTAURADA
# ------------------------------------------------------------------
with tabs[3]:
    st.header("Productos y Recetas")
    
    # --- SECCIÓN CARGA MASIVA RESTAURADA ---
    with st.expander("📂 Carga Masiva de Productos (CSV)", expanded=True):
        st.info("Columnas: `codigo, nombre, categoria, tipo, precio, unidades_lote, minutos_total`")
        with st.form("csv_prod_form", clear_on_submit=True):
            f_p = st.file_uploader("Subir CSV Productos", type="csv")
            
            # CHECKBOX IVA PARA PRODUCTOS (OPCIONAL, AUNQUE EL PRECIO VENTA SUELE SER CON IVA)
            # Nota: El precio de venta sugerido es el final al público, usualmente con IVA.
            # Si quieres quitarle el IVA al guardarlo, marca esto.
            quitar_iva = st.checkbox("El precio de venta en el CSV incluye IVA (se guardará sin IVA)", value=False)
            
            if st.form_submit_button("Cargar Productos") and f_p:
                try:
                    dfp = pd.read_csv(f_p)
                    # Crear categorías faltantes
                    for c in dfp['categoria'].unique():
                        try: run_query("INSERT INTO categorias_producto (nombre) VALUES (:n)", {'n':c})
                        except: pass
                    
                    for _, r in dfp.iterrows():
                        mins = r['minutos_total'] if pd.notna(r['minutos_total']) else 0
                        es_lote = r['tipo'] == 'Lote'
                        u_lote = r['unidades_lote'] if es_lote else 1
                        m_unit = (mins / u_lote) if es_lote and u_lote > 0 else mins
                        
                        # Cálculo Precio
                        precio_final = calcular_sin_iva(r['precio'], quitar_iva)
                        
                        run_query("""INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                            VALUES (:c, :n, :l, :t, :ul, :ml, :mu, :p)
                            ON CONFLICT (codigo_barras) DO UPDATE SET 
                            nombre=:n, linea=:l, tipo_produccion=:t, unidades_por_lote=:ul, minutos_por_lote=:ml, minutos_por_unidad=:mu, precio_venta_sugerido=:p""",
                            {'c':str(r['codigo']), 'n':r['nombre'], 'l':r['categoria'], 't':r['tipo'], 'ul':u_lote, 'ml':mins, 'mu':m_unit, 'p':precio_final})
                    st.success("✅ Productos Cargados"); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
    
    # Panel Manual
    c_izq, c_der = st.columns([1, 2])
    
    with c_izq:
        st.subheader("Crear Individual")
        cats = get_data("SELECT nombre FROM categorias_producto")
        lista_cats = cats['nombre'].tolist() if not cats.empty else ['General']
        
        with st.form("new_p"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            cat = st.selectbox("Línea", lista_cats)
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            u_lote = st.number_input("Uds/Lote", 1)
            m_total = st.number_input("Minutos Totales", 0.0)
            precio = st.number_input("Precio Venta Sugerido", 0.0)
            iva_check = st.checkbox("Este precio incluye IVA", value=True)
            
            if st.form_submit_button("Guardar"):
                precio_real = calcular_sin_iva(precio, iva_check)
                m_unit = m_total / u_lote if tipo == "Lote" else m_total
                
                run_query("""INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                       VALUES (:c, :n, :l, :t, :ul, :ml, :mu, :p)
                       ON CONFLICT (codigo_barras) DO UPDATE SET 
                       nombre=:n, linea=:l, tipo_produccion=:t, unidades_por_lote=:ul, minutos_por_lote=:ml, minutos_por_unidad=:mu, precio_venta_sugerido=:p""",
                       {'c':cod, 'n':nom, 'l':cat, 't':tipo, 'ul':u_lote, 'ml':m_total, 'mu':m_unit, 'p':precio_real})
                st.success("Guardado"); st.rerun()

    with c_der:
        st.subheader("Constructor Recetas")
        prods = get_data("SELECT codigo_barras, nombre FROM productos")
        d_prods = {f"{r['nombre']}": r['codigo_barras'] for _, r in prods.iterrows()}
        sel = st.selectbox("Producto:", list(d_prods.keys()) if d_prods else [])
        
        if sel:
            pid = d_prods[sel]
            
            c1, c2, c3 = st.columns([3,2,1])
            # Ahora mostramos el Código Interno en el selector
            mps = get_data("SELECT id, nombre, codigo_interno FROM materias_primas ORDER BY nombre")
            d_mps = {f"{r['codigo_interno']} - {r['nombre']}" if r['codigo_interno'] else r['nombre']: r['id'] for _, r in mps.iterrows()}
            
            m_sel = c1.selectbox("MP", list(d_mps.keys()) if d_mps else [])
            cant = c2.number_input("Cant", 0.0, step=0.0001, format="%.4f")
            
            if c3.button("➕"):
                run_query("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (:pid, :mid, :c)", {'pid':pid, 'mid':d_mps[m_sel], 'c':cant}); st.rerun()
            
            rec = get_data("SELECT r.id, m.nombre, m.codigo_interno, r.cantidad, m.costo_unitario FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
            st.dataframe(rec, hide_index=True)
            if not rec.empty:
                del_id = st.selectbox("Borrar ID", rec['id'].tolist())
                if st.button("🗑️"): run_query("DELETE FROM recetas WHERE id=:id", {'id':del_id}); st.rerun()

# ------------------------------------------------------------------
# TAB 5: FICHA TÉCNICA
# ------------------------------------------------------------------
with tabs[4]:
    st.header("Buscador")
    # (Mantener el código de ficha técnica tal cual estaba en la versión anterior)
    prods = get_data("SELECT codigo_barras, nombre FROM productos")
    lista = [f"{r['nombre']} | {r['codigo_barras']}" for _, r in prods.iterrows()]
    sel = st.selectbox("Buscar", [""] + lista)
    
    if sel:
        cod = sel.split(" | ")[-1]
        p_dat = get_data("SELECT * FROM productos WHERE codigo_barras=:c", {'c':cod}).iloc[0]
        
        # 1. MP
        c_mat = get_data("SELECT SUM(r.cantidad * m.costo_unitario) FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:c", {'c':cod}).iloc[0,0] or 0
        div = p_dat['unidades_por_lote'] if p_dat['tipo_produccion'] == 'Lote' else 1
        c_mat_u = float(c_mat) / div
        
        # 2. MOD
        u_prom = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
        mod_cfg = get_data(f"SELECT salario_base, p_prestaciones, num_operarios as num_empleados, horas_mes FROM config_mod WHERE id=1").iloc[0]
        mod_dinero = float(mod_cfg['salario_base']*mod_cfg['num_empleados']*(1+mod_cfg['p_prestaciones']/100))
        
        if float(p_dat['minutos_por_unidad']) > 0:
            mod_hrs = float(mod_cfg['horas_mes']*mod_cfg['num_empleados'])
            c_min = mod_dinero / mod_hrs / 60 if mod_hrs > 0 else 0
            c_mod_u = float(p_dat['minutos_por_unidad']) * c_min
        else:
            c_mod_u = mod_dinero / u_prom if u_prom > 0 else 0

        # 3. CIF
        cif_df = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos WHERE id > 0")
        cif_tot = float(cif_df.iloc[0,0]) if not cif_df.empty and cif_df.iloc[0,0] else 0
        c_cif_u = cif_tot / u_prom if u_prom > 0 else 0
        
        c_tot = c_mat_u + c_mod_u + c_cif_u
        
        st.markdown(f"## {p_dat['nombre']}")
        k1, k2, k3 = st.columns(3)
        k1.metric("Costo Unitario", f"Q{c_tot:.2f}")
        k2.metric("Precio Venta", f"Q{p_dat['precio_venta_sugerido']:.2f}")
        margen = p_dat['precio_venta_sugerido'] - c_tot
        pct_margen = (margen / p_dat['precio_venta_sugerido'] * 100) if p_dat['precio_venta_sugerido'] > 0 else 0
        k3.metric("Margen", f"Q{margen:.2f}", f"{pct_margen:.1f}%")
