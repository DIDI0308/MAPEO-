import streamlit as st
import pandas as pd
import io
import folium
from folium import plugins
import streamlit.components.v1 as components
import zlib
import base64
from datetime import datetime
import zipfile

# Configuración de interfaz ejecutiva
st.set_page_config(page_title="Módulo de Ruteo Estratégico", layout="wide")

# --- LECTURA SEGURA DEL LINK (Evita el "Error running app" en cualquier versión) ---
data_encoded = None
try:
    if hasattr(st, "query_params") and "data" in st.query_params:
        data_encoded = st.query_params["data"]
    elif hasattr(st, "experimental_get_query_params") and "data" in st.experimental_get_query_params():
        data_encoded = st.experimental_get_query_params()["data"][0]
except Exception:
    pass

# --- VISTA OPERATIVA (Para el Ayudante en Ruta) ---
if data_encoded:
    try:
        # Se agrega padding por si WhatsApp recorta el link
        data_encoded += "=" * ((4 - len(data_encoded) % 4) % 4)
        
        decoded_bytes = base64.urlsafe_b64decode(data_encoded)
        decompressed = zlib.decompress(decoded_bytes).decode('utf-8')
        df_ruta = pd.read_json(io.StringIO(decompressed))
        
        st.title("Mapa Operativo de Rutas")
        
        # Blindaje contra valores nulos al ordenar
        camiones_disponibles = sorted([str(x) for x in df_ruta['cam'].unique() if pd.notna(x)])
        camion_seleccionado = st.selectbox("Seleccione su unidad:", ["Visión Global"] + camiones_disponibles)
        
        if camion_seleccionado != "Visión Global":
            df_mostrar = df_ruta[df_ruta['cam'].astype(str) == camion_seleccionado]
        else:
            df_mostrar = df_ruta
            
        st.caption(f"Total de PDVs a visitar: {len(df_mostrar)}")
        
        if not df_mostrar.empty:
            centro_lat = df_mostrar['la'].mean()
            centro_lon = df_mostrar['lo'].mean()
            mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB positron")
            
            plugins.LocateControl(
                strings={"title": "Mostrar ubicación actual", "popup": "Posición actual"},
                drawCircle=True, drawMarker=True, position='topleft'
            ).add_to(mapa_rutas)
            
            for index, row in df_mostrar.iterrows():
                info_popup = f"""
                <div style='font-family: Arial; font-size: 14px;'>
                    <b>Unidad:</b> {row['cam']}<br>
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
        st.error("Enlace de ruteo inválido o datos corruptos.")
    
    st.stop() 

# --- VISTA ADMINISTRATIVA ---
st.title("Procesamiento de Ruteo y Generación de Mapas")

def preparar_link_drive(url):
    if "/edit" in url or "/view" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    return url

URL_CLIENTES_ORIGINAL = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/edit?usp=sharing&ouid=106121329840167757528&rtpof=true&sd=true"
URL_CLIENTES = preparar_link_drive(URL_CLIENTES_ORIGINAL)

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
        with st.spinner("Procesando matriz de datos..."):
            # PROCESAMIENTO INTACTO (No ralentizado)
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

            col_izq, col_der = st.columns([1, 1.5])
            with col_izq:
                st.subheader("Resumen Operativo")
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
            with col_der:
                st.subheader("Base de Ruteo Consolidada")
                st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            st.divider()

            # --- SECCIÓN DE EXPORTACIÓN Y LINKS ---
            col_export_1, col_export_2 = st.columns(2)

            with col_export_1:
                st.subheader("📱 Enlace para Ayudantes")
                st.caption("Envíe este enlace al personal. Podrán seleccionar su camión y ver su ubicación GPS.")
                
                if not df_mapa.empty:
                    df_mini = pd.DataFrame({
                        'la': df_mapa['LATITUD'], 'lo': df_mapa['LONGITUD'],
                        'c': df_mapa[col_cliente], 'r': df_mapa[col_ruta],
                        'cam': df_mapa[col_cam], 'd': df_mapa['DIRECCION'].fillna(""),
                        'n': df_mapa['NUMERO'].fillna("")
                    })
                    
                    json_str = df_mini.to_json(orient='records')
                    compressed = zlib.compress(json_str.encode('utf-8'))
                    encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
                    
                    url_servidor = st.text_input("URL de su portal:", value="https://su-portal.streamlit.app")
                    link_final = f"{url_servidor.strip('/')}/?data={encoded}"
                    
                    st.code(link_final, language="http")
                else:
                    st.warning("No hay coordenadas para generar el enlace.")

            with col_export_2:
                st.subheader("🗺️ Exportación a My Maps")
                
                fecha_hoy = datetime.now().strftime("%d/%m/%Y")
                nombre_mapa = f"MAPA({fecha_hoy})"
                
                st.info(
                    f"**Pasos para My Maps:**\n"
                    f"1. Descargue la base con el botón inferior.\n"
                    f"2. Abra **[Google My Maps](https://www.google.com/maps/d/)**.\n"
                    f"3. Copie y pegue este nombre: **`{nombre_mapa}`**\n"
                    f"4. Importe el Excel, elija `LATITUD` y `LONGITUD`, y agrupe por `CAM`."
                )
                
                # --- DIVISIÓN DE ARCHIVOS SI HAY > 20 RUTAS ---
                rutas_unicas = df_final[col_ruta].unique()
                
                if len(rutas_unicas) > 20:
                    st.warning(f"Se detectaron {len(rutas_unicas)} rutas. El sistema dividirá los archivos (máx. 20 rutas por archivo).")
                    
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for i in range(0, len(rutas_unicas), 20):
                            rutas_bloque = rutas_unicas[i:i+20]
                            df_bloque = df_final[df_final[col_ruta].isin(rutas_bloque)]
                            
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df_bloque.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                            
                            nombre_archivo = f"Base_Final_Rutas_Parte_{i//20 + 1}.xlsx"
                            zip_file.writestr(nombre_archivo, excel_buffer.getvalue())
                    
                    st.download_button(
                        label="📥 Descargar Archivos ZIP (Divididos)",
                        data=zip_buffer.getvalue(),
                        file_name="Bases_MyMaps_Divididas.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                else:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                    
                    st.download_button(
                        label="📥 Descargar Base para My Maps (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="Base_Final_Rutas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

    except Exception as e:
        st.error(f"Falla en el procesamiento de los datos. Detalle técnico: {e}")
