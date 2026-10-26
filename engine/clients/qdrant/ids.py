import uuid
from typing import Union

PointId = Union[int, str]


def qdrant_point_id(record_id: Union[int, str, uuid.UUID]) -> PointId:
    """Qdrant accepts u64 or UUID. Python ints wider than 64 bits must be UUIDs."""
    if isinstance(record_id, uuid.UUID):
        return str(record_id)
    if isinstance(record_id, str):
        return record_id
    if record_id.bit_length() > 64:
        return str(uuid.UUID(int=record_id))
    return record_id


def qdrant_hit_id(hit_id: Union[int, str, uuid.UUID]) -> int:
    if isinstance(hit_id, uuid.UUID):
        return hit_id.int
    if isinstance(hit_id, str):
        try:
            return uuid.UUID(hit_id).int
        except ValueError:
            return int(hit_id)
    return int(hit_id)
