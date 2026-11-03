import argparse
import csv
import shutil
import sys
import urllib.request
from pathlib import Path

from build_index import CATALOG, MEDIA, SCHEMA, convert_urls, split_urls


def columns(cat):
    with (CATALOG / f"{cat}.tsv").open(encoding="utf-8") as f:
        return f.readline().rstrip("\n").split("\t")


def remote_size(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "VPKGJ/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            n = r.headers.get("Content-Length")
            return int(n) if n and n.isdigit() else 0
    except Exception:
        return 0


def copy_media(key, files, prefix):
    out = []
    dest = MEDIA / key
    dest.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(files, start=1):
        src = Path(src)
        if src.as_posix().startswith(("http://", "https://")):
            out.append(src.as_posix())
            continue
        name = f"{prefix}{i if prefix != 'icon' else ''}{src.suffix.lower()}"
        if src.resolve() != (dest / name).resolve():
            shutil.copyfile(src, dest / name)
        out.append(f"{key}/{name}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Добавить или обновить запись в каталоге")
    ap.add_argument("category", choices=sorted(SCHEMA))
    ap.add_argument("--set", nargs=2, action="append", metavar=("KEY", "VALUE"), default=[])
    ap.add_argument("--icon")
    ap.add_argument("--shot", action="append", default=[])
    args = ap.parse_args()

    cat = args.category
    cols = columns(cat)
    row = {k: v for k, v in args.set}
    unknown = [k for k in row if k not in cols]
    if unknown:
        sys.exit(f"нет колонок {unknown}, есть: {cols}")
    key_col = "id" if cat == "plugins" else "titleid"
    key = row.get(key_col)
    if not key:
        sys.exit(f"нужен --set {key_col} ...")

    if args.icon:
        row["icon"] = copy_media(key, [args.icon], "icon")[0]
    if args.shot:
        row["shots"] = ";".join(copy_media(key, args.shot, "shot"))
    for col in SCHEMA[cat]["urls"]:
        if row.get(col):
            row[col] = convert_urls(row[col])
    if "size" in cols and not row.get("size"):
        total = 0
        for col in SCHEMA[cat]["urls"]:
            if col == "mirror":
                continue
            for part in row.get(col, "").split(";"):
                urls = split_urls(part)
                if urls:
                    total += remote_size(urls[0])
        if total:
            row["size"] = str(total)

    path = CATALOG / f"{cat}.tsv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    for old in rows:
        if old.get(key_col) == key and old.get("region", "") == row.get("region", old.get("region", "")):
            old.update(row)
            break
    else:
        rows.append({c: row.get(c, "") for c in cols})
    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join((r.get(c) or "").replace("\t", " ").replace("\r", "").replace("\n", "\\n") for c in cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{cat}.tsv: {key} записан")


if __name__ == "__main__":
    main()
