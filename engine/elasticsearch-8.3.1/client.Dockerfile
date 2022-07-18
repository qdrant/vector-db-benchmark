FROM python:3.10-slim

RUN pip install elasticsearch==8.3.1 typer

WORKDIR /client
COPY client/ .

ENTRYPOINT ["tail", "-f", "/dev/null"]