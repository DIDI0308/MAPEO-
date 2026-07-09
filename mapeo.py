import streamlit as st
import pandas as pd
import folium
from folium import plugins
import streamlit.components.v1 as components

# Configuración de interfaz ejecutiva y minimalista
st.set_page_config(page_title="Sistema de Mapeo de Rutas", layout="centered")
st.title("Distribución y Mapeo de Rutas")

# Función para convertir enlaces de Drive automáticamente
def preparar_link_drive(url):
    if "/edit" in url or "/view" in url:
        try:
            file_id = url.split("/d/")[1].split("/")[0]
            return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        except IndexError:
            return url
    return url

# 1. Enlaces de origen de datos
URL_CLIENTES_BASE = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/edit?usp=sharing&ouid=106121329840167757528&rtpof=true&sd=true"
URL_CLIENTES = preparar_link_drive(URL_CLIENTES_BASE)

# REEMPLACE EL SIGUIENTE TEXTO CON EL ENLACE DE DRIVE DE SU ARCHIVO DE RUTEO
URL_RUTEO_BASE = "PEGAR_ENLACE_DE_RUTEO_AQUI"
URL_RUTEO = preparar_link_drive(URL_RUTEO_BASE)

# Botón de actualización manual
col_header1, col_header2 = st.columns([3, 1])
with col_header2:
    if st.button("Actualizar Base de Drive", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Validación de seguridad antes de procesar
if "PEGAR_ENLACE" in URL_RUTEO_BASE:
    st.warning("Para iniciar la operación, por favor inserte el enlace de Google Drive de su archivo maestro de Ruteo en el código fuente.")
    st.stop()

@st.cache_data(ttl=600)
def procesar_bases():
    # Extracción de la hoja FOX (Ruteo) garantizando bajo consumo de memoria
    df_fox = pd.read_excel(URL_RUTEO, sheet_name="FOX", usecols="A:C")
    col_ruta = df_fox.columns[0]
    col_cliente = df_fox.columns[1]
    col_cam = df_fox.columns[2]
    
    # Estandarización y filtrado exacto
    df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
    df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
    
    # Eliminación de duplicados simultánea en las tres columnas
    df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
    
    # Cruce con la base de clientes
    df_clientes = pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])
    df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
    
    df_merged.rename(columns={'CLIDOM': 'DIRECCION', 'TELEFONO': 'NUMERO', 'X': 'LONGITUD', 'Y': 'LATITUD'}, inplace=True)
    df_merged['LATITUD'] = pd.to_numeric(df_merged['LATITUD'], errors='coerce')
    df_merged['LONGITUD'] = pd.to_numeric(df_merged['LONGITUD'], errors='coerce')
    
    return df_merged.dropna(subset=['LATITUD', 'LONGITUD']), col_cam, col_cliente, col_ruta

try:
    with st.spinner("Sincronizando y procesando bases de datos..."):
        df_mapa, col_cam, col_cliente, col_ruta = procesar_bases()
        
    # Interfaz operativa
    st.subheader("Panel de Control de Unidades")
    
    camiones_disponibles = sorted(df_mapa[col_cam].unique())
    camion_seleccionado = st.selectbox("Seleccione el código de la unidad:", ["Visión Global"] + camiones_disponibles)
    
    if camion_seleccionado != "Visión Global":
        df_filtrado = df_mapa[df_mapa[col_cam] == camion_seleccionado]
    else:
        df_filtrado = df_mapa

    if not df_filtrado.empty:
        st.metric("Puntos de Venta (PDVs) a visitar", len(df_filtrado))
        
        # Renderizado de Mapa Folium
        centro_lat = df_filtrado['LATITUD'].mean()
        centro_lon = df_filtrado['LONGITUD'].mean()
        mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB positron")
        
        # Control GPS para ubicación en tiempo real
        plugins.LocateControl(
            strings={"title": "Mostrar ubicación actual", "popup": "Posición actual"},
            drawCircle=True, drawMarker=True, position='topleft'
        ).add_to(mapa_rutas)
        
        for index, row in df_filtrado.iterrows():
            info_popup = f"""
            <div style='font-family: Arial; font-size: 14px;'>
                <b>Cliente:</b> {row[col_cliente]}<br>
                <b>Ruta:</b> {row[col_ruta]}<br>
                <b>Teléfono:</b> {row['NUMERO']}<br>
                <hr style='margin: 5px 0; border: 0.5px solid #ccc;'>
                <b>Dirección:</b> {row['DIRECCION']}
            </div>
            """
            folium.Marker(
                location=[row['LATITUD'], row['LONGITUD']],
                popup=folium.Popup(info_popup, max_width=250),
                icon=folium.Icon(color='darkblue', icon='info-sign')
            ).add_to(mapa_rutas)
        
        html_mapa = mapa_rutas.get_root().render()
        components.html(html_mapa, height=550)
    else:
        st.info("La unidad seleccionada no cuenta con rutas georreferenciadas asignadas.")

except Exception as e:
    st.error(f"Fallo de conexión o estructura. Verifique los enlaces y la integridad de las hojas de cálculo. Detalle: {e}")
