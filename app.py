import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase Final", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_final.db', check_same_thread=False)

db = get_connection()

# --- INICIALIZACIÓN ---
def init_db():
    cursor = db.cursor()
    tablas = [
        '''CREATE TABLE IF NOT EXISTS costos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, total_mensual REAL, 
            p_admin REAL DEFAULT 50, p_ventas REAL DEFAULT 10, p_prod REAL DEFAULT 40)''',
        '''CREATE TABLE IF NOT EXISTS config_mod (
            id INTEGER PRIMARY KEY, salario_base REAL, p_prestaciones REAL, num_operarios INTEGER, horas_mes REAL)''',
        '''CREATE TABLE IF NOT EXISTS config_admin (
            id INTEGER PRIMARY KEY, salario_base REAL, p_prestaciones REAL, num_empleados INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS config_global (
            id INTEGER PRIMARY KEY, unidades_promedio_mes INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS materias_primas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, categoria TEXT, unidad_medida TEXT, costo_unitario REAL)''',
        '''CREATE TABLE IF NOT EXISTS categorias_producto (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''',
        '''CREATE TABLE IF NOT EXISTS productos (
            codigo_barras TEXT PRIMARY KEY, sku TEXT, nombre TEXT, linea TEXT, tipo_produccion TEXT,
            unidades_por_lote INTEGER DEFAULT 1, minutos_por_lote REAL DEFAULT 0, 
            minutos_por_unidad REAL DEFAULT 0, precio_venta_sugerido REAL DEFAULT 0, activo INTEGER DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS recetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id TEXT, mp_id INTEGER, cantidad REAL,
            FOREIGN KEY(producto_id) REFERENCES productos(codigo_barras),
            FOREIGN KEY(mp_id) REFERENCES materias_primas(id))'''
    ]
    for t in tablas: cursor.execute(t)
    
    # Datos semilla
    if cursor.execute("SELECT count(*) FROM config_mod WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_mod VALUES (1, 4252.28, 41.83, 2, 176)")
    if cursor.execute("SELECT count(*) FROM config_admin WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_admin VALUES (1, 5000.00, 41.83, 10)")
    if cursor.execute("SELECT count(*) FROM config_global WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_global VALUES (1, 5000)")
    if cursor.execute("SELECT count(*) FROM categorias_producto").fetchone()[0] == 0:
        cats = [('Rollon',), ('Estuche',), ('Spray',), ('AAA',), ('F1',), ('Estrellita',), ('Réplica',)]
        cursor.executemany("INSERT INTO categorias_producto (nombre) VALUES (?)", cats)
        
    db.commit()

init_db()

# --- FUNCIONES DE CÁLCULO ---
def get_total_mod():
    # Retorna (Total Dinero MOD, Costo Por Minuto)
    mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
    if mod:
        total_dinero = (mod[1] * (1 + mod[2]/100)) * mod[3]
        total_horas = mod[4] * mod[3]
        costo_min = total_dinero / total_horas / 60 if total_horas > 0 else 0
        return total_dinero, costo_min
    return 0, 0

def get_unidades_promedio():
    res = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    return res[0] if res and res[0] > 0 else 1

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería: Sistema Integral de Costos")

tabs = st.tabs(["👥 Nóminas", "💰 Matriz Costos", "🌿 Materias Primas", "📦 Productos & Recetas"])

# ---------------------------------------------------------
# TAB 1: NÓMINAS
# ---------------------------------------------------------
with tabs[0]:
    st.header("Configuración de Personal")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("👷 Producción (MOD)")
        mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
        with st.form("f_mod"):
            s = st.number_input("Salario Base", value=float(mod[1]))
            p = st.number_input("% Prestaciones", value=float(mod[2]))
            n = st.number_input("Nº Operarios", value=int(mod[3]))
            h = st.number_input("Horas/Mes/Op", value=float(mod[4]))
            if st.form_submit_button("Actualizar MOD"):
                db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1", (s,p,n,h))
                db.commit(); st.rerun()
        
        tot_mod, c_min = get_total_mod()
        st.info(f"Total Nómina Producción: Q{tot_mod:,.2f}")
        st.success(f"Costo Minuto Real: Q{c_min:,.4f}")

    with c2:
        st.subheader("👔 Admin y Ventas")
        adm = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
        with st.form("f_adm"):
            s = st.number_input("Salario Promedio", value=float(adm[1]))
            p = st.number_input("% Prestaciones", value=float(adm[2]))
            n = st.number_input("Nº Empleados", value=int(adm[3]))
            if st.form_submit_button("Actualizar Admin"):
                db.execute("UPDATE config_admin SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", (s,p,n))
                db.commit(); st.rerun()

