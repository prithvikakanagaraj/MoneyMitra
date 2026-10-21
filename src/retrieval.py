
"""
retrieval.py - User-scoped semantic search for MoneyMitra transactions.

Uses Sentence Transformers to embed transaction descriptions and FAISS
to retrieve transactions relevant to a user's question.

Every search must specify the authenticated user's ID.
"""

from functools import lru_cache

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.database import get_transactions


# Load the embedding model only once.
@lru_cache(maxsize=1)
def load_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


def create_transaction_text(row):
    """Convert a transaction into searchable text."""
    return (
        f"Date: {row['date']}. "
        f"Description: {row['description']}. "
        f"Amount: {row['amount']}. "
        f"Type: {row['type']}. "
        f"Category: {row['category']}."
    )


def search_transactions(query, top_k=5, user_id=None, db_path=None):
    """
    Find transactions semantically relevant to a question.

    Args:
        query: User's search question.
        top_k: Maximum number of transactions to return.
        user_id: ID of the authenticated user. Required.
        db_path: Optional database path, useful for testing.

    Returns:
        A list of relevant transactions with similarity scores.

    Returns an empty list when no valid user ID or searchable
    transactions are available.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        return []

    # Fail closed: never perform an unscoped search.
    if user_id is None:
        return []

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return []

    if user_id < 1:
        return []

    # Retrieve only this user's transactions.
    transactions = get_transactions(
        db_path=db_path,
        user_id=user_id,
    )

    if transactions is None or transactions.empty:
        return []

    # Prepare transaction descriptions.
    transaction_texts = [
        create_transaction_text(row)
        for _, row in transactions.iterrows()
    ]

    # Load the embedding model.
    model = load_embedding_model()

    # Convert transaction descriptions into numerical vectors.
    transaction_embeddings = model.encode(
        transaction_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    transaction_embeddings = np.asarray(
        transaction_embeddings,
        dtype=np.float32,
    )

    # Create a FAISS similarity-search index.
    dimension = transaction_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(transaction_embeddings)

    # Convert the user's question into an embedding.
    query_embedding = model.encode(
        [query.strip()],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    # Retrieve the most relevant transactions.
    number_to_search = min(top_k, len(transactions))

    scores, indices = index.search(
        query_embedding,
        number_to_search,
    )

    results = []

    for score, transaction_index in zip(scores[0], indices[0]):
        if transaction_index < 0:
            continue

        transaction = transactions.iloc[int(transaction_index)]
        result = transaction.to_dict()
        result["similarity_score"] = float(score)
        results.append(result)

    return results
