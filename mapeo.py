import streamlit as st
import pandas as pd
import io

# Configuración de interfaz
st.set_page_config(page_title="Módulo de Ruteo y Georreferenciación", layout="wide")
st.title("Procesamiento de Ruteo y Georreferenciación")

# Convertimos tu enlace de Google Drive en un enlace de descarga directa
URL_CLIENTES = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"

# Esta función descarga la base de Drive una sola vez y la guarda en memoria para no ralentizar
@st.cache_data
def cargar_base_clientes():
    # Solo leemos las columnas que necesitamos extraer (equivalente a tu matriz de BUSCARV)
    return pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        with st.spinner("Procesando archivo local y conectando con Drive..."):
            # 1. Extracción de Ruteo (Hoja FOX)
            df_fox = pd.read_excel(archivo_subido, sheet_name="FOX", usecols="A:C")
            
            col_ruta = df_fox.columns[0]
            col_cliente = df_fox.columns[1]
            col_cam = df_fox.columns[2]
            
            # Limpieza y filtrado
            df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
            df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
            df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
            
            # 2. Descarga de la base en la nube
            df_clientes = cargar_base_clientes()
            
            # 3. CRUCE DE DATOS (Sustituto automatizado de BUSCARV)
            # left_on y right_on indican qué columnas deben coincidir (Código de cliente)
            df_merged = pd.merge(
                df_ruteo, 
                df_clientes, 
                left_on=col_cliente, 
                right_on='CLIID', 
                how='left'
            )
            
            # 4. Estructurar la tabla final en el orden solicitado
            df_final = df_merged[[col_ruta, col_cliente, col_cam, 'CLIDOM', 'TELEFONO', 'X', 'Y']]
            
            # Renombramos para que el Excel final sea claro
            df_final.rename(columns={
                'CLIDOM': 'DIRECCION',
                'TELEFONO': 'NUMERO',
                'X': 'LONGITUD',
                'Y': 'LATITUD'
            }, inplace=True)
            
            # --- VISTA PREVIA EN PORTAL ---
            st.success("Cruce de datos completado con éxito.")
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # 5. MOTOR DE EXPORTACIÓN A EXCEL
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
            
            st.divider()
            
            # Botón para descargar el resultado
            st.download_button(
                label="📥 Descargar Excel Final (Columnas Separadas)",
                data=buffer.getvalue(),
                file_name="Base_Final_Rutas_Geo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    except Exception as e:
        st.error(f"Error en el procesamiento: Verifique que el archivo coincida con la estructura requerida. Detalle: {e}")