# ---------------------------------------------------------
# TAB 2: COSTOS FIJOS (MATRIZ)
# ---------------------------------------------------------
with tabs[1]:
    st.header("Matriz de Costos Fijos")
    
    # 1. Carga CSV
    with st.expander("📂 Cargar Gastos (CSV)"):
        f = st.file_uploader("CSV: concepto,total_mensual,p_admin,p_ventas,p_prod", type="csv")
        if f:
            try:
                df = pd.read_csv(f)
                for _, r in df.iterrows():
                    db.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)",
                               (r['concepto'], r['total_mensual'], r['p_admin'], r['p_ventas'], r['p_prod']))
                db.commit(); st.success("Cargado"); st.rerun()
            except Exception as e: st.error(e)

    # 2. Tabla Editable
    df_man = pd.read_sql("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos", db)
    
    # Inyección Nóminas Admin
    adm = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
    sal_tot = adm[1]*adm[3]
    pre_tot = sal_tot*(adm[2]/100)
    df_auto = pd.DataFrame([
        {'id': -1, 'concepto': '⚡ Nómina Admin', 'total_mensual': sal_tot, 'p_admin': 50, 'p_ventas': 50, 'p_prod': 0},
        {'id': -2, 'concepto': '⚡ Prest. Admin', 'total_mensual': pre_tot, 'p_admin': 50, 'p_ventas': 50, 'p_prod': 0}
    ])
    
    ed_df = st.data_editor(pd.concat([df_man, df_auto], ignore_index=True), disabled=["id"], num_rows="dynamic", key="cf_ed")
    
    if st.button("💾 Guardar Matriz"):
        # Lógica de guardado simplificada para brevedad
        ids_now = set()
        for _, r in ed_df.iterrows():
            if r['id'] >= 0:
                ids_now.add(r['id'])
                db.execute("UPDATE costos_fijos SET concepto=?, total_mensual=?, p_admin=?, p_ventas=?, p_prod=? WHERE id=?",
                           (r['concepto'], r['total_mensual'], r['p_admin'], r['p_ventas'], r['p_prod'], r['id']))
            elif pd.isna(r['id']):
                db.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)",
                           (r['concepto'], r['total_mensual'], r['p_admin'], r['p_ventas'], r['p_prod']))
        
        # Eliminar
        ids_old = set(df_man['id'].tolist())
        to_del = ids_old - ids_now
        if to_del: db.execute(f"DELETE FROM costos_fijos WHERE id IN ({','.join(map(str, to_del))})")
        db.commit(); st.rerun()

    # 3. Totales
    ed_df['Prod'] = ed_df['total_mensual'] * (ed_df['p_prod']/100)
    total_cif = ed_df['Prod'].sum()
    
    st.divider()
    # Configuración de UNIDADES BASE
    col_u1, col_u2 = st.columns([1, 3])
    with col_u1:
        st.markdown("### ⚙️ Base de Cálculo")
        u_prom = st.number_input("Unidades Promedio Mensuales", value=get_unidades_promedio())
        if u_prom != get_unidades_promedio():
            db.execute("UPDATE config_global SET unidades_promedio_mes=? WHERE id=1", (u_prom,))
            db.commit(); st.rerun()
    
    with col_u2:
        st.markdown("### 🎯 Costos Unitarios Base (Prorrateo)")
        cif_u = total_cif / u_prom
        mod_tot, _ = get_total_mod()
        mod_u_prom = mod_tot / u_prom
        
        c_a, c_b = st.columns(2)
        c_a.metric("CIF Unitario (Gastos Fijos)", f"Q{cif_u:,.2f}")
        c_b.metric("MOD Unitario (Prorrateo)", f"Q{mod_u_prom:,.2f}", help="Se usa este valor si el producto tiene 0 minutos de fabricación.")

# ---------------------------------------------------------
# TAB 3: MATERIAS PRIMAS
# ---------------------------------------------------------
with tabs[2]:
    st.header("Inventario MP")
    with st.expander("Subir CSV"):
        f = st.file_uploader("CSV MP", type="csv")
        if f:
            try:
                pd.read_csv(f).to_sql("materias_primas", db, if_exists="append", index=False)
                st.success("Ok"); st.rerun()
            except: st.error("Error CSV")
            
    df = pd.read_sql("SELECT * FROM materias_primas", db)
    ed = st.data_editor(df, num_rows="dynamic", key="mp_ed")
    if st.button("💾 Guardar MP"):
        db.execute("DELETE FROM materias_primas")
        for _, r in ed.iterrows():
            db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)",
                       (r['nombre'], r['categoria'], r['unidad_medida'], r['costo_unitario']))
        db.commit(); st.rerun()

