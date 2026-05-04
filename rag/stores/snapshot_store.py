from __future__ import annotations

import json
import os
import shutil
from datetime import datetime


def sanitize_snapshot_tag(tag: str) -> str:
    return "".join(c for c in (tag or "").strip() if c.isalnum() or c in ("-", "_"))


def resolve_snapshot_path(snapshot_root: str, snapshot_name: str) -> str:
    name = (snapshot_name or "").strip()
    if not name:
        raise ValueError("快照名称不能为空")
    if name != os.path.basename(name) or sanitize_snapshot_tag(name) != name:
        raise ValueError("快照名称只能包含字母、数字、短横线和下划线")

    root_path = os.path.abspath(snapshot_root)
    snapshot_path = os.path.abspath(os.path.join(root_path, name))
    if os.path.commonpath([root_path, snapshot_path]) != root_path:
        raise ValueError("快照路径越界")
    return snapshot_path


def create_snapshot_files(
    *,
    snapshot_root: str,
    persist_directory: str,
    md5_store_path: str,
    manifest_store_path: str,
    tag: str = "",
) -> str:
    os.makedirs(snapshot_root, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_tag = sanitize_snapshot_tag(tag)
    snapshot_name = f"{timestamp}_{safe_tag}" if safe_tag else timestamp
    snapshot_path = os.path.join(snapshot_root, snapshot_name)
    os.makedirs(snapshot_path, exist_ok=False)

    snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
    if os.path.exists(persist_directory):
        shutil.copytree(persist_directory, snapshot_vector_path)
    else:
        os.makedirs(snapshot_vector_path, exist_ok=True)

    snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
    if os.path.exists(md5_store_path):
        shutil.copy2(md5_store_path, snapshot_md5_path)
    else:
        open(snapshot_md5_path, "w", encoding="utf-8").close()

    snapshot_manifest_path = os.path.join(
        snapshot_path, os.path.basename(manifest_store_path)
    )
    if os.path.exists(manifest_store_path):
        shutil.copy2(manifest_store_path, snapshot_manifest_path)
    else:
        with open(snapshot_manifest_path, "w", encoding="utf-8") as file_obj:
            json.dump({}, file_obj, ensure_ascii=False, indent=2)

    return snapshot_name


def restore_snapshot_files(
    *,
    snapshot_root: str,
    persist_directory: str,
    md5_store_path: str,
    manifest_store_path: str,
    snapshot_name: str,
) -> str:
    snapshot_path = resolve_snapshot_path(snapshot_root, snapshot_name)
    if not os.path.isdir(snapshot_path):
        raise FileNotFoundError(f"快照不存在: {snapshot_name}")

    snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
    if not os.path.isdir(snapshot_vector_path):
        raise FileNotFoundError(f"快照向量目录不存在: {snapshot_vector_path}")

    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)
    shutil.copytree(snapshot_vector_path, persist_directory)

    snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
    snapshot_manifest_path = os.path.join(
        snapshot_path, os.path.basename(manifest_store_path)
    )

    md5_parent = os.path.dirname(md5_store_path)
    manifest_parent = os.path.dirname(manifest_store_path)
    if md5_parent:
        os.makedirs(md5_parent, exist_ok=True)
    if manifest_parent:
        os.makedirs(manifest_parent, exist_ok=True)

    if os.path.exists(snapshot_md5_path):
        shutil.copy2(snapshot_md5_path, md5_store_path)
    else:
        open(md5_store_path, "w", encoding="utf-8").close()

    if os.path.exists(snapshot_manifest_path):
        shutil.copy2(snapshot_manifest_path, manifest_store_path)
    else:
        with open(manifest_store_path, "w", encoding="utf-8") as file_obj:
            json.dump({}, file_obj, ensure_ascii=False, indent=2)

    return snapshot_name
