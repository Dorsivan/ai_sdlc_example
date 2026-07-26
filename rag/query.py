#!/usr/bin/env python3
import argparse
import sys

import chromadb
from openai import OpenAI

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    EMBEDDING_API_URL,
    LLM_API_URL,
    LLM_MODEL,
    TOP_K,
    get_embeddings,
)

SYSTEM_PROMPT = (
    "You are a business analyst assistant for Miruvor Coffee, a chain of coffee shops. "
    "Answer questions using ONLY the context provided below. "
    "If the context does not contain enough information to answer, say so. "
    "Cite specific branch names and quarters when relevant. "
    "Be concise and data-driven in your responses."
)


def get_question(args) -> str | None:
    if args.question:
        return " ".join(args.question).strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return None


def retrieve(collection, question: str, top_k: int, verbose: bool) -> str:
    query_embedding = get_embeddings([question], prefix="search_query: ")

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    if verbose and results["documents"][0]:
        print(f"\n--- Retrieved {len(results['documents'][0])} chunks ---")
        for i, (doc, meta, dist) in enumerate(
            zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
        ):
            print(f"[{i+1}] {meta['branch_name']} | {meta['quarter']} | distance: {dist:.4f}")
        print("---\n")

    context_parts = []
    for doc in results["documents"][0]:
        context_parts.append(doc)

    return "\n---\n".join(context_parts)


def ask_llm(client: OpenAI, context: str, question: str):
    user_message = f"Context:\n---\n{context}\n---\n\nQuestion: {question}"

    stream = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)
    print()


def run_query(collection, llm_client: OpenAI, question: str, top_k: int, verbose: bool):
    context = retrieve(collection, question, top_k, verbose)
    ask_llm(llm_client, context, question)


def main():
    parser = argparse.ArgumentParser(description="Query Miruvor branch data using RAG")
    parser.add_argument("question", nargs="*", help="Question to ask (omit for interactive mode)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show retrieved chunks")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Number of chunks to retrieve")
    args = parser.parse_args()

    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        collection = chroma_client.get_collection(CHROMA_COLLECTION_NAME)
    except ValueError:
        print("No data found. Run ingest.py first.", file=sys.stderr)
        return 1

    mode = "remote" if EMBEDDING_API_URL else "local"
    print(f"Using {mode} embeddings | LLM: {LLM_MODEL}")

    llm_client = OpenAI(base_url=LLM_API_URL)

    question = get_question(args)
    if question:
        run_query(collection, llm_client, question, args.top_k, args.verbose)
        return 0

    print("Interactive mode (Ctrl+C to exit)\n")
    try:
        while True:
            question = input("Question: ").strip()
            if not question:
                continue
            run_query(collection, llm_client, question, args.top_k, args.verbose)
            print()
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
