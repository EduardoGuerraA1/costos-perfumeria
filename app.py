# ============================================
# SISTEMA ERP DE COSTOS - PERFUMERÍA
# Versión: 1.0
# Autor: Asistente de Programación
# ============================================

import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
st.set_page_config(
    page_title="ERP Costos | Perfumería",
    page_icon="🧴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes iniciales (después serán configurables)
IVA = 12
COSTO_MOD_MINUTO = 0.44
COSTO_FIJO_UNITARIO = 2.38
GASTO_OPERATIVO_UNITARIO = 15.34

# ============================================
# BASE DE DATOS
# ============================================
def init_db():
    conn = sqlite3.connect('erp_costos.db', check_same_thread=False)
    c = conn.cursor()
    
    # Tabla de usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  nombre TEXT,
                  rol TEXT DEFAULT 'usuario',
                  activo INTEGER DEFAULT 1)''')
    
    # Tabla de productos
    c.execute('''CREATE TABLE IF NOT EXISTS productos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sku TEXT UNIQUE,
                  codigo_barras TEXT,
                  nombre TEXT,
                  linea TEXT,
                  precio_venta REAL DEFAULT 0,
                  tiempo_mod REAL DEFAULT 3,
                  activo INTEGER DEFAULT 1)''')
    
    # Insertar usuario admin por defecto
    c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                 ('admin', password_hash, 'Administrador', 'dueno'))
    
    conn.commit()
    return conn

conn = init_db()

# ============================================
# FUNCIONES DE AUTENTICACIÓN
# ============================================
def autenticar(username, password):
    c = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT id, username, nombre, rol FROM usuarios WHERE username = ? AND password = ? AND activo = 1",
             (username, password_hash))
    return c.fetchone()

# ============================================
# FUNCIONES DE PRODUCTOS
# ============================================
def cargar_productos_csv(df):
    """Carga productos desde DataFrame de pandas"""
    c = conn.cursor()
    resultados = {'nuevos': 0, 'actualizados': 0, 'errores': 0}
    
    for _, row in df.iterrows():
        try:
            sku = str(row['sku']).strip()
            nombre = row['nombre'] if pd.notna(row.get('nombre')) else sku
            tiempo_mod = float(row['tiempo_mod']) if pd.notna(row.get('tiempo_mod')) else 3.0
            linea = row['linea'] if pd.notna(row.get('linea')) else 'General'
            
            c.execute('''INSERT INTO productos (sku, nombre, tiempo_mod, linea)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(sku) DO UPDATE SET
                            nombre = excluded.nombre,
                            tiempo_mod = excluded.tiempo_mod,
                            linea = excluded.linea''',
                     (sku, nombre, tiempo_mod, linea))
            resultados['nuevos' if c.rowcount == 1 else 'actualizados'] += 1
        except Exception as e:
            resultados['errores'] += 1
            print(f"Error con {row.get('sku')}: {e}")
    
    conn.commit()
    return resultados

def obtener_productos(linea=None):
    c = conn.cursor()
    if linea and linea != "Todas":
        c.execute("SELECT sku, nombre, tiempo_mod, linea, precio_venta FROM productos WHERE activo = 1 AND linea = ?", (linea,))
    else:
        c.execute("SELECT sku, nombre, tiempo_mod, linea, precio_venta FROM productos WHERE activo = 1")
    return c.fetchall()

def obtener_lineas():
    c = conn.cursor()
    c.execute("SELECT DISTINCT linea FROM productos WHERE activo = 1 AND linea IS NOT NULL")
    return ['Todas'] + [l[0] for l in c.fetchall()]

# ============================================
# INTERFAZ DE LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None

if not st.session_state.autenticado:
    st.title("🔐 Sistema ERP de Costos - Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://img.icons8.com/color/96/000000/perfume-bottle.png", width=120)
        with st.form("login"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
                usuario = autenticar(username, password)
                if usuario:
                    st.session_state.autenticado = True
                    st.session_state.usuario = {
                        'id': usuario[0],
                        'username': usuario[1],
                        'nombre': usuario[2],
                        'rol': usuario[3]
                    }
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
    st.stop()

# ============================================
# INTERFAZ PRINCIPAL
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/perfume-bottle.png", width=80)
    st.title(f"🧴 ERP Costos")
    st.markdown(f"**Usuario:** {st.session_state.usuario['nombre']}")
    st.markdown(f"**Rol:** {st.session_state.usuario['rol'].upper()}")
    st.markdown("---")
    
    menu = st.radio("Menú Principal", [
        "📊 Dashboard",
        "📦 Productos",
        "💰 Costear Pedido",
        "⚙️ Configuración"
    ])
    
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# ============================================
# DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    
    productos = obtener_productos()
    total_productos = len(productos)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Productos", total_productos)
    with col2:
        st.metric("Líneas Activas", len(obtener_lineas()) - 1)
    with col3:
        st.metric("Costo MOD/min", f"Q{COSTO_MOD_MINUTO:.2f}")
    
    if productos:
        df = pd.DataFrame(productos, columns=['SKU', 'Nombre', 'Tiempo MOD', 'Línea', 'Precio'])
        st.dataframe(df, use_container_width=True)

# ============================================
# PRODUCTOS - CARGA MASIVA
# ============================================
elif menu == "📦 Productos":
    st.title("📦 Gestión de Productos")
    
    tab1, tab2, tab3 = st.tabs(["📤 Cargar CSV", "📋 Listado", "✏️ Editar"])
    
    with tab1:
        st.subheader("Cargar Productos desde CSV")
        
        st.markdown("""
        **Formato requerido:**
        ```csv
        sku,nombre,tiempo_mod,linea
        0701095502664,LOCION AAA TOY BOY MOSCHINO,5,REPLICA
        ```
        
        - `sku` y `nombre` son obligatorios
        - `tiempo_mod` opcional (valor por defecto: 3)
        - `linea` opcional (valor por defecto: "General")
        """)
        
        archivo = st.file_uploader("Seleccionar archivo CSV", type=['csv'])
        
        if archivo:
            df = pd.read_csv(archivo)
            st.write("Vista previa:", df.head())
            
            if st.button("🚀 Cargar Productos", type="primary"):
                with st.spinner("Cargando productos..."):
                    resultados = cargar_productos_csv(df)
                    st.success(f"""
                    ✅ Carga completada:
                    - Nuevos: {resultados['nuevos']}
                    - Actualizados: {resultados['actualizados']}
                    - Errores: {resultados['errores']}
                    """)
    
    with tab2:
        st.subheader("Listado de Productos")
        
        lineas = obtener_lineas()
        linea_filtro = st.selectbox("Filtrar por línea:", lineas)
        
        productos = obtener_productos(linea_filtro if linea_filtro != "Todas" else None)
        
        if productos:
            df = pd.DataFrame(productos, columns=['SKU', 'Nombre', 'Tiempo MOD', 'Línea', 'Precio'])
            st.dataframe(df, use_container_width=True)
            
            # Botón para exportar
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Exportar a CSV",
                data=csv,
                file_name=f"productos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay productos cargados")
    
    with tab3:
        st.subheader("Editar Producto")
        st.info("Selecciona un producto del listado para editar (próximamente)")

# ============================================
# COSTEAR PEDIDO
# ============================================
elif menu == "💰 Costear Pedido":
    st.title("💰 Costear Pedido")
    
    st.markdown("""
    **Sube un archivo CSV con el pedido:**
    ```csv
    sku,cantidad,precio
    0701095502664,10,85.00
    0737250133904,5,125.00
    ```
    - `sku`: Código del producto
    - `cantidad`: Unidades
    - `precio`: Precio de venta unitario
    """)
    
    archivo = st.file_uploader("Seleccionar archivo del pedido", type=['csv'])
    
    if archivo:
        df_pedido = pd.read_csv(archivo)
        st.write("Vista previa del pedido:", df_pedido)
        
        if st.button("💰 Calcular Costos", type="primary"):
            with st.spinner("Calculando..."):
                # Obtener productos de la BD
                c = conn.cursor()
                skus = tuple(df_pedido['sku'].unique())
                placeholders = ','.join(['?'] * len(skus))
                c.execute(f"SELECT sku, nombre, tiempo_mod FROM productos WHERE sku IN ({placeholders})", skus)
                productos_db = {p[0]: {'nombre': p[1], 'tiempo_mod': p[2]} for p in c.fetchall()}
                
                # Calcular cada línea
                resultados = []
                total_venta = 0
                total_costo = 0
                
                for _, row in df_pedido.iterrows():
                    sku = str(row['sku']).strip()
                    cantidad = float(row['cantidad'])
                    precio = float(row['precio'])
                    
                    # Datos del producto
                    if sku in productos_db:
                        producto = productos_db[sku]
                        nombre = producto['nombre']
                        tiempo_mod = producto['tiempo_mod']
                        
                        # Costos
                        costo_mod = tiempo_mod * COSTO_MOD_MINUTO
                        costo_variable = costo_mod  # + MP + fórmula (después)
                        costo_total_unitario = costo_variable + COSTO_FIJO_UNITARIO + GASTO_OPERATIVO_UNITARIO
                        
                        # Cálculos
                        precio_sin_iva = precio / (1 + IVA/100)
                        iva = precio - precio_sin_iva
                        subtotal = cantidad * precio
                        costo_total_linea = cantidad * costo_total_unitario
                        utilidad = subtotal - costo_total_linea
                        margen = (utilidad / subtotal * 100) if subtotal > 0 else 0
                        
                        total_venta += subtotal
                        total_costo += costo_total_linea
                        
                        estado = "✅"
                    else:
                        nombre = "NO ENCONTRADO"
                        tiempo_mod = 0
                        costo_mod = 0
                        costo_total_unitario = 0
                        precio_sin_iva = precio / (1 + IVA/100)
                        iva = precio - precio_sin_iva
                        subtotal = cantidad * precio
                        costo_total_linea = 0
                        utilidad = 0
                        margen = 0
                        estado = "❌"
                    
                    resultados.append({
                        'SKU': sku,
                        'Producto': nombre,
                        'Cantidad': cantidad,
                        'Precio': f"Q{precio:.2f}",
                        'Subtotal': f"Q{subtotal:.2f}",
                        'Costo Unit.': f"Q{costo_total_unitario:.2f}",
                        'Costo Total': f"Q{costo_total_linea:.2f}",
                        'Utilidad': f"Q{utilidad:.2f}",
                        'Margen': f"{margen:.1f}%",
                        'Estado': estado
                    })
                
                # Mostrar resultados
                st.markdown("---")
                st.subheader("📊 Resultados del Pedido")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Venta", f"Q{total_venta:,.2f}")
                with col2:
                    st.metric("Total Costo", f"Q{total_costo:,.2f}")
                with col3:
                    utilidad_total = total_venta - total_costo
                    margen_total = (utilidad_total / total_venta * 100) if total_venta > 0 else 0
                    st.metric("Utilidad", f"Q{utilidad_total:,.2f}", f"{margen_total:.1f}%")
                
                # Tabla de resultados
                df_resultados = pd.DataFrame(resultados)
                st.dataframe(df_resultados, use_container_width=True)
                
                # Botón para exportar
                csv_resultados = df_resultados.to_csv(index=False)
                st.download_button(
                    label="📥 Descargar Resultados",
                    data=csv_resultados,
                    file_name=f"costeo_pedido_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )

# ============================================
# CONFIGURACIÓN
# ============================================
elif menu == "⚙️ Configuración":
    st.title("⚙️ Configuración del Sistema")
    
    st.info(f"""
    **Parámetros actuales:**
    - IVA: {IVA}%
    - Costo MOD/minuto: Q{COSTO_MOD_MINUTO:.2f}
    - Costo Fijo Unitario: Q{COSTO_FIJO_UNITARIO:.2f}
    - Gasto Operativo Unitario: Q{GASTO_OPERATIVO_UNITARIO:.2f}
    
    *Próximamente: configuración dinámica de parámetros*
    """)
