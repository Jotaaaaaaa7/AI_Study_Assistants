import pandas as pd
import streamlit as st
import os
# from utils import (ingest_docs, get_all_indexes, get_docs_by_index,
#                   delete_index, delete_files_from_index, get_document_content_by_id,
#                   run_llm_on_index, delete_document_by_id, create_sources_string)

import utils


def main():
    """Función principal de la aplicación"""
    st.set_page_config(layout="wide")

    # Crear la carpeta docs si no existe
    if not os.path.exists("docs"):
        os.makedirs("docs")

    # Inicializar variables de sesión
    if "page" not in st.session_state:
        st.session_state.page = "crear"
    if "selected_index" not in st.session_state:
        st.session_state.selected_index = None
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "chatbot"
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = {}

    # Configurar la barra lateral
    with st.sidebar:
        # st.title("Study Assistants")

        # Botón para ir a la página de creación de asistentes
        if st.button("🤖 Crear Nuevo asistente", use_container_width=True):
            st.session_state.page = "crear"
            st.session_state.selected_index = None

        # Separador
        st.markdown("---")
        st.subheader("asistentes disponibles")

        # Lista de asistentes existentes
        indices = utils.get_all_indexes(detailed=True)
        for idx in indices:
            if st.button(f"🧠 {idx['name']}", key=f"idx_{idx['name']}", use_container_width=True):
                st.session_state.page = "index_page"
                st.session_state.selected_index = idx['name']
                st.session_state.active_tab = "chatbot"

                # Inicializar historial de chat si no existe
                if idx['name'] not in st.session_state.chat_histories:
                    st.session_state.chat_histories[idx['name']] = {
                        "user_prompt_history": [],
                        "chat_answers_history": [],
                        "chat_history": [],
                        "used_fragments": {}
                    }
                st.rerun()

    # Mostrar la página correspondiente
    if st.session_state.page == "crear":
        show_create_index_page()
    elif st.session_state.page == "index_page":
        show_index_page(st.session_state.selected_index)

