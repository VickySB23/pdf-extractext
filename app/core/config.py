import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pdf-extractext")
    SECRET_KEY = os.getenv("SECRET_KEY", "clave_por_defecto_cambiar_en_produccion")
settings = Settings()