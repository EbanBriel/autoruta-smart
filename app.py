import sqlite3
import pandas as pd
import streamlit as st
import os

st.set_page_config(
    page_title="AutoRuta Smart - Catálogo Maestro",
    page_icon="🚗",
    layout="wide"
)

EXCEL_PATH = "LISTA DE FILTROS PARA WEB APP.xlsx"
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

    total = cursor.execute("SELECT COUNT(*) FROM repuestos").fetchone()[0]
    if total == 0 and os.path.exists(EXCEL_PATH):
        xls = pd.ExcelFile(EXCEL_PATH)
        for sheet in xls.sheet_names:
            if "RESUMEN" in sheet.upper():
                continue
            
            # Leer el Excel buscando la cabecera correcta (fila 7, que corresponde a header=7)
            try:
                df = pd.read_excel(xls, sheet_name=sheet, header=7)
            except:
                df = pd.read_excel(xls, sheet_name=sheet)

            # Normalizar nombres de columnas para que coincidan sin importar mayúsculas/espacios
            df.columns = [str(c).strip().upper() for c in df.columns]

            for _, row in df.iterrows():
                # Obtener valores clave por nombre de columna exacto si existe
                codigo_principal = None
                for col_candidata in ['PN GLI', 'CODIGO', 'CÓDIGO', 'ITEM', 'PARTE']:
                    if col_candidata in df.columns and pd.notna(row[col_candidata]):
                        codigo_principal = str(row[col_candidata]).strip()
                        break
                
                # Si no encuentra columna por nombre estricto, toma el primer valor válido que parezca código
                if not codigo_principal:
                    for v in row.values:
                        if pd.notna(v) and len(str(v).strip()) < 20 and str(v).strip() != '-':
                            codigo_principal = str(v).strip()
                            break
                
                if not codigo_principal or codigo_principal.lower() == 'nan':
                    continue

                marca = sheet[:25]
                
                # Extraer Categoría / Tipo de filtro
                categoria = "Filtro"
                for col_candidata in ['TIPO DE FILTRO', 'CATEGORIA', 'TIPO']:
                    if col_candidata in df.columns and pd.notna(row[col_candidata]):
                        categoria = str(row[col_candidata]).strip()
                        break

                # Extraer Aplicación de forma directa desde la columna
                aplicacion = "No especificada"
                for col_candidata in ['APLICACIONES', 'APLICACION', 'APLICACIONES / COMENTARIOS', 'COMENTARIOS']:
                    if col_candidata in df.columns and pd.notna(row[col_candidata]):
                        val_app = str(row[col_candidata]).strip()
                        if val_app and val_app != '-' and val_app.lower() != 'nan':
                            aplicacion = val_app
                            break

                # Extraer Precio (PVP)
                pvp = 0.0
                for col_candidata in ['PRECIO CON DESCUENTO INCLUIDO', 'PVP', 'PRECIO', 'VALOR']:
                    if col_candidata in df.columns and pd.notna(row[col_candidata]):
                        pvp = limpiar_precio(row[col_candidata])
                        if pvp > 0:
                            break
                if pvp == 0.0:
                    # Buscar cualquier número candidato en la fila si la columna exacta no trajo precio
                    for v in row.values:
                        pc = limpiar_precio(v)
                        if pc > 500:
                            pvp = pc

                # Extraer Stock
                stock = "Disponible"
                for col_candidata in ['STOCK', 'ESTADO']:
                    if col_candidata in df.columns and pd.notna(row[col_candidata]):
                        val_st = str(row[col_candidata]).strip()
                        if val_st and val_st.lower() != 'nan':
                            stock = val_st
                            break

                # Extraer Equivalencias (Marcas Tecfil, Mann, etc.)
                equivalentes = []
                for col_name in df.columns:
                    if any(k in col_name for k in ['TECFIL', 'MANN', 'BALDWIN', 'DONALDSON', 'FLEETGUARD', 'WEGA', 'HIGHfil', 'EQUIVALENCIA', 'CRUCE']):
                        val_eq = row[col_name]
                        if pd.notna(val_eq):
                            eq_str = str(val_eq).strip()
                            if eq_str and eq_str != '-' and eq_str.lower() != 'nan' and eq_str != codigo_principal:
                                equivalentes.append(eq_str)

                # Insertar repuesto principal
                cursor.execute("""
                    INSERT OR IGNORE INTO repuestos (codigo, marca_fabricante, categoria, pvp, stock, aplicacion)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (codigo_principal, marca, categoria, pvp, stock, aplicacion))
                
                # Actualizar si ya existía para refrescar datos nuevos
                cursor.execute("""
                    UPDATE repuestos SET pvp = ?, stock = ?, aplicacion = ? WHERE codigo = ?
                """, (pvp, stock, aplicacion, codigo_principal))

                cursor.execute("SELECT id_repuesto FROM repuestos WHERE codigo = ?", (codigo_principal,))
                res_orig = cursor.fetchone()
                
                if res_orig:
                    id_orig = res_orig[0]
                    for eq_cod in equivalentes:
                        for sub_eq in eq_cod.replace('/', ' ').split():
                            sub_eq = sub_eq.strip()
                            if len(sub_eq) > 1 and sub_eq != codigo_principal:
                                cursor.execute("""
                                    INSERT OR IGNORE INTO repuestos (codigo, marca_fabricante, categoria, pvp, stock, aplicacion)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (sub_eq, 'Equivalente', categoria, pvp, stock, aplicacion))
                                
                                cursor.execute("SELECT id_repuesto FROM repuestos WHERE codigo = ?", (sub_eq,))
                                res_dest = cursor.fetchone()
                                if res_dest:
                                    cursor.execute("""
                                        INSERT OR IGNORE INTO equivalencias (id_repuesto_origen, id_repuesto_destino)
                                        VALUES (?, ?)
                                    """, (id_orig, res_dest[0]))
        conn.commit()
    conn.close()

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
