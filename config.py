import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")
    SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
    SENSOR_API_KEY = os.environ.get("SENSOR_API_KEY")
