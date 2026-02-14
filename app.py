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

# TAB 1: NÓMINAS

# ------------------------------------------------------------------

with tabs[0]:

    st.header("Configuración de Personal")

    c1, c2, c3 = st.columns(3)

    

    def render_nomina_form(titulo, tabla, key_prefix):

        with st.container(border=True):

            st.subheader(titulo)

            try:

                # Query seguro

                col_emp = "num_operarios" if tabla == 'config_mod' else "num_empleados"

                cols = f"salario_base, p_prestaciones, {col_emp}"

                if tabla == 'config_mod': cols += ", horas_mes"

                

                df = get_data(f"SELECT {cols} FROM {tabla} WHERE id=1")

                

                if not df.empty:

                    data = df.iloc[0]

                    with st.form(f"form_{key_prefix}"):

                        s = st.number_input("Salario", value=float(data['salario_base']))

                        p = st.number_input("% Prestaciones", value=float(data['p_prestaciones']))

                        n = st.number_input("Nº Personas", value=int(data[col_emp]))

                        

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

                    st.warning("⚠️ Datos vacíos. Recarga la página para auto-reparar.")

            except Exception as e: st.error(f"Error DB: {e}")



    with c1: render_nomina_form("🏢 Admin", "config_admin", "adm")

    with c2: render_nomina_form("🛍️ Ventas", "config_ventas", "ven")

    with c3: render_nomina_form("🏭 Producción", "config_mod", "mod")



# --- TAB 2: COSTOS FIJOS (RESTAURADO CON TOTALES) ---

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



    try:

        df_man = get_data("SELECT id, concepto, total_mensual, p_admin, p_ventas, p_prod FROM costos_fijos ORDER BY id")

        

        # Lógica de Filas Auto de Nóminas

        filas_auto = []

        adm = get_data("SELECT salario_base, p_prestaciones, num_empleados FROM config_admin WHERE id=1").iloc[0]

        t_adm = float(adm['salario_base'] * adm['num_empleados'])

        filas_auto.append({'id': -1, 'concepto': '⚡ Nómina: Salarios Admin', 'total_mensual': t_adm, 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})

        filas_auto.append({'id': -2, 'concepto': '⚡ Nómina: Prestaciones Admin', 'total_mensual': t_adm*(adm['p_prestaciones']/100), 'p_admin': 100, 'p_ventas': 0, 'p_prod': 0})

        

        ven = get_data("SELECT salario_base, p_prestaciones, num_empleados FROM config_ventas WHERE id=1").iloc[0]

        t_ven = float(ven['salario_base'] * ven['num_empleados'])

        filas_auto.append({'id': -3, 'concepto': '⚡ Nómina: Salarios Ventas', 'total_mensual': t_ven, 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})

        filas_auto.append({'id': -4, 'concepto': '⚡ Nómina: Prestaciones Ventas', 'total_mensual': t_ven*(ven['p_prestaciones']/100), 'p_admin': 0, 'p_ventas': 100, 'p_prod': 0})



        df_show = pd.concat([df_man, pd.DataFrame(filas_auto)], ignore_index=True)

        ed_df = st.data_editor(df_show, disabled=["id"], num_rows="dynamic", key="cf_ed", column_config={"total_mensual": st.column_config.NumberColumn(format="Q%.2f")})

        

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



        # --- SECCIÓN DE TOTALES RESTAURADA ---

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

        u_prom = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]

        u_base = st.number_input("Unidades Base", value=int(u_prom))

        if u_base != u_prom:

            run_query("UPDATE config_global SET unidades_promedio_mes=:u WHERE id=1", {'u':u_base})

            st.rerun()

            

        cif_unit = ed_df['M_Prod'].sum() / u_base if u_base > 0 else 0

        st.success(f"🎯 CIF Unitario: **Q{cif_unit:,.2f}**")



    except Exception as e: st.error(f"Error cargando matriz: {e}")
