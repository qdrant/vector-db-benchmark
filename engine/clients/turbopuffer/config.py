import os
from typing import Optional

TURBOPUFFER_API_KEY = os.getenv("TURBOPUFFER_API_KEY")
TURBOPUFFER_REGION = os.getenv("TURBOPUFFER_REGION", "aws-us-west-2")
TURBOPUFFER_NAMESPACE = os.getenv("TURBOPUFFER_NAMESPACE", "benchmark")

# Set by TurbopufferConfigurator.configure() so uploader/searcher can fall back
# to the dataset name when no namespace is given in connection_params.
_active_namespace: Optional[str] = None


def resolve_namespace(connection_params: dict, dataset_name: Optional[str] = None) -> str:
    if "namespace" in connection_params:
        return connection_params["namespace"]
    if _active_namespace is not None:
        return _active_namespace
    if dataset_name:
        return dataset_name
    return TURBOPUFFER_NAMESPACE
