import streamlit as st
import pandas as pd
import io
import folium
from folium import plugins
import streamlit.components.v1 as components
import zlib
import base64
from datetime import datetime
import matplotlib.pyplot as plt

# Configuración de interfaz ejecutiva
st.set_page_config(page_title="Módulo de Ruteo Estratégico", layout="wide")

# --- LECTURA SEGURA DEL LINK ---
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
        data_encoded += "=" * ((4 - len(data_encoded) % 4) % 4)
        
        decoded_bytes = base64.urlsafe_b64decode(data_encoded)
        decompressed = zlib.decompress(decoded_bytes).decode('utf-8')
        df_ruta = pd.read_json(io.StringIO(decompressed))
        
        st.title("Mapa Operativo de Rutas")
        
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

# Función para generar imágenes formales de las tablas
def generar_imagen_tabla(df, titulo):
    # Ajuste dinámico de dimensiones según el tamaño de la tabla
    ancho = max(12, len(df.columns) * 1.8)
    alto = max(3, len(df) * 0.4 + 1.5)
    
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.axis('tight')
    ax.axis('off')
    
    # Renderizado de la tabla
    df_str = df.astype(str)
    tabla = ax.table(cellText=df_str.values, colLabels=df_str.columns, cellLoc='center', loc='center')
    
    # Estilo formal y ajuste de texto
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    tabla.scale(1, 1.5)
    
    # Color de cabecera
    for i in range(len(df.columns)):
        tabla[(0, i)].set_facecolor("#2c3e50")
        tabla[(0, i)].set_text_props(color="white", weight="bold")
    
    # Filas alternas
    for i in range(1, len(df_str) + 1):
        for j in range(len(df.columns)):
            if i % 2 == 0:
                tabla[(i, j)].set_facecolor("#ecf0f1")
                
    plt.title(titulo, fontsize=14, weight='bold', pad=20)
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf

archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        with st.spinner("Procesando matriz de datos..."):
            # --- PROCESAMIENTO ORIGINAL INTACTO ---
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

            # --- SECCIÓN DE EXPORTACIÓN Y LINKS (Modificada: Sin ZIP, múltiples botones) ---
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
                    f"1. Descargue los archivos Excel inferiores.\n"
                    f"2. Abra **Google My Maps**.\n"
                    f"3. Copie y pegue este nombre: **`{nombre_mapa}`**\n"
                    f"4. Importe el Excel y agrupe por `CAM`."
                )
                
                # --- Lógica de división sin usar ZIP (Múltiples botones de descarga) ---
                rutas_unicas = df_final[col_ruta].unique()
                
                if len(rutas_unicas) > 20:
                    st.warning(f"Se detectaron {len(rutas_unicas)} rutas. Descargue los archivos divididos (máx. 20 rutas c/u).")
                    
                    for i in range(0, len(rutas_unicas), 20):
                        rutas_bloque = rutas_unicas[i:i+20]
                        df_bloque = df_final[df_final[col_ruta].isin(rutas_bloque)]
                        
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df_bloque.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                        
                        nombre_archivo = f"Base_Final_Rutas_Parte_{i//20 + 1}.xlsx"
                        
                        st.download_button(
                            label=f"📥 Descargar {nombre_archivo}",
                            data=excel_buffer.getvalue(),
                            file_name=nombre_archivo,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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

            st.divider()

            # --- NUEVA SECCIÓN: VENTANAS HORARIAS ---
            st.header("🕒 Procesamiento de Ventanas Horarias")
            
            try:
                # Leer hoja VH FIJAS
                df_vh = pd.read_excel(archivo_subido, sheet_name="VH FIJAS")
                
                # Identificadores de columnas (F es índice 5, G es índice 6)
                col_f = df_vh.columns[5]
                col_g = df_vh.columns[6]
                
                # 1. Filtrar columna G: Que tenga valor y no sea un error de Excel
                df_vh = df_vh.dropna(subset=[col_g])
                errores_excel = ["#N/D", "#N/A", "#VALOR!", "#VALUE!", "#REF!", "#DIV/0!", "#NOMBRE?", "#NUM!", "#NULL!"]
                df_vh_valido = df_vh[~df_vh[col_g].astype(str).str.strip().str.upper().isin(errores_excel)]
                # Por seguridad extra, omitir si empieza con '#'
                df_vh_valido = df_vh_valido[~df_vh_valido[col_g].astype(str).str.startswith("#")]
                
                # 2. Filtrar para tabla Críticas (Col F = SI)
                df_criticas = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "SI"]
                
                # 3. Filtrar para tabla VH a Considerar (Col F = NO)
                df_considerar = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "NO"]
                
                # Mostrar en el portal
                st.subheader("Tablas Procesadas")
                col_vh1, col_vh2 = st.columns(2)
                
                with col_vh1:
                    st.write("**Críticas (SI)**")
                    st.dataframe(df_criticas, use_container_width=True)
                    if not df_criticas.empty:
                        img_criticas = generar_imagen_tabla(df_criticas, "Ventanas Horarias Críticas")
                        st.download_button(
                            label="🖼️ Descargar Críticas como Imagen",
                            data=img_criticas.getvalue(),
                            file_name="VH_Criticas.png",
                            mime="image/png",
                            use_container_width=True
                        )
                
                with col_vh2:
                    st.write("**VH a Considerar (NO)**")
                    st.dataframe(df_considerar, use_container_width=True)
                    if not df_considerar.empty:
                        img_considerar = generar_imagen_tabla(df_considerar, "Ventanas Horarias a Considerar")
                        st.download_button(
                            label="🖼️ Descargar VH a Considerar como Imagen",
                            data=img_considerar.getvalue(),
                            file_name="VH_Considerar.png",
                            mime="image/png",
                            use_container_width=True
                        )
                        
            except ValueError:
                st.warning("No se encontró la hoja 'VH FIJAS' en el archivo cargado. Asegúrese de que el archivo contiene esta pestaña para usar este módulo.")
            except Exception as e:
                st.error(f"Ocurrió un error al procesar las Ventanas Horarias: {e}")

    except Exception as e:
        st.error(f"Falla en el procesamiento de los datos de Ruteo. Detalle técnico: {e}")
