import streamlit as st
import pandas as pd
import folium
from folium import plugins
import streamlit.components.v1 as components

st.set_page_config(page_title="Rutas Automotores", layout="centered")
st.title("📍 Mapeo de Rutas para Distribución")

# --- 1. ENLACES DE LA NUBE ---
URL_CLIENTES = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"
# AQUI DEBES PEGAR EL LINK DE TU EXCEL DE RUTEO DE DRIVE (Asegúrate de que termine en /export?format=xlsx)
URL_RUTEO = "PON_AQUI_TU_LINK_DE_RUTEO_DE_DRIVE" 

@st.cache_data(ttl=600) # Se actualiza cada 10 minutos
def procesar_bases():
    # --- PROCESAMIENTO INTACTO ---
    # 1. Leemos exactamente las columnas A, B y C de la hoja FOX
    df_fox = pd.read_excel(URL_RUTEO, sheet_name="FOX", usecols="A:C")
    col_ruta = df_fox.columns[0]
    col_cliente = df_fox.columns[1]
    col_cam = df_fox.columns[2]
    
    # 2. Estandarizamos y filtramos "NO" y "#N/D"
    df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
    df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
    
    # 3. Eliminamos duplicados de las 3 columnas simultáneamente
    df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
    
    # --- CRUCE DE DATOS ---
    df_clientes = pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])
    df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
    
    df_merged.rename(columns={'CLIDOM': 'DIRECCION', 'TELEFONO': 'NUMERO', 'X': 'LONGITUD', 'Y': 'LATITUD'}, inplace=True)
    df_merged['LATITUD'] = pd.to_numeric(df_merged['LATITUD'], errors='coerce')
    df_merged['LONGITUD'] = pd.to_numeric(df_merged['LONGITUD'], errors='coerce')
    
    return df_merged.dropna(subset=['LATITUD', 'LONGITUD']), col_cam, col_cliente, col_ruta

try:
    with st.spinner("Sincronizando datos desde Google Drive..."):
        df_mapa, col_cam, col_cliente, col_ruta = procesar_bases()
        
    # --- VISTA PARA EL AYUDANTE (CELULAR) ---
    st.info("Selecciona tu camión para ver la ruta asignada.")
    
    camiones_disponibles = sorted(df_mapa[col_cam].unique())
    camion_seleccionado = st.selectbox("🚜 Código de Camión:", ["Todos"] + camiones_disponibles)
    
    if camion_seleccionado != "Todos":
        df_filtrado = df_mapa[df_mapa[col_cam] == camion_seleccionado]
    else:
        df_filtrado = df_mapa

    if not df_filtrado.empty:
        st.success(f"Total de clientes a visitar: {len(df_filtrado)}")
        
        # Generar Mapa
        centro_lat = df_filtrado['LATITUD'].mean()
        centro_lon = df_filtrado['LONGITUD'].mean()
        mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB positron")
        
        # Botón de GPS para el celular
        plugins.LocateControl(
            strings={"title": "Mostrar mi ubicación actual", "popup": "Estás aquí"},
            drawCircle=True, drawMarker=True, position='topleft'
        ).add_to(mapa_rutas)
        
        # Agregar los pines
        for index, row in df_filtrado.iterrows():
            info_popup = f"""
            <div style='font-family: Arial; font-size: 14px;'>
                <b>Cliente:</b> {row[col_cliente]}<br>
                <b>Ruta:</b> {row[col_ruta]}<br>
                <b>Tel:</b> {row['NUMERO']}<br>
                <hr style='margin: 5px 0;'>
                <b>Dir:</b> {row['DIRECCION']}
            </div>
            """
            folium.Marker(
                location=[row['LATITUD'], row['LONGITUD']],
                popup=folium.Popup(info_popup, max_width=250),
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(mapa_rutas)
        
        html_mapa = mapa_rutas.get_root().render()
        components.html(html_mapa, height=500)
    else:
        st.warning("No hay clientes asignados a este camión.")

except Exception as e:
    st.error("Error conectando con Drive. Asegúrate de colocar el link de ruteo correctamente en el código.")
