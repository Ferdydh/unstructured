import hashlib
import json
import os.path
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from unstructured.ingest.interfaces import (
    ChunkingConfig,
)
from unstructured.ingest.logger import logger
from unstructured.ingest.pipeline.interfaces import ReformatNode
from unstructured.staging.base import elements_from_json, elements_to_dicts


@dataclass
class Chunker(ReformatNode):
    chunking_config: ChunkingConfig

    def initialize(self):
        logger.info(
            f"Running chunking node. Chunking config: {self.chunking_config.to_json()}]",
        )
        super().initialize()

    def create_hash(self) -> str:
        hash_dict = self.chunking_config.to_dict()
        return hashlib.sha256(json.dumps(hash_dict, sort_keys=True).encode()).hexdigest()[:32]

    def run(self, elements_json: str) -> Optional[str]:
        try:
            elements_json_filename = os.path.basename(elements_json)
            filename_ext = os.path.basename(elements_json_filename)
            filename = os.path.splitext(filename_ext)[0]
            hashed_filename = hashlib.sha256(
                f"{self.create_hash()}{filename}".encode(),
            ).hexdigest()[:32]
            json_filename = f"{hashed_filename}.json"
            json_path = (Path(self.get_path()) / json_filename).resolve()
            self.pipeline_context.ingest_docs_map[hashed_filename] = (
                self.pipeline_context.ingest_docs_map[filename]
            )
            if (
                not self.pipeline_context.reprocess
                and json_path.is_file()
                and json_path.stat().st_size
            ):
                logger.debug(f"File exists: {json_path}, skipping chunking")
                return str(json_path)
            elements = elements_from_json(filename=elements_json)
            chunked_elements = self.chunking_config.chunk(elements=elements)
            element_dicts = elements_to_dicts(chunked_elements)
            with open(json_path, "w", encoding="utf8") as output_f:
                logger.info(f"writing chunking content to {json_path}")
                json.dump(element_dicts, output_f, ensure_ascii=False, indent=2)
            return str(json_path)
        except Exception as e:
            if self.pipeline_context.raise_on_error:
                raise
            logger.error(f"failed to run chunking on file {elements_json}, {e}", exc_info=True)
            return None

    def get_path(self) -> Path:
        return (Path(self.pipeline_context.work_dir) / "chunked").resolve()
