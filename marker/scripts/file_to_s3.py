import json
import shutil
import datetime
from pathlib import Path
import boto3

from huggingface_hub import snapshot_download

import click

S3_API_URL = "https://1afbe4656a6b40d982ab5e730a39f6b9.r2.cloudflarestorage.com"

@click.command(help="Uploads files to an S3 bucket")
@click.argument("filepath", type=str)
@click.argument("s3_path", type=str)
@click.option("--bucket_name", type=str, default="datalab")
@click.option("--access_key_id", type=str, default="<access_key_id>")
@click.option("--access_key_secret", type=str, default="<access_key_secret>")
def main(filepath: str, s3_path: str, bucket_name: str, access_key_id: str, access_key_secret: str):
    filepath = Path(filepath)
    # Upload the files to S3
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_API_URL,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=access_key_secret,
        region_name="enam"
    )

    s3_key = f"{s3_path}/{filepath.name}"

    try:
        s3_client.upload_file(
            str(filepath),
            bucket_name,
            s3_key
        )
    except Exception as e:
        print(f"Error uploading {filepath}: {str(e)}")

    print(f"Uploaded files to {s3_path}")

if __name__ == "__main__":
    main()



