import streamlit as st
import pandas as pd
import sqlite3

# Configuración de página
st.set_page_config(page_title="ERP Costos Perfumería", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
def get_connection():
    conn = sqlite3.connect('costos_perfumeria.db', check_same_thread=False)
    return conn

db = get_connection()

def init_db():
    cursor = db.cursor()
    # Tabla de Costos Fijos
    cursor.execute('''CREATE TABLE IF NOT EXISTS costos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT,
        total_mensual REAL,
        p_admin REAL DEFAULT 50,
        p_ventas REAL DEFAULT 10,
        p_prod REAL DEFAULT 40
    )''')
    
    # Tabla de Configuración MOD
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_mod (
        id INTEGER PRIMARY KEY,
        salario_base REAL,
        p_prestaciones REAL,
        num_operarios INTEGER,
        horas_mes REAL
    )''')
    
    # Tabla de Producción Mensual
    cursor.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes TEXT,
        anio INTEGER,
        unidades INTEGER
    )''')
    
    # Datos iniciales si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM costos_fijos")
    if cursor.fetchone()[0] == 0:
        datos_iniciales = [
            ('Alquiler', 13400.00, 50, 10, 40),
            ('Internet', 600.00, 50, 10, 40),
            ('Teléfono', 1300.00, 50, 10, 40),
            ('Energía Eléctrica', 1000.00, 50, 10, 40),
            ('Agua', 300.00, 50, 10, 40),
            ('Seguridad', 800.00, 50, 10, 40),
            ('Software', 1057.00, 50, 10, 40),
            ('Contabilidad', 2650.00, 50, 10, 40),
            ('Asesoría Externa', 8000.00, 50, 10, 40),
            ('Combustible', 2000.00, 10, 20, 70), # Ajuste según tus datos (200/400/1400)
            ('Empaque', 1900.00, 0, 20, 80),      # Ajuste según tus datos (0/380/1520)
            ('Nómina Admin/Ventas', 72288.76, 82.35, 17.65, 0),
            ('Prestaciones', 30238.39, 82.35, 17.65, 0)
        ]
        cursor.executemany("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)", datos_iniciales)
        
        # MOD Inicial
        cursor.execute("INSERT INTO config_mod VALUES (1, 4252.28, 41.83, 3, 176)")
        
        # Producción inicial (ejemplo para promedio)
        cursor.execute("INSERT INTO produccion (mes, anio, unidades) VALUES ('Enero', 2024, 5000)")
        
    db.commit()

init_db()

# --- FUNCIONES DE CÁLCULO ---
def get_costos_fijos():
    df = pd.read_sql_query("SELECT * FROM costos_fijos", db)
    df['Admin (Q)'] = df['total_mensual'] * (df['p_admin'] / 100)
    df['Ventas (Q)'] = df['total_mensual'] * (df['p_ventas'] / 100)
    df['Producción (Q)'] = df['total_mensual'] * (df['p_prod'] / 100)
    return df

# --- INTERFAZ STREAMLIT ---
st.title("🧪 Sistema ERP: Costos de Perfumería")

tabs = st.tabs(["📊 Matriz Costos Fijos", "👷 Mano de Obra (MOD)", "📦 Producción y Unitarios"])

