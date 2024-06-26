import time
from typing import List

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.azure_ai.config import (
    AZUREAI_API_KEY,
    AZUREAI_API_VERSION,
    AZUREAI_INDEX_NAME,
    AZUREAI_SERVICE_NAME,
    DOC_COUNT,
    add_docs,
    list_indices_statssummary,
)


class AzureAIUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        if AZUREAI_API_VERSION is None:
            raise Exception(
                "An api key is required to use Azure AI Search. Specify it via AZUREAI_API_KEY=..."
            )
        cls.api_version = AZUREAI_API_VERSION
        cls.service_endpoint = f"https://{AZUREAI_SERVICE_NAME}.search.windows.net"
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        docs = {"value": []}

        for record in batch:
            idx = record.id
            vec = record.vector
            doc = {
                "@search.action": "mergeOrUpload",
                "Id": f"{idx}",
                "VectorField": vec,
            }
            docs["value"].append(doc)

        retries = 6
        delay = 2
        for attempt in range(retries):
            try:
                add_docs(
                    cls.service_endpoint,
                    cls.api_version,
                    AZUREAI_API_KEY,
                    AZUREAI_INDEX_NAME,
                    docs,
                )
                break
            except Exception as e:
                if attempt < retries - 1:
                    print(
                        f"received exception {e.__str__}. sleeping for {delay} secs and trying again."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(
                        f"received exception {e.__str__}. failing after {retries} tries..."
                    )
                    raise e

    @classmethod
    def post_upload(cls, _distance):
        indexing = True
        delay = 2
        doc_count = None
        if DOC_COUNT is not None:
            doc_count = int(DOC_COUNT)
        while indexing is True:
            indexstats = list_indices_statssummary(
                cls.service_endpoint, cls.api_version, AZUREAI_API_KEY
            )
            for index in indexstats["value"]:
                if index["name"] == AZUREAI_INDEX_NAME:
                    if doc_count is None:
                        print(
                            "Found index. given doc_count is null, skipping indexing check..."
                        )
                        indexing = False
                    else:
                        indexed_docs = index["documentCount"]
                        print(
                            f"checking if indexed docs({indexed_docs}) == doc_count ({doc_count}) of dataset."
                        )
                        if indexed_docs < doc_count:
                            print(
                                f"Indexing still in progress... {indexed_docs} < {doc_count}. Sleeping for {delay} secs"
                            )
                            time.sleep(delay)
                            delay *= 2
                        else:
                            indexing = False
                            print("finished indexing...")
                            return {}
        return {}

    def get_memory_usage(cls):
        stats = {}
        indexstats = list_indices_statssummary(
            cls.service_endpoint, cls.api_version, AZUREAI_API_KEY
        )
        for index in indexstats["value"]:
            if index["name"] == AZUREAI_INDEX_NAME:
                stats = index
        return stats

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            del cls.client
