import streamlit as st
import pandas as pd
import sqlite3

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ERP Perfumería - Unificado", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('costos_perfumeria.db', check_same_thread=False)

db = get_connection()

def init_db():
    cursor = db.cursor()
    # 1. Tabla de Costos Fijos
    cursor.execute('''CREATE TABLE IF NOT EXISTS costos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT,
        total_mensual REAL,
        p_admin REAL DEFAULT 50,
        p_ventas REAL DEFAULT 10,
        p_prod REAL DEFAULT 40
    )''')
    
    # 2. Tabla de Configuración MOD
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_mod (
        id INTEGER PRIMARY KEY,
        salario_base REAL,
        p_prestaciones REAL,
        num_operarios INTEGER,
        horas_mes REAL
    )''')
    
    # 3. Configuración Global (Unidades Promedio)
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_global (
        id INTEGER PRIMARY KEY,
        unidades_promedio_mes INTEGER DEFAULT 1
    )''')

    # 4. Categorías de Producto
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias_producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )''')

    # 5. Materias Primas
    cursor.execute('''CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        categoria TEXT,
        unidad_medida TEXT,
        costo_unitario REAL
    )''')

    # 6. Productos
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        codigo_barras TEXT PRIMARY KEY,
        sku TEXT,
        nombre TEXT,
        linea TEXT,
        tipo_produccion TEXT,
        unidades_por_lote INTEGER DEFAULT 1,
        minutos_por_lote REAL DEFAULT 0,
        minutos_por_unidad REAL DEFAULT 0,
        precio_venta_sugerido REAL DEFAULT 0,
        activo INTEGER DEFAULT 1
    )''')

    # 7. Recetas
    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id TEXT,
        mp_id INTEGER,
        cantidad REAL,
        FOREIGN KEY(producto_id) REFERENCES productos(codigo_barras),
        FOREIGN KEY(mp_id) REFERENCES materias_primas(id)
    )''')

    # --- DATOS INICIALES (Si las tablas están vacías) ---
    cursor.execute("SELECT COUNT(*) FROM costos_fijos")
    if cursor.fetchone()[0] == 0:
        fijos = [
            ('Alquiler', 13400.0, 50, 10, 40), ('Internet', 600.0, 50, 10, 40),
            ('Teléfono', 1300.0, 50, 10, 40), ('Energía Eléctrica', 1000.0, 50, 10, 40),
            ('Agua', 300.0, 50, 10, 40), ('Seguridad', 800.0, 50, 10, 40),
            ('Software', 1057.0, 50, 10, 40), ('Contabilidad', 2650.0, 50, 10, 40),
            ('Asesoría Externa', 8000.0, 50, 10, 40), ('Combustible', 2000.0, 10, 20, 70),
            ('Empaque', 1900.0, 0, 20, 80), ('Nómina Admin/Ventas', 72288.76, 82.35, 17.65, 0),
            ('Prestaciones', 30238.39, 82.35, 17.65, 0)
        ]
        cursor.executemany("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)", fijos)
        cursor.execute("INSERT INTO config_mod VALUES (1, 4252.28, 41.83, 3, 176)")
        cursor.execute("INSERT INTO config_global (id, unidades_promedio_mes) VALUES (1, 5000)")
        cats = [('Rollon',), ('Estuche',), ('Spray',), ('AAA',), ('F1',), ('Estrellita',), ('Réplica',)]
        cursor.executemany("INSERT INTO categorias_producto (nombre) VALUES (?)", cats)
        
    db.commit()

init_db()

# --- FUNCIONES DE APOYO ---
def get_costos_fijos_df():
    df = pd.read_sql_query("SELECT * FROM costos_fijos", db)
    df['Admin (Q)'] = df['total_mensual'] * (df['p_admin'] / 100)
    df['Ventas (Q)'] = df['total_mensual'] * (df['p_ventas'] / 100)
    df['Producción (Q)'] = df['total_mensual'] * (df['p_prod'] / 100)
    return df

# --- INTERFAZ PRINCIPAL ---
st.title("🧪 ERP Perfumería: Control Total de Costos")

tabs = st.tabs(["💰 Matriz Fijos", "👷 MOD", "📦 Productos", "📝 Recetas", "🔬 Materias Primas"])

# 1. TABLA COSTOS FIJOS
with tabs[0]:
    st.header("Matriz de Costos Fijos")
    df_f = get_costos_fijos_df()
    st.dataframe(df_f.style.format({"total_mensual": "Q{:.2f}", "Admin (Q)": "Q{:.2f}", "Ventas (Q)": "Q{:.2f}", "Producción (Q)": "Q{:.2f}"}), use_container_width=True)
    
    totales_f = df_f[['total_mensual', 'Admin (Q)', 'Ventas (Q)', 'Producción (Q)']].sum()
    st.divider()
    
    # Unidades Promedio (Modificable)
    res_global = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    with st.sidebar:
        st.header("Configuración Global")
        u_promedio = st.number_input("Unidades Promedio Mensuales", value=res_global[0], min_value=1)
        if st.button("Actualizar Unidades"):
            db.execute("UPDATE config_global SET unidades_promedio_mes = ? WHERE id=1", (u_promedio,))
            db.commit()
            st.rerun()

    c1, c2, c3 = st.columns(3)
    c1.metric("CIF Total (Producción)", f"Q{totales_f[3]:,.2f}")
    c2.metric("CIF Unitario", f"Q{(totales_f[3]/u_promedio):,.2f}")
    c3.metric("Gasto Admin Unitario", f"Q{(totales_f[1]/u_promedio):,.2f}")

# 2. MANO DE OBRA (MOD)
with tabs[1]:
    st.header("Mano de Obra Directa")
    mod_data = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
    
    with st.form("form_mod"):
        col1, col2 = st.columns(2)
        salario = col1.number_input("Salario Base", value=mod_data[1])
        pct_prest = col2.number_input("% Prestaciones", value=mod_data[2])
        ops = col1.number_input("Operarios", value=mod_data[3])
        h_mes = col2.number_input("Horas/Mes", value=mod_data[4])
        if st.form_submit_button("Guardar Cambios MOD"):
            db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1", (salario, pct_prest, ops, h_mes))
            db.commit()
            st.rerun()
            
    c_op = salario * (1 + pct_prest/100)
    t_mod = c_op * ops
    t_hrs = h_mes * ops
    c_minuto = (t_mod / t_hrs / 60) if t_hrs > 0 else 0
    st.metric("Costo por Minuto MOD", f"Q{c_minuto:,.4f}")

# 3. PRODUCTOS
with tabs[2]:
    st.header("Catálogo de Productos")
    cats_db = db.execute("SELECT nombre FROM categorias_producto").fetchall()
    lista_cats = [c[0] for c in cats_db]
    
    with st.expander("➕ Nuevo Producto"):
        with st.form("n_prod"):
            f1, f2, f3 = st.columns(3)
            cod = f1.text_input("Código Barras")
            nom = f2.text_input("Nombre")
            cat = f3.selectbox("Línea", lista_cats)
            tipo = f1.selectbox("Tipo", ["Unidad", "Lote"])
            u_lote = f2.number_input("Uds por Lote", value=1, min_value=1)
            m_lote = f3.number_input("Minutos Totales", value=1.0)
            if st.form_submit_button("Registrar"):
                m_unit = m_lote / u_lote
                db.execute("INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad) VALUES (?,?,?,?,?,?,?)",
                           (cod, nom, cat, tipo, u_lote, m_lote, m_unit))
                db.commit()
                st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM productos", db), use_container_width=True)

# 4. RECETAS
with tabs[3]:
    st.header("Constructor de Recetas")
    prods_db = db.execute("SELECT codigo_barras, nombre FROM productos").fetchall()
    dict_p = {f"{p[1]} ({p[0]})": p[0] for p in prods_db}
    
    if dict_p:
        sel_p_nom = st.selectbox("Seleccione Producto", dict_p.keys())
        p_id = dict_p[sel_p_nom]
        
        # Panel Edición
        p_info = db.execute("SELECT tipo_produccion, unidades_por_lote, minutos_por_unidad FROM productos WHERE codigo_barras=?", (p_id,)).fetchone()
        
        col_rec_izq, col_rec_der = st.columns(2)
        
        with col_rec_der:
            st.subheader("Añadir Ingredientes")
            mps_db = db.execute("SELECT id, nombre, costo_unitario, categoria FROM materias_primas").fetchall()
            dict_mp = {f"{m[1]} ({m[3]})": m for m in mps_db}
            mp_sel = st.selectbox("Materia Prima", dict_mp.keys())
            cant_n = st.number_input("Cantidad", min_value=0.0, step=0.1)
            if st.button("Añadir"):
                db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (?,?,?)", (p_id, dict_mp[mp_sel][0], cant_n))
                db.commit()
                st.rerun()
        
        with col_rec_izq:
            st.subheader("Composición")
            df_r = pd.read_sql_query('''SELECT r.id, m.nombre, r.cantidad, m.costo_unitario, (r.cantidad * m.costo_unitario) as subtotal 
                                     FROM recetas r JOIN materias_primas m ON r.mp_id = m.id WHERE r.producto_id = ?''', db, params=(p_id,))
            st.table(df_r)
            
            # Cálculos finales
            total_mat = df_r['subtotal'].sum()
            divisor = p_info[1] if p_info[0] == "Lote" else 1
            mat_unit = total_mat / divisor
            mod_unit = p_info[2] * c_minuto
            
            st.metric("Costo Variable Unitario", f"Q{(mat_unit + mod_unit):,.2f}")

# 5. MATERIAS PRIMAS
with tabs[4]:
    st.header("Catálogo de Materiales")
    with st.form("n_mp"):
        n1, n2, n3, n4 = st.columns(4)
        nom_m = n1.text_input("Nombre Material")
        cat_m = n2.selectbox("Categoría", ["Materia Prima", "Fórmula"])
        uni_m = n3.text_input("Unidad (ml, ud)")
        cos_m = n4.number_input("Costo", min_value=0.0)
        if st.form_submit_button("Guardar Material"):
            db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)", (nom_m, cat_m, uni_m, cos_m))
            db.commit()
            st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM materias_primas", db), use_container_width=True)
