import os
from functools import lru_cache

from minio import Minio


@lru_cache
def get_minio_client():
    return Minio(os.environ["MINIO_ENDPOINT"],
                 access_key=os.environ["MINIO_ACCESS_KEY"],
                 secret_key=os.environ["MINIO_SECRET_KEY"],
                 secure=os.getenv("MINIO_SECURE", "true").lower() == "true"
                 )
