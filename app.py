import sqlite3
import streamlit as st

st.set_page_config(
    page_title="AutoRuta Smart - Catálogo Maestro",
    page_icon="🚗",
    layout="wide"
)

DB_NAME = "autoruta_maestra.db"

def obtener_conexion():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

st.title("🚗 AutoRuta Smart — Plataforma de Diagnóstico y Catálogo")
st.markdown("---")

menu = st.sidebar.selectbox(
    "Menú de Operación", 
    [
        "🔎 Buscador Directo de Filtros y Equivalencias",
        "🔍 Consulta por Patente (En Terreno)", 
        "📊 Resumen de Base de Datos"
    ]
)

# ==========================================
# VISTA 1: BUSCADOR DIRECTO DE FILTROS
# ==========================================
if menu == "🔎 Buscador Directo de Filtros y Equivalencias":
    st.subheader("🔎 Buscador Directo de Filtros y Catálogo Maestro")
    st.markdown("Ingrese el código del filtro (ej: `ACP007`, `W610`, `PSL55`) para consultar su ficha, equivalencias, aplicaciones, precios y stock.")

    busqueda = st.text_input("Código de Filtro a Buscar:", "").upper().strip()

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
            st.warning(f"No se encontró ningún filtro que coincida con '{busqueda}'.")
        else:
            st.success(f"Se encontraron {len(resultados)} coincidencia(s):")
            
            for rep in resultados:
                st.markdown("---")
                
                # Dos columnas superiores: Izquierda (Principal), Derecha (Equivalencias / Mann)
                col_izq, col_der = st.columns(2)
                
                with col_izq:
                    st.markdown("### 📦 Filtro Principal")
                    st.markdown(f"**Código:** `{rep['codigo']}`")
                    st.markdown(f"**Línea / Origen:** {rep['marca_fabricante']}")
                    st.markdown(f"**Categoría:** {rep['categoria']}")
                
                with col_der:
                    st.markdown("### 🔄 Equivalencias y Cruces (Cross-Reference)")
                    cursor.execute("""
                        SELECT eq.id_repuesto, eq.codigo, eq.marca_fabricante, eq.categoria, eq.pvp, eq.stock
                        FROM equivalencias e
                        JOIN repuestos eq ON e.id_repuesto_destino = eq.id_repuesto
                        WHERE e.id_repuesto_origen = ?
                    """, (rep['id_repuesto'],))
                    equivalencias = cursor.fetchall()
                    
                    if equivalencias:
                        for eq in equivalencias:
                            st.markdown(f"• **`{eq['codigo']}`** (*{eq['marca_fabricante']}* - {eq['categoria']})")
                    else:
                        st.info("*(Sin equivalencias cruzadas registradas para este código)*")
                
                # Parte inferior: Aplicaciones, Precio de Venta y Stock
                st.markdown("#### 📋 Aplicaciones Vehiculares, Precios y Stock en Sistema")
                
                st.info(f"**🚗 Aplicaciones / Comentarios:**\n\n{rep['aplicacion']}")
                
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    st.success(f"**Precio de Venta al Público (PVP):** `${rep['pvp']:,.0f}`" if rep['pvp'] > 0 else "**Precio:** A consultar")
                with sub_col2:
                    st.warning(f"**Estado de Stock:** {rep['stock']}")
                        
        conn.close()

# ==========================================
# VISTA 2: CONSULTA POR PATENTE
# ==========================================
elif menu == "🔍 Consulta por Patente (En Terreno)":
    st.subheader("Módulo de Identificación Vehicular por Patente")
    patente_input = st.text_input("Ingrese la Patente del Vehículo:", "").upper().strip()
    if st.button("Buscar Vehículo") and patente_input:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id_vehiculo, v.marca, v.modelo, v.motor, v.ano_inicio
            FROM registro_patentes p
            JOIN vehiculos v ON p.id_vehiculo = v.id_vehiculo
            WHERE p.patente = ?
        """, (patente_input,))
        vehiculo = cursor.fetchone()
        if vehiculo:
            st.markdown(f"### 📋 Vehículo: {vehiculo['marca']} {vehiculo['modelo']} ({vehiculo['ano_inicio']}) - Motor: {vehiculo['motor']}")
        else:
            st.warning("Patente no registrada.")
        conn.close()

# ==========================================
# VISTA 3: RESUMEN
# ==========================================
elif menu == "📊 Resumen de Base de Datos":
    st.subheader("Estado General del Sistema Maestro")
    conn = obtener_conexion()
    cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM repuestos").fetchone()[0]
    st.metric("Repuestos Totales con Datos Completos", total)
    conn.close()