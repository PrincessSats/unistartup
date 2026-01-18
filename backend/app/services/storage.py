"""
Сервис для работы с Yandex Object Storage.
Yandex Object Storage совместим с Amazon S3 API.
"""

import boto3
from botocore.exceptions import ClientError
from app.config import settings
import uuid
from PIL import Image
import io

AVATAR_MAX_SIZE = (256, 256)
MAX_FILE_SIZE = 5 * 1024 * 1024


def get_s3_client():
    """Создаёт клиент для работы с S3."""
    return boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY
    )


def compress_image(file_bytes: bytes, max_size: tuple = AVATAR_MAX_SIZE) -> bytes:
    """
    Сжимает изображение до указанного размера.
    Конвертирует в JPEG с качеством 85%.
    """
    image = Image.open(io.BytesIO(file_bytes))
    
    if image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=85, optimize=True)
    output.seek(0)
    
    return output.getvalue()


async def upload_avatar(file_bytes: bytes, user_id: int) -> str:
    """
    Загружает аватарку в Object Storage.
    Возвращает публичный URL.
    """
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"Файл слишком большой. Максимум {MAX_FILE_SIZE // 1024 // 1024}MB")
    
    compressed = compress_image(file_bytes)
    
    # avatars/123/uuid.jpg — uuid чтобы браузер не кэшировал
    file_name = f"avatars/{user_id}/{uuid.uuid4().hex}.jpg"
    
    s3_client = get_s3_client()
    
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=file_name,
            Body=compressed,
            ContentType='image/jpeg',
            ACL='public-read',
        )
    except ClientError as e:
        raise ValueError(f"Ошибка загрузки в хранилище: {str(e)}")
    
    public_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{file_name}"
    
    return public_url


async def delete_avatar(avatar_url: str) -> bool:
    """Удаляет старую аватарку из Object Storage."""
    if not avatar_url:
        return True
    
    try:
        prefix = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/"
        if avatar_url.startswith(prefix):
            file_key = avatar_url[len(prefix):]
            
            s3_client = get_s3_client()
            s3_client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=file_key
            )
    except ClientError:
        pass
    
    return True
