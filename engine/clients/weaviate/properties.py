from typing import Any, Dict

# Property names Weaviate refuses to create (see `reservedPropertyNames` in
# entities/schema/validation.go of weaviate/weaviate); the server answers 422
# "'<name>' is a reserved property name".
RESERVED_PROPERTY_NAMES = frozenset({"_additional", "_id", "id"})

# Reserved names are stored under `<prefix><name>` instead.
RESERVED_PROPERTY_PREFIX = "prop_"


def property_name(name: str) -> str:
    """
    Name under which a dataset field is stored in Weaviate. Configure, upload
    and filter parsing must all go through this function, so the collection
    schema, the uploaded objects and the search filters keep agreeing on it.
    """
    if name in RESERVED_PROPERTY_NAMES:
        return f"{RESERVED_PROPERTY_PREFIX}{name}"
    return name


def rename_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply `property_name` to the keys of a schema or of a record payload.
    """
    renamed = {property_name(name): value for name, value in properties.items()}
    if len(renamed) != len(properties):
        raise ValueError(
            "Renaming Weaviate reserved properties produced a name collision: "
            f"{sorted(properties)}"
        )
    return renamed
