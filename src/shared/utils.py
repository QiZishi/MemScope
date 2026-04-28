"""
Shared utilities for MemScope.

Contains commonly used functions to avoid duplication across modules.
"""

import numpy as np
from typing import List


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    This is the canonical implementation used across MemScope.
    Previously duplicated in recall/mmr.py and core/store.py.

    Args:
        vec_a: Vector A
        vec_b: Vector B

    Returns:
        Cosine similarity in [-1, 1]
    """
    if not vec_a or not vec_b:
        return 0.0

    a = np.array(vec_a)
    b = np.array(vec_b)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def cosine_similarity_batch(query_vec: List[float], matrix: np.ndarray) -> np.ndarray:
    """
    Batch cosine similarity between a query vector and a matrix of embeddings.

    Args:
        query_vec: Query vector (D,)
        matrix: Embedding matrix (N, D)

    Returns:
        Similarity array (N,)
    """
    q = np.array(query_vec)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return np.zeros(matrix.shape[0])

    q_unit = q / q_norm
    emb_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    emb_norms = np.where(emb_norms == 0, 1, emb_norms)
    emb_unit = matrix / emb_norms

    return emb_unit @ q_unit
