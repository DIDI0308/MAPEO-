import streamlit as st
import pandas as pd

# Configuración de interfaz ejecutiva y minimalista
st.set_page_config(page_title="Módulo de Ruteo", layout="wide")
st.title("Procesamiento de Base de Ruteo")

# Carga del archivo
archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        # 1. Extracción Eficiente: Ahora leemos las columnas A, B y C
        df = pd.read_excel(
            archivo_subido, 
            sheet_name="FOX", 
            usecols="A:C"
        )
        
        # Identificamos los nombres de las columnas (A: RUTA, B: CLIENTE, C: CAM)
        col_ruta = df.columns[0]
        col_cliente = df.columns[1]
        col_cam = df.columns[2]
        
        # 2. Estandarización de la columna CAM (C) para el filtro
        df[col_cam] = df[col_cam].astype(str).str.strip().str.upper()
        
        # 3. Filtrado: Excluir "NO" y "#N/D" en la columna CAM
        df_filtrado = df[~df[col_cam].isin(["NO", "#N/D"])]
        
        # 4. Eliminación de duplicados evaluando las TRES columnas simultáneamente
        df_final = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
        
        # 5. Tabla Resumen: Agrupar por Camión y Ruta, contando los Clientes (PDV's)
        df_resumen = df_final.groupby([col_cam, col_ruta])[col_cliente].count().reset_index()
        df_resumen.rename(columns={col_cliente: "N° de PDVs a Visitar"}, inplace=True)
        
        # --- PRESENTACIÓN EN PORTAL ---
        
        # Panel de métricas clave (vista limpia)
        col1, col2, col3 = st.columns(3)
        col1.metric("Registros Iniciales", len(df))
        col2.metric("Base Limpia (Final)", len(df_final))
        col3.metric("Total Camiones", df_resumen[col_cam].nunique())
        
        st.divider()
        
        # Distribución de tablas en pantalla
        col_izq, col_der = st.columns([1, 1.5])
        
        with col_izq:
            st.subheader("Resumen Operativo")
            # hide_index=True mantiene la tabla visualmente limpia
            st.dataframe(df_resumen, use_container_width=True, hide_index=True)
            
        with col_der:
            st.subheader("Base de Ruteo Detallada")
            st.dataframe(df_final, use_container_width=True, hide_index=True)

    except ValueError:
        st.error("Error: Verifique que el archivo contiene la hoja 'FOX' y datos en las columnas A, B y C.")
    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")
        
