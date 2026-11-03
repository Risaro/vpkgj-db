import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
MEDIA = ROOT / "media"
DEFAULT_REPO = "Risaro/vpkgj-db/main"

SCHEMA = {
    "ports": {"required": ["titleid", "name", "version", "vpk"], "urls": ["vpk", "data", "mirror"]},
    "homebrew": {"required": ["titleid", "name", "version", "vpk"], "urls": ["vpk", "data", "mirror"]},
    "translations": {"required": ["titleid", "name", "install", "url"], "urls": ["url", "mirror"]},
    "plugins": {"required": ["id", "name", "url", "tai_section"], "urls": ["url", "mirror"]},
    "games": {"required": ["titleid", "region", "name", "pkg"], "urls": ["pkg", "mirror"]},
}
INSTALL = {"repatch", "plugin", "repatch+plugin", "data", "vpk"}
TITLEID = re.compile(r"^[A-Z]{4}\d{5}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DRIVE_ID = [
    re.compile(r"drive\.google\.com/file/d/([\w-]+)"),
    re.compile(r"drive\.google\.com/(?:open|uc)\?(?:.*&)?id=([\w-]+)"),
    re.compile(r"drive\.usercontent\.google\.com/download\?(?:.*&)?id=([\w-]+)"),
]
GITHUB_BLOB = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/(.+)$")


def direct(url):
    for rx in DRIVE_ID:
        m = rx.search(url)
        if m:
            return f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"
    m = GITHUB_BLOB.match(url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return url


def split_urls(value):
    return [u.strip() for part in value.split(";") for u in part.split("|") if u.strip()]


def convert_urls(value):
    return ";".join("|".join(direct(u.strip()) for u in part.split("|") if u.strip()) for part in value.split(";") if part.strip())


def media_list(value):
    return [p for p in value.split(";") if p] if value else []


def check_row(cat, n, row, errors):
    where = f"{cat}.tsv:{n}"
    for key in SCHEMA[cat]["required"]:
        if not row.get(key):
            errors.append(f"{where}: пустое поле {key}")
    tid = row.get("titleid")
    if tid and not TITLEID.match(tid):
        errors.append(f"{where}: неверный titleid {tid}")
    for key in SCHEMA[cat]["urls"]:
        for url in split_urls(row.get(key, "")):
            if not url.startswith(("http://", "https://")):
                errors.append(f"{where}: {key} не ссылка: {url}")
    if row.get("size") and not row["size"].isdigit():
        errors.append(f"{where}: size должен быть числом байт")
    if row.get("sha256") and not SHA256.match(row["sha256"]):
        errors.append(f"{where}: неверный sha256")
    if cat == "translations" and row.get("install") and row["install"] not in INSTALL:
        errors.append(f"{where}: install должен быть одним из {sorted(INSTALL)}")
    for rel in media_list(row.get("icon")) + media_list(row.get("shots")):
        if not rel.startswith(("http://", "https://")) and not (MEDIA / rel).is_file():
            errors.append(f"{where}: нет файла media/{rel}")


def load(cat, errors):
    path = CATALOG / f"{cat}.tsv"
    items = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for n, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            if not any(row.values()):
                continue
            check_row(cat, n, row, errors)
            for key in SCHEMA[cat]["urls"]:
                if row.get(key):
                    row[key] = convert_urls(row[key])
            row["icon"] = media_list(row.get("icon"))[:1]
            row["icon"] = row["icon"][0] if row["icon"] else ""
            row["shots"] = media_list(row.get("shots"))
            if row.get("size"):
                row["size"] = int(row["size"]) if row["size"].isdigit() else 0
            items.append({k: v for k, v in row.items() if v not in ("", [])})
    seen = set()
    key = "id" if cat == "plugins" else "titleid"
    for it in items:
        k = (it.get(key), it.get("region"))
        if k in seen:
            errors.append(f"{cat}.tsv: дубликат {k[0]}")
        seen.add(k)
    return items


def check_links(index):
    bad = []
    for cat, items in index["categories"].items():
        for it in items:
            for key in SCHEMA[cat]["urls"]:
                for url in split_urls(it.get(key, "")):
                    req = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "VPKGJ/1.0"})
                    try:
                        urllib.request.urlopen(req, timeout=30)
                    except Exception as e:
                        bad.append(f"{cat}/{it.get('titleid') or it.get('id')} {key}: {e}")
    return bad


def main():
    errors = []
    cats = {cat: load(cat, errors) for cat in SCHEMA}
    plugin_ids = {p["id"].lower() for p in cats["plugins"]}
    for cat, items in cats.items():
        for it in items:
            for dep in [d.strip().lower() for d in it.get("requires", "").replace(";", ",").split(",") if d.strip()]:
                if dep not in plugin_ids:
                    errors.append(f"{cat}/{it.get('titleid') or it.get('id')}: нет плагина {dep} в plugins.tsv")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    body = json.dumps(cats, ensure_ascii=False, sort_keys=True)
    index = {"version": hashlib.sha1(body.encode()).hexdigest()[:12], "categories": cats}
    repo = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--repo=")), DEFAULT_REPO)
    index["media"] = f"https://raw.githubusercontent.com/{repo}/media/"
    if "--check-links" in sys.argv:
        bad = check_links(index)
        if bad:
            print("\n".join(bad))
            sys.exit(1)
    out = ROOT / "index.json"
    text = json.dumps(index, ensure_ascii=False, indent=1) + "\n"
    if "--verify" in sys.argv:
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            print("index.json устарел, запусти python3 tools/build_index.py и закоммить его")
            sys.exit(1)
        print(f"index.json {index['version']} актуален")
        return
    out.write_text(text, encoding="utf-8")
    print(f"index.json {index['version']}: " + ", ".join(f"{c} {len(v)}" for c, v in cats.items()))


if __name__ == "__main__":
    main()
