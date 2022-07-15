FROM python:3.10-slim

RUN pip install qdrant-client==v0.8.4 typer

WORKDIR /client
COPY client/ .

ENTRYPOINT ["tail", "-f", "/dev/null"]
