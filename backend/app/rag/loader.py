import json
import logging
from pathlib import Path
import pickle
import re
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class RagStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config: dict = {}
        self.index = None
        self.chunks: list = []
        self.documents: list = []
        self.model = None

    def _enrich_chunks(self) -> None:
        """Enrich all chunks with scheme_name, slug, url, and category metadata."""
        # 1. Parse metadata from documents.pkl if available
        doc_meta = []
        docs_file = self.data_dir / "documents.pkl"
        if docs_file.is_file():
            try:
                with docs_file.open("rb") as f:
                    self.documents = pickle.load(f)
                for d in self.documents:
                    m_name = re.search(r"scheme_name:\s*(.+)", d)
                    m_slug = re.search(r"slug:\s*(.+)", d)
                    m_cat = re.search(r"schemeCategory:\s*(.+)", d)
                    name = m_name.group(1).strip(" \"'") if m_name else ""
                    slug = m_slug.group(1).strip(" \"'") if m_slug else ""
                    cat = m_cat.group(1).strip() if m_cat else ""
                    url = f"https://www.myscheme.gov.in/schemes/{slug}" if slug else None
                    doc_meta.append({"scheme_name": name, "slug": slug, "url": url, "category": cat})
                logger.info("Parsed %d documents metadata for RAG chunks", len(doc_meta))
            except Exception as e:
                logger.warning("Could not parse documents.pkl metadata: %s", e)

        # 2. Build row_number -> slug mapping for new_csv chunks
        row_to_slug = {}
        for c in self.chunks:
            if not isinstance(c, dict):
                continue
            meta = c.get("metadata") or {}
            rn = meta.get("row_number")
            if rn is not None and rn not in row_to_slug:
                t = c.get("text", "")
                m_slug = re.search(r"Scheme Slug:\s*([^\n\r]+)", t)
                if m_slug:
                    row_to_slug[rn] = m_slug.group(1).strip()
                else:
                    m_url = re.search(r"https://www.myscheme.gov.in/schemes/([a-zA-Z0-9_\-]+)", t)
                    if m_url:
                        row_to_slug[rn] = m_url.group(1)

        # 3. Enrich every chunk
        current_doc_idx = 0
        enriched_count = 0

        for c in self.chunks:
            if not isinstance(c, dict):
                continue
            t = c.get("text", "")
            meta = c.get("metadata")
            if not isinstance(meta, dict):
                meta = {}
                c["metadata"] = meta

            # Track doc index for existing_rag chunks
            m_doc = re.search(r"Dataset record ID:\s*(\d+)", t)
            if m_doc:
                current_doc_idx = int(m_doc.group(1))

            # Enrich from documents if scheme_name missing
            if not meta.get("scheme_name") and current_doc_idx < len(doc_meta):
                dm = doc_meta[current_doc_idx]
                meta["scheme_name"] = dm["scheme_name"]
                meta["slug"] = dm["slug"]
                meta["url"] = dm["url"]
                meta["category"] = dm["category"]
                meta["source"] = "myscheme.gov.in"
                enriched_count += 1
            elif not meta.get("scheme_name"):
                # Fallback: extract from chunk text
                m_sn = re.search(r'scheme_name:\s*["“]?([^"\n”]+)', t, re.IGNORECASE)
                if not m_sn:
                    m_sn = re.search(r'Scheme Name:\s*([^\n\r]+)', t, re.IGNORECASE)
                if m_sn:
                    meta["scheme_name"] = m_sn.group(1).strip(' "\'')

            # Ensure URL is populated
            if not meta.get("url"):
                slug = meta.get("slug")
                rn = meta.get("row_number")
                if not slug and rn in row_to_slug:
                    slug = row_to_slug[rn]
                    meta["slug"] = slug
                if not slug:
                    m_slug = re.search(r"Scheme Slug:\s*([^\n\r]+)", t)
                    if m_slug:
                        slug = m_slug.group(1).strip()
                        meta["slug"] = slug
                if slug:
                    meta["url"] = f"https://www.myscheme.gov.in/schemes/{slug}"

        logger.info("Enriched %d RAG chunks with scheme metadata", enriched_count)

    def load(self) -> None:
        required = ["config.json", "schemes.faiss", "chunks.pkl"]
        missing = [name for name in required if not (self.data_dir / name).is_file()]
        if missing:
            raise FileNotFoundError("Missing RAG artifacts: " + ", ".join(missing))
        self.config = json.loads((self.data_dir / "config.json").read_text(encoding="utf-8"))
        self.index = faiss.read_index(str(self.data_dir / "schemes.faiss"))
        with (self.data_dir / "chunks.pkl").open("rb") as file:
            self.chunks = pickle.load(file)
        if self.index.d != self.config.get("embedding_dimension"):
            raise ValueError("FAISS dimension does not match the saved RAG configuration")
        if self.index.ntotal != len(self.chunks):
            raise ValueError("FAISS index and chunk mapping have different sizes")

        # Enrich chunks with metadata
        self._enrich_chunks()

        self.model = SentenceTransformer(self.config["embedding_model"])
