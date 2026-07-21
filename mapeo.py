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
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN E INICIALIZACIÓN DE ESTADOS ---
st.set_page_config(page_title="Sistema Logístico Estratégico", layout="wide")

# Variables de estado para los botones y navegación
if 'pagina_actual' not in st.session_state: st.session_state.pagina_actual = "Inicio"
if 'procesar_parcial' not in st.session_state: st.session_state.procesar_parcial = False
if 'procesar_completo' not in st.session_state: st.session_state.procesar_completo = False
if 'procesar_3308' not in st.session_state: st.session_state.procesar_3308 = False
if 'procesar_zip' not in st.session_state: st.session_state.procesar_zip = False
if 'procesar_fecha' not in st.session_state: st.session_state.procesar_fecha = False
if 'procesar_geos' not in st.session_state: st.session_state.procesar_geos = False
if 'procesar_pedidos' not in st.session_state: st.session_state.procesar_pedidos = False

def ir_a_pagina(pagina): st.session_state.pagina_actual = pagina
def reset_parcial(): st.session_state.procesar_parcial = False
def reset_completo(): st.session_state.procesar_completo = False
def reset_3308(): st.session_state.procesar_3308 = False
def reset_zip(): 
    st.session_state.procesar_zip = False
    st.session_state.procesar_fecha = False
def reset_geos(): st.session_state.procesar_geos = False
def reset_pedidos(): st.session_state.procesar_pedidos = False

# --- LECTURA SEGURA DEL LINK (VISTA AYUDANTES EN RUTA) ---
data_encoded = None
try:
    if hasattr(st, "query_params") and "data" in st.query_params:
        data_encoded = st.query_params["data"]
    elif hasattr(st, "experimental_get_query_params") and "data" in st.experimental_get_query_params():
        data_encoded = st.experimental_get_query_params()["data"][0]
except Exception:
    pass

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

# --- CONFIGURACIÓN DE CONEXIÓN CON DRIVE Y FUNCIONES CACHÉ ---
def preparar_link_drive(url):
    if "/edit" in url or "/view" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    return url

URL_CLIENTES_ORIGINAL = "https://docs.google.com/spreadsheets/d/1zIllojDvh23QUOP8afJbxD66I5Ly6tgY/edit?usp=sharing&ouid=106121329840167757528&rtpof=true&sd=true"
URL_CLIENTES = preparar_link_drive(URL_CLIENTES_ORIGINAL)

URL_CAMIONES_ORIGINAL = "https://docs.google.com/spreadsheets/d/18bsymByHBshLc34kNFhfmhKPVhua7yjl/edit?usp=sharing&ouid=106121329840167757528&rtpof=true&sd=true"
URL_CAMIONES = preparar_link_drive(URL_CAMIONES_ORIGINAL)

@st.cache_data
def cargar_base_clientes():
    return pd.read_excel(URL_CLIENTES, sheet_name="Clientes", usecols=["CLIID", "CLIDOM", "TELEFONO", "X", "Y"])

@st.cache_data
def cargar_estructura_camiones():
    try:
        return pd.read_excel(URL_CLIENTES, sheet_name="estructura_camiones", usecols="A:G", header=None)
    except Exception as e:
        st.error("No se pudo cargar la hoja 'estructura_camiones' del mapa base clientes.")
        return pd.DataFrame()

@st.cache_data
def cargar_datos_camiones_info():
    try:
        return pd.read_excel(URL_CAMIONES, sheet_name="Hoja1", usecols="A:H")
    except Exception as e:
        st.error(f"No se pudo cargar la base de datos de camiones: {e}")
        return pd.DataFrame()

def generar_imagen_tabla(df, titulo):
    fig, ax = plt.subplots(figsize=(14, len(df) * 0.4 + 1.5))
    ax.axis('tight')
    ax.axis('off')
    
    df_str = df.astype(str)
    tabla = ax.table(cellText=df_str.values, colLabels=df_str.columns, cellLoc='center', loc='center')
    
    tabla.auto_set_column_width(col=list(range(len(df.columns))))
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    tabla.scale(1, 1.8) 
    
    for i in range(len(df.columns)):
        tabla[(0, i)].set_facecolor("#2c3e50")
        tabla[(0, i)].set_text_props(color="white", weight="bold")
    
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

