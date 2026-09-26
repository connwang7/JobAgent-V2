"""对象存储抽象：MinIO（S3 协议）为主，本地文件系统为 dev 兜底。"""
import io
import os
import uuid
from abc import ABC, abstractmethod
from datetime import timedelta

from app.core.config import settings


class Storage(ABC):
    """统一对象存储接口。文件名不落盘，使用对象存储 key。"""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """上传，返回 key。"""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """下载内容。"""

    @abstractmethod
    def presigned_url(self, key: str, expires: timedelta = timedelta(hours=1)) -> str:
        """生成下载链接。"""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除对象；对象不存在返回 False（不抛错，删除接口要幂等）。"""


class LocalStorage(Storage):
    def __init__(self, root: str | None = None):
        self.root = root or settings.local_storage_dir
        os.makedirs(self.root, exist_ok=True)

    def _plain_path(self, key: str) -> str:
        """只拼路径、side-effect free（delete 用；避免把目录又建出来）。"""
        return os.path.join(self.root, *key.split("/"))

    def _path(self, key: str) -> str:
        path = self._plain_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        with open(self._path(key), "wb") as f:
            f.write(data)
        return key

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    def presigned_url(self, key: str, expires: timedelta = timedelta(hours=1)) -> str:
        return f"/api/v1/files/local/{key}"

    def delete(self, key: str) -> bool:
        path = self._plain_path(key)
        try:
            os.remove(path)
        except OSError:
            # 文件不存在 / 权限问题都当作"没删掉"，删除接口要幂等不能抛
            return False
        # 顺手清掉空目录（resumes/{user_id}/ 这种），失败无所谓
        parent = os.path.dirname(path)
        try:
            if parent and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except OSError:
            pass
        return True


class MinioStorage(Storage):
    def __init__(self) -> None:
        from minio import Minio
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )
        return key

    def get(self, key: str) -> bytes:
        response = None
        try:
            response = self.client.get_object(self.bucket, key)
            return response.read()
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def presigned_url(self, key: str, expires: timedelta = timedelta(hours=1)) -> str:
        return self.client.presigned_get_object(self.bucket, key, expires=expires)

    def delete(self, key: str) -> bool:
        from minio.error import S3Error
        try:
            self.client.remove_object(self.bucket, key)
            return True
        except S3Error:
            return False


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.storage_backend == "minio":
            _storage = MinioStorage()
        else:
            _storage = LocalStorage()
    return _storage


def new_object_key(prefix: str, ext: str) -> str:
    return f"{prefix}/{uuid.uuid4().hex}.{ext}"
