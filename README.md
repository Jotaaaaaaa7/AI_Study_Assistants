# 📚 Study Assistants

Aplicación Streamlit para crear asistentes de estudio basados en IA capaces de indexar documentos (PDF, DOCX, TXT, Markdown, HTML) en Pinecone y responder consultas en lenguaje natural con soporte de OpenAI GPT‑4o.

## ✨ Características

* Interfaz web responsiva en Streamlit.
* Creación ilimitada de asistentes independientes (índices en Pinecone).
* Ingesta masiva de documentos multiformato con división en *chunks* optimizada.
* Chat contextual con re‑formulación automática del *prompt* e historial completo.
* Visualización y descarga de archivos fuente y fragmentos citados.
* Gestión de documentos: añadir, descargar, eliminar.
* Eliminación segura de índices y carpetas locales.
* Persistencia opcional de metadatos en MongoDB.
* Diseño extensible: utilidades desacopladas en `utils.py`.

## 🏗️ Arquitectura

```
Streamlit UI ──► utils.py ──► Pinecone Vector Store
         │            │
         │            └──► LangChain + OpenAI LLM
         │
         └──► db_config.py (persistencia opcional en MongoDB)
```

Todas las operaciones sobre los documentos viven en **Pinecone**; el modelo de lenguaje se invoca a demanda a través de **LangChain** con *embeddings* `text‑embedding‑3‑small` y `gpt‑4o‑mini` para generación.


## 📥 Instalación rápida

```bash
git clone https://github.com/tuusuario/study-assistants.git
cd study-assistants
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Rellena tus claves
```

### Variables de entorno obligatorias

| Variable           | Descripción       |
| ------------------ | ----------------- |
| `OPENAI_API_KEY`   | Clave de OpenAI   |
| `PINECONE_API_KEY` | Clave de Pinecone |

Variables opcionales:

| Variable    | Descripción                                      | Valor por defecto            |
| ----------- | ------------------------------------------------ | ---------------------------- |
| `MONGO_URI` | URI de conexión a MongoDB para guardar metadatos | `mongodb://localhost:27017/` |

### Ejemplo `.env`

```
OPENAI_API_KEY=...
PINECONE_API_KEY=...
```

## ▶️ Ejecución

```bash
streamlit run app.py
```

La aplicación se abre en tu navegador por defecto (`localhost:8501`).

## 🚀 Uso

1. **Crear nuevo asistente** → Sidebar → “🤖 Crear Nuevo asistente”.
2. Asigna un nombre en minúsculas (`[a‑z0‑9\-]+`) y sube uno o más documentos.
3. Haz clic en **Procesar archivos**; se creará un índice en Pinecone.
4. Selecciona el asistente en la lista y comienza a preguntar en la pestaña **💬 Chatbot**.
5. Explora las fuentes citadas o gestiona archivos desde la pestaña **📊 Información**.

## 🗂️ Estructura del proyecto

```
.
├── app.py            # Interfaz Streamlit
├── utils.py          # Capa de lógica de ingestión y consulta
├── db_config.py      # Persistencia MongoDB (opcional)
├── docs/             # Almacenamiento local de documentos
```
