import os
from typing import List, Tuple

from dataset_reader.base_reader import Query
from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.azure_ai.config import (
    AZUREAI_API_KEY,
    AZUREAI_API_VERSION,
    AZUREAI_EXHAUSTIVE_KNN,
    AZUREAI_INDEX_NAME,
    AZUREAI_SERVICE_NAME,
    cosineScoreToSimilarity,
    search_azure,
)


class AzureAISearcher(BaseSearcher):
    search_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        if AZUREAI_API_VERSION is None:
            raise Exception(
                "An api key is required to use Azure AI Search. Specify it via AZUREAI_API_KEY=..."
            )
        cls.search_params = search_params
        cls.api_version = AZUREAI_API_VERSION
        cls.service_endpoint = f"https://{AZUREAI_SERVICE_NAME}.search.windows.net"

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        query = {
            "count": True,
            "select": "Id",
            "vectorQueries": [
                {
                    "vector": query.vector,
                    "k": top,
                    "fields": "VectorField",
                    "kind": "vector",
                    "exhaustive": AZUREAI_EXHAUSTIVE_KNN,
                }
            ],
        }
        result = []
        total_requests = 0
        searchNextPage = True
        while searchNextPage is True:
            total_requests = total_requests + 1
            reply = search_azure(
                cls.service_endpoint,
                AZUREAI_INDEX_NAME,
                cls.api_version,
                AZUREAI_API_KEY,
                query,
            )

            for value in reply["value"]:
                id = int(value["Id"])
                score = float(value["@search.score"])
                result.append((id, score))

            # Continuation of Partial Search Responses
            # reference: https://learn.microsoft.com/en-us/rest/api/searchservice/search-documents
            # Sometimes Azure AI Search can't return all the requested results in a single Search response. This can happen for different reasons, such as when the query requests too many documents by not specifying $top or specifying a value for $top that is too large. In such cases, Azure AI Search includes the @odata.nextLink annotation in the response body, and also @search.nextPageParameters if it was a POST request. You can use the values of these annotations to formulate another Search request to get the next part of the search response. This is called a continuation of the original Search request, and the annotations are generally called continuation tokens. See the example in Response below for details on the syntax of these annotations and where they appear in the response body.
            if "@search.nextPageParameters" in reply:
                query = reply["@search.nextPageParameters"]
            else:
                searchNextPage = False
        return result
