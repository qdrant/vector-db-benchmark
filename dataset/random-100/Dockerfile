FROM python:3.10-slim

COPY vectors.jsonl /tmp/

ENTRYPOINT ["cp", "/tmp/vectors.jsonl", "/dataset/vectors.jsonl"]
