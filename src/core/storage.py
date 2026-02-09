import os
import json
import uuid
import logging
from typing import Any, Protocol, Dict

logger = logging.getLogger(__name__)

class StorageProvider(Protocol):
    def save(self, data: Dict[str, Any], filename: str = None) -> str:
        ...
    def exists(self, filename: str) -> bool:
        ...
    def load(self, filename: str) -> Dict[str, Any]:
        ...

class LocalStorageProvider:
    def __init__(self, base_dir="data/output"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def save(self, data: Dict[str, Any], filename: str = None) -> str:
        if not filename:
            filename = f"{uuid.uuid4()}.json"
        
        filepath = os.path.join(self.base_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved JSON to local storage: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save local file: {e}")
            raise e
            
        return filepath

    def exists(self, filename: str) -> bool:
        return os.path.exists(os.path.join(self.base_dir, filename))

    def load(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.base_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

class GCSStorageProvider:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
    
    def save(self, data: Dict[str, Any], filename: str = None) -> str:
        if not filename:
            filename = f"{uuid.uuid4()}.json"
        
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            
            json_str = json.dumps(data, ensure_ascii=False)
            blob.upload_from_string(json_str, content_type='application/json')
            
            logger.info(f"Saved JSON to GCS: gs://{self.bucket_name}/{filename}")
            return f"https://storage.googleapis.com/{self.bucket_name}/{filename}"
            
        except ImportError:
            logger.error("google-cloud-storage library not found.")
            raise ImportError("Please install google-cloud-storage to use GCS provider.")
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            raise e

    def exists(self, filename: str) -> bool:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            return blob.exists()
        except Exception as e:
            logger.error(f"Failed to check GCS file existence: {e}")
            return False

    def load(self, filename: str) -> Dict[str, Any]:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            data_str = blob.download_as_string()
            return json.loads(data_str)
        except Exception as e:
            logger.error(f"Failed to load from GCS: {e}")
            raise e

def get_storage() -> StorageProvider:
    storage_type = os.environ.get("STORAGE_TYPE", "LOCAL").upper()
    
    if storage_type == "GCS":
        bucket = os.environ.get("GCS_BUCKET_NAME", "riduck-course-data")
        return GCSStorageProvider(bucket)
    
    return LocalStorageProvider()
