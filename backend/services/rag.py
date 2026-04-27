"""
rag.py
Advanced RAG system for PawPal+.

Features:
- Persistent Chroma vector store (Gemini embeddings)
- Improved chunking strategy
- Multi-query retrieval
- Hybrid reranking (semantic + keyword overlap)
- Relevance filtering (guardrail)
- Source attribution for explainability
"""

import os
import re
from pathlib import Path
from typing import List, Dict

# =========================
# CONFIG
# =========================

_DATA_DIR = Path(__file__).parent.parent / "data"
_CHROMA_DIR = _DATA_DIR / "chroma_db"
_COLLECTION = "pawpal_kb"

_DOG_TERMS = {"dog", "dogs", "canine", "puppy", "puppies"}
_CAT_TERMS = {"cat", "cats", "feline", "kitten", "kittens"}

_vectorstore = None


# =========================
# UTIL FUNCTIONS
# =========================

def _detect_species(text: str, file_species: str) -> str:
    words = set(text.lower().split())
    if words & _DOG_TERMS:
        return "dog"
    if words & _CAT_TERMS:
        return "cat"
    return file_species


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _first_sentences(text: str, n: int = 2, max_chars: int = 300) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result = ""

    for sent in sentences[:n]:
        candidate = (result + " " + sent).strip() if result else sent
        if len(candidate) <= max_chars:
            result = candidate
        else:
            break

    return result or text[:max_chars]


# =========================
# CHUNKING
# =========================

def _load_chunks():
    try:
        import pypdf
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        return [], []

    pdf_paths = list(_DATA_DIR.glob("*.pdf"))
    if not pdf_paths:
        return [], []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,        # ✅ improved
        chunk_overlap=80,
    )

    texts, metadatas = [], []

    for pdf in pdf_paths:
        reader = pypdf.PdfReader(str(pdf))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        stem = pdf.stem.lower()
        file_species = "dog" if "dog" in stem else "cat" if "cat" in stem else "all"

        for chunk in splitter.split_text(full_text):
            clean = _clean_text(chunk)
            if len(clean) < 80:
                continue

            species = _detect_species(clean, file_species)

            texts.append(clean)
            metadatas.append({
                "species": species,
                "source": pdf.name
            })

    return texts, metadatas


# =========================
# EMBEDDINGS + VECTORSTORE
# =========================

def _make_embeddings(api_key: str):
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key,
    )


def _get_vectorstore():
    global _vectorstore

    if _vectorstore:
        return _vectorstore

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    from langchain_chroma import Chroma

    embeddings = _make_embeddings(api_key)

    if _CHROMA_DIR.exists():
        _vectorstore = Chroma(
            collection_name=_COLLECTION,
            embedding_function=embeddings,
            persist_directory=str(_CHROMA_DIR),
        )
        return _vectorstore

    texts, metadatas = _load_chunks()
    if not texts:
        return None

    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    _vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        collection_name=_COLLECTION,
        persist_directory=str(_CHROMA_DIR),
    )

    return _vectorstore


# =========================
# RETRIEVAL LOGIC
# =========================

def _keyword_score(text: str, query: str) -> int:
    return len(set(text.lower().split()) & set(query.lower().split()))


def _is_relevant(text: str, query: str) -> bool:
    return _keyword_score(text, query) >= 3


def _build_queries(pet, tasks: list) -> List[str]:
    task_text = [
        f"{t.title} {t.notes or ''}".strip()
        for t in tasks
    ]

    species = pet.species.value.lower()
    base = f"{pet.age_years} year old {species} care"

    queries = [
        f"{base}: {', '.join(task_text)}",
        f"{species} daily routine best practices",
        f"{species} health timing feeding walking grooming",
    ]

    return queries


# =========================
# MAIN RAG FUNCTION
# =========================

def retrieve_for_pet(pet, tasks: list) -> List[Dict]:
    """
    Advanced retrieval pipeline:
    1. Multi-query search
    2. Merge results
    3. Hybrid rerank (keyword overlap)
    4. Relevance filtering
    5. Deduplicate + trim
    """

    vs = _get_vectorstore()
    if not vs:
        return []

    queries = _build_queries(pet, tasks)

    all_docs = []

    for q in queries:
        try:
            docs = vs.similarity_search(
                q,
                k=4,
                filter={"species": pet.species.value.lower()}
            )
            if not docs:
                docs = vs.similarity_search(q, k=4)

            all_docs.extend(docs)

        except Exception:
            continue

    # Deduplicate by content
    unique_docs = {doc.page_content: doc for doc in all_docs}.values()

    # Hybrid reranking
    primary_query = queries[0]
    ranked = sorted(
        unique_docs,
        key=lambda d: _keyword_score(d.page_content, primary_query),
        reverse=True
    )

    results = []
    seen = set()

    for doc in ranked:
        snippet = _first_sentences(doc.page_content)

        if (
            snippet
            and snippet not in seen
            and _is_relevant(snippet, primary_query)
        ):
            seen.add(snippet)

            results.append({
                "text": snippet,
                "source": doc.metadata.get("source"),
                "species": doc.metadata.get("species")
            })

        if len(results) >= 4:
            break

    return results
