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
st.set_page_config(page_title="Módulo de Ruteo Estratégico", layout="wide")

# Variables de estado para los botones
if 'procesar_parcial' not in st.session_state: st.session_state.procesar_parcial = False
if 'procesar_completo' not in st.session_state: st.session_state.procesar_completo = False
if 'procesar_3308' not in st.session_state: st.session_state.procesar_3308 = False
if 'procesar_zip' not in st.session_state: st.session_state.procesar_zip = False
if 'procesar_fecha' not in st.session_state: st.session_state.procesar_fecha = False
if 'procesar_geos' not in st.session_state: st.session_state.procesar_geos = False
if 'procesar_pedidos' not in st.session_state: st.session_state.procesar_pedidos = False

def reset_parcial(): st.session_state.procesar_parcial = False
def reset_completo(): st.session_state.procesar_completo = False
def reset_3308(): st.session_state.procesar_3308 = False
def reset_zip(): 
    st.session_state.procesar_zip = False
    st.session_state.procesar_fecha = False
def reset_geos(): st.session_state.procesar_geos = False
def reset_pedidos(): st.session_state.procesar_pedidos = False

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

# --- FUNCIONES NÚCLEO DE PROCESAMIENTO ---
def modulo_ruteo(df_fox, sufijo_key):
    col_ruta = df_fox.columns[0]
    col_cliente = df_fox.columns[1]
    col_cam = df_fox.columns[2]
    
    df_fox[col_cam] = df_fox[col_cam].astype(str).str.strip().str.upper()
    
    # Memoria Súper para los eventuales y geos
    st.session_state.df_cruce_fox = df_fox[[col_cliente, col_cam]].drop_duplicates(subset=[col_cliente])
    st.session_state.col_cliente_fox = col_cliente
    st.session_state.col_cam_fox = col_cam
    
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
            
            url_servidor = st.text_input("URL de su portal:", value="https://su-portal.streamlit.app", key=f"url_{sufijo_key}")
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
                    use_container_width=True,
                    key=f"dl_{nombre_archivo}_{sufijo_key}"
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
                use_container_width=True,
                key=f"dl_base_{sufijo_key}"
            )

def modulo_vh_fijas(archivo_subido, sufijo_key):
    st.divider()
    st.header("🕒 Ventanas Horarias Fijas")
    try:
        if isinstance(archivo_subido, list):
            lista_vh = []
            for arch in archivo_subido:
                try:
                    arch.seek(0)
                    df_temp = pd.read_excel(arch, sheet_name="VH FIJAS")
                    lista_vh.append(df_temp)
                except ValueError:
                    pass
            if len(lista_vh) > 0:
                df_vh = pd.concat(lista_vh, ignore_index=True)
            else:
                st.warning("No se encontró la hoja 'VH FIJAS' en los archivos cargados.")
                return
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
                    col_cli_vh = col
                    break
            if not col_cli_vh:
                col_cli_vh = df_vh.columns[1]
                
            df_vh['__temp_cli__'] = df_vh[col_cli_vh].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_cruce['__temp_cli__'] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            mapa_camiones = df_cruce.set_index('__temp_cli__')[col_fox_cam].to_dict()
            
            df_vh[col_cam_vh] = df_vh['__temp_cli__'].map(mapa_camiones).fillna(df_vh[col_cam_vh])
            df_vh = df_vh.drop(columns=['__temp_cli__'])
        
        if not col_cli_vh:
            col_cli_vh = df_vh.columns[1]
            
        df_vh = df_vh.dropna(subset=[col_cam_vh])
        errores_excel = ["NO", "#N/D", "#N/A", "#VALOR!", "#VALUE!", "#REF!", "#DIV/0!", "#NOMBRE?", "#NUM!", "#NULL!", "NAN", "NONE", "NULL"]
        df_vh_valido = df_vh[~df_vh[col_cam_vh].astype(str).str.strip().str.upper().isin(errores_excel)]
        df_vh_valido = df_vh_valido[~df_vh_valido[col_cam_vh].astype(str).str.startswith("#")]
        
        df_vh_valido = df_vh_valido.sort_values(by=col_cam_vh, ascending=True)
        df_vh_valido = df_vh_valido.drop_duplicates(subset=[col_cli_vh])
        
        df_criticas = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "SI"]
        df_considerar = df_vh_valido[df_vh_valido[col_f].astype(str).str.strip().str.upper() == "NO"]
        
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
                    use_container_width=True,
                    key=f"img_crit_{sufijo_key}"
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
                    use_container_width=True,
                    key=f"img_cons_{sufijo_key}"
                )
                
    except ValueError:
        st.warning("No se encontró la hoja 'VH FIJAS' en el archivo cargado.")
    except Exception as e:
        st.error(f"Error procesando Ventanas Horarias Fijas: {e}")

