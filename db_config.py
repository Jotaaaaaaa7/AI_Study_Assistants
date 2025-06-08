from pymongo import MongoClient
from datetime import datetime
import os
from bson import ObjectId

# Configuración
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "documentos_db"
COLLECTION_NAME = "indices"

# Conexión a MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

def guardar_indice(index_name: str, documentos: list):
    """
    Guarda un índice y sus documentos en MongoDB.
    """
    doc = {
        "index_name": index_name,
        "document_count": len(documentos),
        "created_at": datetime.utcnow(),
        "documentos": documentos  # Lista de chunks o strings
    }
    result = collection.insert_one(doc)
    print(f"Índice '{index_name}' guardado con ID: {result.inserted_id}")

def obtener_indices():
    """
    Retorna todos los índices almacenados.
    """
    return list(collection.find({}, {"_id": 0}))

# Ejemplo de uso
if __name__ == "__main__":
    index = "ejemplo-indice"
    documentos = [
        {"contenido": "Este es el contenido 1", "origen": "doc1.pdf"},
        {"contenido": "Este es el contenido 2", "origen": "doc2.pdf"}
    ]
    guardar_indice(index, documentos)
    print("Índices existentes:", obtener_indices())
