import tempfile
import os
import logging
from typing import List
from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from streamlit.runtime.uploaded_file_manager import UploadedFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import ChatOpenAI
from langchain import hub




# Configuración del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

def ingest_docs(uploaded_files: List[UploadedFile], assistant_id: str, index_name, delete_existing_files=False):
    try:
        if not os.path.exists("docs"):
            os.makedirs("docs")
            logger.info("Carpeta 'docs' creada")

        # Verificar que existe la carpeta específica del índice
        index_dir = os.path.join("docs", index_name)
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
            logger.info(f"Carpeta '{index_dir}' creada")
        # Inicializar cliente de Pinecone
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

        # Comprobar si el índice existe
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        index_exists = index_name in existing_indexes

        if not index_exists:
            # Crear el índice si no existe
            logger.info(f"Creando nuevo índice: {index_name}")
            pc.create_index(
                name=index_name,
                dimension=1536,  # Dimensión para text-embedding-3-small
                metric="cosine",
                spec={
                    # "replicas": 1,
                    # "shard_size": 1000,
                    "serverless": {
                        "cloud": "aws",
                        "region": "us-east-1"  # o la región que prefieras
                    }
                }
            )

        all_documents = []

        # Procesar cada archivo subido
        for uploaded_file in uploaded_files:
            # Crear un archivo temporal para guardarlo
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name

            # Seleccionar el loader apropiado según el tipo de archivo
            try:
                if uploaded_file.name.endswith('.pdf'):
                    loader = PyMuPDFLoader(temp_path)
                elif uploaded_file.name.endswith('.docx'):
                    loader = TextLoader(temp_path, encoding="utf-8")
                elif uploaded_file.name.endswith('.md'):
                    loader = UnstructuredMarkdownLoader(temp_path)
                elif uploaded_file.name.endswith('.txt'):
                    loader = TextLoader(temp_path, encoding="utf-8")
                elif uploaded_file.name.endswith('.html'):
                    loader = TextLoader(temp_path, encoding="utf-8")
                else:
                    logger.warning(f"Tipo de archivo no soportado: {uploaded_file.name}")
                    continue

                # Cargar documentos del archivo
                file_documents = loader.load()
                logger.info(f"Cargados {len(file_documents)} documentos de {uploaded_file.name}")

                # Añadir metadatos del archivo original
                for doc in file_documents:
                    doc.metadata.update({
                        "filename": uploaded_file.name,
                        "filetype": uploaded_file.type,
                        "assistant_id": assistant_id
                    })

                all_documents.extend(file_documents)

            finally:
                # Asegurar la eliminación del archivo temporal
                os.unlink(temp_path)

        # Salir si no hay documentos
        if not all_documents:
            logger.warning("No se pudieron cargar documentos válidos")
            return

        # Dividir en chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=50,
        )
        documents = text_splitter.split_documents(all_documents)
        logger.info(f"Dividido en {len(documents)} chunks")

        # Definir tamaño del lote
        batch_size = 100
        total_batches = (len(documents) + batch_size - 1) // batch_size

        # Inicializar vectorstore con el índice existente
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

        # Si se indica que se deben eliminar archivos existentes
        if delete_existing_files:
            # Obtener nombres de archivos a insertar
            filenames = [doc.metadata["filename"] for doc in all_documents if "filename" in doc.metadata]
            filenames = list(set(filenames))  # Eliminar duplicados

            if filenames:
                # Eliminar vectores con estos nombres de archivo
                vectorstore.delete(
                    filter={"filename": {"$in": filenames}}
                )
                logger.info(f"Eliminados documentos anteriores para los archivos: {', '.join(filenames)}")

        logger.info(f'Agregando {len(documents)} documentos a Pinecone en {total_batches} lotes')

        # Procesar por lotes
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            end_idx = min(i+batch_size, len(documents))
            logger.info(f"Procesando lote {i//batch_size + 1}/{total_batches} (documentos {i+1}-{end_idx})")

            # Añadir documentos al índice existente
            vectorstore.add_documents(batch)

        logger.info("****Carga en el índice vectorial completada****")
        return True

    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def get_all_indexes(detailed=False):
    """
    Obtiene todos los índices disponibles en la cuenta de Pinecone.

    Args:
        detailed (bool): Si es True, devuelve información detallada sobre cada índice.
                         Si es False, solo devuelve los nombres de los índices.

    Returns:
        list: Lista de nombres de índices o lista de diccionarios con información detallada.
    """
    try:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        indexes = pc.list_indexes()

        if not detailed:
            # Solo devolver los nombres de los índices
            return [idx.name for idx in indexes]
        else:
            # Devolver información detallada sobre cada índice
            detailed_info = []
            for idx in indexes:
                # Obtener propiedades disponibles del objeto índice
                index_info = {
                    "name": idx.name,
                    "host": getattr(idx, "host", "N/A"),
                    "dimension": getattr(idx, "dimension", "N/A"),
                    "metric": getattr(idx, "metric", "N/A"),
                    "status": getattr(idx, "status", "N/A")
                }
                detailed_info.append(index_info)
            return detailed_info
    except Exception as e:
        logger.error(f"Error al obtener índices: {e}")
        return []

