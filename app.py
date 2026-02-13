import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería Pro", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_v2.db', check_same_thread=False)

db = get_connection()

def init_db():
    cursor = db.cursor()
    # 1. Costos Fijos (Ahora incluye campos para vinculación automática)
    cursor.execute('''CREATE TABLE IF NOT EXISTS costos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT,
        total_mensual REAL,
        p_admin REAL, p_ventas REAL, p_prod REAL,
        es_automatico INTEGER DEFAULT 0
    )''')
    
    # 2. Nóminas (MOD y Admin/Ventas)
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracion_nominas (
        tipo TEXT PRIMARY KEY, -- 'MOD' o 'ADMIN_VENTAS'
        salario_base REAL, p_prestaciones REAL, num_empleados INTEGER, horas_mes REAL
    )''')

    # 3. Materias Primas y Productos
    cursor.execute('''CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT, categoria TEXT, unidad_medida TEXT, costo_unitario REAL
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
        codigo_barras TEXT PRIMARY KEY, nombre TEXT, linea TEXT, 
        tipo_produccion TEXT, unidades_lote INTEGER, minutos_lote REAL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id TEXT, 
        mp_id INTEGER, cantidad REAL, unidad_receta TEXT
    )''')

    # Datos Iniciales si está vacío
    cursor.execute("SELECT COUNT(*) FROM configuracion_nominas")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracion_nominas VALUES ('MOD', 4252.28, 41.83, 3, 176)")
        cursor.execute("INSERT INTO configuracion_nominas VALUES ('ADMIN_VENTAS', 72288.76, 41.83, 1, 176)")
        # Insertar conceptos fijos base
        conceptos = [
            ('Alquiler', 13400, 50, 10, 40), ('Energía Eléctrica', 1000, 50, 10, 40),
            ('Agua', 300, 50, 10, 40), ('Seguridad', 800, 50, 10, 40)
        ]
        for c in conceptos:
            cursor.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)", c)
    
    db.commit()

init_db()

# --- LÓGICA DE CONVERSIÓN ---
def convertir_a_base(cantidad, unidad_origen, unidad_base):
    # Diccionario simple de conversión
    conversiones = {
        ('Litro', 'ml'): 1000,
        ('Kg', 'gramo'): 1000,
        ('Galón', 'ml'): 3785.41
    }
    factor = conversiones.get((unidad_origen, unidad_base), 1)
    return cantidad * factor

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería: Arquitectura de Costos")

menu = ["💰 Matriz de Costos", "👥 Nóminas", "🌿 Materias Primas", "📝 Constructor Recetas"]
choice = st.sidebar.selectbox("Módulo", menu)

# --- MÓDULO NÓMINAS (Base para la Matriz) ---
if choice == "👥 Nóminas":
    st.header("Gestión de Personal")
    tipo_n = st.radio("Seleccione Nómina", ["MOD (Producción)", "Administración y Ventas"])
    db_key = 'MOD' if "MOD" in tipo_n else 'ADMIN_VENTAS'
    
    data = db.execute("SELECT * FROM configuracion_nominas WHERE tipo=?", (db_key,)).fetchone()
    
    with st.form("form_nomina"):
        c1, c2 = st.columns(2)
        salario = c1.number_input("Salario/Monto Base", value=data[1])
        prest = c2.number_input("% Prestaciones", value=data[2])
        emps = c1.number_input("Cantidad Personas/Cargos", value=data[3])
        if st.form_submit_button("Actualizar Nómina"):
            db.execute("UPDATE configuracion_nominas SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE tipo=?",
                       (salario, prest, emps, db_key))
            db.commit()
            st.success("Nómina actualizada")

# --- MÓDULO MATRIZ (EDITABLE) ---
elif choice == "💰 Matriz de Costos":
    st.header("Matriz de Costos Fijos Mensuales")
    
    # Obtener datos de nómina para actualizar la matriz automáticamente
    nom_admin = db.execute("SELECT salario_base, p_prestaciones FROM configuracion_nominas WHERE tipo='ADMIN_VENTAS'").fetchone()
    total_nomina_admin = nom_admin[0] * (1 + nom_admin[1]/100)
    
    df_fijos = pd.read_sql_query("SELECT * FROM costos_fijos", db)
    
    # Hacer la tabla editable
    edited_df = st.data_editor(df_fijos, num_rows="dynamic", key="editor_matriz", hide_index=True)
    
    if st.button("Guardar Cambios en Matriz"):
        for index, row in edited_df.iterrows():
            if row['id'] is not None:
                db.execute("UPDATE costos_fijos SET concepto=?, total_mensual=?, p_admin=?, p_ventas=?, p_prod=? WHERE id=?",
                           (row['concepto'], row['total_mensual'], row['p_admin'], row['p_ventas'], row['p_prod'], row['id']))
        db.commit()
        st.rerun()

    # Cálculos de Totales
    edited_df['Admin (Q)'] = edited_df['total_mensual'] * (edited_df['p_admin']/100)
    edited_df['Ventas (Q)'] = edited_df['total_mensual'] * (edited_df['p_ventas']/100)
    edited_df['Producción (Q)'] = edited_df['total_mensual'] * (edited_df['p_prod']/100)
    
    st.divider()
    t_gen = edited_df['total_mensual'].sum()
    t_prod = edited_df['Producción (Q)'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("TOTAL GENERAL", f"Q{t_gen:,.2f}")
    c2.metric("TOTAL PRODUCCIÓN (CIF)", f"Q{t_prod:,.2f}")
    c3.metric("Nómina Admin Actual", f"Q{total_nomina_admin:,.2f}")

# --- MÓDULO MATERIAS PRIMAS (CSV + ELIMINAR) ---
elif choice == "🌿 Materias Primas":
    st.header("Inventario de Materias Primas")
    
    with st.expander("⬆️ Carga Masiva (CSV)"):
        uploaded_file = st.file_uploader("Subir archivo CSV", type=["csv"])
        if uploaded_file:
            df_upload = pd.read_csv(uploaded_file)
            st.write("Vista previa:", df_upload.head())
            if st.button("Confirmar Carga"):
                df_upload.to_sql('materias_primas', db, if_exists='append', index=False)
                st.success("Datos cargados")

    df_mp = pd.read_sql_query("SELECT * FROM materias_primas", db)
    
    # Opción para eliminar
    st.subheader("Lista de Materiales")
    for idx, row in df_mp.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"**{row['nombre']}** ({row['unidad_medida']}) - Q{row['costo_unitario']}")
        if col3.button("Eliminar", key=f"del_{row['id']}"):
            db.execute("DELETE FROM materias_primas WHERE id=?", (row['id'],))
            db.commit()
            st.rerun()

# --- MÓDULO RECETAS (CON CONVERSOR) ---
elif choice == "📝 Constructor Recetas":
    st.header("Constructor de Recetas e Ingeniería de Producto")
    
    prods = pd.read_sql_query("SELECT codigo_barras, nombre FROM productos", db)
    if prods.empty:
        st.warning("Primero registre productos en el catálogo")
    else:
        sel_p = st.selectbox("Seleccione Producto", prods['nombre'])
        p_id = prods[prods['nombre'] == sel_p]['codigo_barras'].values[0]
        
        col_rec1, col_rec2 = st.columns([2, 1])
        
        with col_rec2:
            st.subheader("Añadir Ingrediente")
            mps = pd.read_sql_query("SELECT * FROM materias_primas", db)
            mp_sel = st.selectbox("Materia Prima", mps['nombre'])
            mp_data = mps[mps['nombre'] == mp_sel].iloc[0]
            
            cant = st.number_input("Cantidad", min_value=0.0)
            u_medida = st.selectbox("Unidad de Medida", ["ml", "Litro", "gramo", "Kg", "Unidad"])
            
            if st.button("Agregar a Receta"):
                # Aquí podrías aplicar la lógica de conversión antes de guardar
                db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_receta) VALUES (?,?,?,?)",
                           (p_id, int(mp_data['id']), cant, u_medida))
                db.commit()
                st.rerun()

        with col_rec1:
            st.subheader("Composición de la Receta")
            df_rec = pd.read_sql_query(f'''
                SELECT r.id, m.nombre, r.cantidad, r.unidad_receta, m.costo_unitario
                FROM recetas r JOIN materias_primas m ON r.mp_id = m.id
                WHERE r.producto_id = '{p_id}'
            ''', db)
            
            if not df_rec.empty:
                # Calcular subtotal con conversor (simplificado para el ejemplo)
                df_rec['Subtotal'] = df_rec['cantidad'] * df_rec['costo_unitario']
                st.table(df_rec)
                st.metric("COSTO TOTAL RECETA", f"Q{df_rec['Subtotal'].sum():,.2f}")
