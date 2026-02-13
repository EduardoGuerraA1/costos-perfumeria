import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase 3.1 (Clonado+Ficha)", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_fase3.db', check_same_thread=False)

db = get_connection()

# --- INICIALIZACIÓN DB ---
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
        '''CREATE TABLE IF NOT EXISTS config_ventas (
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
        cursor.execute("INSERT INTO config_admin VALUES (1, 5000.00, 41.83, 3)")
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

def get_unidades_promedio():
    res = db.execute("SELECT unidades_promedio_mes FROM config_global WHERE id=1").fetchone()
    return res[0] if res and res[0] > 0 else 1

# --- INTERFAZ ---
st.title("🧪 ERP Perfumería Integral")

tabs = st.tabs(["👥 Nóminas", "💰 Matriz Costos", "🌿 Materias Primas", "📦 Fábrica (Prod & Recetas)", "📄 Ficha Técnica (Buscador)"])

# ---------------------------------------------------------
# TAB 1: NÓMINAS
# ---------------------------------------------------------
with tabs[0]:
    st.header("Configuración de Personal")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("🏢 Admin Central")
        adm = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
        with st.form("f_adm"):
            s = st.number_input("Salario", value=float(adm[1]), key="s_adm")
            p = st.number_input("% Prestaciones", value=float(adm[2]), key="p_adm")
            n = st.number_input("Nº Empleados", value=int(adm[3]), key="n_adm")
            if st.form_submit_button("Guardar Admin"):
                db.execute("UPDATE config_admin SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", (s,p,n))
                db.commit(); st.rerun()

    with c2:
        st.subheader("🛍️ Sala Ventas")
        ven = db.execute("SELECT * FROM config_ventas WHERE id=1").fetchone()
        with st.form("f_ven"):
            s = st.number_input("Salario", value=float(ven[1]), key="s_ven")
            p = st.number_input("% Prestaciones", value=float(ven[2]), key="p_ven")
            n = st.number_input("Nº Empleados", value=int(ven[3]), key="n_ven")
            if st.form_submit_button("Guardar Ventas"):
                db.execute("UPDATE config_ventas SET salario_base=?, p_prestaciones=?, num_empleados=? WHERE id=1", (s,p,n))
                db.commit(); st.rerun()

    with c3:
        st.subheader("🏭 Producción (MOD)")
        mod = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
        with st.form("f_mod"):
            s = st.number_input("Salario", value=float(mod[1]), key="s_mod")
            p = st.number_input("% Prestaciones", value=float(mod[2]), key="p_mod")
            n = st.number_input("Nº Ops", value=int(mod[3]), key="n_mod")
            h = st.number_input("Horas/Mes", value=float(mod[4]), key="h_mod")
            if st.form_submit_button("Guardar MOD"):
                db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1", (s,p,n,h))
                db.commit(); st.rerun()

# ---------------------------------------------------------
# TAB 2: MATRIZ COSTOS
# ---------------------------------------------------------
with tabs[1]:
    st.header("Matriz de Costos Fijos")
    
    # Filas Auto
    adm_row = db.execute("SELECT * FROM config_admin WHERE id=1").fetchone()
    ven_row = db.execute("SELECT * FROM config_ventas WHERE id=1").fetchone()
    
    t_adm = adm_row[1]*adm_row[3]*(1+adm_row[2]/100)
    t_ven = ven_row[1]*ven_row[3]*(1+ven_row[2]/100)
    
    filas_auto = [
        {'id': -1, 'concepto': '⚡ Nomina Admin Central', 'total_mensual': t_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0},
        {'id': -2, 'concepto': '⚡ Nomina Sala Ventas', 'total_mensual': t_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0}
    ]
    
    df_man = pd.read_sql("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos", db)
    ed_df = st.data_editor(pd.concat([df_man, pd.DataFrame(filas_auto)], ignore_index=True), disabled=["id"], num_rows="dynamic", key="cf_ed")
    
    if st.button("💾 Guardar Matriz"):
        ids_now = set()
        for _, r in ed_df.iterrows():
            if r['id'] >= 0:
                ids_now.add(r['id'])
                db.execute("UPDATE costos_fijos SET concepto=?, total_mensual=?, p_admin=?, p_ventas=?, p_prod=? WHERE id=?",
                           (r['concepto'], r['total_mensual'], r['p_admin'], r['p_ventas'], r['p_prod'], r['id']))
            elif pd.isna(r['id']):
                db.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)",
                           (r['concepto'], r['total_mensual'], r['p_admin'], r['p_ventas'], r['p_prod']))
        
        ids_old = set(df_man['id'].tolist())
        to_del = ids_old - ids_now
        if to_del: db.execute(f"DELETE FROM costos_fijos WHERE id IN ({','.join(map(str, to_del))})")
        db.commit(); st.rerun()

    # Totales y CIF
    ed_df['M_Prod'] = ed_df['total_mensual'] * (ed_df['p_prod']/100)
    st.divider()
    
    u_prom = st.number_input("Unidades Base", value=get_unidades_promedio())
    if u_prom != get_unidades_promedio():
        db.execute("UPDATE config_global SET unidades_promedio_mes=? WHERE id=1", (u_prom,))
        db.commit(); st.rerun()
    
    cif_unit = ed_df['M_Prod'].sum() / u_prom
    st.info(f"🎯 CIF Unitario: **Q{cif_unit:,.2f}**")

# ---------------------------------------------------------
# TAB 3: MATERIAS PRIMAS
# ---------------------------------------------------------
with tabs[2]:
    st.header("Inventario MP")
    with st.expander("Subir CSV"):
        f = st.file_uploader("CSV MP", type="csv")
        if f:
            try: pd.read_csv(f).to_sql("materias_primas", db, if_exists="append", index=False); st.success("Ok"); st.rerun()
            except: st.error("Error")
            
    df = pd.read_sql("SELECT * FROM materias_primas", db)
    ed = st.data_editor(df, num_rows="dynamic", key="mp_ed", column_config={"costo_unitario": st.column_config.NumberColumn(format="Q%.4f")})
    if st.button("💾 Guardar MP"):
        db.execute("DELETE FROM materias_primas")
        for _, r in ed.iterrows():
            db.execute("INSERT INTO materias_primas (nombre, categoria, unidad_medida, costo_unitario) VALUES (?,?,?,?)",
                       (r['nombre'], r['categoria'], r['unidad_medida'], r['costo_unitario']))
        db.commit(); st.rerun()

# ---------------------------------------------------------
# TAB 4: FÁBRICA (PRODUCTOS Y RECETAS)
# ---------------------------------------------------------
with tabs[3]:
    st.header("Gestión de Productos y Recetas")
    
    c_izq, c_der = st.columns([1, 2])
    
    # 1. CREAR PRODUCTO
    with c_izq:
        st.subheader("Crear Producto")
        cats = [x[0] for x in db.execute("SELECT nombre FROM categorias_producto").fetchall()]
        with st.form("new_p"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            cat = st.selectbox("Línea", cats if cats else ["General"])
            tipo = st.selectbox("Tipo", ["Unidad", "Lote"])
            u_lote = st.number_input("Uds/Lote", 1)
            m_total = st.number_input("Minutos Totales", 0.0)
            precio = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("Crear"):
                m_unit = m_total / u_lote if tipo == "Lote" else m_total
                db.execute('''INSERT OR REPLACE INTO productos 
                    (codigo_barras, nombre, linea, tipo_produccion, unidades_por_lote, minutos_por_lote, minutos_por_unidad, precio_venta_sugerido)
                    VALUES (?,?,?,?,?,?,?,?)''', (cod, nom, cat, tipo, u_lote, m_total, m_unit, precio))
                db.commit(); st.rerun()

    # 2. CONSTRUCTOR RECETAS
    with c_der:
        st.subheader("Constructor de Recetas")
        prods = {f"{p[1]}": p[0] for p in db.execute("SELECT codigo_barras, nombre FROM productos").fetchall()}
        sel_nom = st.selectbox("Seleccionar Producto:", list(prods.keys()) if prods else [])
        
        if sel_nom:
            pid = prods[sel_nom]
            
            # --- FUNCIÓN DUPLICAR ---
            with st.expander("🛠️ Herramientas: Clonar Receta"):
                st.write("Copia los ingredientes de otro producto a este.")
                p_origen = st.selectbox("Copiar desde:", ["Seleccionar..."] + list(prods.keys()))
                if st.button("Ejecutar Clonado") and p_origen != "Seleccionar...":
                    pid_origen = prods[p_origen]
                    # Borrar receta actual
                    db.execute("DELETE FROM recetas WHERE producto_id = ?", (pid,))
                    # Copiar nueva
                    db.execute('''INSERT INTO recetas (producto_id, mp_id, cantidad)
                                  SELECT ?, mp_id, cantidad FROM recetas WHERE producto_id = ?''', (pid, pid_origen))
                    db.commit()
                    st.success(f"Receta de {p_origen} copiada a {sel_nom}!")
                    st.rerun()
            
            # --- EDITOR RECETA ---
            c1, c2, c3 = st.columns([3, 2, 1])
            mps = {f"{m[1]}": m[0] for m in db.execute("SELECT id, nombre FROM materias_primas").fetchall()}
            m_id = c1.selectbox("Agregar MP", list(mps.keys()) if mps else [])
            cant = c2.number_input("Cantidad", 0.0, step=0.01)
            if c3.button("➕"):
                db.execute("INSERT INTO recetas (producto_id, mp_id, cantidad) VALUES (?,?,?)", (pid, mps[m_id], cant))
                db.commit(); st.rerun()
            
            df_r = pd.read_sql("SELECT r.id, m.nombre, r.cantidad, m.costo_unitario, (r.cantidad*m.costo_unitario) as tot FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE producto_id=?", db, params=(pid,))
            st.dataframe(df_r, hide_index=True)
            
            if not df_r.empty:
                del_id = st.selectbox("Eliminar ID:", df_r['id'].tolist())
                if st.button("🗑️ Eliminar"):
                    db.execute("DELETE FROM recetas WHERE id=?", (del_id,))
                    db.commit(); st.rerun()

# ---------------------------------------------------------
# TAB 5: FICHA TÉCNICA (BUSCADOR)
# ---------------------------------------------------------
with tabs[4]:
    st.header("🔎 Ficha Técnica y Costeo Final")
    
    # BUSCADOR
    prods_db = db.execute("SELECT codigo_barras, nombre, linea FROM productos").fetchall()
    # Creamos lista simple para buscador
    lista_busqueda = [f"{p[1]} | {p[2]} | {p[0]}" for p in prods_db]
    
    seleccion = st.selectbox("🔍 Buscar Producto (Escribe para filtrar)", [""] + lista_busqueda)
    
    if seleccion:
        # Extraer Codigo Barras del string "Nombre | Linea | Codigo"
        cod_buscado = seleccion.split(" | ")[-1]
        
        # DATOS
        p_dat = db.execute("SELECT * FROM productos WHERE codigo_barras=?", (cod_buscado,)).fetchone()
        
        # CÁLCULOS
        # 1. MP
        cost_mp_total = db.execute("SELECT SUM(r.cantidad * m.costo_unitario) FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=?", (cod_buscado,)).fetchone()[0] or 0
        div = p_dat[5] if p_dat[4] == 'Lote' else 1
        cost_mp_u = cost_mp_total / div
        
        # 2. MOD
        tot_mod_dinero, c_min = get_total_mod()
        u_prom = get_unidades_promedio()
        if p_dat[7] > 0:
            cost_mod_u = p_dat[7] * c_min
        else:
            cost_mod_u = tot_mod_dinero / u_prom
            
        # 3. CIF
        df_f = pd.read_sql("SELECT total_mensual, p_prod FROM costos_fijos", db)
        cif_mensual = (df_f['total_mensual'] * (df_f['p_prod']/100)).sum()
        cost_cif_u = cif_mensual / u_prom
        
        cost_total = cost_mp_u + cost_mod_u + cost_cif_u
        pvp = p_dat[8]
        margen = pvp - cost_total
        margen_pct = (margen / pvp * 100) if pvp > 0 else 0
        
        # VISUALIZACIÓN FICHA
        st.markdown(f"## {p_dat[2]}")
        st.caption(f"Línea: {p_dat[3]} | Código: {p_dat[0]}")
        
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("Costo Total Unitario", f"Q{cost_total:.2f}")
        col_res2.metric("Precio Sugerido", f"Q{pvp:.2f}")
        col_res3.metric("Margen Ganancia", f"{margen_pct:.1f}%", f"Q{margen:.2f}")
        
        st.write("---")
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Materiales:** Q{cost_mp_u:.2f}")
        c2.write(f"**Mano Obra:** Q{cost_mod_u:.2f}")
        c3.write(f"**Costos Fijos:** Q{cost_cif_u:.2f}")
        
        # Mostrar Receta Detallada
        st.write("### 📝 Detalle de Receta")
        receta_det = pd.read_sql("SELECT m.nombre, r.cantidad, m.unidad_medida FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=?", db, params=(cod_buscado,))
        st.table(receta_det)
