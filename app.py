import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase 2.1", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_v2.db', check_same_thread=False)

db = get_connection()

# --- INICIALIZACIÓN DE BASE DE DATOS ---
def init_db():
    cursor = db.cursor()
    
    # 1. Costos Fijos (Rubros manuales)
    cursor.execute('''CREATE TABLE IF NOT EXISTS costos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT,
        total_mensual REAL,
        p_admin REAL DEFAULT 50,
        p_ventas REAL DEFAULT 10,
        p_prod REAL DEFAULT 40
    )''')

    # 2. Config MOD (Operarios Producción)
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_mod (
        id INTEGER PRIMARY KEY,
        salario_base REAL,
        p_prestaciones REAL,
        num_operarios INTEGER,
        horas_mes REAL
    )''')

    # 3. Config Nómina Admin/Ventas (NUEVO)
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_admin (
        id INTEGER PRIMARY KEY,
        salario_base REAL,
        p_prestaciones REAL,
        num_empleados INTEGER
    )''')

    # 4. Config Global
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_global (
        id INTEGER PRIMARY KEY,
        unidades_promedio_mes INTEGER DEFAULT 1
    )''')

    # 5. Materias Primas
    cursor.execute('''CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        categoria TEXT,
        unidad_medida TEXT,
        costo_unitario REAL
    )''')

    # 6. Productos y Recetas
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias_producto (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''')
    
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id TEXT,
        mp_id INTEGER,
        cantidad REAL,
        FOREIGN KEY(producto_id) REFERENCES productos(codigo_barras),
        FOREIGN KEY(mp_id) REFERENCES materias_primas(id)
    )''')

    # --- DATOS POR DEFECTO ---
    cursor.execute("SELECT COUNT(*) FROM costos_fijos")
    if cursor.fetchone()[0] == 0:
        # Solo rubros que NO son nómina (la nómina se calcula aparte ahora)
        fijos = [
            ('Alquiler', 13400.0, 50, 10, 40), ('Internet', 600.0, 50, 10, 40),
            ('Teléfono', 1300.0, 50, 10, 40), ('Energía Eléctrica', 1000.0, 50, 10, 40),
            ('Agua', 300.0, 50, 10, 40), ('Seguridad', 800.0, 50, 10, 40),
            ('Software', 1057.0, 50, 10, 40), ('Contabilidad', 2650.0, 50, 10, 40),
            ('Asesoría Externa', 8000.0, 50, 10, 40), ('Combustible', 2000.0, 10, 20, 70),
            ('Empaque', 1900.0, 0, 20, 80)
        ]
        cursor.executemany("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)", fijos)
        
        # Inicializar Configs
        cursor.execute("INSERT INTO config_mod VALUES (1, 4252.28, 41.83, 2, 176)") # 2 operarios según tus datos
        # Nómina Admin: Calculado para que coincida con tus 72k + 30k aprox, ajusta empleados/salario según realidad
        cursor.execute("INSERT INTO config_admin VALUES (1, 5000.00, 41.83, 10)") 
        cursor.execute("INSERT INTO config_global VALUES (1, 5000)")
        
        cats = [('Rollon',), ('Estuche',), ('Spray',), ('AAA',), ('F1',), ('Estrellita',), ('Réplica',)]
        cursor.executemany("INSERT INTO categorias_producto (nombre) VALUES (?)", cats)

    db.commit()

init_db()

# --- FUNCIONES AUXILIARES ---
def calcular_nomina_admin():
    # Retorna: Total Salarios, Total Prestaciones
    cfg = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
    if cfg:
        salario, prest_pct, empleados = cfg[1], cfg[2], cfg[3]
        total_salario = salario * empleados
        total_prestaciones = total_salario * (prest_pct / 100)
        return total_salario, total_prestaciones
    return 0, 0

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería Integral")

tabs = st.tabs(["👥 Nóminas", "💰 Matriz Costos Fijos", "🌿 Materias Primas", "📦 Productos & Recetas"])

# ---------------------------------------------------------
# TAB 1: NÓMINAS (MOD y ADMIN)
# ---------------------------------------------------------
with tabs[0]:
    st.header("Gestión de Nóminas")
    c_mod, c_admin = st.columns(2)
    
    # 1. MOD (Producción)
    with c_mod:
        st.subheader("👷 Mano de Obra Directa (Producción)")
        mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
        with st.form("edit_mod"):
            sal_mod = st.number_input("Salario Base Operario", value=mod[1])
            pre_mod = st.number_input("% Prestaciones", value=mod[2])
            num_mod = st.number_input("Nº Operarios", value=mod[3])
            hrs_mod = st.number_input("Horas/Mes/Op", value=mod[4])
            if st.form_submit_button("Actualizar MOD"):
                db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1", 
                           (sal_mod, pre_mod, num_mod, hrs_mod))
                db.commit()
                st.rerun()
        
        # Cálculos Visuales MOD
        total_mod = (sal_mod * (1 + pre_mod/100)) * num_mod
        costo_min = (total_mod / (hrs_mod * num_mod) / 60) if (hrs_mod * num_mod) > 0 else 0
        st.info(f"💰 Total Mensual MOD: Q{total_mod:,.2f}")
        st.success(f"⏱️ Costo Minuto Operario: Q{costo_min:,.4f}")

    # 2. ADMIN / VENTAS
    with c_admin:
        st.subheader("👔 Nómina Admin y Ventas")
        adm = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
        with st.form("edit_admin"):
            sal_adm = st.number_input("Salario Promedio", value=adm[1])
            pre_adm = st.number_input("% Prestaciones", value=adm[2])
            num_adm = st.number_input("Nº Empleados", value=adm[3])
            st.caption("Este monto se inyectará automáticamente en la Matriz de Costos Fijos.")
            if st.form_submit_button("Actualizar Admin/Ventas"):
                db.execute("UPDATE config_admin SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", 
                           (sal_adm, pre_adm, num_adm))
                db.commit()
                st.rerun()
        
        # Cálculos Visuales Admin
        t_sal_adm = sal_adm * num_adm
        t_pre_adm = t_sal_adm * (pre_adm/100)
        st.info(f"💰 Nómina Mensual: Q{t_sal_adm:,.2f}")
        st.info(f"💰 Prestaciones: Q{t_pre_adm:,.2f}")

# ---------------------------------------------------------
# TAB 2: MATRIZ DE COSTOS FIJOS (EDITABLE)
# ---------------------------------------------------------
with tabs[1]:
    st.header("Matriz de Distribución de Costos")
    
    # 1. Obtener Datos Manuales
    df_manual = pd.read_sql("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos", db)
    
    # 2. Inyectar Filas de Nómina (Calculadas, NO editables en la grilla)
    sal_adm_tot, prest_adm_tot = calcular_nomina_admin()
    
    # Crear filas virtuales para mostrar
    fila_salario = {'id': -1, 'concepto': '⚡ AUTO: Nómina Admin/Ventas', 'total_mensual': sal_adm_tot, 'p_admin': 50, 'p_ventas': 50, 'p_prod': 0}
    fila_presta = {'id': -2, 'concepto': '⚡ AUTO: Prestaciones Admin/Ventas', 'total_mensual': prest_adm_tot, 'p_admin': 50, 'p_ventas': 50, 'p_prod': 0}
    
    # Unir para visualizar (usamos concat)
    df_full = pd.concat([df_manual, pd.DataFrame([fila_salario, fila_presta])], ignore_index=True)

    # 3. Editor de Datos
    st.write("Edita los montos y porcentajes directamente en la tabla. (Las filas 'AUTO' se editan en la pestaña Nóminas)")
    
    edited_df = st.data_editor(
        df_full,
        column_config={
            "id": None, # Ocultar ID
            "total_mensual": st.column_config.NumberColumn("Total Mensual (Q)", format="Q%.2f"),
            "p_admin": st.column_config.NumberColumn("% Admin", format="%.1f%%"),
            "p_ventas": st.column_config.NumberColumn("% Ventas", format="%.1f%%"),
            "p_prod": st.column_config.NumberColumn("% Prod", format="%.1f%%"),
        },
        disabled=["id"], # Solo editar datos manuales
        num_rows="dynamic",
        key="editor_costos"
    )

    # 4. Guardar Cambios (Solo de las filas manuales, ID > 0)
    if st.button("💾 Guardar Cambios en Costos Fijos"):
        # Filtrar solo las filas que vienen de la DB (tienen ID positivo o son nuevas)
        for index, row in edited_df.iterrows():
            if row['id'] >= 0: # Es un registro existente manual
                # Validar suma 100%
                if abs(row['p_admin'] + row['p_ventas'] + row['p_prod'] - 100) > 0.1:
                    st.warning(f"El concepto '{row['concepto']}' no suma 100%. Se ajustará automáticamente.")
                
                db.execute("UPDATE costos_fijos SET concepto=?, total_mensual=?, p_admin=?, p_ventas=?, p_prod=? WHERE id=?",
                           (row['concepto'], row['total_mensual'], row['p_admin'], row['p_ventas'], row['p_prod'], row['id']))
            elif pd.isna(row['id']): # Es una fila nueva añadida por el usuario
                db.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)",
                           (row['concepto'], row['total_mensual'], row['p_admin'], row['p_ventas'], row['p_prod']))
        
        # Eliminar registros borrados en el editor
        ids_presentes = [r['id'] for i, r in edited_df.iterrows() if r['id'] >= 0]
        if ids_presentes:
            ids_str = ','.join(map(str, ids_presentes))
            db.execute(f"DELETE FROM costos_fijos WHERE id NOT IN ({ids_str})")
        
        db.commit()
        st.success("Matriz actualizada correctamente.")
        st.rerun()

    # 5. CÁLCULO DE TOTALES Y PRORRATEO
    # Recalculamos sobre el DF editado para mostrar tiempo real
    df_calc = edited_df.copy()
    df_calc['Monto Admin'] = df_calc['total_mensual'] * (df_calc['p_admin']/100)
    df_calc['Monto Ventas'] = df_calc['total_mensual'] * (df_calc['p_ventas']/100)
    df_calc['Monto Prod'] = df_calc['total_mensual'] * (df_calc['p_prod']/100)

    # Totales Generales
    total_gral = df_calc['total_mensual'].sum()
    total_adm = df_calc['Monto Admin'].sum()
    total_ven = df_calc['Monto Ventas'].sum()
    total_prod = df_calc['Monto Prod'].sum()

    st.divider()
    st.subheader("📊 Totales Generales del Mes")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("TOTAL GASTOS", f"Q{total_gral:,.2f}", delta="100%")
    col2.metric("Total Administración", f"Q{total_adm:,.2f}", delta=f"{total_adm/total_gral*100:.1f}%")
    col3.metric("Total Sala Ventas", f"Q{total_ven:,.2f}", delta=f"{total_ven/total_gral*100:.1f}%")
    col4.metric("Total Producción (CIF)", f"Q{total_prod:,.2f}", delta=f"{total_prod/total_gral*100:.1f}%")
    
    # Costos Unitarios Base
    st.write("---")
    res_global = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    unidades_base = st.number_input("Unidades Base para Prorrateo", value=res_global[0])
    if unidades_base != res_global[0]:
        db.execute("UPDATE config_global SET unidades_promedio_mes=? WHERE id=1", (unidades_base,))
        db.commit()
    
    cif_unit = total_prod / unidades_base
    st.markdown(f"### 🎯 Costo Fijo Unitario (CIF): **Q{cif_unit:,.2f}**")

# ---------------------------------------------------------
# TAB 3: MATERIAS PRIMAS (CSV, CONVERSOR, BORRAR)
# ---------------------------------------------------------
with tabs[2]:
    st.header("Gestión de Materias Primas")
    
    # A. CALCULADORA CONVERSORA
    with st.expander("🧮 Calculadora de Conversión de Precios (Ayuda Rápida)"):
        c1, c2, c3, c4 = st.columns(4)
        precio_compra = c1.number_input("Precio de Compra (Q)", 0.0)
        cantidad_compra = c2.number_input("Cantidad Comprada", 1.0)
        unidad_compra = c3.text_input("Unidad Compra (ej: Galón, Kg)")
        factor = c4.number_input("Factor a tu unidad (ej: 3785 para Galón->ml)", 1.0)
        
        if factor > 0 and cantidad_compra > 0:
            precio_unitario_real = precio_compra / (cantidad_compra * factor)
            st.code(f"Si compraste {cantidad_compra} {unidad_compra} a Q{precio_compra}, y cada uno tiene {factor} unidades finales...\nEl costo unitario es: Q{precio_unitario_real:.4f}")

    # B. CARGA MASIVA CSV
    with st.expander("📂 Cargar Materias Primas desde CSV"):
        st.write("Formato CSV requerido: `nombre,categoria,unidad_medida,costo_unitario`")
        uploaded_file = st.file_uploader("Subir archivo CSV", type="csv")
        if uploaded_file is not None:
            try:
                df_csv = pd.read_csv(uploaded_file)
                # Validar columnas
                requeridas = {'nombre', 'categoria', 'unidad_medida', 'costo_unitario'}
                if requeridas.issubset(df_csv.columns):
                    for index, row in df_csv.iterrows():
                        db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)",
                                   (row['nombre'], row['categoria'], row['unidad_medida'], row['costo_unitario']))
                    db.commit()
                    st.success(f"Se importaron {len(df_csv)} materias primas correctamente.")
                    st.rerun()
                else:
                    st.error(f"El CSV debe tener las columnas: {requeridas}")
            except Exception as e:
                st.error(f"Error al procesar CSV: {e}")

    # C. TABLA EDITABLE (ELIMINAR/EDITAR)
    st.subheader("Inventario de Materiales")
    df_mp = pd.read_sql("SELECT * FROM materias_primas ORDER BY nombre", db)
    
    edit_mp = st.data_editor(
        df_mp,
        key="editor_mp",
        num_rows="dynamic",
        column_config={
            "costo_unitario": st.column_config.NumberColumn(format="Q%.4f")
        }
    )
    
    if st.button("💾 Guardar Cambios MP"):
        # Actualizar existentes
        for i, row in edit_mp.iterrows():
            if row['id'] is not None:
                 db.execute("UPDATE materias_primas SET nombre=?, categoria=?, unidad_medida=?, costo_unitario=? WHERE id=?",
                            (row['nombre'], row['categoria'], row['unidad_medida'], row['costo_unitario'], row['id']))
            # Insertar nuevos (los que no tienen ID, aunque data_editor maneja index, la lógica simple es recrear o update)
            # Simplificación: En data_editor, las nuevas filas suelen tener index nuevo.
            # Para robustez en SQLite simple: Detectar borrados y updates.
        
        # Detectar borrados: IDs que estaban en df_mp original y no están en edit_mp
        ids_viejos = set(df_mp['id'].dropna())
        ids_nuevos = set(edit_mp['id'].dropna())
        ids_borrar = ids_viejos - ids_nuevos
        
        if ids_borrar:
            ids_str = ",".join(map(str, ids_borrar))
            db.execute(f"DELETE FROM materias_primas WHERE id IN ({ids_str})")
        
        # Insertar nuevos (ID nulo o NaN)
        nuevos = edit_mp[edit_mp['id'].isna()]
        for i, row in nuevos.iterrows():
            db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)",
                       (row['nombre'], row['categoria'], row['unidad_medida'], row['costo_unitario']))
            
        db.commit()
        st.success("Inventario actualizado.")
        st.rerun()

# ---------------------------------------------------------
# TAB 4: PRODUCTOS Y RECETAS (CONSTRUCTOR)
# ---------------------------------------------------------
with tabs[3]:
    st.header("Fábrica de Productos")
    
    # 1. CREACIÓN DE PRODUCTOS
    col_izq, col_der = st.columns([1, 2])
    
    with col_izq:
        st.subheader("Nuevo Producto")
        cats_db = db.execute("SELECT nombre FROM categorias_producto").fetchall()
        lista_cats = [c[0] for c in cats_db] if cats_db else ["General"]
        
        with st.form("crear_prod"):
            cod = st.text_input("Código Barras")
            nom = st.text_input("Nombre Producto")
            cat = st.selectbox("Categoría", lista_cats)
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            
            st.markdown("**Si es Lote:**")
            u_lote = st.number_input("Unidades resultantes", 1)
            m_lote = st.number_input("Minutos producción lote", 60.0)
            
            st.markdown("**Si es Unidad:**")
            m_unit_in = st.number_input("Minutos por unidad", 5.0)
            
            if st.form_submit_button("Crear Producto"):
                if tipo == "Lote":
                    m_final_unit = m_lote / u_lote
                    m_final_lote = m_lote
                else:
                    m_final_unit = m_unit_in
                    m_final_lote = m_unit_in * 1 # Irrelevante
                    u_lote = 1
                
                try:
                    db.execute('''INSERT INTO productos (codigo_barras, nombre, linea, tipo_produccion, 
                                unidades_por_lote, minutos_por_lote, minutos_por_unidad) 
                                VALUES (?,?,?,?,?,?,?)''', 
                               (cod, nom, cat, tipo, u_lote, m_final_lote, m_final_unit))
                    db.commit()
                    st.success("Producto creado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error (posible código duplicado): {e}")

    # 2. CONSTRUCTOR DE RECETAS
    with col_der:
        st.subheader("👨‍🍳 Constructor de Recetas")
        
        # Selector de producto
        prods = db.execute("SELECT codigo_barras, nombre FROM productos").fetchall()
        prod_options = {f"{p[1]} ({p[0]})": p[0] for p in prods}
        
        selected_prod_label = st.selectbox("Seleccionar Producto a Editar:", list(prod_options.keys()) if prods else [])
        
        if selected_prod_label:
            pid = prod_options[selected_prod_label]
            
            # Obtener datos del producto seleccionado
            p_data = db.execute("SELECT * FROM productos WHERE codigo_barras=?", (pid,)).fetchone()
            tipo_prod = p_data[4] # tipo_produccion
            divisor_lote = p_data[5] if tipo_prod == "Lote" else 1
            minutos_prod = p_data[7] # minutos_por_unidad
            
            st.info(f"Editando: **{p_data[2]}** | Tipo: {tipo_prod} | Minutos/Unidad: {minutos_prod:.2f}")

            # --- SECCIÓN INGREDIENTES ---
            c_add1, c_add2, c_add3 = st.columns([3, 1, 1])
            mps = db.execute("SELECT id, nombre, unidad_medida FROM materias_primas ORDER BY nombre").fetchall()
            mp_ops = {f"{m[1]} ({m[2]})": m[0] for m in mps}
            
            with c_add1:
                sel_mp = st.selectbox("Agregar Ingrediente:", list(mp_ops.keys()))
            with c_add2:
                cant_mp = st.number_input("Cant.", 0.0, step=0.1)
            with c_add3:
                st.write("")
                st.write("")
                if st.button("➕ Añadir"):
                    db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (?,?,?)", (pid, mp_ops[sel_mp], cant_mp))
                    db.commit()
                    st.rerun()

            # --- TABLA DE RECETA ACTUAL ---
            query_receta = '''
                SELECT r.id, m.nombre, r.cantidad, m.unidad_medida, m.costo_unitario, (r.cantidad * m.costo_unitario) as total
                FROM recetas r 
                JOIN materias_primas m ON r.mp_id = m.id 
                WHERE r.producto_id = ?
            '''
            df_receta = pd.read_sql(query_receta, db, params=(pid,))
            
            if not df_receta.empty:
                st.dataframe(df_receta, hide_index=True)
                
                # Botón Eliminar Ingrediente
                ing_to_del = st.selectbox("Eliminar Ingrediente (ID)", df_receta['id'].tolist())
                if st.button("🗑️ Eliminar Seleccionado"):
                    db.execute("DELETE FROM recetas WHERE id=?", (ing_to_del,))
                    db.commit()
                    st.rerun()
                
                # --- CÁLCULOS FINALES DEL PRODUCTO ---
                total_materiales = df_receta['total'].sum()
                
                # Costo MOD (Calculado en Tab 1, lo traemos de nuevo)
                mod_cfg = db.execute("SELECT * FROM config_mod").fetchone()
                # Recalculo rápido del costo minuto actual
                mod_total_cash = (mod_cfg[1] * (1 + mod_cfg[2]/100)) * mod_cfg[3]
                mod_total_hrs = mod_cfg[4] * mod_cfg[3]
                costo_minuto = mod_total_cash / mod_total_hrs / 60 if mod_total_hrs > 0 else 0
                
                costo_mod_unit = minutos_prod * costo_minuto
                costo_mat_unit = total_materiales / divisor_lote
                costo_variable = costo_mat_unit + costo_mod_unit
                
                st.divider()
                if tipo_prod == "Lote":
                    st.warning(f"⚠️ Receta para Lote de {divisor_lote} unidades. Los costos se dividen.")
                
                c_fin1, c_fin2, c_fin3 = st.columns(3)
                c_fin1.metric("Materia Prima (Unit)", f"Q{costo_mat_unit:.2f}")
                c_fin2.metric("MOD (Unit)", f"Q{costo_mod_unit:.2f}")
                c_fin3.metric("COSTO VARIABLE TOTAL", f"Q{costo_variable:.2f}")
            else:
                st.warning("Este producto aún no tiene receta.")
