FROM python:3.10-slim

RUN pip install weaviate-client==v3.6.0 typer

WORKDIR /client
COPY weaviate-1.14.1/client/ .
COPY base_client engine/base_client/

ENTRYPOINT ["tail", "-f", "/dev/null"]