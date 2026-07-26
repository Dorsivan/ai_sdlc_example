import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "")
EMBEDDING_DIMENSIONS = 768

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss-20b")
LLM_API_URL = os.getenv("LLM_API_URL", "http://gpt-oss-20b-demo-llm.apps.ocp.example.com/v1")

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION_NAME = "miruvor_branches"

DATA_FILE = os.getenv("DATA_FILE", "./data/miruvor_branches.json")

TOP_K = int(os.getenv("TOP_K", "5"))

os.environ.setdefault("OPENAI_API_KEY", "not-needed")

_local_model = None


def get_embeddings(texts: list[str], prefix: str = "") -> list[list[float]]:
    prefixed = [f"{prefix}{t}" for t in texts] if prefix else texts

    if EMBEDDING_API_URL:
        from openai import OpenAI
        client = OpenAI(base_url=EMBEDDING_API_URL)
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=prefixed)
        return [item.embedding for item in response.data]

    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
    embeddings = _local_model.encode(prefixed, convert_to_numpy=True)
    return embeddings.tolist()