# --- ESTRUCTURACIÓN POR PESTAÑAS ---
tab_parcial, tab_completo, tab_3308 = st.tabs(["Ruteo Parcial", "Ruteo Completo", "RUTEO 3308"])

with tab_parcial:
    st.header("Ruteo Parcial")
    archivo_parcial = st.file_uploader("Cargue el archivo maestro de ruteo (.xlsx)", type=["xlsx"], key="up_parcial", on_change=reset_parcial)
    
    if archivo_parcial is not None:
        if st.button("▶️ Procesar Parcial", type="primary", key="btn_parcial"):
            st.session_state.procesar_parcial = True
            
        if st.session_state.procesar_parcial:
            try:
                with st.spinner("Procesando matriz de datos..."):
                    archivo_parcial.seek(0)
                    df_fox = pd.read_excel(archivo_parcial, sheet_name="FOX", usecols="A:C")
                    modulo_ruteo(df_fox, "parcial")
                    modulo_vh_fijas(archivo_parcial, "parcial")
            except Exception as e:
                st.error(f"Falla en el procesamiento: {e}")

with tab_completo:
    st.header("Ruteo Completo")
    st.caption("Cargue 2 o más archivos simultáneamente. El sistema unificará las hojas FOX para el mapeo.")
    archivos_completos = st.file_uploader("Cargue los archivos de ruteo (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="up_completo", on_change=reset_completo)
    
    if archivos_completos and len(archivos_completos) > 0:
        if st.button("▶️ Procesar Completo", type="primary", key="btn_completo"):
            st.session_state.procesar_completo = True
            
        if st.session_state.procesar_completo:
            try:
                with st.spinner("Concatenando y procesando archivos múltiples..."):
                    lista_dfs = []
                    for arch in archivos_completos:
                        arch.seek(0)
                        df_temp = pd.read_excel(arch, sheet_name="FOX", usecols="A:C")
                        df_temp.columns = ["RUTA", "CLIENTE", "CAM"]
                        lista_dfs.append(df_temp)
                    
                    df_fox_completo = pd.concat(lista_dfs, ignore_index=True)
                    modulo_ruteo(df_fox_completo, "completo")
                    modulo_vh_fijas(archivos_completos, "completo")
            except Exception as e:
                st.error(f"Falla en el procesamiento: {e}")

with tab_3308:
    st.header("RUTEO 3308")
    
    archivo_3308 = st.file_uploader("Cargue el archivo maestro de ruteo 3308 (.csv o .xlsx)", type=["csv", "xlsx"], key="up_3308", on_change=reset_3308)
    
    # 🔴 BOTÓN DE TRATAMIENTO ESTÁ AQUÍ
    aplicar_tratamiento = st.checkbox("⚙️ Archivo Crudo (Eliminar 5 primeras filas y forzar separación por comas)", value=True, key="chk_tratamiento_3308")
    st.caption("Desmarque esta casilla si la base YA está limpia (columnas separadas y sin las 5 filas iniciales).")
    
    if archivo_3308 is not None:
        if st.button("▶️ Procesar 3308", type="primary", key="btn_3308"):
            st.session_state.procesar_3308 = True
            
        if st.session_state.procesar_3308:
            try:
                with st.spinner("Procesando matriz de datos 3308..."):
                    archivo_3308.seek(0)
                    
                    if archivo_3308.name.lower().endswith('.csv'):
                        if aplicar_tratamiento:
                            # TRATAMIENTO: Salta 5 filas, separa por comas y toma Col B y T
                            try:
                                df_3308 = pd.read_csv(archivo_3308, skiprows=5, sep=',', header=None, encoding='utf-8-sig', on_bad_lines='skip', engine='python')
                            except UnicodeDecodeError:
                                archivo_3308.seek(0)
                                df_3308 = pd.read_csv(archivo_3308, skiprows=5, sep=',', header=None, encoding='latin-1', on_bad_lines='skip', engine='python')
                            
                            if len(df_3308.columns) > 19:
                                df_fox = df_3308.iloc[:, [0, 1, 19]].copy()
                                df_fox.columns = ["RUTA", "CLIENTE", "CAM"]
                                df_fox = df_fox.drop_duplicates(subset=["CLIENTE", "CAM"])
                                modulo_ruteo(df_fox, "3308")
                            else:
                                # Rescate si todo quedó en la columna 0
                                archivo_3308.seek(0)
                                df_raw = pd.read_csv(archivo_3308, skiprows=5, sep='\n', header=None, on_bad_lines='skip')
                                df_split = df_raw[0].astype(str).str.split(',', expand=True)
                                if len(df_split.columns) > 19:
                                    df_fox = df_split.iloc[:, [0, 1, 19]].copy()
                                    df_fox.columns = ["RUTA", "CLIENTE", "CAM"]
                                    df_fox = df_fox.drop_duplicates(subset=["CLIENTE", "CAM"])
                                    modulo_ruteo(df_fox, "3308")
                                else:
                                    st.error("Error: El archivo crudo no tiene la estructura esperada (mínimo 20 columnas).")
                        else:
                            # 🔴 BASE YA TRATADA: No salta filas y lee las columnas directamente
                            try:
                                df_3308 = pd.read_csv(archivo_3308, sep=None, engine='python', encoding='utf-8-sig', on_bad_lines='skip')
                            except UnicodeDecodeError:
                                archivo_3308.seek(0)
                                df_3308 = pd.read_csv(archivo_3308, sep=None, engine='python', encoding='latin-1', on_bad_lines='skip')
                            
                            # Validar si tiene 20 columnas toma la B y T. Si tiene 3, toma la A, B y C.
                            if len(df_3308.columns) >= 20:
                                df_fox = df_3308.iloc[:, [0, 1, 19]].copy()
                            elif len(df_3308.columns) >= 3:
                                df_fox = df_3308.iloc[:, [0, 1, 2]].copy()
                            else:
                                st.error("Error: El archivo tratado no tiene suficientes columnas.")
                                st.stop()
                                
                            df_fox.columns = ["RUTA", "CLIENTE", "CAM"]
                            df_fox = df_fox.drop_duplicates(subset=["CLIENTE", "CAM"])
                            modulo_ruteo(df_fox, "3308")
                    
                    else:
                        # Si es un Excel clásico
                        df_fox = pd.read_excel(archivo_3308, sheet_name="FOX", usecols="A:C")
                        modulo_ruteo(df_fox, "3308")
                        modulo_vh_fijas(archivo_3308, "3308")
                        
            except Exception as e:
                st.error(f"Falla en el procesamiento: {e}")

# --- MÓDULO: VENTANAS HORARIAS EVENTUALES ---
st.divider()
st.header("📅 Procesamiento de Ventanas Horarias Eventuales")

archivo_zip = st.file_uploader("Cargue el archivo .zip de VH Eventuales", type=["zip"], on_change=reset_zip, key="up_zip")

if archivo_zip is not None:
    if st.button("▶️ Procesar Archivo ZIP", type="primary", key="btn_zip"):
        st.session_state.procesar_zip = True
        
    if st.session_state.procesar_zip:
        try:
            with zipfile.ZipFile(archivo_zip, 'r') as z:
                nombres_archivos = z.namelist()
                archivo_datos = next((f for f in nombres_archivos if f.endswith('.csv') or f.endswith('.xlsx')), None)
                
                if archivo_datos:
                    with z.open(archivo_datos) as f:
                        if archivo_datos.endswith('.csv'):
                            df_vh_ev = pd.read_csv(f, sep=None, engine='python', encoding='utf-8-sig') 
                        else:
                            df_vh_ev = pd.read_excel(f)
                    
                    col_fecha = df_vh_ev.columns[0]
                    col_cliente_ev = df_vh_ev.columns[1]
                    
                    if 'df_cruce_fox' in st.session_state:
                        df_cruce = st.session_state.df_cruce_fox.copy()
                        col_fox_cli = st.session_state.col_cliente_fox
                        col_fox_cam = st.session_state.col_cam_fox
                        
                        df_vh_ev[col_cliente_ev] = df_vh_ev[col_cliente_ev].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                        df_cruce[col_fox_cli] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                        
                        df_vh_ev = pd.merge(df_vh_ev, df_cruce, left_on=col_cliente_ev, right_on=col_fox_cli, how='left')
                        
                        if col_cliente_ev != col_fox_cli:
                            df_vh_ev = df_vh_ev.drop(columns=[col_fox_cli])
                        
                        df_vh_ev.rename(columns={col_fox_cam: 'CAMIÓN ASIGNADO'}, inplace=True)
                        
                        df_vh_ev['CAMIÓN ASIGNADO'] = df_vh_ev['CAMIÓN ASIGNADO'].fillna("")
                        df_vh_ev = df_vh_ev[~df_vh_ev['CAMIÓN ASIGNADO'].astype(str).str.strip().str.upper().isin(['NO', '#N/D'])]
                        df_vh_ev = df_vh_ev.sort_values(by='CAMIÓN ASIGNADO', ascending=True)
                    else:
                        st.warning("⚠️ Procese primero alguna de las pestañas de Ruteo arriba para poder cruzar los camiones asignados.")

                    df_vh_ev = df_vh_ev.dropna(subset=[col_fecha])
                    df_vh_ev['Fecha_Limpia'] = pd.to_datetime(df_vh_ev[col_fecha], errors='coerce').dt.date
                    
                    st.subheader("Filtro Operativo")
                    fecha_calendario = st.date_input("Seleccione la fecha a consultar:", key="cal_ev")
                    
                    if st.button("▶️ Procesar Fecha Seleccionada", key="btn_fecha"):
                        st.session_state.procesar_fecha = True
                        st.session_state.fecha_activa = fecha_calendario
                        
                    if st.session_state.procesar_fecha:
                        fecha_elegida = st.session_state.fecha_activa
                        df_filtrado_ev = df_vh_ev[df_vh_ev['Fecha_Limpia'] == fecha_elegida].drop(columns=['Fecha_Limpia'])
                        
                        df_filtrado_ev = df_filtrado_ev.drop_duplicates(subset=[col_cliente_ev])
                        
                        buscador_cliente = st.text_input("🔍 Buscar por Código de Cliente (Opcional):", key="search_cli_ev")
                        if buscador_cliente:
                            df_filtrado_ev = df_filtrado_ev[df_filtrado_ev[col_cliente_ev].astype(str).str.contains(buscador_cliente.strip(), case=False, na=False)]
                        
                        st.success(f"Mostrando {len(df_filtrado_ev)} registros correspondientes al {fecha_elegida.strftime('%d/%m/%Y')}")
                        st.dataframe(df_filtrado_ev, use_container_width=True)
                        
                        if not df_filtrado_ev.empty:
                            df_imagen_ev = df_filtrado_ev.copy()
                            
                            if len(df_imagen_ev.columns) >= 6:
                                columnas_a_omitir = df_imagen_ev.columns[3:6]
                                df_imagen_ev = df_imagen_ev.drop(columns=columnas_a_omitir)
                            
                            img_ev = generar_imagen_tabla(df_imagen_ev, f"Ventanas Horarias Eventuales - {fecha_elegida.strftime('%d/%m/%Y')}")
                            
                            st.download_button(
                                label="🖼️ Descargar Reporte (Sin columnas D, E, F) como Imagen",
                                data=img_ev.getvalue(),
                                file_name=f"VH_Eventuales_{fecha_elegida}.png",
                                mime="image/png",
                                use_container_width=True,
                                key="dl_img_ev"
                            )
                        
                else:
                    st.warning("El archivo ZIP no contiene ningún archivo válido (.csv o .xlsx).")
                    
        except Exception as e:
            st.error(f"Error al procesar el archivo comprimido. Detalle técnico: {e}")

# --- MÓDULO: GEOS EVENTUALES ---
st.divider()
st.header("📍 Geos Eventuales")
st.caption("Pegue los datos desde Excel directamente en la tabla inferior. Las columnas están predefinidas y bloqueadas.")

columnas_geos = [
    "FECHA", "COD CLIENTE", "Y", "X", "Motivo", 
    "CD", "Bultos", "SDV", "JDV", "VALIDACIÓN", "¿Para mañana?"
]

df_geos_template = pd.DataFrame(columns=columnas_geos)

df_geos_input = st.data_editor(
    df_geos_template,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="geos_eventuales_editor",
    on_change=reset_geos
)

if st.button("▶️ Procesar Geos Eventuales", type="primary", key="btn_geos"):
    st.session_state.procesar_geos = True

if st.session_state.procesar_geos:
    if not df_geos_input.empty:
        if 'df_cruce_fox' in st.session_state:
            df_cruce = st.session_state.df_cruce_fox.copy()
            col_fox_cli = st.session_state.col_cliente_fox
            col_fox_cam = st.session_state.col_cam_fox
            
            df_geos_input["COD CLIENTE"] = df_geos_input["COD CLIENTE"].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_cruce[col_fox_cli] = df_cruce[col_fox_cli].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            df_merged_geos = pd.merge(
                df_geos_input, 
                df_cruce, 
                left_on="COD CLIENTE", 
                right_on=col_fox_cli, 
                how="left"
            )
            
            mensaje_wp = "*Geo Alternativas*\n\n"
            
            for index, row in df_merged_geos.iterrows():
                cliente = row["COD CLIENTE"]
                camion = row[col_fox_cam] if pd.notna(row[col_fox_cam]) else "SIN ASIGNAR"
                lat = row["Y"]
                lon = row["X"]
                link_maps = f"https://www.google.com/maps?q={lat},{lon}"
                mensaje_wp += f"• {cliente} - {link_maps} - {camion}\n"
            
            st.success("Cruce exitoso. Copie el mensaje a continuación para enviarlo por WhatsApp:")
            st.code(mensaje_wp, language="text")
            
        else:
            st.warning("⚠️ Procese primero alguna de las pestañas de Ruteo (arriba) para poder cruzar y obtener los códigos de camión.")
    else:
        st.info("La tabla está vacía. Por favor pegue sus datos antes de procesar.")


# --- MÓDULO: PEDIDOS EVENTUALES ---
st.divider()
st.header("📦 Pedidos Eventuales")
st.caption("Pegue los datos desde Excel directamente en la tabla inferior. Las columnas están predefinidas y bloqueadas.")

columnas_pedidos = [
    "COD CLIENTE", "CLIENTE", "LATITUD yLONGITUD x", "N° DE PEDIDO", "COD PROD", 
    "DESCRIPCION", "CANTIDAD", "Peso HB", "SIS", "SOLICITANTE", "TELÉFONO SOLIC", 
    "OBS FACTURA", "PERSONA QUE RECIBE", "NIT", "TELÉFONO PERSONA QUE RECIBE", 
    "DIRECCIÓN ESCRITA", "CAMIÓN", "PLANILLA", "EVENTO", "MONTO", "OBSERVACIONES", 
    "VENTANA HORARIA"
]

df_pedidos_template = pd.DataFrame(columns=columnas_pedidos)

df_pedidos_input = st.data_editor(
    df_pedidos_template,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="pedidos_eventuales_editor",
    on_change=reset_pedidos
)

if st.button("▶️ Procesar Pedidos", type="primary", key="btn_pedidos"):
    st.session_state.procesar_pedidos = True

if st.session_state.procesar_pedidos:
    if not df_pedidos_input.empty:
        mensaje_wp_pedidos = ""
        
        for index, row in df_pedidos_input.iterrows():
            cod_cliente = "" if pd.isna(row.get("COD CLIENTE")) else str(row.get("COD CLIENTE")).replace('.0', '').strip()
            tel_solic = "" if pd.isna(row.get("TELÉFONO SOLIC")) else str(row.get("TELÉFONO SOLIC")).replace('.0', '').strip()
            tel_recibe = "" if pd.isna(row.get("TELÉFONO PERSONA QUE RECIBE")) else str(row.get("TELÉFONO PERSONA QUE RECIBE")).replace('.0', '').strip()
            persona_recibe = "" if pd.isna(row.get("PERSONA QUE RECIBE")) else str(row.get("PERSONA QUE RECIBE")).strip()
            link_maps = "" if pd.isna(row.get("OBSERVACIONES")) else str(row.get("OBSERVACIONES")).strip()
            ventana_horaria = "" if pd.isna(row.get("VENTANA HORARIA")) else str(row.get("VENTANA HORARIA")).strip()
            
            bloque_texto = "EVENTUAL\n"
            bloque_texto += f"COD: {cod_cliente} @+591 {tel_solic}\n"
            bloque_texto += f"Contacto: {tel_recibe} - {persona_recibe}\n"
            bloque_texto += f"{link_maps}\n"
            bloque_texto += f"VH: {ventana_horaria}\n\n"
            
            mensaje_wp_pedidos += bloque_texto
            
        st.success("Pedidos procesados con éxito. Copie el mensaje a continuación para enviarlo:")
        st.code(mensaje_wp_pedidos, language="text")
    else:
        st.info("La tabla de pedidos está vacía. Por favor pegue sus datos antes de procesar.")
