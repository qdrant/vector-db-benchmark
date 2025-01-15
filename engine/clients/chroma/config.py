import os

CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "benchmark")


def chroma_fix_host(host: str):
    return host if host != "localhost" else "127.0.0.1"
