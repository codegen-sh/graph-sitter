"""File-level semantic code search index using scikit-learn."""

import pickle
from pathlib import Path
from typing import Any, override

from sklearn.feature_extraction.text import TfidfVectorizer

from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.index.code_index import CodeIndex


class ScikitCodeIndex(CodeIndex):
    """Local code index using TF-IDF vectorization for semantic search.

    Chis CodeIndex implementation builds a local vector database with scikit, not requiring openai api access.
    """

    def __init__(self, codebase: Codebase, vectorizer: TfidfVectorizer | None = None) -> None:
        super().__init__(codebase)
        if vectorizer:
            self.vectorizer = vectorizer
        else:
            self.vectorizer: TfidfVectorizer = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2))
        self._fitted: bool = False

    @property
    @override
    def save_file_name(self) -> str:
        return "local_index_{commit}.pkl"

    @override
    def _get_embeddings(self, items: list[Any]) -> list[list[float]]:
        """Get TF-IDF embeddings for content."""
        if not self._fitted:
            all_items = [content for _, content in self._get_items_to_index()]
            if all_items:
                _ = self.vectorizer.fit(all_items)
                self._fitted = True

        if not items:
            return []

        # Extract content strings from items if they are tuples
        content_items = []
        for item in items:
            if isinstance(item, tuple) and len(item) >= 2:
                content_items.append(item[1])  # Get content from tuple
            elif isinstance(item, str):
                content_items.append(item)
            else:
                content_items.append(str(item))

        vectors = self.vectorizer.transform(content_items)
        return vectors.toarray().tolist()  # pyright: ignore [reportAttributeAccessIssue]

    @override
    def _get_items_to_index(self) -> list[tuple[Any, str]]:
        """Get all files and their content."""
        items = []
        for file in self.codebase.files():
            try:
                content = file.content
                if content.strip():  # Only index non-empty files
                    items.append((file, content))
            # pylint: disable-next=broad-exception-caught, can't do a lot anyways here
            except Exception:
                continue  # Skip files that can't be read
        return items

    @override
    def _get_changed_items(self) -> set[Any]:
        """Get files that have changed since last commit."""
        if not self.commit_hash:
            return set()

        changed = set()
        try:
            current_commit = self._get_current_commit()
            if current_commit != self.commit_hash:
                # For simplicity, consider all files as potentially changed
                changed = set(self.codebase.files())
        # pylint: disable-next=broad-exception-caught, can't do a lot anyways here
        except Exception:
            pass

        return changed

    @override
    def _save_index(self, path: Path) -> None:
        """Save index data to disk."""
        data = {
            "E": self.E,
            "items": self.items,
            "commit_hash": self.commit_hash,
            "vectorizer": self.vectorizer,
            "fitted": self._fitted,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    @override
    def _load_index(self, path: Path) -> None:
        """Load index data from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.E = data["E"]
        self.items = data["items"]
        self.commit_hash = data["commit_hash"]
        self.vectorizer = data["vectorizer"]
        self._fitted = data["fitted"]

    @override
    def similarity_search(self, query: str, k: int = 5) -> list[tuple[Any, float]]:
        """Find the k most similar files to a query."""
        raw_results = self._similarity_search_raw(query, k)

        results = []
        for item_str, score in raw_results:
            for file in self.codebase.files():
                if str(file) == item_str:
                    results.append((file, score))
                    break

        return results
