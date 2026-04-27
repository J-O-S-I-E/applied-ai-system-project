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
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


# =========================
# CONFIGURATION
# =========================

@dataclass
class RAGConfig:
    """Configuration for the RAG system."""
    data_dir: Path
    chroma_dir: Path
    collection_name: str = "pawpal_kb"
    chunk_size: int = 400
    chunk_overlap: int = 80
    max_passages: int = 3
    min_chunk_length: int = 80
    max_passage_chars: int = 400
    relevance_threshold: float = 2.0

    # Species detection terms
    dog_terms: set = frozenset({"dog", "dogs", "canine", "puppy", "puppies"})
    cat_terms: set = frozenset({"cat", "cats", "feline", "kitten", "kittens"})

    # Important terms for relevance boosting
    important_terms: set = frozenset({
        "walk", "walking", "exercise", "feeding", "grooming", "nail", "trim",
        "trimming", "health", "care", "training", "play", "playing", "rest",
        "sleep", "eating", "diet", "water", "hydration", "bathroom", "potty"
    })

    # Terms to filter out from chunks
    junk_terms: set = frozenset({
        "page", "figure", "diagram", "chapter", "contents", "index"
    })


# Global config instance
_config = RAGConfig(
    data_dir=Path(__file__).parent.parent / "data",
    chroma_dir=Path(__file__).parent.parent / "data" / "chroma_db"
)


# =========================
# TEXT PROCESSING
# =========================

class TextProcessor:
    """Handles text cleaning and processing operations."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean extracted text by removing PDF noise and artifacts."""
        if not text:
            return ""

        text = " ".join(text.split())

        # Remove page numbers and weird number artifacts (1620, 12345, "1 2 3 4 5")
        text = re.sub(r"\b\d{4,}\b", "", text)  # removes 1620, page numbers
        text = re.sub(r"\b\d\s+\d\s+\d+\s+\d+\s+\d+", "", text)  # removes "1 2 3 4 5"
        text = re.sub(r"^[^\w]*", "", text)  # removes leading junk

        # Clean up extra spaces created by removals
        text = " ".join(text.split())

        return text.strip()

    @staticmethod
    def extract_passage(text: str, max_chars: int = 400) -> str:
        """Extract clean, complete passage from text without breaking mid-sentence."""
        if not text:
            return ""

        text = text.strip()
        text = " ".join(text.split())

        # If text fits in max_chars, return it as-is
        if len(text) <= max_chars:
            return text

        # Otherwise, find a good cutoff point - look for sentence boundaries
        cutoff = text[:max_chars]

        # Try to find last sentence boundary before cutoff
        for sep in [". ", "! ", "? "]:
            last_sep = cutoff.rfind(sep)
            if last_sep > max_chars * 0.7:  # Only use if it's reasonably far in
                return cutoff[:last_sep + 1]

        # If no good boundary found, cut at word boundary
        last_space = cutoff.rfind(" ")
        if last_space > 0:
            return cutoff[:last_space] + "..."

        return cutoff + "..."

    @staticmethod
    def detect_species(text: str, file_species: str) -> str:
        """Detect species from text content."""
        words = set(text.lower().split())
        if words & _config.dog_terms:
            return "dog"
        if words & _config.cat_terms:
            return "cat"
        return file_species


# =========================
# VECTOR STORE MANAGEMENT
# =========================

class VectorStoreManager:
    """Manages the Chroma vector store operations."""

    def __init__(self):
        self._vectorstore = None

    def get_vectorstore(self):
        """Get or create the vector store."""
        if self._vectorstore:
            return self._vectorstore

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        try:
            from langchain_chroma import Chroma
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError:
            return None

        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key,
        )

        if _config.chroma_dir.exists():
            try:
                self._vectorstore = Chroma(
                    collection_name=_config.collection_name,
                    embedding_function=embeddings,
                    persist_directory=str(_config.chroma_dir),
                )
                # Quick check to see if vectorstore has documents
                if self._vectorstore._collection.count() > 0:
                    return self._vectorstore
                # If empty, fall through to rebuild
            except Exception as e:
                print(f"WARNING: Failed to load existing vectorstore: {e}. Rebuilding...")

        texts, metadatas = self._load_chunks()
        if not texts:
            print("WARNING: No PDF chunks found.")
            return None

        _config.chroma_dir.mkdir(parents=True, exist_ok=True)

        self._vectorstore = Chroma.from_texts(
            texts=texts,
            embedding=embeddings,
            metadatas=metadatas,
            collection_name=_config.collection_name,
            persist_directory=str(_config.chroma_dir),
        )
        print(f"Built vectorstore with {len(texts)} chunks")

        return self._vectorstore

    def rebuild_vectorstore(self):
        """Force rebuild the entire vectorstore from PDFs."""
        import shutil

        # Clear the old vectorstore from memory
        self._vectorstore = None

        # Delete the old chroma_db directory
        if _config.chroma_dir.exists():
            shutil.rmtree(_config.chroma_dir)
            print(f"Removed old vectorstore at {_config.chroma_dir}")

        # Rebuild fresh
        vs = self.get_vectorstore()
        if vs:
            print("Vectorstore rebuilt successfully")
        else:
            print("Failed to rebuild vectorstore")

        return vs

    def _load_chunks(self) -> Tuple[List[str], List[Dict]]:
        """Load and process PDF chunks."""
        try:
            import pypdf
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            return [], []

        pdf_paths = list(_config.data_dir.glob("*.pdf"))
        if not pdf_paths:
            return [], []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=_config.chunk_size,
            chunk_overlap=_config.chunk_overlap,
        )

        texts, metadatas = [], []

        for pdf in pdf_paths:
            try:
                reader = pypdf.PdfReader(str(pdf))
                full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

                stem = pdf.stem.lower()
                file_species = "dog" if "dog" in stem else "cat" if "cat" in stem else "all"

                for chunk in splitter.split_text(full_text):
                    clean = TextProcessor.clean_text(chunk)
                    if len(clean) < _config.min_chunk_length:
                        continue

                    # Filter out textbook junk
                    if any(bad in clean.lower() for bad in _config.junk_terms):
                        continue

                    species = TextProcessor.detect_species(clean, file_species)

                    texts.append(clean)
                    metadatas.append({
                        "species": species,
                        "source": pdf.name
                    })
            except Exception as e:
                print(f"WARNING: Failed to process {pdf}: {e}")
                continue

        return texts, metadatas


