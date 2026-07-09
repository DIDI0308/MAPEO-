import streamlit as st
import pandas as pd
import io
import folium
from folium import plugins
import streamlit.components.v1 as components
import zlib
import base64
import urllib.parse

# Configuración de interfaz ejecutiva
st.set_page_config(page_title="Módulo de Ruteo Estratégico", layout="wide")

# --- VISTA DE AYUDANTE (Activación automática si hay un link con datos) ---
if "ruta" in st.query_params and "data" in st.query_params:
    camion = st.query_params["ruta"]
    data_encoded = st.query_params["data"]
    
    try:
        # Decodificación instantánea de los datos empaquetados en el link
        decoded_bytes = base64.urlsafe_b64decode(data_encoded)
        decompressed = zlib.decompress(decoded_bytes).decode('utf-8')
        df_ruta = pd.read_json(io.StringIO(decompressed))
        
        st.subheader(f"Unidad Asignada: {camion}")
        st.caption(f"Total de PDVs a visitar: {len(df_ruta)}")
        
        # Renderizado del mapa en tiempo real
        centro_lat = df_ruta['la'].mean()
        centro_lon = df_ruta['lo'].mean()
        mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB positron")
        
        plugins.LocateControl(
            strings={"title": "Mostrar ubicación actual", "popup": "Posición actual"},
            drawCircle=True, drawMarker=True, position='topleft'
        ).add_to(mapa_rutas)
        
        for index, row in df_ruta.iterrows():
            info_popup = f"""
            <div style='font-family: Arial; font-size: 14px;'>
                <b>Cliente:</b> {row['c']}<br>
                <b>Ruta:</b> {row['r']}<br>
                <b>Teléfono:</b> {row['n']}<br>
                <hr style='margin: 5px 0; border: 0.5px solid #ccc;'>
                <b>Dirección:</b> {row['d']}
            </div>
            """
            folium.Marker(
                location=[row['la'], row['lo']],
                popup=folium.Popup(info_popup, max_width=250),
                icon=folium.Icon(color='darkblue', icon='info-sign')
            ).add_to(mapa_rutas)
        
        components.html(mapa_rutas.get_root().render(), height=650)
        
    except Exception as e:
        st.error("Enlace de ruteo inválido o corrupto.")
    
    # Detiene la ejecución para que el ayudante no vea las tablas de administración
    st.stop() 

# --- VISTA ADMINISTRATIVA (Tu código original) ---
st.title("Procesamiento de Ruteo y Generación de Mapas")

def preparar_link_drive(url):
    if "/edit" in url or "/view" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    return url

URL_CLIENTES_ORIGINAL = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/edit?usp=sharing&ouid=106121329840167757528&rtpof=true&sd=true"
URL_CLIENTES = preparar_link_drive(URL_CLIENTES_ORIGINAL)

# Botón de actualización de caché
col_head1, col_head2 = st.columns([3, 1])
with col_head2:
    if st.button("Actualizar Datos de Drive", use_container_width=True):
        st.cache_data.clear()

@st.cache_data
def cargar_base_clientes():
    return pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        with st.spinner("Procesando datos y estructurando mapa interactivo..."):
            # Procesamiento original estricto
            df_fox = pd.read_excel(archivo_subido, sheet_name="FOX", usecols="A:C")
            col_ruta = df_fox.columns[0]
            col_cliente = df_fox.columns[1]
            col_cam = df_fox.columns[2]
            
            df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
            df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
            df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
            
            df_resumen = df_ruteo.groupby([col_cam, col_ruta])[col_cliente].count().reset_index()
            df_resumen.rename(columns={col_cliente: "N° de PDVs a Visitar"}, inplace=True)
            
            df_clientes = cargar_base_clientes()
            df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
            
            df_final = df_merged[[col_ruta, col_cliente, col_cam, 'CLIDOM', 'TELEFONO', 'X', 'Y']].copy()
            df_final.rename(columns={'CLIDOM': 'DIRECCION', 'TELEFONO': 'NUMERO', 'X': 'LONGITUD', 'Y': 'LATITUD'}, inplace=True)

            df_final['LATITUD'] = pd.to_numeric(df_final['LATITUD'], errors='coerce')
            df_final['LONGITUD'] = pd.to_numeric(df_final['LONGITUD'], errors='coerce')
            df_mapa = df_final.dropna(subset=['LATITUD', 'LONGITUD'])

            # Tablas operativas
            col_izq, col_der = st.columns([1, 1.5])
            with col_izq:
                st.subheader("Resumen Operativo")
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
            with col_der:
                st.subheader("Base de Ruteo Consolidada")
                st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            st.divider()

            # --- GENERADOR DE ENLACES PARA AYUDANTES ---
            st.subheader("Generación de Enlaces de Ruteo")
            st.caption("Seleccione una unidad para generar su enlace operativo. La compresión permite procesar volúmenes altos de PDVs sin ralentizar el sistema.")
            
            if not df_mapa.empty:
                camiones_unicos = sorted(df_mapa[col_cam].unique())
                camion_seleccionado = st.selectbox("Seleccionar Unidad:", camiones_unicos)
                
                if camion_seleccionado:
                    df_cam = df_mapa[df_mapa[col_cam] == camion_seleccionado]
                    
                    # Estructura minimalista para comprimir el link al máximo
                    df_mini = pd.DataFrame({
                        'la': df_cam['LATITUD'],
                        'lo': df_cam['LONGITUD'],
                        'c': df_cam[col_cliente],
                        'r': df_cam[col_ruta],
                        'd': df_cam['DIRECCION'].fillna(""),
                        'n': df_cam['NUMERO'].fillna("")
                    })
                    
                    # Compresión Zlib y empaquetado Base64
                    json_str = df_mini.to_json(orient='records')
                    compressed = zlib.compress(json_str.encode('utf-8'))
                    encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
                    
                    # --- IMPORTANTE: Reemplace 'http://localhost:8501' con su enlace de Streamlit Cloud ---
                    base_url = "http://localhost:8501" 
                    link_final = f"{base_url}/?ruta={urllib.parse.quote(camion_seleccionado)}&data={encoded}"
                    
                    st.success(f"Enlace generado correctamente para la unidad {camion_seleccionado}")
                    st.code(link_final, language="http")
                    st.markdown(f"[Abrir vista de prueba del Ayudante]({link_final})")
            else:
                st.warning("No se detectaron coordenadas válidas para generar enlaces operativos.")

    except Exception as e:
        st.error(f"Se detectó una falla en el procesamiento. Verifique la integridad de los archivos. Detalle: {e}")