def modulo_ruteo(df_fox, sufijo_key, df_adelantos=None):
    col_ruta = df_fox.columns[0]
    col_cliente = df_fox.columns[1]
    col_cam = df_fox.columns[2]
    
    # 🔴 INTEGRACIÓN DE ADELANTOS
    if df_adelantos is not None and not df_adelantos.empty:
        df_ad_clean = df_adelantos.dropna(how='all')
        if not df_ad_clean.empty:
            df_ad_renamed = pd.DataFrame({
                col_ruta: df_ad_clean.iloc[:, 0],    # RUTA
                col_cliente: df_ad_clean.iloc[:, 1], # CLIENTE
                col_cam: df_ad_clean.iloc[:, 2]      # CAMION
            })
            df_fox = pd.concat([df_fox, df_ad_renamed], ignore_index=True)
    
    # 🔴 LIMPIEZA RIGUROSA PARA QUE MY MAPS AGRUPE PERFECTAMENTE LAS RUTAS
    df_fox[col_ruta] = df_fox[col_ruta].astype(str).str.strip().str.upper()
    df_fox[col_cliente] = df_fox[col_cliente].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
    
    st.session_state.df_cruce_fox = df_fox[[col_cliente, col_cam]].drop_duplicates(subset=[col_cliente])
    st.session_state.col_cliente_fox = col_cliente
    st.session_state.col_cam_fox = col_cam
    
    df_filtrado = df_fox[~df_fox[col_cam].isin(["NO", "#N/D"])]
    df_ruteo = df_filtrado.drop_duplicates(subset=[col_ruta, col_cliente, col_cam])
    
    df_resumen = df_ruteo.groupby([col_cam, col_ruta])[col_cliente].count().reset_index()
    df_resumen.rename(columns={col_cliente: "N° de PDVs a Visitar"}, inplace=True)
    
    df_clientes = cargar_base_clientes().copy() 
    df_clientes['CLIID'] = df_clientes['CLIID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    
    df_merged = pd.merge(df_ruteo, df_clientes, left_on=col_cliente, right_on='CLIID', how='left')
    
    df_final = df_merged[[col_ruta, col_cliente, col_cam, 'CLIDOM', 'TELEFONO', 'X', 'Y']].copy()
    
    df_final.rename(columns={'CLIDOM': 'DIRECCION', 'TELEFONO': 'NUMERO', 'X': 'Longitude', 'Y': 'Latitude'}, inplace=True)

    df_final['Latitude'] = pd.to_numeric(df_final['Latitude'], errors='coerce')
    df_final['Longitude'] = pd.to_numeric(df_final['Longitude'], errors='coerce')
    df_mapa = df_final.dropna(subset=['Latitude', 'Longitude'])

    df_final['Latitude'] = df_final['Latitude'].apply(lambda x: f"{x}" if pd.notnull(x) else "")
    df_final['Longitude'] = df_final['Longitude'].apply(lambda x: f"{x}" if pd.notnull(x) else "")

    col_izq, col_der = st.columns([1, 1.5])
    with col_izq:
        st.subheader("Resumen Operativo")
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
    with col_der:
        st.subheader("Base de Ruteo Consolidada")
        st.dataframe(df_final, use_container_width=True, hide_index=True)
    
    st.divider()

    col_export_1, col_export_2 = st.columns(2)
    with col_export_1:
        st.subheader("📱 Enlace para Ayudantes")
        st.caption("Envíe este enlace al personal. Podrán seleccionar su camión y ver su ubicación GPS.")
        if not df_mapa.empty:
            df_mini = pd.DataFrame({'la': df_mapa['Latitude'], 'lo': df_mapa['Longitude'], 'c': df_mapa[col_cliente], 'r': df_mapa[col_ruta], 'cam': df_mapa[col_cam], 'd': df_mapa['DIRECCION'].fillna(""), 'n': df_mapa['NUMERO'].fillna("")})
            json_str = df_mini.to_json(orient='records')
            compressed = zlib.compress(json_str.encode('utf-8'))
            encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
            url_servidor = st.text_input("URL de su portal:", value="https://su-portal.streamlit.app", key=f"url_{sufijo_key}")
            link_final = f"{url_servidor.strip('/')}/?data={encoded}"
            st.code(link_final, language="http")
        else:
            st.warning("No hay coordenadas para generar el enlace.")

    with col_export_2:
        st.subheader("🗺️ Exportación a My Maps")
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        nombre_mapa = f"MAPA({fecha_hoy})"
        st.info(f"**Pasos para My Maps:**\n1. Descargue los archivos Excel inferiores *(My Maps reconocerá automáticamente las coordenadas)*.\n2. Abra **Google My Maps**.\n3. Copie y pegue este nombre: **`{nombre_mapa}`**\n4. Importe el Excel y agrupe por `CAM`.")
        
        rutas_unicas = df_final[col_ruta].unique()
        if len(rutas_unicas) > 20:
            st.warning(f"Se detectaron {len(rutas_unicas)} rutas. Descargue los archivos divididos (máx. 20 rutas c/u).")
            for i in range(0, len(rutas_unicas), 20):
                rutas_bloque = rutas_unicas[i:i+20]
                df_bloque = df_final[df_final[col_ruta].isin(rutas_bloque)]
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer: df_bloque.to_excel(writer, index=False, sheet_name='Base_Mapeada')
                nombre_archivo = f"Base_Final_Rutas_Parte_{i//20 + 1}.xlsx"
                st.download_button(label=f"📥 Descargar {nombre_archivo}", data=excel_buffer.getvalue(), file_name=nombre_archivo, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key=f"dl_{nombre_archivo}_{sufijo_key}")
        else:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_final.to_excel(writer, index=False, sheet_name='Base_Mapeada')
            st.download_button(label="📥 Descargar Base para My Maps (.xlsx)", data=buffer.getvalue(), file_name="Base_Final_Rutas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key=f"dl_base_{sufijo_key}")

def modulo_vh_fijas(archivo_subido, sufijo_key):
    st.divider()
    st.header("🕒 Ventanas Horarias Fijas")
    try:
        if isinstance(archivo_subido, list):
            lista_vh = []
            for arch in archivo_subido:
                try: arch.seek(0); lista_vh.append(pd.read_excel(arch, sheet_name="VH FIJAS"))
                except ValueError: pass
            if len(lista_vh) > 0: df_vh = pd.concat(lista_vh, ignore_index=True)
            else: return st.warning("No se encontró la hoja 'VH FIJAS'.")
        else:
            archivo_subido.seek(0)
            df_vh = pd.read_excel(archivo_subido, sheet_name="VH FIJAS")
        
        col_f = df_vh.columns[5]
        col_cam_vh = next((c for c in df_vh.columns if str(c).strip().upper() in ['CAM', 'CAMION', 'CAMIÓN']), df_vh.columns[6])
        col_cli_vh = None

        if 'df_cruce_fox' in st.session_state:
            df_cruce = st.session_state.df_cruce_fox.copy()
            col_fox_cli = st.session_state.col_cliente_fox
            col_fox_cam = st.session_state.col_cam_fox
            for col in df_vh.columns:
                if str(col).strip().upper() == str(col_fox_cli).strip().upper() or 'CLIENTE' in str(col).upper() or 'COD' in str(col).upper():
                    col_cli_vh = col; break
            if not col_cli_vh: col_cli_vh = df_vh.columns[1]
                
            df_vh['__temp_cli__'] = df_vh[col_cli_vh].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_cruce['__temp_cli__'] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            mapa_camiones = df_cruce.set_index('__temp_cli__')[col_fox_cam].to_dict()
            df_vh[col_cam_vh] = df_vh['__temp_cli__'].map(mapa_camiones).fillna(df_vh[col_cam_vh])
            df_vh = df_vh.drop(columns=['__temp_cli__'])
        
        if not col_cli_vh: col_cli_vh = df_vh.columns[1]
            
        df_vh = df_vh.dropna(subset=[col_cam_vh])
        errores_excel = ["NO", "#N/D", "#N/A", "#VALOR!", "#VALUE!", "#REF!", "#DIV/0!", "#NOMBRE?", "#NUM!", "#NULL!", "NAN", "NONE", "NULL"]
        df_vh_valido = df_vh[~df_vh[col_cam_vh].astype(str).str.strip().str.upper().isin(errores_excel)]
        df_vh_valido = df_vh_valido[~df_vh_valido[col_cam_vh].astype(str).str.startswith("#")]
        df_vh_valido = df_vh_valido.sort_values(by=col_cam_vh, ascending=True).drop_duplicates(subset=[col_cli_vh])
        
        df_criticas = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "SI"]
        df_considerar = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "NO"]
        
        col_vh1, col_vh2 = st.columns(2)
        with col_vh1:
            st.write("**Críticas (SI)**"); st.dataframe(df_criticas, use_container_width=True)
            if not df_criticas.empty:
                st.download_button(label="🖼️ Descargar Críticas", data=generar_imagen_tabla(df_criticas, "VH Críticas").getvalue(), file_name="VH_Criticas.png", mime="image/png", use_container_width=True, key=f"img_crit_{sufijo_key}")
        with col_vh2:
            st.write("**VH a Considerar (NO)**"); st.dataframe(df_considerar, use_container_width=True)
            if not df_considerar.empty:
                st.download_button(label="🖼️ Descargar VH Considerar", data=generar_imagen_tabla(df_considerar, "VH Considerar").getvalue(), file_name="VH_Considerar.png", mime="image/png", use_container_width=True, key=f"img_cons_{sufijo_key}")
    except ValueError: st.warning("No se encontró la hoja 'VH FIJAS'.")
    except Exception as e: st.error(f"Error procesando Ventanas Horarias Fijas: {e}")