# TABA 1: COSTOS FIJOS
with tabs[0]:
    st.header("Matriz de Costos Fijos Mensuales")
    
    with st.expander("➕ Agregar Nuevo Concepto"):
        with st.form("nuevo_costo"):
            c1, c2 = st.columns(2)
            nuevo_concepto = c1.text_input("Concepto")
            monto = c2.number_input("Total Mensual (Q)", min_value=0.0, step=100.0)
            p_adm = st.slider("Admin %", 0, 100, 50)
            p_ven = st.slider("Ventas %", 0, 100, 10)
            p_pro = st.slider("Producción %", 0, 100, 40)
            
            if st.form_submit_button("Guardar"):
                if (p_adm + p_ven + p_pro) == 100:
                    db.execute("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,?)",
                               (nuevo_concepto, monto, p_adm, p_ven, p_pro))
                    db.commit()
                    st.success("Agregado")
                    st.rerun()
                else:
                    st.error("Los porcentajes deben sumar 100%")

    df_fijos = get_costos_fijos()
    st.dataframe(df_fijos.style.format({"total_mensual": "Q{:.2f}", "Admin (Q)": "Q{:.2f}", "Ventas (Q)": "Q{:.2f}", "Producción (Q)": "Q{:.2f}"}), use_container_width=True)
    
    totales = df_fijos[['total_mensual', 'Admin (Q)', 'Ventas (Q)', 'Producción (Q)']].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("TOTAL MENSUAL", f"Q{totales[0]:,.2f}")
    col2.metric("Admin (50% avg)", f"Q{totales[1]:,.2f}")
    col3.metric("Ventas (10% avg)", f"Q{totales[2]:,.2f}")
    col4.metric("Producción (CIF)", f"Q{totales[3]:,.2f}")

# TABA 2: MANO DE OBRA DIRECTA
with tabs[1]:
    st.header("Cálculo de Mano de Obra Directa (MOD)")
    
    mod_data = db.execute("SELECT * FROM config_mod WHERE id=1").fetchone()
    
    with st.form("form_mod"):
        c1, c2 = st.columns(2)
        salario = c1.number_input("Salario Base por Operario", value=mod_data[1])
        pct_prest = c2.number_input("% Prestaciones Laborales", value=mod_data[2])
        operarios = c1.number_input("Número de Operarios", value=mod_data[3])
        hrs_mes = c2.number_input("Horas Laborales/Mes por Operario", value=mod_data[4])
        
        if st.form_submit_button("Actualizar Parámetros MOD"):
            db.execute("UPDATE config_mod SET salario_base=?, p_prestaciones=?, num_operarios=?, horas_mes=? WHERE id=1",
                       (salario, pct_prest, operarios, hrs_mes))
            db.commit()
            st.rerun()

    # Cálculos
    costo_operario_total = salario * (1 + pct_prest/100)
    total_mod_mensual = costo_operario_total * operarios
    total_horas = hrs_mes * operarios
    costo_hora = total_mod_mensual / total_horas if total_horas > 0 else 0
    costo_min = costo_hora / 60

    st.subheader("Resultados MOD")
    res_mod = {
        "Concepto": ["Salario por Operario", "Costo Total por Operario", "Total Nómina MOD", "Total Horas Disponibles", "Costo por Hora", "Costo por Minuto"],
        "Valor": [f"Q{salario:,.2f}", f"Q{costo_operario_total:,.2f}", f"Q{total_mod_mensual:,.2f}", f"{total_horas} hrs", f"Q{costo_hora:,.2f}", f"Q{costo_min:,.4f}"]
    }
    st.table(pd.DataFrame(res_mod))

# TABA 3: PRODUCCIÓN Y UNITARIOS
with tabs[2]:
    st.header("Unidades y Costeo Unitario")
    
    df_prod = pd.read_sql_query("SELECT * FROM produccion", db)
    promedio_unidades = df_prod['unidades'].mean() if not df_prod.empty else 1
    
    st.metric("Promedio Unidades Mensuales", f"{promedio_unidades:,.0f} unidades")
    
    # Cálculos finales
    cifu = totales[3] / promedio_unidades
    gau = totales[1] / promedio_unidades
    gvu = totales[2] / promedio_unidades
    modu = total_mod_mensual / promedio_unidades

    st.subheader("Costos Unitarios Base")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("CIF Unitario", f"Q{cifu:,.2f}")
    col_b.metric("Admin Unitario", f"Q{gau:,.2f}")
    col_c.metric("Ventas Unitario", f"Q{gvu:,.2f}")
    col_d.metric("MOD Unitario", f"Q{modu:,.2f}")