def get_docs_by_index(index_name: str, limit: int = 10):
    """
    Obtiene documentos de un índice específico en Pinecone.

    Args:
        index_name (str): Nombre del índice del cual obtener los documentos.
        limit (int): Número máximo de documentos a recuperar.

    Returns:
        list: Lista de documentos recuperados del índice.
    """
    try:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)
        docs = vectorstore.similarity_search("", k=limit)
        return docs
    except Exception as e:
        logger.error(f"Error al obtener documentos del índice {index_name}: {e}")
        return []

def get_chunked_docs_by_index(index_name: str, limit: int = 10):
    """
    Obtiene documentos fragmentados de un índice específico en Pinecone.

    Args:
        index_name (str): Nombre del índice del cual obtener los documentos.
        limit (int): Número máximo de documentos a recuperar.

    Returns:
        list: Lista de documentos fragmentados recuperados del índice.
    """
    try:
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)
        docs = vectorstore.similarity_search("", k=limit)
        return [doc.page_content for doc in docs]
    except Exception as e:
        logger.error(f"Error al obtener documentos fragmentados del índice {index_name}: {e}")
        return []


def delete_index(index_name: str):
    try:
        # Eliminar índice de Pinecone
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        if index_name in [idx.name for idx in pc.list_indexes()]:
            pc.delete_index(index_name)
            logger.info(f"Índice {index_name} eliminado correctamente.")

            # Eliminar carpeta física docs/nombre-indice
            docs_dir = os.path.join("docs", index_name)
            if os.path.exists(docs_dir):
                import shutil
                shutil.rmtree(docs_dir)
                logger.info(f"Carpeta {docs_dir} y todos sus archivos eliminados correctamente.")

            dir_contenido = f'docs/{index_name}'

            try:
                os.remove(dir_contenido)
            except FileNotFoundError:
                print("El directorio no existe")
            except PermissionError:
                print("Sin permisos para borrar el directorio")
            except OSError as e:
                print(f"Error al borrar recursivamente: {e}")


            return True
        else:
            logger.warning(f"El índice {index_name} no existe.")
            return False
    except Exception as e:
        logger.error(f"Error al eliminar el índice: {e}")
        return False


