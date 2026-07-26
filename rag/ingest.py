#!/usr/bin/env python3
import argparse
import json

import chromadb

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    DATA_FILE,
    EMBEDDING_API_URL,
    get_embeddings,
)


def load_data(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def build_chunks(branches: list[dict]) -> tuple[list[str], list[str], list[dict]]:
    ids = []
    documents = []
    metadatas = []

    for branch in branches:
        for q in branch["quarters"]:
            chunk_id = f"{branch['branch_id']}_{q['quarter']}"
            document = (
                f"Branch: {branch['branch_name']} ({branch['branch_id']})\n"
                f"Location: {branch['city']}, {branch['state']} ({branch['region']})\n"
                f"Manager: {branch['manager']}\n"
                f"Quarter: {q['quarter']} | Revenue: ${q['revenue_usd']:,} | "
                f"Transactions: {q['transactions']:,} | Avg Ticket: ${q['avg_ticket_usd']:.2f}\n"
                f"Satisfaction: {q['customer_satisfaction_score']}/5.0 | "
                f"Employees: {q['employee_count']} | Top Seller: {q['top_selling_item']}\n"
                f"\n{q['narrative']}"
            )
            metadata = {
                "branch_id": branch["branch_id"],
                "branch_name": branch["branch_name"],
                "city": branch["city"],
                "state": branch["state"],
                "region": branch["region"],
                "quarter": q["quarter"],
                "revenue_usd": q["revenue_usd"],
                "customer_satisfaction_score": q["customer_satisfaction_score"],
            }

            ids.append(chunk_id)
            documents.append(document)
            metadatas.append(metadata)

    return ids, documents, metadatas


def main():
    parser = argparse.ArgumentParser(description="Ingest Miruvor branch data into ChromaDB")
    parser.add_argument("--data", default=DATA_FILE, help="Path to branch data JSON file")
    parser.add_argument("--reset", action="store_true", help="Clear existing collection before ingesting")
    args = parser.parse_args()

    branches = load_data(args.data)
    ids, documents, metadatas = build_chunks(branches)

    mode = "remote" if EMBEDDING_API_URL else "local"
    print(f"Embedding {len(documents)} chunks using {mode} model...")

    embeddings = get_embeddings(documents, prefix="search_document: ")

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    if args.reset:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
            print(f"Cleared existing collection '{CHROMA_COLLECTION_NAME}'")
        except ValueError:
            pass

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"Ingested {len(documents)} chunks into '{CHROMA_COLLECTION_NAME}'")
    print(f"ChromaDB persisted to: {CHROMA_PERSIST_DIR}")


if __name__ == "__main__":
    main()
