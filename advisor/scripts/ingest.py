"""Step 5.2 - chunk, embed and store the knowledge base in ChromaDB.

Run from advisor/ (or inside the container):
    python -m scripts.ingest                       # ingest everything in knowledge/manifest.yaml
    python -m scripts.ingest --check "what is Section 80C"   # CP-5.2 top-3 check
    python -m scripts.ingest --strict              # fail if any doc is verified: false

Idempotent: chunk ids are deterministic and a doc's old chunks are deleted first,
so running it twice never duplicates anything.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

import yaml
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import settings
from app.retriever import Retriever

REQUIRED = ["id", "title", "file", "source_url", "retrieved_on", "as_of", "licence"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_manifest(kb: Path) -> list[dict]:
    docs = yaml.safe_load((kb / "manifest.yaml").read_text(encoding="utf-8"))["documents"]
    for d in docs:
        missing = [k for k in REQUIRED if not d.get(k)]
        if missing:
            sys.exit(f"manifest: {d.get('id', '?')} is missing {missing}")
        for key in ("retrieved_on", "as_of"):
            if not DATE_RE.match(str(d[key])):
                sys.exit(f"manifest: {d['id']}.{key} must be YYYY-MM-DD")
    return docs


def chunk_doc(text: str):
    md = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
                                    strip_headers=False)
    # ~2400 chars is roughly 600 tokens; 400 chars is roughly 100 tokens of overlap
    rec = RecursiveCharacterTextSplitter(chunk_size=2400, chunk_overlap=400)
    return rec.split_documents(md.split_text(text))


def ingest(strict: bool) -> None:
    kb = Path(settings.kb_dir)
    docs = load_manifest(kb)
    r = Retriever()
    col = r.collection

    unverified = [d["id"] for d in docs if not d.get("verified", False)]
    if unverified:
        print(f"WARNING: not yet spot-checked (CP-5.1): {unverified}")
        if strict:
            sys.exit(1)

    # drop chunks of documents that were removed from the manifest
    keep = {d["id"] for d in docs}
    existing = {m["doc_id"] for m in col.get(include=["metadatas"])["metadatas"]}
    for gone in existing - keep:
        col.delete(where={"doc_id": gone})

    total = 0
    for d in docs:
        text = (kb / d["file"]).read_text(encoding="utf-8")
        chunks = chunk_doc(text)
        col.delete(where={"doc_id": d["id"]})
        ids, texts, embed_in, metas = [], [], [], []
        for i, ch in enumerate(chunks):
            section = ch.metadata.get("h3") or ch.metadata.get("h2") or ch.metadata.get("h1") or ""
            cid = hashlib.sha1(f"{d['id']}|{i}|{ch.page_content}".encode()).hexdigest()[:16]
            ids.append(cid)
            texts.append(ch.page_content)
            embed_in.append(f"{d['title']} - {section}\n{ch.page_content}")
            metas.append({"doc_id": d["id"], "title": d["title"], "source_url": d["source_url"],
                          "section": section, "as_of": str(d["as_of"])})
        if ids:
            col.upsert(ids=ids, documents=texts, embeddings=r.embed(embed_in), metadatas=metas)
        total += len(ids)
        print(f"  {d['id']}: {len(ids)} chunks")
    print(f"Done. {total} chunks written, collection now holds {col.count()}.")


def check(query: str) -> None:
    for i, c in enumerate(Retriever().search(query, 3, use_threshold=False), 1):
        print(f"{i}. [{c.distance:.3f}] {c.title} / {c.section} (as of {c.as_of})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="run a test query and print the top 3 chunks")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    check(a.check) if a.check else ingest(a.strict)
