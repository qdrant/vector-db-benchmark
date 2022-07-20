FROM python:3.10-slim

RUN pip install weaviate-client==v3.6.0 typer

WORKDIR /client
COPY client/ .

ENTRYPOINT ["tail", "-f", "/dev/null"]
