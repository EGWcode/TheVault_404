# utils/s3.py
# The Pirate Cove Campus Marketplace
# Created by Day Ekoi - Iteration 5 4/10/26
# Handles all S3 image upload functionality

import boto3
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

# S3 client setup
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-2")
)

BUCKET_NAME = os.getenv("AWS_S3_BUCKET")
REGION = os.getenv("AWS_REGION", "us-east-2")

# Added by Ethan Williams 10/20/26: save to static/uploads/ when AWS_S3_BUCKET isn't set (local dev)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOCAL_UPLOAD_ROOT = os.path.join(PROJECT_ROOT, "static", "uploads")


def _safe_folder(folder):
    """
    Keeps only simple folder names like 'storefronts/logos' so a request can't
    write outside static/uploads (no '..', no absolute paths, no odd characters).
    """
    parts = []
    for part in str(folder or "uploads").split("/"):
        cleaned = "".join(ch for ch in part.lower() if ch.isalnum() or ch in "-_")
        if cleaned:
            parts.append(cleaned)
    return "/".join(parts) or "uploads"


def _save_locally(file, folder):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    relative_path = f"{_safe_folder(folder)}/{uuid.uuid4().hex}.{ext}"
    destination = os.path.join(LOCAL_UPLOAD_ROOT, *relative_path.split("/"))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    file.save(destination)
    return f"/static/uploads/{relative_path}"


def upload_image_to_s3(file, folder="uploads"):
    """
    Uploads an image file to S3 and returns the public URL.
    
    Args:
        file: file object from request.files
        folder: subfolder in S3 bucket (e.g. 'storefronts', 'listings')
    
    Returns:
        Public S3 URL string or None if upload fails
        (or a /static/uploads/... URL in local development, see _save_locally)
    """
    if not BUCKET_NAME:
        try:
            return _save_locally(file, folder)
        except Exception as e:
            print(f"Local upload error: {e}")
            return None

    try:
        # generate unique filename
        ext = file.filename.rsplit(".", 1)[-1].lower()
        filename = f"{folder}/{uuid.uuid4().hex}.{ext}"

        # upload to S3 - bucket policy handles public read access
        s3_client.upload_fileobj(
            file,
            BUCKET_NAME,
            filename,
            ExtraArgs={"ContentType": file.content_type}
        )

        # return public URL
        url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"
        return url

    except Exception as e:
        print(f"S3 upload error: {e}")
        return None