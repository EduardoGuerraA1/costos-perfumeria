import streamlit as st
import pandas as pd
import sqlite3
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ERP Perfumería - Fase 2.1", layout="wide")

def get_connection():
    return sqlite3.connect('costos_perfumeria_v2.db', check_same_thread=False)

db = get_connection()

# --- INICIALIZACIÓN DE BASE DE DATOS ROBUSTA ---
def init_db():
    cursor = db.cursor()
    
    # 1. Crear Tablas
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
    
    for t in tablas:
        cursor.execute(t)
    db.commit()

    # 2. Verificar e Insertar Datos Iniciales (ID=1)
    
    # Config MOD
    cursor.execute("SELECT count(*) FROM config_mod WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_mod (id, salario_base, p_prestaciones, num_operarios, horas_mes) VALUES (1, 4252.28, 41.83, 2, 176)")

    # Config Admin
    cursor.execute("SELECT count(*) FROM config_admin WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_admin (id, salario_base, p_prestaciones, num_empleados) VALUES (1, 5000.00, 41.83, 10)")

    # Config Global
    cursor.execute("SELECT count(*) FROM config_global WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO config_global (id, unidades_promedio_mes) VALUES (1, 5000)")

    # Costos Fijos (Solo si la tabla está vacía)
    cursor.execute("SELECT count(*) FROM costos_fijos")
    if cursor.fetchone()[0] == 0:
        fijos = [
            ('Alquiler', 13400.0, 50, 10, 40), ('Internet', 600.0, 50, 10, 40),
            ('Teléfono', 1300.0, 50, 10, 40), ('Energía Eléctrica', 1000.0, 50, 10, 40),
            ('Agua', 300.0, 50, 10, 40), ('Seguridad', 800.0, 50, 10, 40),
            ('Software', 1057.0, 50, 10, 40), ('Contabilidad', 2650.0, 50, 10, 40),
            ('Asesoría Externa', 8000.0, 50, 10, 40), ('Combustible', 2000.0, 10, 20, 70),
            ('Empaque', 1900.0, 0, 20, 80)
        ]
        cursor.executemany("INSERT INTO costos_fijos (concepto, total_mensual, p_admin, p_ventas, p_prod) VALUES (?,?,?,?,
