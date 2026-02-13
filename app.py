import streamlit as st
import pandas as pd
import sqlite3

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase 2", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria.db', check_same_thread=False)

db = get_connection()

def init_db_fase2():
    cursor = db.cursor()
    # 1. Configuración Global (Unidades Promedio)
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_global (
        id INTEGER PRIMARY KEY,
        unidades_promedio_mes INTEGER DEFAULT 1
    )''')
    
    # 2. Tabla de Materias Primas (Catálogo)
    cursor.execute('''CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        categoria TEXT, -- 'Materia Prima' o 'Fórmula'
        unidad_medida TEXT,
        costo_unitario REAL
    )''')

    # 3. Tabla de Productos
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        codigo_barras TEXT PRIMARY KEY,
        sku TEXT,
        nombre TEXT,
        linea TEXT,
        tipo_produccion TEXT, -- 'Unidad' o 'Lote'
        unidades_por_lote INTEGER DEFAULT 1,
        minutos_por_lote REAL DEFAULT 0,
        minutos_por_unidad REAL DEFAULT 0,
        precio_venta_sugerido REAL DEFAULT 0,
        activo INTEGER DEFAULT 1
    )''')

    # 4. Tabla de Recetas (Ingredientes)
    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id TEXT,
        mp_id INTEGER,
        cantidad REAL,
        FOREIGN KEY(producto_id) REFERENCES productos(codigo_barras),
        FOREIGN KEY(mp_id) REFERENCES materias_primas(id)
    )''')

    # Datos iniciales para pruebas
    cursor.execute("SELECT COUNT(*) FROM config_global")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_global (id, unidades_promedio_mes) VALUES (1, 1000)")
        # MP de ejemplo
        mps = [
            ('Envase 100ml', 'Materia Prima', 'Unidad', 5.50),
            ('Esencia Pink Sugar', 'Fórmula', 'ml', 0.85),
            ('Alcohol Etílico', 'Fórmula', 'ml', 0.05),
            ('Caja Lujo', 'Materia Prima', 'Unidad', 2.10)
        ]
        cursor.executemany("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)", mps)
    db.commit()

init_db_fase2()

# --- LÓGICA DE NEGOCIO ---

def duplicar_receta(origen_cod, destino_cod):
    cursor = db.cursor()
    cursor.execute("DELETE FROM recetas WHERE producto_id = ?", (destino_cod,))
    cursor.execute('''INSERT INTO recetas (producto_id, mp_id, cantidad) 
                      SELECT ?, mp_id, cantidad FROM recetas WHERE producto_id = ?''', (destino_cod, origen_cod))
    db.commit()

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería: Producción y Recetas")

tabs = st.tabs(["⚙️ Config. Base", "📦 Catálogo Productos", "📝 Constructor de Recetas", "🌿 Materias Primas"])

# TAB: CONFIGURACIÓN BASE (Denominador de Costos)
with tabs[0]:
    st.header("Configuración de Capacidad")
    res_global = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    
    with st.form("form_global"):
        nueva_media = st.number_input("Unidades Promedio Producidas al Mes", value=res_global[0], min_value=1)
        if st.form_submit_button("Actualizar Promedio"):
            db.execute("UPDATE config_global SET unidades_promedio_mes = ? WHERE id=1", (nueva_media,))
            db.commit()
            st.success("Promedio actualizado. Esto afectará el prorrateo de costos fijos.")

# TAB: CATÁLOGO DE PRODUCTOS
with tabs[1]:
    st.header("Gestión de Productos")
    with st.expander("🆕 Registrar Nuevo Producto"):
        with st.form("nuevo_producto"):
            c1, c2, c3 = st.columns(3)
            cod = c1.text_input("Código de Barras")
            sku = c2.text_input("SKU Interno")
            nom = c3.text_input("Nombre del Producto")
            
            lin = c1.selectbox("Línea", ["Rollon", "Estuche", "Spray", "AAA", "F1", "Estrellita"])
            tipo = c2.selectbox("Tipo de Producción", ["Unidad", "Lote"])
            
            if tipo == "Lote":
                u_lote = c3.number_input("Unidades por Lote", min_value=1, value=100)
                m_lote = c1.number_input("Minutos por Lote", min_value=0.1, value=60.0)
                m_unit = m_lote / u_lote
            else:
                u_lote = 1
                m_unit = c3.number_input("Minutos por Unidad", min_value=0.1, value=5.0)
                m_lote = m_unit

            pvp = c2.number_input("Precio Venta Sugerido (Q)", min_value=0.0)
            
            if st.form_submit_button("Guardar Producto"):
                db.execute('''INSERT INTO productos (codigo_barras, sku, nombre, linea, tipo_produccion, 
                              unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido) 
                              VALUES (?,?,?,?,?,?,?,?,?)''', 
                           (cod, sku, nom, lin, tipo, u_lote, m_lote, m_unit, pvp))
                db.commit()
                st.rerun()

    df_prod = pd.read_sql_query("SELECT * FROM productos WHERE activo=1", db)
    st.dataframe(df_prod, use_container_width=True)

# TAB: CONSTRUCTOR DE RECETAS
with tabs[2]:
    st.header("Estructura de Costos por Producto")
    
    prods = db.execute("SELECT codigo_barras, nombre FROM productos").fetchall()
    prod_dict = {f"{p[1]} ({p[0]})": p[0] for p in prods}
    
    if prods:
        col_sel, col_dup = st.columns([2, 1])
        prod_sel_nom = col_sel.selectbox("Seleccione Producto para editar receta", prod_dict.keys())
        prod_id = prod_dict[prod_sel_nom]
        
        # Botón Duplicar
        with col_dup:
            st.write("---")
            prod_origen = st.selectbox("Duplicar desde:", ["Seleccionar..."] + list(prod_dict.keys()), key="dup_src")
            if st.button("🚀 Clonar Receta") and prod_origen != "Seleccionar...":
                duplicar_receta(prod_dict[prod_origen], prod_id)
                st.success("Receta duplicada con éxito.")
                st.rerun()

        # Datos del producto seleccionado
        p_info = db.execute("SELECT tipo_produccion, unidades_por_lote, minutos_por_unidad FROM productos WHERE codigo_barras=?", (prod_id,)).fetchone()
        
        # Obtener costo_minuto de la Fase 1 (Simulado aquí con el valor que diste: 0.44)
        costo_minuto_actual = 0.44 

        # Interfaz de dos paneles
        panel_izq, panel_der = st.columns(2)
        
        with panel_der:
            st.subheader("➕ Agregar Ingrediente")
            mps = db.execute("SELECT id, nombre, categoria, costo_unitario, unidad_medida FROM materias_primas").fetchall()
            mp_dict = {f"{m[1]} ({m[2]}) - {m[4]}": m for m in mps}
            
            mp_sel_nom = st.selectbox("Buscar Materia Prima", mp_dict.keys())
            cant = st.number_input("Cantidad necesaria", min_value=0.0, step=0.01)
            
            if st.button("Añadir a Receta"):
                db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (?,?,?)", 
                           (prod_id, mp_dict[mp_sel_nom][0], cant))
                db.commit()
                st.rerun()

        with panel_izq:
            st.subheader("📋 Composición de la Receta")
            query_receta = '''
                SELECT r.id, m.nombre, m.categoria, r.cantidad, m.unidad_medida, m.costo_unitario,
                (r.cantidad * m.costo_unitario) as subtotal
                FROM recetas r JOIN materias_primas m ON r.mp_id = m.id
                WHERE r.producto_id = ?
            '''
            df_receta = pd.read_sql_query(query_receta, db, params=(prod_id,))
            
            if not df_receta.empty:
                st.table(df_receta[['nombre', 'categoria', 'cantidad', 'unidad_medida', 'subtotal']])
                
                # Cálculos de Totales
                total_formula = df_receta[df_receta['categoria'] == 'Fórmula']['subtotal'].sum()
                total_mp = df_receta[df_receta['categoria'] == 'Materia Prima']['subtotal'].sum()
                costo_materiales = total_formula + total_mp
                
                # Ajuste por lote
                divisor = p_info[1] if p_info[0] == "Lote" else 1
                
                costo_mat_unitario = costo_materiales / divisor
                costo_mod_unitario = p_info[2] * costo_minuto_actual
                costo_variable_total = costo_mat_unitario + costo_mod_unitario
                
                st.divider()
                if p_info[0] == "Lote":
                    st.info(f"💡 Esta receta es por LOTE ({p_info[1]} uds).")
                
                c_a, c_b = st.columns(2)
                c_a.metric("Costo Materiales (Unit)", f"Q{costo_mat_unitario:.2f}")
                c_b.metric("Costo MOD (Unit)", f"Q{costo_mod_unitario:.2f}")
                st.metric("COSTO VARIABLE TOTAL UNITARIO", f"Q{costo_variable_total:.2f}")

# TAB: MATERIAS PRIMAS (Gestión de precios base)
with tabs[3]:
    st.header("Catálogo de Materias Primas")
    # Formulario simple para añadir MP
    with st.expander("Añadir Nueva Materia Prima"):
        with st.form("nueva_mp"):
            n_mp = st.text_input("Nombre MP")
            cat_mp = st.radio("Categoría", ["Fórmula", "Materia Prima"])
            uni_mp = st.text_input("Unidad (ej: ml, gramo, Unidad)")
            cos_mp = st.number_input("Costo Unitario (Q)", min_value=0.0)
            if st.form_submit_button("Guardar MP"):
                db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)",
                           (n_mp, cat_mp, uni_mp, cos_mp))
                db.commit()
                st.rerun()
    
    st.dataframe(pd.read_sql_query("SELECT * FROM materias_primas", db), use_container_width=True)
