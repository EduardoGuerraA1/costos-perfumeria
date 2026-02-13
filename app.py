import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase 3 (3 Nóminas)", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_fase3.db', check_same_thread=False)

db = get_connection()

# --- INICIALIZACIÓN DB ---
def init_db():
    cursor = db.cursor()
    tablas = [
        # 1. Costos Fijos Generales
        '''CREATE TABLE IF NOT EXISTS costos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, total_mensual REAL, 
            p_admin REAL DEFAULT 50, p_ventas REAL DEFAULT 10, p_prod REAL DEFAULT 40)''',
        
        # 2. Configuración Nóminas (3 Áreas)
        '''CREATE TABLE IF NOT EXISTS config_mod (
            id INTEGER PRIMARY KEY, salario_base REAL, p_prestaciones REAL, num_operarios INTEGER, horas_mes REAL)''',
        '''CREATE TABLE IF NOT EXISTS config_admin (
            id INTEGER PRIMARY KEY, salario_base REAL, p_prestaciones REAL, num_empleados INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS config_ventas (
            id INTEGER PRIMARY KEY, salario_base REAL, p_prestaciones REAL, num_empleados INTEGER)''',
        
        # 3. Configuraciones Varias
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
    
    # Datos por defecto (Semillas)
    # MOD
    if cursor.execute("SELECT count(*) FROM config_mod WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_mod VALUES (1, 4252.28, 41.83, 2, 176)")
    # Admin Central
    if cursor.execute("SELECT count(*) FROM config_admin WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_admin VALUES (1, 5000.00, 41.83, 3)")
    # Sala Ventas
    if cursor.execute("SELECT count(*) FROM config_ventas WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_ventas VALUES (1, 3500.00, 41.83, 2)")
    
    if cursor.execute("SELECT count(*) FROM config_global WHERE id=1").fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_global VALUES (1, 5000)")
        
    if cursor.execute("SELECT count(*) FROM categorias_producto").fetchone()[0] == 0:
        cats = [('Rollon',), ('Estuche',), ('Spray',), ('AAA',), ('F1',), ('Estrellita',), ('Réplica',)]
        cursor.executemany("INSERT INTO categorias_producto (nombre) VALUES (?)", cats)
        
    db.commit()

init_db()

# --- FUNCIONES DE CÁLCULO ---
def get_total_mod():
    mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
    if mod:
        total_dinero = (mod[1] * (1 + mod[2]/100)) * mod[3]
        total_horas = mod[4] * mod[3]
        costo_min = total_dinero / total_horas / 60 if total_horas > 0 else 0
        return total_dinero, costo_min
    return 0, 0

def get_nomina_admin():
    # Retorna (Total Salarios, Total Prestaciones)
    cfg = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
    if cfg: return (cfg[1]*cfg[3]), (cfg[1]*cfg[3]*(cfg[2]/100))
    return 0, 0

def get_nomina_ventas():
    # Retorna (Total Salarios, Total Prestaciones)
    cfg = db.execute("SELECT * FROM config_ventas WHERE id=1").fetchone()
    if cfg: return (cfg[1]*cfg[3]), (cfg[1]*cfg[3]*(cfg[2]/100))
    return 0, 0

def get_unidades_promedio():
    res = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    return res[0] if res and res[0] > 0 else 1

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería Integral")

tabs = st.tabs(["👥 Nóminas (3 Áreas)", "💰 Matriz Costos", "🌿 Materias Primas", "📦 Productos & Recetas"])

# ---------------------------------------------------------
# TAB 1: NÓMINAS (3 COLUMNAS AHORA)
# ---------------------------------------------------------
with tabs[0]:
    st.header("Configuración de Personal")
    c1, c2, c3 = st.columns(3)
    
    # 1. ADMIN CENTRAL
    with c1:
        st.subheader("🏢 Admin Central")
        adm = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
        with st.form("f_adm"):
            s = st.number_input("Salario Promedio", value=float(adm[1]), key="s_adm")
            p = st.number_input("% Prestaciones", value=float(adm[2]), key="p_adm")
            n = st.number_input("Nº Empleados", value=int(adm[3]), key="n_adm")
            if st.form_submit_button("Guardar Admin"):
                db.execute("UPDATE config_admin SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", (s,p,n))
                db.commit(); st.rerun()
        st.info(f"Total Mes: Q{(s*n*(1+p/100)):,.2f}")
        st.caption("➡️ Se cargará 100% a Gasto Administrativo")

    # 2. SALA DE VENTAS
    with c2:
        st.subheader("🛍️ Sala de Ventas")
        ven = db.execute("SELECT * FROM config_ventas WHERE id=1").fetchone()
        with st.form("f_ven"):
            s = st.number_input("Salario Promedio", value=float(ven[1]), key="s_ven")
            p = st.number_input("% Prestaciones", value=float(ven[2]), key="p_ven")
            n = st.number_input("Nº Empleados", value=int(ven[3]), key="n_ven")
            if st.form_submit_button("Guardar Ventas"):
                db.execute("UPDATE config_ventas SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", (s,p,n))
                db.commit(); st.rerun()
        st.info(f"Total Mes: Q{(s*n*(1+p/100)):,.2f}")
        st.caption("➡️ Se cargará 100% a Gasto de Ventas")

    # 3. PRODUCCIÓN (MOD)
    with c3:
        st.subheader("🏭 Producción (MOD)")
        mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
        with st.form("f_mod"):
            s = st.number_input("Salario Base", value=float(mod[1]), key="s_mod")
            p = st.number_input("% Prestaciones", value=float(mod[2]), key="p_mod")
            n = st.number_input("Nº Operarios", value=int(mod[3]), key="n_mod")
            h = st.number_input("Horas/Mes/Op", value=float(mod[4]), key="h_mod")
            if st.form_submit_button("Guardar MOD"):
                db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1", (s,p,n,h))
                db.commit(); st.rerun()
        
        tot_mod, c_min = get_total_mod()
        st.success(f"Costo Minuto: Q{c_min:,.4f}")
        st.caption("➡️ Se carga al Costo Unitario del Producto")

# ---------------------------------------------------------
# TAB 2: MATRIZ COSTOS
# ---------------------------------------------------------
with tabs[1]:
    st.header("Matriz de Costos Fijos")
    
    # Carga CSV Gastos
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

    # Lógica de Filas Automáticas (Admin vs Ventas)
    df_man = pd.read_sql("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos", db)
    
    # Obtener totales calculados
    s_adm, p_adm = get_nomina_admin()
    s_ven, p_ven = get_nomina_ventas()
    
    # Crear filas automáticas con asignación 100% estricta
    filas_auto = [
        # Admin Central (100% Admin)
        {'id': -1, 'concepto': '⚡ Nomina Admin Central', 'total_mensual': s_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0},
        {'id': -2, 'concepto': '⚡ Prestaciones Admin', 'total_mensual': p_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0},
        # Sala Ventas (100% Ventas)
        {'id': -3, 'concepto': '⚡ Nomina Sala Ventas', 'total_mensual': s_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0},
        {'id': -4, 'concepto': '⚡ Prestaciones Ventas', 'total_mensual': p_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0}
    ]
    
    # Mostrar Editor
    df_show = pd.concat([df_man, pd.DataFrame(filas_auto)], ignore_index=True)
    ed_df = st.data_editor(df_show, disabled=["id"], num_rows="dynamic", key="cf_ed")
    
    if st.button("💾 Guardar Cambios Matriz"):
        # Guardar solo manuales (ID >= 0 o NaN)
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

    # Totales Generales
    df_calc = ed_df.copy()
    df_calc['M_Adm'] = df_calc['total_mensual'] * (df_calc['p_admin']/100)
    df_calc['M_Ven'] = df_calc['total_mensual'] * (df_calc['p_ventas']/100)
    df_calc['M_Prod'] = df_calc['total_mensual'] * (df_calc['p_prod']/100)
    
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TOTAL GASTOS EMPRESA", f"Q{df_calc['total_mensual'].sum():,.2f}")
    c2.metric("Total Admin", f"Q{df_calc['M_Adm'].sum():,.2f}")
    c3.metric("Total Ventas", f"Q{df_calc['M_Ven'].sum():,.2f}")
    c4.metric("Total Prod (CIF)", f"Q{df_calc['M_Prod'].sum():,.2f}")

    # Unidades para Prorrateo
    st.markdown("---")
    u_prom = st.number_input("Unidades Base (Promedio Mensual)", value=get_unidades_promedio())
    if u_prom != get_unidades_promedio():
        db.execute("UPDATE config_global SET unidades_promedio_mes=? WHERE id=1", (u_prom,))
        db.commit(); st.rerun()
    
    cif_unit = df_calc['M_Prod'].sum() / u_prom
    st.info(f"🎯 CIF Unitario (Costo Fijo por Producto): **Q{cif_unit:,.2f}**")

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
    ed = st.data_editor(df, num_rows="dynamic", key="mp_ed", column_config={"costo_unitario": st.column_config.NumberColumn(format="Q%.4f")})
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
    st.header("Fábrica de Productos")
    
    # 1. Carga Masiva Productos
    with st.expander("📂 Carga Masiva Productos (CSV)"):
        st.info("Columnas: codigo, nombre, categoria, tipo, precio, unidades_lote, minutos_total")
        f_p = st.file_uploader("CSV Prod", type="csv")
        if f_p:
            try:
                dfp = pd.read_csv(f_p)
                for c in dfp['categoria'].unique():
                    db.execute("INSERT OR IGNORE INTO categorias_producto (nombre) VALUES (?)", (c,))
                
                for _, r in dfp.iterrows():
                    mins = r['minutos_total'] if pd.notna(r['minutos_total']) else 0
                    es_lote = r['tipo'] == 'Lote'
                    u_lote = r['unidades_lote'] if es_lote else 1
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
        st.subheader("Crear Producto")
        cats = [x[0] for x in db.execute("SELECT nombre FROM categorias_producto").fetchall()]
        
        # Add new cat
        n_cat = st.text_input("Nueva Categoría (Enter)")
        if n_cat:
             try:
                 db.execute("INSERT INTO categorias_producto (nombre) VALUES (?)", (n_cat,))
                 db.commit(); st.rerun()
             except: pass

        with st.form("new_p"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            cat = st.selectbox("Línea", cats if cats else ["General"])
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            u_lote = st.number_input("Unidades/Lote", 1)
            m_total = st.number_input("Minutos Totales", 0.0)
            precio = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("Crear"):
                m_unit = m_total / u_lote if tipo == "Lote" else m_total
                db.execute('''INSERT OR REPLACE INTO productos 
                    (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                    VALUES (?,?,?,?,?,?,?,?)''', (cod, nom, cat, tipo, u_lote, m_total, m_unit, precio))
                db.commit(); st.rerun()

    with c_der:
        st.subheader("Receta")
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
            
            # Tabla
            df_r = pd.read_sql("SELECT r.id, m.nombre, r.cantidad, m.costo_unitario, (r.cantidad*m.costo_unitario) as tot FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE producto_id=?", db, params=(pid,))
            st.dataframe(df_r, hide_index=True)
            
            if not df_r.empty:
                # CÁLCULOS FINALES
                tot_mat = df_r['tot'].sum()
                div = dat[5] if dat[4] == 'Lote' else 1
                cost_mat_u = tot_mat / div
                
                # MOD (Híbrido)
                u_prom = get_unidades_promedio()
                tot_mod_dinero, c_min = get_total_mod()
                
                if dat[7] > 0: # Tiene tiempos
                    cost_mod_u = dat[7] * c_min
                    lbl_mod = f"Tiempo ({dat[7]:.2f} min)"
                else: # Prorrateo
                    cost_mod_u = tot_mod_dinero / u_prom
                    lbl_mod = "Prorrateo"

                # CIF
                # Sumamos total Prod de tabla Costos Fijos
                df_f = pd.read_sql("SELECT total_mensual, p_prod FROM costos_fijos", db)
                total_cif_mes = (df_f['total_mensual'] * (df_f['p_prod']/100)).sum()
                # Sumar las nominas que no estan en la tabla (las auto)
                # OJO: Las filas "Auto" ya estan en df_f cuando usamos read_sql? NO.
                # Las filas auto estan en memoria en el Tab 2. Aqui hay que recalcular solo las auto que tengan componente Prod.
                # En este caso, Admin y Ventas tienen 0% Prod, así que no suman al CIF.
                # Solo la nómina MOD suma al costo producto pero VA SEPARADO en la linea MOD.
                # Por tanto, CIF es correcto tomarlo solo de la tabla manual.
                
                cost_cif_u = total_cif_mes / u_prom

                st.divider()
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("MP Unit.", f"Q{cost_mat_u:.2f}")
                k2.metric(f"MOD ({lbl_mod})", f"Q{cost_mod_u:.2f}")
                k3.metric("CIF Unit.", f"Q{cost_cif_u:.2f}")
                
                cost_total = cost_mat_u + cost_mod_u + cost_cif_u
                k4.metric("COSTO TOTAL", f"Q{cost_total:.2f}")
                
                # Margen
                pvp = dat[8]
                if pvp > 0:
                    ganancia = pvp - cost_total
                    margen = (ganancia / pvp) * 100
                    st.progress(margen/100 if 0 < margen < 100 else 0)
                    st.caption(f"Precio Venta: Q{pvp} | Margen: {margen:.1f}%")
