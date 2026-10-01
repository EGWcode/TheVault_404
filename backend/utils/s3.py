# utils/s3.py
# The Vault Campus Marketplace
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


def upload_image_to_s3(file, folder="uploads"):
    """
    Uploads an image file to S3 and returns the public URL.
    
    Args:
        file: file object from request.files
        folder: subfolder in S3 bucket (e.g. 'storefronts', 'listings')
    
    Returns:
        Public S3 URL string or None if upload fails
    """
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