# --- TAB 3: MATERIAS PRIMAS ---
with tabs[2]:
    st.header("Inventario Materia Prima")
    df_mps = get_data("SELECT id, codigo_interno, nombre, categoria, unidad_medida, costo_unitario FROM materias_primas ORDER BY nombre")
    ed_mp = st.data_editor(df_mps, num_rows="dynamic", key="mp_ed_safe", disabled=["id"])
    if st.button("💾 Guardar Cambios MP"):
        for _, r in ed_mp.iterrows():
            if 'id' in r and pd.notna(r['id']): 
                run_query("UPDATE materias_primas SET codigo_interno=:cod, nombre=:n, categoria=:c, unidad_medida=:u, costo_unitario=:p WHERE id=:id", 
                          {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario'], 'id':r['id']})
            else: 
                run_query("INSERT INTO materias_primas (codigo_interno, nombre, categoria, unidad_medida, costo_unitario) VALUES (:cod, :n, :c, :u, :p)", 
                          {'cod':r['codigo_interno'], 'n':r['nombre'], 'c':r['categoria'], 'u':r['unidad_medida'], 'p':r['costo_unitario']})
        st.rerun()

# --- TAB 4: FÁBRICA (PRODUCTOS Y RECETAS) ---
with tabs[3]:
    st.header("Gestión de Producción")
    try:
        mod_cfg = get_data("SELECT salario_base, p_prestaciones, num_operarios, horas_mes FROM config_mod WHERE id=1").iloc[0]
        t_mod_mensual = float(mod_cfg['salario_base'] * mod_cfg['num_operarios'] * (1 + mod_cfg['p_prestaciones']/100))
        minutos_disponibles = float(mod_cfg['horas_mes'] * mod_cfg['num_operarios'] * 60)
        costo_minuto = t_mod_mensual / minutos_disponibles if minutos_disponibles > 0 else 0
        st.info(f"⏱️ **Costo de Mano de Obra por Minuto:** Q{costo_minuto:,.4f}")
    except:
        st.warning("Configure la nómina de producción para calcular el costo por minuto.")
    with st.expander("📂 Carga Masiva de Productos (CSV)"):
        with st.form("csv_p_f", clear_on_submit=True):
            f_p = st.file_uploader("Subir CSV Productos", type="csv")
            if st.form_submit_button("Procesar Productos") and f_p:
                df_p = pd.read_csv(f_p)
                for _, r in df_p.iterrows():
                    run_query("INSERT INTO productos (codigo_barras, nombre, tipo_produccion, unidades_por_lote, precio_venta_sugerido) VALUES (:c, :n, :t, :u, :p) ON CONFLICT (codigo_barras) DO UPDATE SET nombre=:n",
                              {'c':str(r['codigo']), 'n':r['nombre'], 't':r['tipo'], 'u':r['unidades_lote'], 'p':r['precio']})
                st.success("Cargado"); st.rerun()

    c_left, c_right = st.columns([1, 2])
with c_left:
        st.subheader("🆕 Crear Individual")
        with st.form("new_p_safe"):
            cod = st.text_input("Código")
            nom = st.text_input("Nombre")
            tip = st.selectbox("Tipo", ["Unidad", "Lote"])
            uds = st.number_input("Uds/Lote", 1)
            # NUEVO CAMPO: Tiempo de ciclo
            ciclo = st.number_input("Tiempo de ciclo (Minutos por unidad)", value=5.0, step=0.1)
            prc = st.number_input("Precio Venta", 0.0)
            
            if st.form_submit_button("💾 Guardar"):
                # Query actualizado para incluir minutos_por_unidad
                run_query("""
                    INSERT INTO productos (codigo_barras, nombre, tipo_produccion, unidades_por_lote, minutos_por_unidad, precio_venta_sugerido) 
                    VALUES (:c, :n, :t, :u, :m, :p)
                    ON CONFLICT (codigo_barras) DO UPDATE SET 
                    nombre=:n, tipo_produccion=:t, unidades_por_lote=:u, minutos_por_unidad=:m, precio_venta_sugerido=:p
                """, {'c':cod, 'n':nom, 't':tip, 'u':uds, 'm':ciclo, 'p':prc})
                st.success(f"Producto {nom} guardado.")
                st.rerun()

with c_right:
        prods_list = get_data("SELECT codigo_barras, nombre FROM productos ORDER BY nombre")
        if not prods_list.empty:
            sel_p = st.selectbox("Editar Receta de:", prods_list['nombre'].tolist())
            pid = prods_list[prods_list['nombre']==sel_p]['codigo_barras'].values[0]
            
            # --- Lógica de Unidades de Medida ---
            mps_list = get_data("SELECT id, nombre, unidad_medida FROM materias_primas ORDER BY nombre")
            
            # 1. Obtenemos unidades únicas de la DB para el desplegable
            unidades_db = get_data("SELECT DISTINCT unidad_medida FROM materias_primas WHERE unidad_medida IS NOT NULL")
            opciones_u = unidades_db['unidad_medida'].tolist() if not unidades_db.empty else []
            if "Nueva unidad..." not in opciones_u:
                opciones_u.append("Nueva unidad...")

            with st.form("add_rec_f"):
                st.subheader(f"🛠️ Editor: {sel_p}")
                c1, c2, c3 = st.columns([3,1,1])
                
                m_n = c1.selectbox("MP", mps_list['nombre'].tolist())
                m_r = mps_list[mps_list['nombre']==m_n].iloc[0]
                can = c2.number_input("Cant.", format="%.4f")
                
                # 2. Selector de unidades existentes
                u_sel = c3.selectbox("Unidad", opciones_u, index=opciones_u.index(m_r['unidad_medida']) if m_r['unidad_medida'] in opciones_u else 0)
                
                # 3. Campo extra que solo se usa si eliges "Nueva unidad..."
                nueva_u = st.text_input("Escribe la nueva unidad (solo si seleccionaste 'Nueva unidad...' arriba)", placeholder="Ej: Mililitros")
                
                if st.form_submit_button("➕ Añadir Ingrediente"):
                    # Si eligió "Nueva unidad...", usamos el texto escrito, si no, la del selectbox
                    unidad_final = nueva_u if u_sel == "Nueva unidad..." else u_sel
                    
                    if u_sel == "Nueva unidad..." and not nueva_u:
                        st.error("Por favor, escribe el nombre de la nueva unidad.")
                    else:
                        run_query("INSERT INTO recetas (producto_id, mp_id, cantidad, unidad_uso) VALUES (:pid, :mid, :c, :u)", 
                                  {'pid':pid, 'mid':int(m_r['id']), 'c':can, 'u':unidad_final})
                        st.success(f"Añadido: {m_n}")
                        st.rerun()
            
            curr_rec = get_data("SELECT r.id, m.nombre, r.cantidad, r.unidad_uso FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:pid", {'pid':pid})
            st.dataframe(curr_rec, use_container_width=True, hide_index=True)
# --- TAB 5: FICHA TÉCNICA (ACTUALIZADA CON DESGLOSE DETALLADO) ---
with tabs[4]:
    st.header("🔎 Ficha Técnica de Costeo")
    prods_f = get_data("SELECT * FROM productos ORDER BY nombre")
    sel_f = st.selectbox("Ver Ficha de:", [""] + prods_f['nombre'].tolist())
    
    if sel_f:
        p_info = prods_f[prods_f['nombre']==sel_f].iloc[0]
        cod_p = p_info['codigo_barras']
        
        # Recuperar receta
        rec_det = get_data("SELECT m.nombre, m.categoria, r.cantidad, r.unidad_uso, m.id as mid FROM recetas r JOIN materias_primas m ON r.mp_id=m.id WHERE r.producto_id=:c", {'c':cod_p})
        df_frag = rec_det[rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        df_otros = rec_det[~rec_det['categoria'].str.contains("FRAGANCIA|FORMULA", case=False, na=False)]
        
        st.markdown(f"### {p_info['nombre']}")
        c_f, c_o = st.columns(2)
        tot_formula = 0
        tot_empaque = 0
        
        with c_f:
            st.write("**🧪 FRAGANCIA / FÓRMULA**")
            sub_f = 0
            for _, r in df_frag.iterrows():
                linea = r['cantidad'] * obtener_costo_convertido(r['mid'], r['unidad_uso'])
                sub_f += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"SUB-TOTAL FORMULA: Q{sub_f:.4f}")
            tot_formula = sub_f

        with c_o:
            st.write("**📦 MATERIA PRIMA / EMPAQUE**")
            sub_o = 0
            for _, r in df_otros.iterrows():
                linea = r['cantidad'] * obtener_costo_convertido(r['mid'], r['unidad_uso'])
                sub_o += linea
                st.write(f"- {r['nombre']}: Q{linea:.4f}")
            st.info(f"SUB-TOTAL MATERIA PRIMA: Q{sub_o:.4f}")
            tot_empaque = sub_o
        
        st.divider()

        # --- CÁLCULOS TÉCNICOS ---
        u_div = p_info['unidades_por_lote'] if p_info['tipo_produccion'] == 'Lote' else 1
        u_prom_base = get_data("SELECT unidades_promedio_mes FROM config_global WHERE id=1").iloc[0,0]
        
        # 1. Costo Variable Unitario
        costo_variable_u = (tot_formula + tot_empaque) / u_div
        
        # 2. Mano de Obra Directa (MOD) por minuto
        mod_cfg = get_data("SELECT salario_base, p_prestaciones, num_operarios, horas_mes FROM config_mod WHERE id=1").iloc[0]
        t_mod_mensual = float(mod_cfg['salario_base'] * mod_cfg['num_operarios'] * (1 + mod_cfg['p_prestaciones']/100))
        minutos_disponibles = float(mod_cfg['horas_mes'] * mod_cfg['num_operarios'] * 60)
        costo_minuto = t_mod_mensual / minutos_disponibles if minutos_disponibles > 0 else 0
        
        # Tiempo de ciclo (si no existe la columna en DB, usamos el estándar de 5 min)
        tiempo_ciclo = float(p_info.get('minutos_por_unidad', 5.0)) 
        mod_u = tiempo_ciclo * costo_minuto
        
        # 3. Costos Fijos Unitarios (CIF)
        cif_tot = get_data("SELECT SUM(total_mensual * (p_prod/100)) FROM costos_fijos").iloc[0,0] or 0
        c_fijos_u = float(cif_tot) / u_prom_base
        
        # 4. Gasto Operativo (Admin + Ventas)
        gasto_op_tot = get_data("SELECT SUM(total_mensual * ((p_admin + p_ventas)/100)) FROM costos_fijos").iloc[0,0] or 0
        gasto_op_u = float(gasto_op_tot) / u_prom_base
        
        # --- TOTALES FINALES ---
        costo_total_u = costo_variable_u + mod_u + c_fijos_u
        total_costos_gastos = costo_total_u + gasto_op_u
        precio_venta = float(p_info['precio_venta_sugerido'])
        utilidad = precio_venta - total_costos_gastos
        margen = (utilidad / precio_venta * 100) if precio_venta > 0 else 0

        # --- TABLA DE RESULTADOS ESTILO EXCEL ---
        st.subheader("📊 Desglose Final de Costos y Utilidad")
        
        res_cols = st.columns(2)
        with res_cols[0]:
            st.write(f"**COSTO VARIABLE UNITARIO:** Q{costo_variable_u:,.2f}")
            st.write(f"**MANO DE OBRA DIRECTA (MOD):** Q{mod_u:,.2f}")
            st.write(f"**COSTOS FIJOS UNITARIOS:** Q{c_fijos_u:,.2f}")
            st.markdown(f"### **COSTO TOTAL UNITARIO:** Q{costo_total_u:,.2f}")
            st.write(f"**Tiempo de ciclo:** {tiempo_ciclo} min")
            
        with res_cols[1]:
            st.write(f"**Gasto total Unitario (operativo promedio):** Q{gasto_op_u:,.2f}")
            st.markdown(f"### **Total de costos y gastos:** Q{total_costos_gastos:,.2f}")
            st.write(f"**PRECIO DE VENTA:** Q{precio_venta:,.2f}")
            
        st.divider()
        
        # KPIs Visuales
        k1, k2, k3 = st.columns(3)
        k1.metric("UTILIDAD POR UNIDAD", f"Q{utilidad:,.2f}", delta_color="normal")
        k2.metric("MARGEN DE GANANCIA", f"{margen:.2f}%")
        k3.metric("PUNTO DE EQUILIBRIO (Est.)", f"{int(total_costos_gastos / (precio_venta - costo_variable_u) * u_prom_base) if precio_venta > costo_variable_u else 0} uds")
# --- TAB 6: AJUSTES (CONVERSIONES) ---
with tabs[5]:
    st.header("⚙️ Ajustes y Conversiones")
    with st.form("new_conv"):
        c1, c2, c3 = st.columns(3)
        o = c1.text_input("Unidad Compra")
        d = c2.text_input("Unidad Receta")
        f = c3.number_input("Factor (Ej: 1 Gal = 128 Oz)", value=1.0)
        if st.form_submit_button("Registrar"):
            run_query("INSERT INTO conversiones (unidad_origen, unidad_destino, factor_multiplicador) VALUES (:o, :d, :f) ON CONFLICT (unidad_origen, unidad_destino) DO UPDATE SET factor_multiplicador=:f", {'o':o, 'd':d, 'f':f})
            st.rerun()
    st.dataframe(get_data("SELECT * FROM conversiones"), use_container_width=True)
