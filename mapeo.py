import streamlit as st
import pandas as pd
import io
import folium
from folium import plugins
import streamlit.components.v1 as components

# Configuración de interfaz ejecutiva
st.set_page_config(page_title="Módulo de Ruteo Estratégico", layout="wide")
st.title("Procesamiento de Ruteo y Generación de Mapas")

URL_CLIENTES = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"

@st.cache_data
def cargar_base_clientes():
    return pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        with st.spinner("Procesando datos y estructurando mapa interactivo..."):
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

            # Preparación para el mapa
            df_final['LATITUD'] = pd.to_numeric(df_final['LATITUD'], errors='coerce')
            df_final['LONGITUD'] = pd.to_numeric(df_final['LONGITUD'], errors='coerce')
            df_mapa = df_final.dropna(subset=['LATITUD', 'LONGITUD'])

            # --- PRESENTACIÓN EN PORTAL ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Registros Iniciales", len(df_fox))
            col2.metric("Base Limpia", len(df_ruteo))
            col3.metric("Puntos Georreferenciados", len(df_mapa))
            
            st.divider()
            
            col_izq, col_der = st.columns([1, 1.5])
            with col_izq:
                st.subheader("Resumen Operativo")
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
            with col_der:
                st.subheader("Base de Ruteo Consolidada")
                st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            st.divider()

            # --- GENERACIÓN DEL MAPA FOLIUM (OPTIMIZADO PARA CELULAR) ---
            st.subheader("Mapa Interactivo para Ayudantes")
            
            if not df_mapa.empty:
                centro_lat = df_mapa['LATITUD'].mean()
                centro_lon = df_mapa['LONGITUD'].mean()
                
                # Mapa base
                mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB positron")
                
                # 🔴 NUEVO: Botón de GPS para el celular del ayudante
                plugins.LocateControl(
                    strings={"title": "Mostrar mi ubicación actual", "popup": "Estás aquí"},
                    drawCircle=True,
                    drawMarker=True,
                    position='topleft'
                ).add_to(mapa_rutas)
                
                colores_disponibles = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'darkblue', 'pink']
                camiones_unicos = df_mapa[col_cam].unique()
                diccionario_colores = {cam: colores_disponibles[i % len(colores_disponibles)] for i, cam in enumerate(camiones_unicos)}
                
                for index, row in df_mapa.iterrows():
                    # Tarjeta optimizada para pantallas pequeñas
                    info_popup = f"""
                    <div style='font-family: Arial; font-size: 15px; width: 200px;'>
                        <b style='color: {diccionario_colores.get(row[col_cam], 'gray')};'>CAMIÓN: {row[col_cam]}</b><br>
                        <b>Cliente:</b> {row[col_cliente]}<br>
                        <b>Ruta:</b> {row[col_ruta]}<br>
                        <hr style='margin: 5px 0;'>
                        <b>Dir:</b> {row['DIRECCION']}<br>
                        <b>Tel:</b> {row['NUMERO']}
                    </div>
                    """
                    
                    folium.Marker(
                        location=[row['LATITUD'], row['LONGITUD']],
                        popup=folium.Popup(info_popup, max_width=250),
                        tooltip=f"Cliente: {row[col_cliente]}",
                        icon=folium.Icon(color=diccionario_colores.get(row[col_cam], 'gray'), icon='truck', prefix='fa')
                    ).add_to(mapa_rutas)
                
                html_mapa = mapa_rutas.get_root().render()
                components.html(html_mapa, height=500)
                
                st.divider()
                
                # --- BOTONES DE DESCARGA ---
                st.subheader("Archivos de Operación")
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    st.download_button(
                        label="📱 Descargar Mapa para Celulares (.html)",
                        data=html_mapa,
                        file_name="Mapa_Rutas_Ayudantes.html",
                        mime="text/html",
                        type="primary",
                        use_container_width=True
                    )
                    st.caption("Envía este archivo por WhatsApp a los choferes/ayudantes. Podrán ver su ubicación GPS en vivo y los clientes.")
                
                with col_btn2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                    
                    st.download_button(
                        label="📥 Descargar Base Consolidada (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="Base_Final_Rutas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

            else:
                st.warning("No se encontraron coordenadas válidas para generar el mapa.")

    except Exception as e:
        st.error(f"Error en el procesamiento. Verifique la estructura del archivo. Detalle técnico: {e}")
