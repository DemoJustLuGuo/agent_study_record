import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime

from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.path_tools import get_abs_path
from utils.config_handler import chroma_conf
from model.factory import embeddings_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.file_handler import txt_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from utils.log import logger

class VectorStoreService:
    def __init__(self):
        self.persist_directory = get_abs_path(chroma_conf["persist_directory"])
        self.vector_store = Chroma(
            collection_name = chroma_conf["collection_name"],
            embedding_function = embeddings_model,
            persist_directory = self.persist_directory,
        )
        self.spliter = RecursiveCharacterTextSplitter (
            chunk_size = chroma_conf["chunk_size"],
            chunk_overlap = chroma_conf["chunk_overlap"],
            separators = chroma_conf["separator"],
            length_function = len,
        )

    def _md5_store_path(self) -> str:
        return get_abs_path(chroma_conf["md5_hex_store"])

    def _manifest_store_path(self) -> str:
        return get_abs_path(chroma_conf.get("index_manifest_store", "chroma_manifest.json"))

    def _snapshot_root_path(self) -> str:
        return get_abs_path(chroma_conf.get("lifecycle_snapshot_dir", "chroma_snapshots"))

    def _ensure_parent_dir(self, file_path:str):
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def _load_md5_store(self) -> set[str]:
        md5_store_path = self._md5_store_path()
        if not os.path.exists(md5_store_path):
            self._write_md5_store(set())
            return set()

        with open(md5_store_path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f.readlines() if line.strip()}

    def _write_md5_store(self, md5_values:set[str]):
        md5_store_path = self._md5_store_path()
        self._ensure_parent_dir(md5_store_path)
        with open(md5_store_path, "w", encoding="utf-8") as f:
            for md5_hex in sorted(md5_values):
                f.write(md5_hex + "\n")

    def _load_manifest(self) -> dict[str, dict]:
        manifest_store_path = self._manifest_store_path()
        if not os.path.exists(manifest_store_path):
            self._save_manifest({})
            return {}

        try:
            with open(manifest_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"索引清单读取失败，已回退为空清单: {str(e)}")
        return {}

    def _save_manifest(self, manifest:dict[str, dict]):
        manifest_store_path = self._manifest_store_path()
        self._ensure_parent_dir(manifest_store_path)
        with open(manifest_store_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _manifest_entry(self, md5_hex:str, source_type:str, operator:str) -> dict[str, str]:
        return {
            "md5": md5_hex,
            "source_type": source_type,
            "operator": operator,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _sync_md5_store_with_manifest(self, manifest:dict[str, dict]):
        md5_values = {
            item.get("md5", "")
            for item in manifest.values()
            if item.get("md5", "")
        }
        self._write_md5_store(md5_values)

    def _delete_vectors_by_source(self, source:str):
        try:
            self.vector_store.delete(where={"source": source})
            logger.info(f"已删除source={source}对应向量数据")
        except Exception as e:
            logger.error(f"删除source={source}对应向量数据失败: {str(e)}", exc_info=True)

    def _drop_removed_file_sources(self, manifest:dict[str, dict]) -> list[str]:
        removed_sources:list[str] = []
        for source, entry in list(manifest.items()):
            if entry.get("source_type") != "file_scan":
                continue
            if os.path.exists(source):
                continue

            self._delete_vectors_by_source(source)
            manifest.pop(source, None)
            removed_sources.append(source)
            logger.info(f"源文件已删除，已从索引清单移除: {source}")

        return removed_sources

    def _normalize_source_path(self, source_path:str) -> str:
        return os.path.normpath(os.path.abspath(source_path))

    def sync_removed_sources(self) -> dict[str, object]:
        manifest = self._load_manifest()
        removed_sources = self._drop_removed_file_sources(manifest)
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)
        return {
            "removed_source_count": len(removed_sources),
            "removed_sources": removed_sources,
        }

    def create_snapshot(self, tag:str="") -> str:
        snapshot_root = self._snapshot_root_path()
        os.makedirs(snapshot_root, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tag = "".join(c for c in tag.strip() if c.isalnum() or c in ("-", "_"))
        snapshot_name = f"{timestamp}_{safe_tag}" if safe_tag else timestamp
        snapshot_path = os.path.join(snapshot_root, snapshot_name)

        os.makedirs(snapshot_path, exist_ok=False)

        snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
        if os.path.exists(self.persist_directory):
            shutil.copytree(self.persist_directory, snapshot_vector_path)
        else:
            os.makedirs(snapshot_vector_path, exist_ok=True)

        md5_store_path = self._md5_store_path()
        snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
        if os.path.exists(md5_store_path):
            shutil.copy2(md5_store_path, snapshot_md5_path)
        else:
            open(snapshot_md5_path, "w", encoding="utf-8").close()

        manifest_store_path = self._manifest_store_path()
        snapshot_manifest_path = os.path.join(snapshot_path, os.path.basename(manifest_store_path))
        if os.path.exists(manifest_store_path):
            shutil.copy2(manifest_store_path, snapshot_manifest_path)
        else:
            with open(snapshot_manifest_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        logger.info(f"向量生命周期快照创建成功: {snapshot_name}")
        return snapshot_name

    def rollback_snapshot(self, snapshot_name:str) -> str:
        snapshot_path = os.path.join(self._snapshot_root_path(), snapshot_name)
        if not os.path.isdir(snapshot_path):
            raise FileNotFoundError(f"快照不存在: {snapshot_name}")

        snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
        if not os.path.isdir(snapshot_vector_path):
            raise FileNotFoundError(f"快照向量目录不存在: {snapshot_vector_path}")

        if os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory)
        shutil.copytree(snapshot_vector_path, self.persist_directory)

        md5_store_path = self._md5_store_path()
        manifest_store_path = self._manifest_store_path()
        snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
        snapshot_manifest_path = os.path.join(snapshot_path, os.path.basename(manifest_store_path))

        self._ensure_parent_dir(md5_store_path)
        self._ensure_parent_dir(manifest_store_path)

        if os.path.exists(snapshot_md5_path):
            shutil.copy2(snapshot_md5_path, md5_store_path)
        else:
            open(md5_store_path, "w", encoding="utf-8").close()

        if os.path.exists(snapshot_manifest_path):
            shutil.copy2(snapshot_manifest_path, manifest_store_path)
        else:
            with open(manifest_store_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        self.vector_store = Chroma(
            collection_name = chroma_conf["collection_name"],
            embedding_function = embeddings_model,
            persist_directory = self.persist_directory,
        )

        logger.info(f"已回滚到向量生命周期快照: {snapshot_name}")
        return snapshot_name

    def _check_md5_hex(self, md5_for_check:str) -> bool:
        return md5_for_check in self._load_md5_store()

    def _save_md5_hex(self, md5_hex:str):
        md5_values = self._load_md5_store()
        if md5_hex in md5_values:
            return
        md5_values.add(md5_hex)
        self._write_md5_store(md5_values)

    def upload_text(self, data:str, filename:str, operator:str="admin") -> str:
        text = (data or "").strip()
        if not text:
            return "【失败】文本内容为空"

        md5_hex = hashlib.md5(text.encode("utf-8")).hexdigest()
        if self._check_md5_hex(md5_hex):
            logger.info("文本内容已存在于知识库中，跳过入库")
            return "【跳过】内容已经存在于知识库中"

        if len(text) > chroma_conf["chunk_size"]:
            knowledge_chunks:list[str] = self.spliter.split_text(text)
        else:
            knowledge_chunks = [text]

        if not knowledge_chunks:
            logger.warning("文本切分后为空，未执行入库")
            return "【失败】文本切分后为空"

        # 同名文本重复上传时先删旧向量，再覆盖新版本。
        self._delete_vectors_by_source(filename)

        indexed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = {
            "source": filename,
            "create_time": indexed_time,
            "operator": operator,
            "source_md5": md5_hex,
            "source_type": "text_upload",
        }

        self.vector_store.add_texts(
            knowledge_chunks,
            metadatas=[metadata for _ in knowledge_chunks],
        )

        manifest = self._load_manifest()
        manifest[filename] = self._manifest_entry(
            md5_hex=md5_hex,
            source_type="text_upload",
            operator=operator,
        )
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)

        logger.info(f"文本{filename}已成功上传到向量数据库")
        return "【成功】内容已成功添加到知识库中"
        
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_documents(self):
        manifest = self._load_manifest()

        def get_file_documents(read_path:str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)

            return []
        
        allowed_files_path:tuple[str, ...] = listdir_with_allowed_type(
        get_abs_path(chroma_conf["data_path"]),
        tuple(chroma_conf["allowed_knowledge_file_type"])
        )

        add_count = 0
        update_count = 0

        for path in allowed_files_path:
            source_path = self._normalize_source_path(path)
            md5_hex = get_file_md5_hex(path)
            if not md5_hex:
                logger.warning(f"文件{path}的MD5计算失败，跳过")
                continue

            old_entry = manifest.get(source_path, {})
            old_md5 = old_entry.get("md5", "")

            if old_md5 == md5_hex and self._check_md5_hex(md5_hex):
                logger.info(f"文件{path}已处理过，跳过")
                continue

            if not old_entry and self._check_md5_hex(md5_hex):
                # 兼容历史只记录MD5、未记录source映射的老版本数据。
                manifest[source_path] = self._manifest_entry(
                    md5_hex=md5_hex,
                    source_type="file_scan",
                    operator="system",
                )
                logger.info(f"文件{path}已存在于MD5记录，已补齐source映射")
                continue

            if old_md5 and old_md5 != md5_hex:
                self._delete_vectors_by_source(source_path)
                update_count += 1

            try:
                documents : list[Document] = get_file_documents(path)
                if not documents:
                    logger.warning(f"文件{path}没有加载到任何文档，可能是格式不受支持")
                    continue
                split_document : list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"文件{path}没有被分割成任何文档，可能是因为chunk_size设置过大")
                    continue

                indexed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for doc in split_document:
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata["source"] = source_path
                    doc.metadata["source_md5"] = md5_hex
                    doc.metadata["source_type"] = "file_scan"
                    doc.metadata["indexed_at"] = indexed_time

                self.vector_store.add_documents(split_document)
                manifest[source_path] = self._manifest_entry(
                    md5_hex=md5_hex,
                    source_type="file_scan",
                    operator="system",
                )
                add_count += 1
                logger.info(f"文件{path}已成功加载到向量数据库")
            except Exception as e:
                logger.error(f"加载文件{path}时发生错误: {str(e)}",exc_info=True)
                continue

        removed_sources = self._drop_removed_file_sources(manifest)
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)

        logger.info(
            "向量库同步完成: 新增/重建=%s, 更新=%s, 删除失效源=%s",
            add_count,
            update_count,
            len(removed_sources),
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="向量库生命周期管理工具")
    sub_parser = parser.add_subparsers(dest="command")

    sub_parser.add_parser("load", help="扫描data目录并增量同步向量库")
    sub_parser.add_parser("sync", help="仅执行删除源文件同步清理")

    snapshot_parser = sub_parser.add_parser("snapshot", help="创建向量库快照")
    snapshot_parser.add_argument("--tag", default="", help="快照标签，可选")

    rollback_parser = sub_parser.add_parser("rollback", help="回滚到指定快照")
    rollback_parser.add_argument("snapshot", help="快照目录名")

    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()

    vector_store_service = VectorStoreService()

    if args.command in (None, "load"):
        vector_store_service.load_documents()
    elif args.command == "sync":
        sync_result = vector_store_service.sync_removed_sources()
        print(json.dumps(sync_result, ensure_ascii=False, indent=2))
    elif args.command == "snapshot":
        snapshot_name = vector_store_service.create_snapshot(args.tag)
        print(f"snapshot created: {snapshot_name}")
    elif args.command == "rollback":
        snapshot_name = vector_store_service.rollback_snapshot(args.snapshot)
        print(f"snapshot restored: {snapshot_name}")
