import streamlit as st
import pandas as pd
import io
import plotly.express as px

st.set_page_config(page_title="Módulo de Ruteo y Georreferenciación", layout="wide")
st.title("Procesamiento de Ruteo y Georreferenciación")

URL_CLIENTES = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"

@st.cache_data
def cargar_base_clientes():
    return pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        with st.spinner("Procesando datos y generando visualizaciones..."):
            # 1. Extracción y Limpieza
            df_fox = pd.read_excel(archivo_subido, sheet_name="FOX", usecols="A:C")
            
            col_ruta = df_fox.columns[0]
            col_cliente = df_fox.columns[1]
            col_cam = df_fox.columns[2]
            
            df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
            df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
            df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
            
            # 2. Generación de Tabla Resumen
            df_resumen = df_ruteo.groupby([col_cam, col_ruta])[col_cliente].count().reset_index()
            df_resumen.rename(columns={col_cliente: "N° de PDVs a Visitar"}, inplace=True)
            
            # 3. Cruce con Base de Coordenadas
            df_clientes = cargar_base_clientes()
            df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
            
            df_final = df_merged[[col_ruta, col_cliente, col_cam, 'CLIDOM', 'TELEFONO', 'X', 'Y']]
            df_final.rename(columns={
                'CLIDOM': 'DIRECCION',
                'TELEFONO': 'NUMERO',
                'X': 'LONGITUD',
                'Y': 'LATITUD'
            }, inplace=True)

            # 4. Preparación de datos para el mapa
            df_final['LATITUD'] = pd.to_numeric(df_final['LATITUD'], errors='coerce')
            df_final['LONGITUD'] = pd.to_numeric(df_final['LONGITUD'], errors='coerce')
            df_mapa = df_final.dropna(subset=['LATITUD', 'LONGITUD'])

            # --- PRESENTACIÓN EN PORTAL ---
            
            # Panel de Métricas
            col1, col2, col3 = st.columns(3)
            col1.metric("Registros Iniciales", len(df_fox))
            col2.metric("Base Limpia (Final)", len(df_ruteo))
            col3.metric("Puntos Georreferenciados", len(df_mapa))
            
            st.divider()

            # Mapa Integrado (Reemplazo de My Maps)
            st.subheader("Mapa de Distribución por Camión")
            if not df_mapa.empty:
                fig = px.scatter_mapbox(
                    df_mapa, 
                    lat="LATITUD", 
                    lon="LONGITUD", 
                    color=col_cam, # Agrupación solicitada en la imagen
                    hover_name=col_cliente,
                    hover_data=[col_ruta, "DIRECCION", "NUMERO"],
                    zoom=11,
                    height=600,
                    mapbox_style="carto-positron"
                )
                fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No se encontraron coordenadas válidas para graficar.")

            st.divider()
            
            # Tablas Restauradas
            col_izq, col_der = st.columns([1, 1.5])
            
            with col_izq:
                st.subheader("Resumen Operativo")
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                
            with col_der:
                st.subheader("Base de Ruteo Consolidada")
                st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Exportación a Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
            
            st.download_button(
                label="Descargar Archivo Maestro (.xlsx)",
                data=buffer.getvalue(),
                file_name="Base_Final_Rutas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    except Exception as e:
        st.error(f"Error en el procesamiento. Detalle técnico: {e}")
