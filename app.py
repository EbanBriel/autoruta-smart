import sqlite3
import pandas as pd
import streamlit as st
import os

st.set_page_config(
    page_title="AutoRuta Smart - Catálogo Maestro",
    page_icon="🚗",
    layout="wide"
)

EXCEL_PATH = "Lista de Precios Filtros - Julio2026 (1).xlsx"
DB_NAME = "autoruta_maestra.db"

def limpiar_precio(val):
    if pd.isna(val):
        return 0.0
    v_str = str(val).strip().replace('$', '').replace(' ', '')
    try:
        if '.' in v_str and ',' in v_str:
            v_str = v_str.replace('.', '').replace(',', '.')
        elif '.' in v_str:
            parts = v_str.split('.')
            if len(parts) > 1 and len(parts[-1]) == 3:
                v_str = v_str.replace('.', '')
            else:
                v_str = v_str.replace('.', '.')
        elif ',' in v_str:
            parts = v_str.split(',')
            if len(parts) > 1 and len(parts[-1]) == 3:
                v_str = v_str.replace(',', '')
            else:
                v_str = v_str.replace(',', '.')
        num = float(v_str)
        return num if num > 500 else 0.0
    except:
        return 0.0

def asegurar_y_cargar_base_datos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Garantizar que las tablas SIEMPRE se crean al iniciar
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS repuestos (
        id_repuesto INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL, 
        marca_fabricante TEXT NOT NULL, 
        categoria TEXT NOT NULL,
        pvp REAL DEFAULT 0.0,
        stock TEXT DEFAULT 'Disponible',
        aplicacion TEXT DEFAULT 'No especificada'
    );

    CREATE TABLE IF NOT EXISTS equivalencias (
        id_equivalencia INTEGER PRIMARY KEY AUTOINCREMENT,
        id_repuesto_origen INT, 
        id_repuesto_destino INT
    );
    """)
    conn.commit()

    # Si la tabla está vacía y el Excel existe, procesar la carga
    total = cursor.execute("SELECT COUNT(*) FROM repuestos").fetchone()[0]
    if total == 0 and os.path.exists(EXCEL_PATH):
        xls = pd.ExcelFile(EXCEL_PATH)
        for sheet in xls.sheet_names:
            if "RESUMEN" in sheet.upper():
                continue
            df = pd.read_excel(xls, sheet_name=sheet)
            for idx, row in df.iterrows():
                row_vals = [str(v).strip() for v in row.values if pd.notna(v)]
                if len(row_vals) < 3:
                    continue
                
                codigo_principal = None
                marca = sheet[:20]
                categoria = "Filtro"
                pvp = 0.0
                stock = "Disponible"
                aplicacion = "No especificada"
                equivalentes = []
                precios_encontrados = []

                for val in row.values:
                    if pd.isna(val):
                        continue
                    v_str = str(val).strip()
                    if not v_str or v_str == '-' or v_str.lower() == 'nan':
                        continue
                    
                    precio_candidato = limpiar_precio(val)
                    if precio_candidato > 500:
                        precios_encontrados.append(precio_candidato)
                        continue
                    
                    if v_str.lower() in ['disponible', 'agotado', 'confirmar disponibilidad/precio']:
                        stock = v_str
                        continue
                    
                    if len(v_str) > 10 and any(k in v_str.upper() for k in ['VOLVO', 'SCANIA', 'TOYOTA', 'FORD', 'CHEVROLET', 'HYUNDAI', 'MITSUBISHI', 'REEMPLAZA', 'N°', 'MOTOR']):
                        aplicacion = v_str
                        continue
                    
                    if len(v_str) < 20 and not any(k in v_str.upper() for k in ['FILTRO', 'ACEITE', 'AIRE', 'DISPONIBLE']):
                        if not codigo_principal:
                            codigo_principal = v_str
                        else:
                            equivalentes.append(v_str)

                if precios_encontrados:
                    pvp = precios_encontrados[-1]

                if codigo_principal:
                    cursor.execute("""
                        INSERT OR IGNORE INTO repuestos (codigo, marca_fabricante, categoria, pvp, stock, aplicacion)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (codigo_principal, marca, categoria, pvp, stock, aplicacion))
                    
                    cursor.execute("SELECT id_repuesto FROM repuestos WHERE codigo = ?", (codigo_principal,))
                    res_orig = cursor.fetchone()
                    
                    if res_orig:
                        id_orig = res_orig[0]
                        for eq_cod in equivalentes:
                            if eq_cod != codigo_principal and len(eq_cod) < 20:
                                cursor.execute("""
                                    INSERT OR IGNORE INTO repuestos (codigo, marca_fabricante, categoria, pvp, stock, aplicacion)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (eq_cod, 'Equivalente', categoria, pvp, stock, aplicacion))
                                
                                cursor.execute("SELECT id_repuesto FROM repuestos WHERE codigo = ?", (eq_cod,))
                                res_dest = cursor.fetchone()
                                if res_dest:
                                    cursor.execute("""
                                        INSERT OR IGNORE INTO equivalencias (id_repuesto_origen, id_repuesto_destino)
                                        VALUES (?, ?)
                                    """, (id_orig, res_dest[0]))
        conn.commit()
    conn.close()

# Asegurar base de datos antes de renderizar la interfaz
asegurar_y_cargar_base_datos()

st.title("🚗 AutoRuta Smart — Catálogo en Terreno")
st.markdown("---")

menu = st.sidebar.selectbox(
    "Menú de Operación", 
    [
        "🔎 Buscador Directo de Filtros y Equivalencias",
        "📊 Resumen de Base de Datos"
    ]
)

def obtener_conexion():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

if menu == "🔎 Buscador Directo de Filtros y Equivalencias":
    st.subheader("🔎 Buscador de Filtros, Precios y Stock")
    busqueda = st.text_input("Ingrese Código de Filtro (ej: `ACP007`, `W610`):", "").upper().strip()

    if busqueda:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_repuesto, codigo, marca_fabricante, categoria, pvp, stock, aplicacion
            FROM repuestos
            WHERE codigo LIKE ?
            LIMIT 30
        """, (f"%{busqueda}%",))
        resultados = cursor.fetchall()
        
        if not resultados:
            st.warning(f"No se encontró ningún filtro con '{busqueda}'.")
        else:
            st.success(f"Se encontraron {len(resultados)} coincidencia(s):")
            for rep in resultados:
                st.markdown("---")
                col_izq, col_der = st.columns(2)
                
                with col_izq:
                    st.markdown("### 📦 Filtro Principal")
                    st.markdown(f"**Código:** `{rep['codigo']}`")
                    st.markdown(f"**Línea:** {rep['marca_fabricante']}")
                    st.markdown(f"**Categoría:** {rep['categoria']}")
                
                with col_der:
                    st.markdown("### 🔄 Equivalencias (Cross-Reference)")
                    cursor.execute("""
                        SELECT eq.codigo, eq.marca_fabricante, eq.categoria
                        FROM equivalencias e
                        JOIN repuestos eq ON e.id_repuesto_destino = eq.id_repuesto
                        WHERE e.id_repuesto_origen = ?
                    """, (rep['id_repuesto'],))
                    equivalencias = cursor.fetchall()
                    if equivalencias:
                        for eq in equivalencias:
                            st.markdown(f"• **`{eq['codigo']}`** (*{eq['marca_fabricante']}*)")
                    else:
                        st.info("*(Sin equivalencias registradas)*")
                
                st.markdown("#### 📋 Aplicaciones, Precio y Stock")
                st.info(f"**🚗 Aplicaciones:**\n\n{rep['aplicacion']}")
                sub1, sub2 = st.columns(2)
                with sub1:
                    st.success(f"**Precio Venta (PVP):** `${rep['pvp']:,.0f}`" if rep['pvp'] > 0 else "**Precio:** A consultar")
                with sub2:
                    st.warning(f"**Stock:** {rep['stock']}")
        conn.close()

elif menu == "📊 Resumen de Base de Datos":
    st.subheader("Estado General del Sistema")
    conn = obtener_conexion()
    cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM repuestos").fetchone()[0]
    st.metric("Total de Filtros Registrados", total)
    conn.close()