# ==========================================
# 🏠 SISTEMA DE NAVEGACIÓN (CARÁTULA)
# ==========================================

if st.session_state.pagina_actual == "Inicio":
    st.title("🚛 Bienvenido al Sistema Logístico Integrado")
    st.markdown("---")
    st.markdown("### Seleccione el módulo de trabajo:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("🗺️ **Módulo de Mapeo y Base de Datos**")
        st.write("Generación de rutas para GPS, MyMaps, tratamiento de archivos 3308, validación de Ventanas Horarias, Geos y Pedidos Eventuales.")
        st.button("Ingresar a Mapeo", on_click=ir_a_pagina, args=("Mapeo",), use_container_width=True)
        
    with col2:
        st.success("🛣️ **Módulo de Ruteo Estratégico**")
        st.write("Planificación de camiones según velocidad, restricciones de zonas y disponibilidad de flota operativa.")
        st.button("Ingresar a Ruteo", on_click=ir_a_pagina, args=("Ruteo",), use_container_width=True)


# ==========================================
# 🛣️ MÓDULO DE RUTEO (NUEVO)
# ==========================================

elif st.session_state.pagina_actual == "Ruteo":
    st.button("⬅️ Volver al Menú Principal", on_click=ir_a_pagina, args=("Inicio",), use_container_width=True)
    
    st.title("🛣️ Módulo de Ruteo")
    
    ciudad_ruteo = st.radio("📍 Seleccione la Ciudad Operativa:", ["EA", "LP"], horizontal=True)
    
    st.write("Consulta y validación de las características de cada unidad operativa.")
    
    df_camiones = cargar_datos_camiones_info()
    
    if not df_camiones.empty:
        lista_camiones = df_camiones.iloc[:, 0].dropna().astype(str).tolist()
        lista_camiones = sorted(list(set(lista_camiones)))
        
        camion_sel = st.selectbox("🔍 Seleccione la unidad (Código de Camión):", [""] + lista_camiones)
        
        if camion_sel:
            st.markdown("---")
            info = df_camiones[df_camiones.iloc[:, 0].astype(str) == camion_sel].iloc[0]
            
            val_ol = str(info.iloc[6]).strip()
            val_flota = str(info.iloc[7]).strip()
            prioridad = "🔥 ALTA (Asignar primero)" if "fija" in val_flota.lower() else "⏳ BAJA (Asignar después)"
            
            if ciudad_ruteo == "EA":
                val_lento = str(info.iloc[1]).replace('.0', '').strip()
                val_vuelta = str(info.iloc[2]).replace('.0', '').strip()
                val_ceja = str(info.iloc[3]).replace('.0', '').strip()
                val_pirhua = str(info.iloc[4]).replace('.0', '').strip()
                val_jpii = str(info.iloc[5]).replace('.0', '').strip()
                
                text_lento = "⚠️ Sí (Evitar rutas dispersas o largas)" if val_lento == "1" else "✅ No (Ruta normal)"
                text_vuelta = "⚡ Sí (Vehículo rápido)" if val_vuelta == "1" else "Normal"
                
                if val_ceja == "1": text_ceja = "✅ Sí va a la Ceja"
                elif val_ceja == "2": text_ceja = "🚫 ¡NI LOCAS mandarlo a la Ceja!"
                else: text_ceja = "❌ No va normalmente"
                
                text_pirhua = "✅ Sí" if val_pirhua == "1" else "❌ No"
                text_jpii = "✅ Sí" if val_jpii == "1" else "❌ No"
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info("👤 **Datos Base**")
                    st.write(f"**Operador Logístico:** {val_ol}")
                    st.write(f"**Tipo de Flota:** {val_flota}")
                    st.write(f"**Prioridad de Asignación:** {prioridad}")
                    
                with col2:
                    st.warning("⏱️ **Capacidad de Ruta**")
                    st.write(f"**Es Lento:** {text_lento}")
                    st.write(f"**Puede hacer 2 vueltas:** {text_vuelta}")
                    
                with col3:
                    st.success("📍 **Restricciones de Zona**")
                    st.write(f"**La Ceja:** {text_ceja}")
                    st.write(f"**Partida Pirhua:** {text_pirhua}")
                    st.write(f"**Juan Pablo II:** {text_jpii}")
            else: # SI ES LP
                col1, col2 = st.columns(2)
                with col1:
                    st.info("👤 **Datos Base**")
                    st.write(f"**Operador Logístico:** {val_ol}")
                    st.write(f"**Tipo de Flota:** {val_flota}")
                    st.write(f"**Prioridad de Asignación:** {prioridad}")
                with col2:
                    st.write("*(Los detalles específicos de zona y velocidad se aplican a EA)*")
    else:
        st.warning("Cargando la base de datos de camiones desde Drive...")

    # 🔴 TABLA DE DISPONIBILIDAD DE FLOTA
    st.divider()
    st.subheader("📋 Disponibilidad de Flota")
    st.caption("Pegue aquí la disponibilidad del día.")
    
    columnas_disp = ["Flota", "OL", "N° Camión", "Matrícula", "Tipo Camión", "Capacidad en Caja", 
                     "Capacidad en Peso", "Zona de Entrega", "Status", "Tipo Ruta", "Prioridad", 
                     "Observaciones", "Canal", "Codigo de la transportadora", "Transportadora", "Empresa"]
    
    df_disp_template = pd.DataFrame(columns=columnas_disp)
    
    df_disp = st.data_editor(
        df_disp_template,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="disponibilidad_editor"
    )

# ==========================================
# 🗺️ MÓDULO DE MAPEO (TODO LO ANTERIOR)
# ==========================================

elif st.session_state.pagina_actual == "Mapeo":
    st.button("⬅️ Volver al Menú Principal", on_click=ir_a_pagina, args=("Inicio",), use_container_width=True)
    
    st.title("🗺️ Módulo de Mapeo y Base de Datos")

    col_head1, col_head2 = st.columns([3, 1])
    with col_head2:
        if st.button("🔄 Actualizar Datos de Drive", use_container_width=True):
            st.cache_data.clear()

    # --- ESTRUCTURACIÓN POR PESTAÑAS (MAPEO) ---
    tab_parcial, tab_completo, tab_3308 = st.tabs(["Ruteo Parcial", "Ruteo Completo", "RUTEO 3308"])

    with tab_parcial:
        st.header("Ruteo Parcial")
        archivo_parcial = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"], key="up_parcial", on_change=reset_parcial)
        
        st.subheader("➕ Adelantos Manuales (Opcional)")
        df_adelantos_parcial = st.data_editor(pd.DataFrame(columns=["RUTA", "CLIENTE", "CAMION"]), num_rows="dynamic", use_container_width=True, key="ad_parcial")
        
        if archivo_parcial is not None:
            if st.button("▶️ Procesar Parcial", type="primary", key="btn_parcial"):
                st.session_state.procesar_parcial = True
            if st.session_state.procesar_parcial:
                try:
                    with st.spinner("Procesando matriz de datos..."):
                        archivo_parcial.seek(0)
                        df_fox = pd.read_excel(archivo_parcial, sheet_name="FOX", usecols="A:C")
                        modulo_ruteo(df_fox, "parcial", df_adelantos_parcial)
                        modulo_vh_fijas(archivo_parcial, "parcial")
                except Exception as e:
                    st.error(f"Falla en el procesamiento: {e}")

    with tab_completo:
        st.header("Ruteo Completo")
        st.caption("Cargue 2 o más archivos simultáneamente.")
        archivos_completos = st.file_uploader("Cargue los archivos de ruteo (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="up_completo", on_change=reset_completo)
        
        st.subheader("➕ Adelantos Manuales (Opcional)")
        df_adelantos_completo = st.data_editor(pd.DataFrame(columns=["RUTA", "CLIENTE", "CAMION"]), num_rows="dynamic", use_container_width=True, key="ad_completo")
        
        if archivos_completos and len(archivos_completos) > 0:
            if st.button("▶️ Procesar Completo", type="primary", key="btn_completo"):
                st.session_state.procesar_completo = True
            if st.session_state.procesar_completo:
                try:
                    with st.spinner("Concatenando y procesando..."):
                        lista_dfs = []
                        for arch in archivos_completos:
                            arch.seek(0)
                            df_temp = pd.read_excel(arch, sheet_name="FOX", usecols="A:C")
                            df_temp.columns = ["RUTA", "CLIENTE", "CAM"]
                            lista_dfs.append(df_temp)
                        df_fox_completo = pd.concat(lista_dfs, ignore_index=True)
                        modulo_ruteo(df_fox_completo, "completo", df_adelantos_completo)
                        modulo_vh_fijas(archivos_completos, "completo")
                except Exception as e:
                    st.error(f"Falla en el procesamiento: {e}")

    with tab_3308:
        st.header("RUTEO 3308")
        archivo_3308 = st.file_uploader("Cargue el archivo maestro de ruteo 3308 (.csv o .xlsx)", type=["csv", "xlsx"], key="up_3308", on_change=reset_3308)
        
        selector_ciudad = st.radio("📍 Seleccione la Región para el filtro de camiones:", ["EA", "LP"], key="ciudad_3308", horizontal=True)
        aplicar_tratamiento = st.checkbox("⚙️ Archivo Crudo (Eliminar 5 primeras filas y forzar separación por comas)", value=True, key="chk_tratamiento_3308")
        st.caption("Desmarque esta casilla si la base YA está limpia.")
        
        st.subheader("➕ Adelantos Manuales (Opcional)")
        df_adelantos_3308 = st.data_editor(pd.DataFrame(columns=["RUTA", "CLIENTE", "CAMION"]), num_rows="dynamic", use_container_width=True, key="ad_3308")
        
        if archivo_3308 is not None:
            if st.button("▶️ Procesar 3308", type="primary", key="btn_3308"):
                st.session_state.procesar_3308 = True
            if st.session_state.procesar_3308:
                try:
                    with st.spinner("Procesando matriz de datos 3308..."):
                        archivo_3308.seek(0)
                        df_est = cargar_estructura_camiones()
                        camiones_validos = set()
                        
                        if not df_est.empty:
                            for c in df_est.columns: df_est[c] = df_est[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
                            cols_validas = [0, 1, 2, 5] if selector_ciudad == "EA" else [3, 4, 6]
                            for idx in cols_validas:
                                if idx < len(df_est.columns): camiones_validos.update(df_est.iloc[:, idx].tolist())
                            camiones_validos = {c for c in camiones_validos if c not in ["NAN", "NONE", "NULL", ""]}
                        
                        def extraer_columnas(df_raw):
                            if len(df_raw.columns) >= 20: return pd.DataFrame({"CLIENTE": df_raw.iloc[:, 1], "CAM": df_raw.iloc[:, 19]})
                            elif len(df_raw.columns) >= 3: return pd.DataFrame({"CLIENTE": df_raw.iloc[:, 1], "CAM": df_raw.iloc[:, 2]})
                            elif len(df_raw.columns) == 2: return pd.DataFrame({"CLIENTE": df_raw.iloc[:, 0], "CAM": df_raw.iloc[:, 1]})
                            return None

                        df_fox_temp = None
                        if archivo_3308.name.lower().endswith('.csv'):
                            if aplicar_tratamiento:
                                try: df_3308 = pd.read_csv(archivo_3308, skiprows=5, sep=',', header=None, encoding='utf-8-sig', on_bad_lines='skip', engine='python')
                                except UnicodeDecodeError: archivo_3308.seek(0); df_3308 = pd.read_csv(archivo_3308, skiprows=5, sep=',', header=None, encoding='latin-1', on_bad_lines='skip', engine='python')
                                df_fox_temp = extraer_columnas(df_3308)
                                if df_fox_temp is None:
                                    archivo_3308.seek(0)
                                    df_raw = pd.read_csv(archivo_3308, skiprows=5, sep='\n', header=None, on_bad_lines='skip')
                                    df_split = df_raw[0].astype(str).str.split(',', expand=True)
                                    df_fox_temp = extraer_columnas(df_split)
                            else:
                                try: df_3308 = pd.read_csv(archivo_3308, sep=None, engine='python', encoding='utf-8-sig', on_bad_lines='skip')
                                except UnicodeDecodeError: archivo_3308.seek(0); df_3308 = pd.read_csv(archivo_3308, sep=None, engine='python', encoding='latin-1', on_bad_lines='skip')
                                df_fox_temp = extraer_columnas(df_3308)
                        else:
                            df_temp_excel = pd.read_excel(archivo_3308, sheet_name="FOX", header=None)
                            if len(df_temp_excel.columns) >= 3: df_fox_temp = pd.DataFrame({"CLIENTE": df_temp_excel.iloc[1:, 1], "CAM": df_temp_excel.iloc[1:, 2]})
                        
                        if df_fox_temp is not None:
                            df_fox_temp['CAM'] = df_fox_temp['CAM'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
                            if not df_est.empty:
                                def es_valido(cam): return (cam in camiones_validos) or (cam.split('.')[0] in camiones_validos)
                                df_fox_temp = df_fox_temp[df_fox_temp['CAM'].apply(es_valido)]
                            
                            df_fox_temp = df_fox_temp.drop_duplicates(subset=["CLIENTE", "CAM"])
                            df_fox_temp['RUTA'] = df_fox_temp['CAM']
                            
                            df_fox = df_fox_temp[["RUTA", "CLIENTE", "CAM"]].copy()
                            modulo_ruteo(df_fox, "3308", df_adelantos_3308)
                            
                            if archivo_3308.name.lower().endswith('.xlsx'): modulo_vh_fijas(archivo_3308, "3308")
                        else:
                            st.error("Error: El archivo no tiene la estructura esperada.")
                except Exception as e:
                    st.error(f"Falla en el procesamiento: {e}")

    # --- VENTANAS HORARIAS EVENTUALES ---
    st.divider()
    st.header("📅 Ventanas Horarias Eventuales")
    archivo_zip = st.file_uploader("Cargue el archivo .zip de VH Eventuales", type=["zip"], on_change=reset_zip, key="up_zip")

    if archivo_zip is not None:
        if st.button("▶️ Procesar Archivo ZIP", type="primary", key="btn_zip"): st.session_state.procesar_zip = True
        if st.session_state.procesar_zip:
            try:
                with zipfile.ZipFile(archivo_zip, 'r') as z:
                    archivo_datos = next((f for f in z.namelist() if f.endswith(('.csv', '.xlsx'))), None)
                    if archivo_datos:
                        with z.open(archivo_datos) as f:
                            df_vh_ev = pd.read_csv(f, sep=None, engine='python', encoding='utf-8-sig') if archivo_datos.endswith('.csv') else pd.read_excel(f)
                        col_fecha, col_cliente_ev = df_vh_ev.columns[0], df_vh_ev.columns[1]
                        
                        if 'df_cruce_fox' in st.session_state:
                            df_cruce = st.session_state.df_cruce_fox.copy()
                            col_fox_cli, col_fox_cam = st.session_state.col_cliente_fox, st.session_state.col_cam_fox
                            df_vh_ev[col_cliente_ev] = df_vh_ev[col_cliente_ev].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            df_cruce[col_fox_cli] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            df_vh_ev = pd.merge(df_vh_ev, df_cruce, left_on=col_cliente_ev, right_on=col_fox_cli, how='left')
                            if col_cliente_ev != col_fox_cli: df_vh_ev = df_vh_ev.drop(columns=[col_fox_cli])
                            df_vh_ev.rename(columns={col_fox_cam: 'CAMIÓN ASIGNADO'}, inplace=True)
                            df_vh_ev['CAMIÓN ASIGNADO'] = df_vh_ev['CAMIÓN ASIGNADO'].fillna("")
                            df_vh_ev = df_vh_ev[~df_vh_ev['CAMIÓN ASIGNADO'].astype(str).str.strip().str.upper().isin(['NO', '#N/D'])].sort_values(by='CAMIÓN ASIGNADO', ascending=True)
                        else: st.warning("⚠️ Procese primero alguna de las pestañas de Ruteo arriba.")

                        df_vh_ev = df_vh_ev.dropna(subset=[col_fecha])
                        df_vh_ev['Fecha_Limpia'] = pd.to_datetime(df_vh_ev[col_fecha], errors='coerce').dt.date
                        
                        fecha_calendario = st.date_input("Seleccione la fecha a consultar:", key="cal_ev")
                        if st.button("▶️ Procesar Fecha Seleccionada", key="btn_fecha"):
                            st.session_state.procesar_fecha, st.session_state.fecha_activa = True, fecha_calendario
                        if st.session_state.procesar_fecha:
                            fecha_elegida = st.session_state.fecha_activa
                            df_filtrado_ev = df_vh_ev[df_vh_ev['Fecha_Limpia'] == fecha_elegida].drop(columns=['Fecha_Limpia']).drop_duplicates(subset=[col_cliente_ev])
                            buscador_cliente = st.text_input("🔍 Buscar por Código:", key="search_cli_ev")
                            if buscador_cliente: df_filtrado_ev = df_filtrado_ev[df_filtrado_ev[col_cliente_ev].astype(str).str.contains(buscador_cliente.strip(), case=False, na=False)]
                            st.success(f"Mostrando {len(df_filtrado_ev)} registros para el {fecha_elegida.strftime('%d/%m/%Y')}")
                            st.dataframe(df_filtrado_ev, use_container_width=True)
                            if not df_filtrado_ev.empty:
                                df_imagen_ev = df_filtrado_ev.copy()
                                if len(df_imagen_ev.columns) >= 6: df_imagen_ev = df_imagen_ev.drop(columns=df_imagen_ev.columns[3:6])
                                st.download_button("🖼️ Descargar Reporte", generar_imagen_tabla(df_imagen_ev, f"VH Eventuales - {fecha_elegida}").getvalue(), f"VH_Eventuales_{fecha_elegida}.png", "image/png", use_container_width=True, key="dl_img_ev")
                    else: st.warning("El ZIP no contiene un archivo .csv o .xlsx.")
            except Exception as e: st.error(f"Error al procesar el archivo: {e}")

    # --- GEOS EVENTUALES ---
    st.divider()
    st.header("📍 Geos Eventuales")
    df_geos_input = st.data_editor(pd.DataFrame(columns=["FECHA", "COD CLIENTE", "Y", "X", "Motivo", "CD", "Bultos", "SDV", "JDV", "VALIDACIÓN", "¿Para mañana?"]), num_rows="dynamic", use_container_width=True, hide_index=True, key="geos_editor", on_change=reset_geos)
    if st.button("▶️ Procesar Geos", type="primary", key="btn_geos"): st.session_state.procesar_geos = True
    if st.session_state.procesar_geos:
        if not df_geos_input.empty:
            if 'df_cruce_fox' in st.session_state:
                df_cruce, col_fox_cli, col_fox_cam = st.session_state.df_cruce_fox.copy(), st.session_state.col_cliente_fox, st.session_state.col_cam_fox
                df_geos_input["COD CLIENTE"] = df_geos_input["COD CLIENTE"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_cruce[col_fox_cli] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_merged_geos = pd.merge(df_geos_input, df_cruce, left_on="COD CLIENTE", right_on=col_fox_cli, how="left")
                mensaje_wp = "*Geo Alternativas*\n\n"
                for _, row in df_merged_geos.iterrows(): mensaje_wp += f"• {row['COD CLIENTE']} - https://www.google.com/maps?q={row['Y']},{row['X']} - {row[col_fox_cam] if pd.notna(row[col_fox_cam]) else 'SIN ASIGNAR'}\n"
                st.success("Cruce exitoso. Copie el mensaje:")
                st.code(mensaje_wp, language="text")
            else: st.warning("⚠️ Procese primero una pestaña de Ruteo arriba.")
        else: st.info("Pegue datos antes de procesar.")

    # --- PEDIDOS EVENTUALES ---
    st.divider()
    st.header("📦 Pedidos Eventuales")
    df_pedidos_input = st.data_editor(pd.DataFrame(columns=["COD CLIENTE", "CLIENTE", "LATITUD yLONGITUD x", "N° DE PEDIDO", "COD PROD", "DESCRIPCION", "CANTIDAD", "Peso HB", "SIS", "SOLICITANTE", "TELÉFONO SOLIC", "OBS FACTURA", "PERSONA QUE RECIBE", "NIT", "TELÉFONO PERSONA QUE RECIBE", "DIRECCIÓN ESCRITA", "CAMIÓN", "PLANILLA", "EVENTO", "MONTO", "OBSERVACIONES", "VENTANA HORARIA"]), num_rows="dynamic", use_container_width=True, hide_index=True, key="pedidos_editor", on_change=reset_pedidos)
    if st.button("▶️ Procesar Pedidos", type="primary", key="btn_pedidos"): st.session_state.procesar_pedidos = True
    if st.session_state.procesar_pedidos:
        if not df_pedidos_input.empty:
            mensaje_wp_pedidos = ""
            for _, row in df_pedidos_input.iterrows():
                cc, ts, tr, pr, obs, vh = ["" if pd.isna(row.get(k)) else str(row.get(k)).replace('.0', '').strip() for k in ["COD CLIENTE", "TELÉFONO SOLIC", "TELÉFONO PERSONA QUE RECIBE", "PERSONA QUE RECIBE", "OBSERVACIONES", "VENTANA HORARIA"]]
                mensaje_wp_pedidos += f"EVENTUAL\nCOD: {cc} @+591 {ts}\nContacto: {tr} - {pr}\n{obs}\nVH: {vh}\n\n"
            st.success("Pedidos procesados:")
            st.code(mensaje_wp_pedidos, language="text")
        else: st.info("Pegue datos antes de procesar.")
