FROM python:3.10-slim

RUN pip install qdrant-client==v0.8.4

WORKDIR /client
COPY cmd.py .

ENTRYPOINT ["tail", "-f", "/dev/null"]