def show_create_index_page():
    """Muestra la página de creación de asistentes"""
    st.title("Crear Nuevo asistente")

    # Campo para que el usuario ingrese el nombre del asistente
    index_name = st.text_input("Nombre del asistente", "asistente-para-estudio",)

    # Validar el formato del nombre del asistente
    import re
    is_valid_name = bool(re.match(r'^[a-z0-9-]+$', index_name))

    if not is_valid_name:
        st.warning("El nombre del asistente debe contener solo letras minúsculas, números o guiones '-'")

    files = st.file_uploader("Subir documentos", type=["pdf", "docx", "txt", "md"],
                          accept_multiple_files=True, key="file_uploader")

    if files:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"{len(files)} archivos seleccionados")
        with col2:
            # Desactivar el botón si el nombre no es válido
            button_disabled = not is_valid_name
            if st.button("Procesar archivos", use_container_width=True, disabled=button_disabled):
                # Crear carpeta específica para el asistente
                docs_dir = os.path.join("docs", index_name)
                if not os.path.exists(docs_dir):
                    os.makedirs(docs_dir)

                # Guardar archivos en la carpeta
                saved_files = []
                for file in files:
                    file_path = os.path.join(docs_dir, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_files.append(file_path)

                with st.spinner("Procesando documentos..."):
                    result = utils.ingest_docs(uploaded_files=files, index_name=index_name, assistant_id="5")
                    if result:
                        st.success(f"¡asistente '{index_name}' creado correctamente!")
                        st.info(f"Los documentos se han guardado en: {docs_dir}")

                        # Mostrar lista de archivos guardados
                        with st.expander("Archivos guardados"):
                            for file in files:
                                st.write(file.name)

                        # Actualizar la lista de asistentes
                        st.rerun()
                    else:
                        st.error("Error al procesar los documentos")

def show_index_page(index_name):
    """Muestra la página de un asistente específico con pestañas"""
    # Crear pestañas
    chatbot_tab, info_tab = st.tabs(["💬 Chatbot", "📊 Información"])

    # Inicializar el historial si no existe
    if index_name not in st.session_state.chat_histories:
        st.session_state.chat_histories[index_name] = {
            "user_prompt_history": [],
            "chat_answers_history": [],
            "chat_history": [],
            "used_fragments": {}
        }
    chat_state = st.session_state.chat_histories[index_name]

    # Mostrar contenido de cada pestaña
    with chatbot_tab:
        show_chatbot_tab(index_name, chat_state)

    with info_tab:
        show_info_tab(index_name)


def show_chatbot_tab(index_name, chat_state):
    """Muestra la pestaña del chatbot"""
    st.title(f"Chat con {index_name}")

    # Inicializar variable de estado para controlar el procesamiento
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "current_prompt" not in st.session_state:
        st.session_state.current_prompt = None
    if "message_sources" not in st.session_state:
        st.session_state.message_sources = {}

    # Botón para reiniciar conversación
    if st.button("🔄 Reiniciar conversación", key="reset_chat"):
        chat_state["user_prompt_history"] = []
        chat_state["chat_answers_history"] = []
        chat_state["chat_history"] = []
        chat_state["used_fragments"] = {}
        st.session_state.message_sources = {}
        st.session_state.is_processing = False
        st.session_state.current_prompt = None
        st.rerun()

    # Área de mensajes con scroll
    chat_messages = st.container(height=600)
    with chat_messages:
        # Mostrar historial de mensajes
        for i, (user_query, ai_response) in enumerate(zip(
                chat_state["user_prompt_history"],
                chat_state["chat_answers_history"]
        )):
            # Mensaje del usuario
            st.chat_message("user").write(user_query)

            # Extraer respuesta sin fuentes
            clean_response = ai_response
            if "*fuentes utilizados:*" in ai_response:
                clean_response = ai_response.split("*fuentes utilizados:*")[0]

            # Mensaje del asistente
            with st.chat_message("assistant"):
                st.markdown(clean_response)

                # Mostrar fuentes para este mensaje específico
                message_id = f"msg_{i}"
                if message_id in st.session_state.message_sources and st.session_state.message_sources[message_id]:
                    st.markdown("**Fuentes utilizadas:**")

                    # Crear 4 columnas para las fuentes
                    cols = st.columns(4)

                    # Obtener fuentes de este mensaje
                    message_fragments = st.session_state.message_sources[message_id]
                    fragments_by_file = {}

                    # Agrupar fuentes por archivo
                    for key, fragment in message_fragments.items():
                        filename = fragment["metadata"].get("filename", "Desconocido") if "metadata" in fragment else "Desconocido"
                        if filename not in fragments_by_file:
                            fragments_by_file[filename] = []
                        fragments_by_file[filename].append(fragment)

                    # Distribuir las fuentes entre las columnas
                    files_list = list(fragments_by_file.items())
                    for j, (filename, fragments) in enumerate(files_list):
                        col_index = j % 4  # Distribuir en las 4 columnas
                        with cols[col_index]:
                            if st.button(f"📄 {filename} ({len(fragments)})", key=f"file_{message_id}_{filename}"):
                                st.session_state.show_fragment_dialog = True
                                st.session_state.current_file = filename
                                st.session_state.current_fragments = fragments
                                st.rerun()

        # Mostrar mensaje en procesamiento (si aplica)
        if st.session_state.is_processing and st.session_state.current_prompt:
            st.chat_message("user").write(st.session_state.current_prompt)
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    # Generar respuesta
                    generated_response = utils.run_llm_on_index(
                        query=st.session_state.current_prompt,
                        chat_history=chat_state["chat_history"],
                        index_name=index_name
                    )

                    # Crear un ID para este mensaje
                    message_id = f"msg_{len(chat_state['user_prompt_history'])}"
                    st.session_state.message_sources[message_id] = {}

                    # Guardar fuentes específicas para este mensaje
                    if "source_documents" in generated_response and generated_response["source_documents"]:
                        for doc in generated_response["source_documents"]:
                            if hasattr(doc, "metadata") and "filename" in doc.metadata:
                                fragment_key = f"{doc.metadata.get('filename')}_{doc.page_content[:30]}"
                                # Guardar en el historial general
                                if "used_fragments" not in chat_state:
                                    chat_state["used_fragments"] = {}
                                if fragment_key not in chat_state["used_fragments"]:
                                    chat_state["used_fragments"][fragment_key] = {
                                        "content": doc.page_content,
                                        "metadata": doc.metadata
                                    }
                                # Guardar para este mensaje específico
                                st.session_state.message_sources[message_id][fragment_key] = {
                                    "content": doc.page_content,
                                    "metadata": doc.metadata
                                }

                    # Actualizar historial
                    chat_state["user_prompt_history"].append(st.session_state.current_prompt)
                    chat_state["chat_answers_history"].append(generated_response['result'])
                    chat_state["chat_history"].append(("human", st.session_state.current_prompt))
                    chat_state["chat_history"].append(("ai", generated_response["result"]))

                    # Finalizar procesamiento
                    st.session_state.is_processing = False
                    st.session_state.current_prompt = None
                    st.rerun()

    # Input para nuevos mensajes
    prompt = st.chat_input("Haz una pregunta sobre los documentos...")
    if prompt and not st.session_state.is_processing:
        # Iniciar procesamiento
        st.session_state.is_processing = True
        st.session_state.current_prompt = prompt
        st.rerun()

    # Dialog de fuentes
    if "show_fragment_dialog" in st.session_state and st.session_state.show_fragment_dialog:
        if hasattr(st.session_state, "current_fragments") and st.session_state.current_file:
            @st.dialog(f"Fuentes de {st.session_state.current_file}", width='large')
            def show_fragments_dialog():
                st.subheader(f"Fuentes de {st.session_state.current_file}")

                for idx, fragment in enumerate(st.session_state.current_fragments):
                    expander_title = ""
                    if "metadata" in fragment and "page" in fragment["metadata"]:
                        expander_title = f"Page {int(fragment['metadata']['page'])} --- "
                    expander_title += fragment['content'][:90] + "..."

                    with st.expander(expander_title, expanded=(idx == 0)):
                        st.markdown("**Contenido:**")
                        st.markdown(f"```\n{fragment['content']}\n```")

            show_fragments_dialog()
            st.session_state.show_fragment_dialog = False




def show_info_tab(index_name):
    """Muestra la pestaña de información del asistente"""
    st.title(f"Información del asistente: {index_name}")

    # Dividir en columnas: detalles y acciones
    details_col, actions_col = st.columns([3, 1])

    with details_col:
        indices = utils.get_all_indexes(detailed=True)
        index_details = next((idx for idx in indices if idx['name'] == index_name), None)
        if index_details:
            display_details = {}
            for key, value in index_details.items():
                if isinstance(value, (dict, list, tuple)) or not isinstance(value, (str, int, float, bool, type(None))):
                    display_details[key] = str(value)
                else:
                    display_details[key] = value
            df = pd.DataFrame([display_details])
            st.dataframe(df)
        else:
            st.warning("No se encontró información del asistente")

    with actions_col:
        if "confirm_delete_index" not in st.session_state:
            st.session_state.confirm_delete_index = False

        if st.button("🗑️ Eliminar asistente", use_container_width=True):
            st.session_state.confirm_delete_index = True

        if st.session_state.confirm_delete_index:
            if st.button("✓ Confirmar eliminación", key="confirm_delete_btn", type="primary", use_container_width=True):
                with st.spinner("Eliminando asistente..."):
                    if utils.delete_index(index_name):
                        st.success(f"asistente eliminado correctamente")
                        st.session_state.page = "crear"
                        st.session_state.confirm_delete_index = False
                        st.rerun()
                    else:
                        st.error("Error al eliminar el asistente")
                        st.session_state.confirm_delete_index = False

    st.subheader("Documentos en este asistente")

    with st.spinner("Cargando documentos..."):
        docs = utils.get_docs_by_index(index_name, limit=100)
        files_info = {}
        for doc in docs:
            if hasattr(doc, "metadata") and "filename" in doc.metadata:
                filename = doc.metadata.get("filename", "Desconocido")
                source_path = doc.metadata.get("source", None)
                if filename not in files_info:
                    files_info[filename] = {
                        "count": 0,
                        "metadata": doc.metadata.copy(),
                        "file_path": source_path
                    }
                files_info[filename]["count"] += 1

        if not files_info:
            st.info("No se encontraron documentos en este asistente")
            add_documents_uploader(index_name)
            return

        df_col, selector_col = st.columns([3, 2])

        with df_col:
            # Obtener conteo completo de chunks aumentando significativamente el límite
            docs = utils.get_docs_by_index(index_name, limit=10000)  # Aumentado de 100 a 10000

            # Reinicializar files_info para no duplicar con el cálculo previo
            files_info = {}
            for doc in docs:
                if hasattr(doc, "metadata") and "filename" in doc.metadata:
                    filename = doc.metadata.get("filename", "Desconocido")
                    source_path = doc.metadata.get("source", None)
                    if filename not in files_info:
                        files_info[filename] = {
                            "count": 0,
                            "metadata": doc.metadata.copy(),
                            "file_path": source_path
                        }
                    files_info[filename]["count"] += 1

            # Advertir si se alcanzó el límite
            if len(docs) >= 10000:
                st.warning("⚠️ Es posible que no se muestren todos los chunks debido al límite de consulta (10.000).")

            file_data = []
            for filename, info in files_info.items():
                file_ext = filename.split('.')[-1].upper() if '.' in filename else "DESCONOCIDO"
                file_data.append({
                    "Archivo": filename,
                    "Tipo": file_ext,
                    "Chunks": info["count"]  # Cambiado de "fuentes" a "Chunks" para mayor claridad
                })

            # Ordenar por nombre de archivo
            file_data = sorted(file_data, key=lambda x: x["Archivo"])

            st.dataframe(pd.DataFrame(file_data), hide_index=True, height=300)

        with selector_col:
            if "selected_file" not in st.session_state:
                st.session_state.selected_file = None
            if "confirm_delete_file" not in st.session_state:
                st.session_state.confirm_delete_file = False

            file_options = list(files_info.keys())
            selected_file = st.selectbox("Seleccionar archivo:", options=file_options)
            st.session_state.selected_file = selected_file

            if selected_file:
                file_info = files_info[selected_file]
                possible_paths = [
                    file_info.get("file_path"),
                    os.path.join("docs", index_name, selected_file),
                    os.path.join("docs", selected_file)
                ]
                valid_paths = [p for p in possible_paths if p and os.path.exists(p)]

                if valid_paths:
                    file_path = valid_paths[0]
                    file_ext = selected_file.lower().split('.')[-1] if '.' in selected_file else ''

                    try:
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()

                        mime_type = "application/octet-stream"
                        if file_ext == "pdf":
                            mime_type = "application/pdf"
                        elif file_ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
                            mime_type = f"image/{file_ext}"

                        st.download_button(
                            label="📥 Descargar archivo",
                            data=file_bytes,
                            file_name=selected_file,
                            mime=mime_type,
                            use_container_width=True
                        )
                    except Exception:
                        pass

                if st.button("🗑️ Eliminar archivo", use_container_width=True):
                    st.session_state.confirm_delete_file = True

                if st.session_state.confirm_delete_file:
                    if st.button("✓ Confirmar eliminación", key="confirm_delete_file_btn", type="primary"):
                        with st.spinner("Eliminando archivo..."):
                            filename = os.path.basename(selected_file)
                            st.info(f"Intentando eliminar archivo '{filename}' del asistente '{index_name}'")
                            success = utils.delete_document_by_id(index_name, filename)
                            if success:
                                st.success(f"Archivo '{filename}' eliminado correctamente")
                                st.cache_data.clear()
                                import time
                                time.sleep(1)
                                st.session_state.confirm_delete_file = False
                                st.rerun()
                            else:
                                st.error(f"Error al eliminar el archivo '{filename}'")
                                st.info("Revise los logs para más detalles.")
                                st.session_state.confirm_delete_file = False

                add_documents_uploader(index_name)




        if selected_file:
            file_info = files_info[selected_file]
            file_ext = selected_file.lower().split('.')[-1] if '.' in selected_file else ''
            st.subheader(f"Visualización de {selected_file}")

            possible_paths = [
                file_info.get("file_path"),
                os.path.join("docs", index_name, selected_file),
                os.path.join("docs", selected_file)
            ]
            valid_paths = [p for p in possible_paths if p and os.path.exists(p)]

            if valid_paths:
                file_path = valid_paths[0]
                try:
                    if file_ext == 'pdf':
                        import base64
                        with open(file_path, "rb") as f:
                            pdf_bytes = f.read()
                        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                        pdf_display = f"""
                            <div style="display: flex; justify-content: center;">
                                <iframe 
                                    src="data:application/pdf;base64,{base64_pdf}" 
                                    width="80%"
                                    height="800" 
                                    type="application/pdf">
                                </iframe>
                            </div>
                        """
                        st.markdown(pdf_display, unsafe_allow_html=True)


                    elif file_ext in ['txt', 'md', 'py', 'html', 'css', 'js', 'json']:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.code(content)
                    elif file_ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
                        st.image(file_path, caption=selected_file)
                    else:
                        st.info(f"Vista previa no disponible para archivos de tipo {file_ext.upper()}")
                except Exception as e:
                    st.error(f"Error al mostrar el archivo: {str(e)}")
            else:
                st.warning("No se pudo encontrar el archivo original.")
                st.info("Mostrando fuentes indexados como alternativa.")
                fragments = [d for d in docs if hasattr(d, "metadata") and d.metadata.get("filename") == selected_file]
                if fragments:
                    for i, fragment in enumerate(fragments[:5]):
                        with st.expander(f"fuente {i+1} de {len(fragments)}", expanded=(i == 0)):
                            st.code(fragment.page_content)
                    if len(fragments) > 5:
                        st.info(f"Mostrando 5 de {len(fragments)} fuentes disponibles.")




def add_documents_uploader(index_name):
    files = st.file_uploader("Añadir documentos", type=["pdf", "docx", "txt", "md"],
                             accept_multiple_files=True, key="file_uploader")

    if files:
        if st.button("Añadir documentos al asistente", use_container_width=True):
            with st.spinner("Verificando documentos..."):
                # Obtener documentos existentes en el asistente
                docs = utils.get_docs_by_index(index_name, limit=100)
                existing_filenames = set()
                for doc in docs:
                    if hasattr(doc, "metadata") and "filename" in doc.metadata:
                        existing_filenames.add(doc.metadata.get("filename"))

                # Verificar duplicados
                duplicate_files = [file for file in files if file.name in existing_filenames]
                new_files = [file for file in files if file.name not in existing_filenames]

                # Mostrar advertencia si hay duplicados
                if duplicate_files:
                    duplicate_names = [file.name for file in duplicate_files]
                    st.warning(
                        f"Los archivos {', '.join(duplicate_names)} tienen nombres duplicados y no serán procesados:")
                    for file in duplicate_files:
                        st.info(f"- {file.name}")

                # Crear carpeta específica para el asistente si no existe
                docs_dir = os.path.join("docs", index_name)
                if not os.path.exists(docs_dir):
                    os.makedirs(docs_dir)

                # Guardar solo los archivos no duplicados
                for file in new_files:
                    file_path = os.path.join(docs_dir, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())

                # Procesar los documentos y añadirlos al asistente existente
                result = utils.ingest_docs(
                    uploaded_files=new_files,
                    assistant_id="5",
                    index_name=index_name,
                    delete_existing_files=False
                )

                if result:
                    st.success(f"{len(new_files)} documentos añadidos al asistente '{index_name}' correctamente")
                    # Limpiar caché y recargar la página
                    st.cache_data.clear()
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error al procesar los documentos")

                st.rerun()







# Ejecutar la aplicación
if __name__ == "__main__":
    main()