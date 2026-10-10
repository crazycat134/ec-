"""Lumix GF9 照片导入：查找 DCIM → MD5 去重 → Pillow 压缩 → 写入 photos 表。

按文件名分组：形如「1.1.JPG」「1.2.JPG」的照片，小数点前为商品号、小数点后为张号，
导入时自动按商品号创建/关联商品，便于 Automa 直接读取分组数据。
"""
import hashlib
import os
import re
import string
from pathlib import Path

from PIL import Image, ImageOps

from . import db
from .config import PROJECT_ROOT

JPEG_EXTS = (".jpg", ".jpeg")
PRODUCT_NAME_RE = re.compile(r"^(\d+)\.(\d+)$")


def parse_product_name(stem: str):
    """解析文件名（不含扩展名）为 (商品号, 张号)；不匹配返回 (None, None)。"""
    m = PRODUCT_NAME_RE.match(stem.strip())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def md5_of_file(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_camera_roots(cfg) -> list:
    """返回所有候选相机根目录（存在 DCIM 子目录的路径）。"""
    roots = []

    def add_if_has_dcim(p):
        if p.is_dir() and (p / cfg.camera_dcim_subdir).is_dir() and p not in roots:
            roots.append(p)

    # 1) 用户显式指定（如 E:\ 或 /media/DCIM 所在盘）
    if cfg.camera_drive and cfg.camera_drive.strip().lower() != "auto":
        add_if_has_dcim(Path(cfg.camera_drive.strip()))

    # 2) 自动检测
    if cfg.camera_auto_detect:
        if os.name == "nt":
            for letter in string.ascii_uppercase:
                add_if_has_dcim(Path(f"{letter}:\\"))
        else:
            for base in (Path("/media"), Path("/mnt"), Path("/run/media")):
                if not base.is_dir():
                    continue
                for child in sorted(base.iterdir()):
                    add_if_has_dcim(child)
    return roots


def scan_jpgs(root: Path, dcim_subdir: str) -> list:
    dcim = Path(root) / dcim_subdir
    if not dcim.is_dir():
        return []
    return [p for p in sorted(dcim.rglob("*")) if p.suffix.lower() in JPEG_EXTS]


def process_image(src: Path, dest: Path, max_long_edge: int, quality: int) -> None:
    """自动旋转（按 EXIF）→ 转 RGB → 限制长边 → JPEG 保存。"""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        w, h = im.size
        long_edge = max(w, h)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        im.save(dest, "JPEG", quality=quality, optimize=True)


def import_photos(cfg):
    """执行一次照片导入。返回 {status, imported, photos, products}。"""
    db.init_db()

    import_dir = Path(cfg.camera_import_dir)
    if not import_dir.is_absolute():
        import_dir = PROJECT_ROOT / import_dir
    import_dir.mkdir(parents=True, exist_ok=True)

    roots = resolve_camera_roots(cfg)
    status = "ok" if roots else "no_camera"
    imported = []
    photos = []
    groups = {}  # 商品号 -> [(photo_id, photo_no), ...]

    conn = db.get_db()
    try:
        seen = {row["file_hash"] for row in conn.execute("SELECT file_hash FROM photos")}

        for root in roots:
            for src in scan_jpgs(root, cfg.camera_dcim_subdir):
                file_hash = md5_of_file(src)
                if file_hash in seen:
                    continue  # MD5 去重，已导入的跳过

                product_no, photo_no = parse_product_name(src.stem)
                dest = import_dir / f"{file_hash[:8]}.jpg"
                process_image(src, dest, cfg.camera_max_long_edge, cfg.camera_jpeg_quality)

                cur = conn.execute(
                    "INSERT INTO photos (local_path, file_hash, product_no, photo_no) "
                    "VALUES (?, ?, ?, ?)",
                    (str(dest), file_hash, product_no, photo_no),
                )
                seen.add(file_hash)
                imported.append(str(dest))
                photos.append({
                    "id": cur.lastrowid,
                    "local_path": str(dest),
                    "file_hash": file_hash,
                    "product_no": product_no,
                    "photo_no": photo_no,
                })
                if product_no is not None:
                    groups.setdefault(product_no, []).append((cur.lastrowid, photo_no))

        # 按商品号分组：为每组创建或复用商品，并关联照片
        # 保护规则：已转正式（is_draft=0）的商品不再自动并入同 N 的新照片
        products = []
        blocked = []
        for product_no in sorted(groups):
            row = conn.execute("SELECT id, is_draft FROM products WHERE product_no = ?", (product_no,)).fetchone()
            if row is not None and row["is_draft"] == 0:
                blocked.append({
                    "product_no": product_no,
                    "product_id": row["id"],
                    "photo_count": len(groups[product_no]),
                })
                continue  # 不并入；照片保留 product_no，等待显式并入（PUT photo_ids）
            if row is not None:
                pid = row["id"]
                created = False
            else:
                cur = conn.execute(
                    "INSERT INTO products (title, price, status, description, product_no, is_draft) "
                    "VALUES (?, 0, 'CLEAN', '', ?, 1)",
                    (f"商品 {product_no}", product_no),
                )
                pid = cur.lastrowid
                created = True
            ids = [i for i, _ in groups[product_no]]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE photos SET product_id = ? WHERE id IN ({placeholders})",
                [pid] + ids,
            )
            count = conn.execute("SELECT COUNT(*) AS c FROM photos WHERE product_id = ?", (pid,)).fetchone()["c"]
            products.append({"id": pid, "product_no": product_no, "created": created, "photo_count": count})
        conn.commit()
    finally:
        conn.close()

    return {
        "status": status,
        "imported": imported,
        "photos": photos,
        "products": products,
        "blocked": blocked,
    }


if __name__ == "__main__":
    # 手动测试：python -m app.camera_import
    from .config import Config

    print(import_photos(Config()))
