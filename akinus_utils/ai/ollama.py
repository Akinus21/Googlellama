import asyncio
import subprocess
import json
import numpy as np
from akinus_utils.utils.logger  import log
import ollama

async def ollama_query(prompt: str, model: str = "llama3.2") -> str:
    proc = await asyncio.create_subprocess_exec(
        "ollama", "run", model, prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Ollama CLI error: {stderr.decode().strip()}")
    return stdout.decode().strip()

def embed_with_ollama(text: str, model: str = "nomic-embed-text") -> np.ndarray:
    response = ollama.embed(model=model, input=text)
    # response is a dict with "embeddings" key
    embedding = response["embeddings"]
    return np.array(embedding)

def chunk_text(text: str, max_chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_chunk_size]
        chunks.append(" ".join(chunk))
        i += max_chunk_size - overlap
    return chunks

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1).reshape(-1)
    vec2 = np.array(vec2).reshape(-1)
    vec1_norm = vec1 / np.linalg.norm(vec1)
    vec2_norm = vec2 / np.linalg.norm(vec2)
    return np.dot(vec1_norm, vec2_norm)

def get_relevant_text_ollama(query: str, text: str, model="nomic-embed-text", top_k=5, chunk_size=500, overlap=100, include_scores=False):
    # Break text into larger overlapping chunks
    chunks = chunk_text(text, max_chunk_size=chunk_size, overlap=overlap)

    # Embed the query once
    query_embedding = embed_with_ollama(query, model=model)

    # Embed all chunks
    chunk_embeddings = [embed_with_ollama(chunk, model=model) for chunk in chunks]

    # Calculate similarity scores
    scores = [cosine_similarity(query_embedding, emb) for emb in chunk_embeddings]

    # Sort by score (highest first)
    top_indices = np.argsort(scores)[-top_k:][::-1]

    # Gather relevant chunks
    relevant_chunks = []
    for idx in top_indices:
        if include_scores:
            relevant_chunks.append(f"[Score: {scores[idx]:.4f}]\n{chunks[idx]}")
        else:
            relevant_chunks.append(chunks[idx])

    # Return them combined with double newlines
    return "\n\n".join(relevant_chunks)