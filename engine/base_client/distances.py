from enum import Enum


class Distance(str, Enum):
    DOT = "dot"
    COSINE = "cosine"
    L2 = "l2"

    @classmethod
    def from_name(cls, name) -> "Distance":
        name = name.upper().replace("-", "_")
        distance = cls.__members__.get(name)
        if distance is not None:
            return distance
        raise ValueError(f"Unknown distance: <{name}>")
