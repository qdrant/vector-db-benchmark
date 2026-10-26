WEAVIATE_CLASS_NAME = "Benchmark"
WEAVIATE_DEFAULT_PORT = 8090
# Weaviate reserves these as object fields; payload keys with the same name
# (e.g. cohere-wiki-1m `id`) must not be inserted as properties.
WEAVIATE_RESERVED_PROPERTIES = frozenset({"id", "vector"})


def weaviate_payload_properties(metadata, allowed_names=None):
    if not metadata:
        return {}
    if allowed_names is not None:
        return {key: value for key, value in metadata.items() if key in allowed_names}
    return {
        key: value
        for key, value in metadata.items()
        if key not in WEAVIATE_RESERVED_PROPERTIES
    }
