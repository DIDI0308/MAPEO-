import streamlit as st
import pandas as pd
import io
import folium
from folium import plugins
import streamlit.components.v1 as components
import colorsys

# Configuración de interfaz ejecutiva
st.set_page_config(page_title="Ruteo y Georreferenciación", layout="wide", initial_sidebar_state="expanded")

# Convertimos tu enlace de Google Drive en un enlace de descarga directa
URL_DRIVE = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/export?format=xlsx"

# Función para generar colores infinitos (supera el límite de 20 rutas)
def generar_colores_infinitos(n):
    colores = []
    for i in range(n):
        # Usamos la proporción áurea para que colores adyacentes sean muy distintos
        h = (i * 0.618033988749895) % 1.0 
        r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.9)
        colores.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colores

@st.cache_data
def cargar_base_clientes():
    return pd.read_excel(URL_DRIVE, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

@st.cache_data(ttl=300) # Se actualiza cada 5 minutos
def cargar_rutas_hoy():
    return pd.read_excel(URL_DRIVE, sheet_name="Rutas_Hoy")

# --- MENÚ LATERAL ---
modo = st.sidebar.radio("Modo de Operación", ["🛡️ Centro de Control (Admin)", "🚚 Mapa de Ruta (Ayudantes)"])

# ==========================================
# MODO ADMINISTRADOR (OFICINA)
# ==========================================
if modo == "🛡️ Centro de Control (Admin)":
    st.title("Procesamiento de Ruteo (Centro de Control)")
    st.info("Sube el archivo FOX diario para generar la base consolidada.")
    
    archivo_subido = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"])

    if archivo_subido is not None:
        try:
            with st.spinner("Procesando datos y cruzando coordenadas..."):
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

                # --- PRESENTACIÓN TABLAS ---
                col1, col2 = st.columns([1, 1.5])
                with col1:
                    st.subheader("Resumen Operativo")
                    st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                with col2:
                    st.subheader("Base de Ruteo Consolidada")
                    st.dataframe(df_final, use_container_width=True, hide_index=True)
                
                st.divider()

                # --- EXPORTACIÓN ---
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                
                st.success("✅ Procesamiento Exitoso. Sigue los pasos para actualizar a los ayudantes:")
                st.markdown("""
                1. Descarga el Excel con el botón de abajo.
                2. Abre tu archivo de Google Sheets en Drive.
                3. Pega los datos en la pestaña llamada **`Rutas_Hoy`** (créala si no existe).
                4. ¡Listo! Los ayudantes ya pueden ver el mapa en su celular.
                """)
                
                st.download_button(
                    label="📥 Descargar Excel Final",
                    data=buffer.getvalue(),
                    file_name="Base_Final_Rutas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

        except Exception as e:
            st.error(f"Error en el procesamiento: {e}")

# ==========================================
# MODO AYUDANTE (CELULAR)
# ==========================================
elif modo == "🚚 Mapa de Ruta (Ayudantes)":
    # Diseño optimizado para pantallas pequeñas
    st.markdown("<h2 style='text-align: center;'>Mapa Operativo</h2>", unsafe_allow_html=True)
    
    try:
        with st.spinner("Cargando mapa en vivo..."):
            df_mapa = cargar_rutas_hoy()
            
            # Limpieza de coordenadas para evitar errores del mapa
            df_mapa['LATITUD'] = pd.to_numeric(df_mapa['LATITUD'], errors='coerce')
            df_mapa['LONGITUD'] = pd.to_numeric(df_mapa['LONGITUD'], errors='coerce')
            df_mapa = df_mapa.dropna(subset=['LATITUD', 'LONGITUD'])
            
            if not df_mapa.empty:
                # Nombres dinámicos de columnas basados en el formato de salida
                col_cam = "CAM" if "CAM" in df_mapa.columns else df_mapa.columns[2]
                col_cliente = "CLIENTE" if "CLIENTE" in df_mapa.columns else df_mapa.columns[1]
                col_ruta = "RUTA" if "RUTA" in df_mapa.columns else df_mapa.columns[0]
                
                centro_lat = df_mapa['LATITUD'].mean()
                centro_lon = df_mapa['LONGITUD'].mean()
                
                mapa_rutas = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB positron")
                
                # GPS del Celular
                plugins.LocateControl(
                    strings={"title": "Centrar en mi ubicación", "popup": "Estás aquí"},
                    drawCircle=True, drawMarker=True, position='topleft'
                ).add_to(mapa_rutas)
                
                # Asignación de colores infinitos (hexadecimal)
                camiones_unicos = df_mapa[col_cam].unique()
                paleta_colores = generar_colores_infinitos(len(camiones_unicos))
                diccionario_colores = dict(zip(camiones_unicos, paleta_colores))
                
                for index, row in df_mapa.iterrows():
                    color_hex = diccionario_colores.get(row[col_cam], '#333333')
                    
                    info_popup = f"""
                    <div style='font-family: Arial; font-size: 16px; width: 220px;'>
                        <b style='color: {color_hex}; font-size: 18px;'>CAMIÓN: {row[col_cam]}</b><br>
                        <b>Cliente:</b> {row[col_cliente]}<br>
                        <b>Ruta:</b> {row[col_ruta]}<br>
                        <hr style='margin: 5px 0;'>
                        <b>Dir:</b> {row['DIRECCION']}<br>
                        <a href="tel:{row['NUMERO']}">📞 Llamar: {row['NUMERO']}</a>
                    </div>
                    """
                    
                    # Usamos CircleMarker: Soporta infinitos colores, es rápido y no satura el celular
                    folium.CircleMarker(
                        location=[row['LATITUD'], row['LONGITUD']],
                        radius=8, # Tamaño del círculo
                        color='white', # Borde
                        weight=1.5,
                        fill_color=color_hex,
                        fill_opacity=0.9,
                        popup=folium.Popup(info_popup, max_width=250),
                        tooltip=f"Tocar para ver: {row[col_cliente]}"
                    ).add_to(mapa_rutas)
                
                html_mapa = mapa_rutas.get_root().render()
                components.html(html_mapa, height=600)
                
            else:
                st.warning("El administrador aún no ha cargado las rutas de hoy.")
    
    except Exception as e:
        st.error(f"Error cargando las rutas. Verifique que la hoja 'Rutas_Hoy' exista en el Drive. Detalle: {e}")