def run_llm_on_index(query: str, chat_history: list, index_name: str):
    """
    Ejecuta el modelo de lenguaje utilizando el índice especificado para responder consultas.
    """
    try:
        # Conexión al índice específico
        vectorstore = PineconeVectorStore(
            index_name=index_name,
            embedding=embeddings
        )

        # Configurar el LLM
        chat = ChatOpenAI(
            verbose=True,
            temperature=0,
            model='gpt-4o-mini'
        )

        # Usar prompts y cadenas de LangChain
        retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
        stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

        # Crear un retriever consciente del historial
        rephrase_prompt = hub.pull("langchain-ai/chat-langchain-rephrase")
        history_aware_retriever = create_history_aware_retriever(
            llm=chat,
            retriever=vectorstore.as_retriever(),
            prompt=rephrase_prompt
        )

        # Crear la cadena de recuperación
        qa = create_retrieval_chain(
            retriever=history_aware_retriever,
            combine_docs_chain=stuff_documents_chain
        )

        # Ejecutar la consulta
        result = qa.invoke({"input": query, "chat_history": chat_history})

        # Formatear el resultado
        return {
            "query": result['input'],
            "result": result['answer'],
            "source_documents": result['context']
        }
    except Exception as e:
        logger.error(f"Error al ejecutar consulta en índice {index_name}: {e}")
        return {
            "query": query,
            "result": f"Error al procesar la consulta: {str(e)}",
            "source_documents": []
        }


def create_sources_string(source_urls):
    """
    Formatea las URLs de las fuentes para mostrarlas en la interfaz.
    """
    if not source_urls:
        return ""

    sources_list = list(set(source_urls))  # Eliminar duplicados
    sources_list.sort()
    sources_string = "Fuentes:\n"

    for i, source in enumerate(sources_list):
        sources_string += f"{i + 1}. {source}\n"

    return sources_string


def get_document_content_by_id(index_name, doc_id):
    """
    Obtiene el contenido completo de un documento específico por su ID.

    Args:
        index_name (str): Nombre del índice donde se encuentra el documento.
        doc_id (str): ID del documento o nombre del archivo.

    Returns:
        dict: Información completa del documento, incluyendo contenido y metadatos.
    """
    try:
        vectorstore = PineconeVectorStore(
            index_name=index_name,
            embedding=embeddings
        )

        # Buscar fragmentos que coincidan con el archivo
        docs = vectorstore.similarity_search(
            "",
            k=100,  # Obtener suficientes documentos para encontrar todos los fragmentos
            filter={"filename": doc_id}
        )

        if not docs:
            return {"content": "No se encontró el documento", "metadata": {}}

        # Organizar por fragmentos
        fragments = [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
        return fragments

    except Exception as e:
        logger.error(f"Error al recuperar documento {doc_id} del índice {index_name}: {e}")
        return {"content": f"Error: {str(e)}", "metadata": {}}


def delete_document_by_id(index_name, doc_id):
    """
    Elimina un documento específico del índice por su ID.

    Args:
        index_name (str): Nombre del índice donde se encuentra el documento.
        doc_id (str): ID del documento o nombre del archivo.

    Returns:
        bool: True si se eliminó correctamente, False en caso contrario.
    """
    try:
        vectorstore = PineconeVectorStore(
            index_name=index_name,
            embedding=embeddings
        )

        # Eliminar documentos que coincidan con el ID
        vectorstore.delete(
            filter={"filename": doc_id}
        )
        logger.info(f"Documento {doc_id} eliminado del índice {index_name}.")

        # Eliminar archivos físicos
        file_path = f'docs/{index_name}/{doc_id}'

        try:
            os.remove(file_path)
        except FileNotFoundError:
            print("El archivo no existe")
        except PermissionError:
            print("Sin permisos para borrar el archivo")
        except OSError as e:
            print(f"Error al borrar: {e}")

        return True


    except Exception as e:
        logger.error(f"Error al eliminar documento {doc_id} del índice {index_name}: {e}")
        return False


def add_docs_to_index(index_name: str, documents: List[dict]):
    """
    Añade documentos al índice especificado.

    Args:
        index_name (str): Nombre del índice donde se añadirán los documentos.
        documents (List[dict]): Lista de documentos a añadir, cada uno con 'content' y 'metadata'.

    Returns:
        bool: True si se añadieron correctamente, False en caso contrario.
    """
    try:
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)
        vectorstore.add_documents(documents)
        logger.info(f"Documentos añadidos al índice {index_name}.")
        return True
    except Exception as e:
        logger.error(f"Error al añadir documentos al índice {index_name}: {e}")
        return False




if __name__ == "__main__":
    pass