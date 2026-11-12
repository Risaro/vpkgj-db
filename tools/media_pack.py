import argparse
import hashlib
import io
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "media")


def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def bundled(vpk):
    if not vpk or not os.path.exists(vpk):
        return set()
    z = zipfile.ZipFile(vpk)
    if "covers.pak" not in z.namelist():
        return set()
    return set(zipfile.ZipFile(io.BytesIO(z.read("covers.pak"))).namelist())


def wanted(skip):
    idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    out = set()
    keep = set()
    for items in idx["categories"].values():
        for it in items:
            icon = it.get("icon") or ""
            if icon and ":" not in icon:
                keep.add(icon)
            shots = it.get("shots") or []
            if shots and ":" not in shots[0]:
                keep.add(shots[0])
    covers = os.path.join(ROOT, "covers.json")
    if os.path.exists(covers):
        for v in json.load(open(covers, encoding="utf-8")).values():
            if v.get("s"):
                out.add(v["s"][0])
            if v.get("c"):
                out.add(v["c"])
    out = {p for p in out if p not in skip} | keep
    return sorted(p for p in out if os.path.isfile(os.path.join(MEDIA, p)))


def build(files, dst):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:
        for p in files:
            z.write(os.path.join(MEDIA, p), p)
    h = hashlib.sha1()
    with open(dst, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--vpk", default="")
    ap.add_argument("--out", default="/tmp/vpkgj_pack.zip")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    files = wanted(bundled(a.vpk))
    pid = build(files, a.out)
    size = os.path.getsize(a.out)
    print(f"{len(files)} files, {size / 1e6:.1f} MB, id {pid}")
    if a.dry:
        return
    import boto3
    from botocore.config import Config

    env = load_env(a.env)
    s3 = boto3.client(
        "s3",
        endpoint_url=env["S3_ENDPOINT"],
        aws_access_key_id=env["S3_ACCESS_KEY"],
        aws_secret_access_key=env["S3_SECRET_KEY"],
        region_name=env.get("S3_REGION", "us-east-1"),
        config=Config(proxies={}, retries={"max_attempts": 8, "mode": "standard"}),
    )
    bucket = env.get("S3_BUCKET", "vpkgj")
    s3.upload_file(a.out, bucket, "media/pack.zip", ExtraArgs={"ContentType": "application/zip", "CacheControl": "no-cache"})
    s3.put_object(Bucket=bucket, Key="media/pack.txt", Body=pid.encode(), ContentType="text/plain", CacheControl="no-cache")
    print("uploaded media/pack.zip and media/pack.txt")


if __name__ == "__main__":
    sys.exit(main())