# ---------------------------------------------------------
# TAB 4: PRODUCTOS & RECETAS
# ---------------------------------------------------------
with tabs[3]:
    st.header("Gestión de Productos")
    
    # 1. Carga Masiva Productos
    with st.expander("📂 Carga Masiva Productos (CSV)"):
        st.info("Tip: Si no conoces los tiempos, deja la columna 'minutos_total' en 0.")
        f_p = st.file_uploader("CSV Prod", type="csv")
        if f_p:
            try:
                dfp = pd.read_csv(f_p)
                # Crear categorias
                for c in dfp['categoria'].unique():
                    db.execute("INSERT OR IGNORE INTO categorias_producto (nombre) VALUES (?)", (c,))
                
                for _, r in dfp.iterrows():
                    # Manejo de nulos o ceros en minutos
                    mins = r['minutos_total'] if pd.notna(r['minutos_total']) else 0
                    es_lote = r['tipo'] == 'Lote'
                    u_lote = r['unidades_lote'] if es_lote else 1
                    
                    # Si es 0, se guarda 0. Si hay dato, se calcula unitario
                    m_unit = (mins / u_lote) if es_lote and u_lote > 0 else mins
                    
                    db.execute('''INSERT OR REPLACE INTO productos 
                        (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (str(r['codigo']), r['nombre'], r['categoria'], r['tipo'], u_lote, mins, m_unit, r['precio']))
                db.commit(); st.success("Cargado"); st.rerun()
            except Exception as e: st.error(e)

    # 2. Panel Principal
    c_izq, c_der = st.columns([1, 2])
    
    with c_izq:
        st.subheader("Crear Producto Manual")
        cats = [x[0] for x in db.execute("SELECT nombre FROM categorias_producto").fetchall()]
        with st.form("new_p"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            cat = st.selectbox("Línea", cats)
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            
            st.markdown("---")
            st.caption("⏱️ **Configuración de Tiempos**")
            st.caption("Si dejas los minutos en 0, el sistema usará el **Costo MOD Promedio** (Prorrateo).")
            
            if tipo == "Lote":
                u_lote = st.number_input("Unidades/Lote", 1)
                m_lote = st.number_input("Minutos Totales Lote", 0.0)
                m_final_unit = m_lote / u_lote
            else:
                u_lote = 1
                m_final_unit = st.number_input("Minutos por Unidad", 0.0)
                m_lote = m_final_unit

            precio = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("Crear"):
                db.execute('''INSERT OR REPLACE INTO productos 
                    (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                    VALUES (?,?,?,?,?,?,?,?)''', (cod, nom, cat, tipo, u_lote, m_lote, m_final_unit, precio))
                db.commit(); st.rerun()

    with c_der:
        st.subheader("Receta y Costeo")
        prods = {f"{p[1]}": p[0] for p in db.execute("SELECT codigo_barras, nombre FROM productos").fetchall()}
        sel = st.selectbox("Producto:", list(prods.keys()) if prods else [])
        
        if sel:
            pid = prods[sel]
            dat = db.execute("SELECT * FROM productos WHERE codigo_barras=?", (pid,)).fetchone()
            
            # Form Ingredientes
            c1, c2, c3 = st.columns([3, 2, 1])
            mps = {f"{m[1]}": m[0] for m in db.execute("SELECT id, nombre FROM materias_primas").fetchall()}
            m_id = c1.selectbox("MP", list(mps.keys()) if mps else [])
            cant = c2.number_input("Cant", 0.0)
            if c3.button("➕"):
                db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (?,?,?)", (pid, mps[m_id], cant))
                db.commit(); st.rerun()
            
            # Tabla y Cálculos
            df_r = pd.read_sql("SELECT r.id, m.nombre, r.cantidad, m.costo_unitario, (r.cantidad*m.costo_unitario) as tot FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE producto_id=?", db, params=(pid,))
            st.dataframe(df_r, hide_index=True)
            
            if not df_r.empty:
                # 1. Costo Materiales
                total_mat = df_r['tot'].sum()
                div_lote = dat[5] if dat[4] == 'Lote' else 1
                cost_mat_u = total_mat / div_lote
                
                # 2. Costo MOD (Lógica Híbrida)
                minutos_u = dat[7] # minutos_por_unidad en DB
                tot_mod, c_min_real = get_total_mod()
                u_prom = get_unidades_promedio()
                
                if minutos_u > 0:
                    cost_mod_u = minutos_u * c_min_real
                    lbl_mod = f"Tiempo ({minutos_u:.2f} min/ud)"
                else:
                    cost_mod_u = tot_mod / u_prom
                    lbl_mod = "Prorrateo (Sin tiempo definido)"

                # 3. Costo CIF (Fijos)
                # Obtenemos el total de la tabla costos fijos (columna Prod)
                df_fijos = pd.read_sql("SELECT total_mensual, p_prod FROM costos_fijos", db)
                df_fijos['Cif'] = df_fijos['total_mensual'] * (df_fijos['p_prod']/100)
                # Sumamos también prestaciones admin si hubiera parte a producción (ahora está en 0 por defecto pero por si acaso)
                total_cif_mes = df_fijos['Cif'].sum() 
                cost_cif_u = total_cif_mes / u_prom

                st.divider()
                st.markdown("### 🏷️ Hoja de Costos Unitaria")
                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric("Materia Prima", f"Q{cost_mat_u:.2f}")
                cc2.metric(f"MOD ({lbl_mod})", f"Q{cost_mod_u:.2f}")
                cc3.metric("CIF (Fijos)", f"Q{cost_cif_u:.2f}")
                
                costo_total = cost_mat_u + cost_mod_u + cost_cif_u
                cc4.metric("COSTO TOTAL", f"Q{costo_total:.2f}", delta="Base para precio")
