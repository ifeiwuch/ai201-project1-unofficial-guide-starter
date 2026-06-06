"""
embed.py — Milestone 4: Embedding and retrieval.

Pipeline stages implemented here (see planning.md → Architecture):
    Embedding (all-MiniLM-L6-v2)  ->  Vector Store (ChromaDB)  ->  Retrieval

What this script does:
    1. embed_and_store() : take the chunks produced by the ingestion/chunking
       stage (ingest.py -> chunks.json), embed each chunk's text with
       all-MiniLM-L6-v2 via sentence-transformers, and store it in a persistent
       ChromaDB collection together with its source metadata (document name,
       URL, chunk index).
    2. retrieve()        : embed a query with the same model and return the
       top-k most similar chunks from ChromaDB (top-k = 5, per planning.md).
    3. main()            : (re)build the collection from chunks.json, then run a
       verification query ("activities fair") and print the chunks that come
       back so we can confirm retrieval works.

Run:
    python embed.py                 # build the vector store, then verify
    python embed.py --query "..."   # build, then run your own test query
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from ingest import CHUNKS_FILE  # reuse the path the ingestion stage writes

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

EMBED_MODEL = "all-MiniLM-L6-v2"   # planning.md → Retrieval Approach
CHROMA_DIR = Path("chroma_db")     # already in .gitignore
COLLECTION_NAME = "brown_clubs"
TOP_K = 5                          # planning.md → Retrieval Approach

# Loaded lazily so importing this module (e.g. from a query UI) is cheap and
# the ~80 MB model is only pulled when embedding actually happens.
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load (once) and return the all-MiniLM-L6-v2 embedding model."""
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBED_MODEL} ...", flush=True)
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings with all-MiniLM-L6-v2.

    Embeddings are L2-normalized so that ChromaDB's cosine space yields
    distances in [0, 2] (distance = 1 - cosine similarity).
    """
    vectors = get_model().encode(
        texts,
        batch_size=64,
        show_progress_bar=len(texts) > 64,
        normalize_embeddings=True,
    )
    return vectors.tolist()


# --------------------------------------------------------------------------- #
# Embedding + vector store
# --------------------------------------------------------------------------- #

def embed_and_store(
    chunks: list[dict],
    collection_name: str = COLLECTION_NAME,
    persist_dir: Path = CHROMA_DIR,
    reset: bool = True,
):
    """Embed each chunk and store it in ChromaDB with its source metadata.

    Args:
        chunks: list of dicts from the ingestion/chunking stage, each with
            keys {id, source, url, chunk_index, text} (see ingest.py).
        collection_name: ChromaDB collection to write to.
        persist_dir: on-disk location for the ChromaDB store.
        reset: if True, drop any existing collection first so re-running yields
            a clean rebuild instead of stacking duplicates.

    Returns:
        The populated ChromaDB collection.
    """
    if not chunks:
        raise ValueError("no chunks to embed — run ingest.py first")

    client = chromadb.PersistentClient(path=str(persist_dir))

    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:  # noqa: BLE001 — fine if it didn't exist yet
            pass

    # Cosine distance suits normalized sentence-transformer embeddings.
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "source": c["source"],
            "url": c["url"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    print(f"Embedding {len(documents)} chunks with {EMBED_MODEL} ...", flush=True)
    embeddings = embed_texts(documents)

    # Add in batches to stay well under ChromaDB's per-call limits.
    batch = 256
    for i in range(0, len(ids), batch):
        sl = slice(i, i + batch)
        collection.add(
            ids=ids[sl],
            documents=documents[sl],
            metadatas=metadatas[sl],
            embeddings=embeddings[sl],
        )

    print(f"Stored {collection.count()} chunks in ChromaDB "
          f"collection '{collection_name}' at {persist_dir}/")
    return collection


def get_collection(
    collection_name: str = COLLECTION_NAME,
    persist_dir: Path = CHROMA_DIR,
):
    """Open an existing ChromaDB collection (for querying)."""
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_collection(collection_name)


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #

def retrieve(query: str, k: int = TOP_K, collection=None) -> list[dict]:
    """Return the top-k chunks most similar to `query`.

    Each result is a dict with keys {id, text, source, url, chunk_index,
    distance} (lower distance = more similar).
    """
    if collection is None:
        collection = get_collection()

    query_embedding = embed_texts([query])
    res = collection.query(
        query_embeddings=query_embedding,
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    results: list[dict] = []
    for doc, meta, dist, _id in zip(
        res["documents"][0],
        res["metadatas"][0],
        res["distances"][0],
        res["ids"][0],
    ):
        results.append({
            "id": _id,
            "text": doc,
            "source": meta.get("source"),
            "url": meta.get("url"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,
        })
    return results


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def load_chunks() -> list[dict]:
    """Load the chunks written by the ingestion/chunking stage."""
    if not CHUNKS_FILE.exists():
        print(f"{CHUNKS_FILE} not found — run `python ingest.py` first.",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Embed chunks into ChromaDB and run a verification query."
    )
    parser.add_argument(
        "--query",
        default="activities fair",
        help='verification query to run after building (default: "activities fair")',
    )
    parser.add_argument(
        "--k", type=int, default=TOP_K, help=f"top-k results (default: {TOP_K})"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="skip rebuilding; query the existing ChromaDB collection",
    )
    args = parser.parse_args()

    if args.no_build:
        collection = get_collection()
    else:
        collection = embed_and_store(load_chunks())

    # Verification: a known term should surface the obviously-relevant chunks.
    print(f"\nVerification query: {args.query!r} (top {args.k})")
    print("=" * 80)
    for rank, r in enumerate(retrieve(args.query, k=args.k, collection=collection), 1):
        preview = r["text"][:240].replace("\n", " ")
        print(f"\n#{rank}  distance={r['distance']:.4f}  source={r['source']}")
        print(f"     id={r['id']}")
        print(f"     {preview!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
