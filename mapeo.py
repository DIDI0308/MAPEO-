import streamlit as st
import pandas as pd
import numpy as np

# Configuración de interfaz ejecutiva y minimalista
st.set_page_config(page_title="Módulo de Ruteo", layout="wide")
st.title("Procesamiento de Base de Ruteo")

# Carga del archivo
archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        # 1. Extracción Eficiente: Solo se lee la hoja 'FOX' y las columnas B y C
        # Esto previene la ralentización del portal al ignorar hojas y columnas irrelevantes
        df = pd.read_excel(
            archivo_subido, 
            sheet_name="FOX", 
            usecols="B:C"
        )
        
        # Identificamos los nombres de las columnas dinámicamente
        col_b = df.columns[0]
        col_c = df.columns[1]
        
        # 2. Estandarización de la columna C para asegurar el filtrado exacto
        # Se convierte a texto mayúscula y se eliminan espacios residuales
        df[col_c] = df[col_c].astype(str).str.strip().str.upper()
        
        # 3. Filtrado estricto: Se excluyen los valores "NO" y "#N/D"
        df_filtrado = df[~df[col_c].isin(["NO", "#N/D"])]
        
        # 4. Eliminación de duplicados evaluando ambas columnas
        df_final = df_filtrado.drop_duplicates(subset=[col_b, col_c])
        
        # Presentación de resultados y métricas de control
        st.subheader("Base Procesada")
        st.dataframe(df_final, use_container_width=True)
        
        # Panel de control de procesamiento
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Registros Iniciales", len(df))
        col2.metric("Descartados (NO o #N/D)", len(df) - len(df_filtrado))
        col3.metric("Total Final (Únicos)", len(df_final))

    except ValueError:
        st.error("Error: Verifique que el archivo contiene una hoja llamada 'FOX' y al menos las columnas B y C.")
    except Exception as e:
        st.error(f"Error inesperado durante el procesamiento: {e}")