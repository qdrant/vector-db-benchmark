import json
import os

import requests

AZUREAI_API_KEY = os.getenv("AZUREAI_API_KEY", None)
DOC_COUNT = os.getenv("DOC_COUNT", None)
AZUREAI_SERVICE_NAME = os.getenv("AZUREAI_SERVICE_NAME", "vecsim")
AZUREAI_INDEX_NAME = os.getenv("AZUREAI_INDEX_NAME", "idx")
# invokes exhaustive KNN at query time, even if the field is indexed for HNSW.
AZUREAI_EXHAUSTIVE_KNN = bool(int(os.getenv("AZUREAI_EXHAUSTIVE_KNN", "0")))
AZUREAI_API_VERSION = os.getenv("AZUREAI_API_VERSION", "2024-05-01-preview")


# Define the function to list indices
def delete_index(service_endpoint, api_version, idx, api_key):
    # Endpoint URL
    endpoint = f"{service_endpoint}/indexes/{idx}?api-version={api_version}"

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.delete(endpoint, headers=headers)

    if response.status_code not in [200, 204]:
        raise Exception(
            f"Error while deleting index: {response.status_code} - {response.text}"
        )


# Define the function to list indices
def list_indices(service_endpoint, api_version, api_key):
    # Endpoint URL
    endpoint = f"{service_endpoint}/indexes?api-version={api_version}"

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Error while listing indices: {response.status_code} - {response.text}"
        )


# create index
def create_index(service_endpoint, api_version, api_key, index_definition):
    # Endpoint URL
    endpoint = f"{service_endpoint}/indexes?api-version={api_version}"

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.post(
        endpoint, headers=headers, data=json.dumps(index_definition)
    )

    # Print the results
    if response.status_code == 201:
        print("Index created successfully.")
    else:
        raise Exception(
            f"Error while creating index: {response.status_code} - {response.text}"
        )


# create index
def add_docs(service_endpoint, api_version, api_key, index_name, docs):
    # Endpoint URL
    endpoint = (
        f"{service_endpoint}/indexes/{index_name}/docs/index?api-version={api_version}"
    )

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.post(endpoint, headers=headers, data=json.dumps(docs))

    # Print the results
    if response.status_code != 200:
        raise Exception(
            f"Error while adding docs: {response.status_code} - {response.text}"
        )


def list_indices_statssummary(service_endpoint, api_version, api_key):
    # Endpoint URL
    endpoint = f"{service_endpoint}/indexes/statssummary?api-version={api_version}"

    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return f"Error: {response.status_code} - {response.text}"


# Define the search function
def search_azure(service_endpoint, index_name, api_version, api_key, query):
    endpoint = (
        f"{service_endpoint}/indexes/{index_name}/docs/search?api-version={api_version}"
    )
    headers = {"Content-Type": "application/json", "api-key": api_key}

    response = requests.post(endpoint, headers=headers, data=json.dumps(query))

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Error while searching: {response.status_code} - {response.text}"
        )


def cosineScoreToSimilarity(score):
    cosineDistance = float(1.0 - score) / score
    return cosineDistance
