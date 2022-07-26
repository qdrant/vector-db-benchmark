FROM python:3.10-slim

RUN pip install h5py

WORKDIR /dataset
COPY download.py /tmp/

ENTRYPOINT ["python", "/tmp/download.py"]
