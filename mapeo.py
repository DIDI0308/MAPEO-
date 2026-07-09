import streamlit as st
import pandas as pd
import folium
from folium import plugins
import streamlit.components.v1 as components

st.set_page_config(page_title="Portal de Ruteo", layout="centered")
st.title("Distribución y Mapeo de Rutas")

# 1. Enlaces de origen de datos
URL_CLIENTES = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"
# Reemplace este enlace con el link de descarga directa de su Excel de Ruteo en Google Drive
URL_RUTEO = "PEGAR_AQUI_LINK_DE_RUTEO" 

@st.cache_data(ttl=600) # Se actualiza cada 10 minutos
def cargar_bases():
    # Carga de base de ruteo (Hoja FOX)
    df_fox = pd.read_excel(URL_RUTEO, sheet_name="FOX", usecols="A:C")
    col_ruta, col_cliente, col_cam = df_fox.columns[0], df_fox.columns[1], df_fox.columns[2]
    
    df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
    df_ruteo = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])].drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
    
    # Carga de base de clientes
    df_clientes = pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])
    
    # Cruce de datos
    df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
    df_merged.rename(columns={'CLIDOM': 'DIRECCION', 'TELEFONO': 'NUMERO', 'X': 'LONGITUD', 'Y': 'LATITUD'}, inplace=True)
    
    # Limpieza de coordenadas
    df_merged['LATITUD'] = pd.to_numeric(df_merged['LATITUD'], errors='coerce')
    df_merged['LONGITUD'] = pd.to_numeric(df_merged['LONGITUD'], errors='coerce')
    
    return df_merged.dropna(subset=['LATITUD', 'LONGITUD']), col_cam, col_cliente, col_ruta

try:
    with st.spinner("Sincronizando datos..."):
        df_mapa, col_cam, col_cliente, col_ruta = cargar_bases()
        
    st.divider()
    
    # 2. Interfaz para el Ayudante
    camiones_disponibles = sorted(df_mapa[col_cam].unique())
    camion_seleccionado = st.selectbox("Seleccione el código del camión:", ["Todos"] + camiones_disponibles)
    
    if camion_seleccionado != "Todos":
        df_filtrado = df_mapa[df_mapa[col_cam] == camion_seleccionado]
    else:
        df_filtrado = df_mapa

    if not df_filtrado.empty:
        st.metric("Total de PDVs a visitar", len(df_filtrado))
        
        centro_lat = df_filtrado['LATITUD'].mean()
        centro_lon = df_filtrado['LONGITUD'].mean()
        
        mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB positron")
        
        # Herramienta de GPS en vivo
        plugins.LocateControl(
            strings={"title": "Mostrar mi ubicación actual", "popup": "Ubicación actual"},
            drawCircle=True,
            drawMarker=True,
            position='topleft'
        ).add_to(mapa_rutas)
        
        for index, row in df_filtrado.iterrows():
            info_popup = f"""
            <div style='font-family: Arial; font-size: 14px;'>
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
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(mapa_rutas)
        
        html_mapa = mapa_rutas.get_root().render()
        components.html(html_mapa, height=600)
    else:
        st.info("No hay datos georreferenciados para el camión seleccionado.")

except Exception as e:
    st.error("Error de conexión. Asegúrese de que ambos enlaces de Google Drive sean públicos o tengan el formato correcto.")