# =========================
# QUERY BUILDING
# =========================

class QueryBuilder:
    """Builds relevant queries for pet-specific retrieval."""

    @staticmethod
    def build_queries(pet, tasks: list) -> List[str]:
        """Build task-aware queries to retrieve specific, relevant guidance."""
        task_descriptions = [
            f"{t.title} {t.notes or ''}".strip()
            for t in tasks
        ]

        species = pet.species.value.lower()
        task_str = ", ".join(task_descriptions)

        return [
            f"{species} care guide for {task_str}",
            f"how to properly {task_str} for a {species}",
            f"{species} safety and tips {task_str}",
            f"{species} health and behavior {task_str}",
        ]


# =========================
# RELEVANCE SCORING
# =========================

class RelevanceScorer:
    """Handles relevance scoring and filtering."""

    @staticmethod
    def keyword_score(text: str, query: str) -> float:
        """Score relevance with weighted boost for important pet care terms."""
        text_words = set(text.lower().split())
        query_words = set(query.lower().split())

        # Base overlap
        overlap = len(text_words & query_words)

        # Boost for task-relevant terms
        boost = len(text_words & _config.important_terms) * 2

        return float(overlap + boost)

    @staticmethod
    def is_relevant(text: str, query: str) -> bool:
        """Check if text is relevant to query."""
        return RelevanceScorer.keyword_score(text, query) >= _config.relevance_threshold


# =========================
# MAIN RETRIEVER
# =========================

class Retriever:
    """Main RAG retrieval system."""

    def __init__(self):
        self.vector_store_manager = VectorStoreManager()

    def retrieve_for_pet(self, pet, tasks: list) -> List[Dict]:
        """
        Advanced retrieval pipeline:
        1. Multi-query search
        2. Merge results
        3. Hybrid rerank (keyword overlap)
        4. Relevance filtering
        5. Deduplicate + trim
        """
        vs = self.vector_store_manager.get_vectorstore()
        if not vs:
            return []

        queries = QueryBuilder.build_queries(pet, tasks)
        if not queries:
            return []

        all_docs = []
        primary_query = queries[0]

        # Multi-query search
        for q in queries:
            try:
                docs = vs.similarity_search(
                    q,
                    k=6,
                    filter={"species": pet.species.value.lower()}
                )
                if not docs:
                    docs = vs.similarity_search(q, k=6)

                all_docs.extend(docs)

            except Exception as e:
                print(f"WARNING: Query failed '{q}': {e}")
                continue

        # Deduplicate by content
        unique_docs = {doc.page_content: doc for doc in all_docs}.values()

        # Hybrid reranking
        ranked = sorted(
            unique_docs,
            key=lambda d: RelevanceScorer.keyword_score(d.page_content, primary_query),
            reverse=True
        )

        # Extract and filter results
        results = []
        seen = set()

        for doc in ranked:
            snippet = TextProcessor.extract_passage(doc.page_content, _config.max_passage_chars)

            if snippet and snippet not in seen:
                # Apply relevance filter, but be lenient for first few results
                if RelevanceScorer.is_relevant(snippet, primary_query) or len(results) < 2:
                    seen.add(snippet)

                    results.append({
                        "text": snippet,
                        "source": doc.metadata.get("source"),
                        "species": doc.metadata.get("species")
                    })

            if len(results) >= _config.max_passages:
                break

        return results


# =========================
# PUBLIC API
# =========================

# Global retriever instance
_retriever = Retriever()


def retrieve_for_pet(pet, tasks: list) -> List[Dict]:
    """Public API for pet-specific retrieval."""
    return _retriever.retrieve_for_pet(pet, tasks)


def rebuild_vectorstore():
    """Public API for rebuilding the vector store."""
    return _retriever.vector_store_manager.rebuild_vectorstore()
