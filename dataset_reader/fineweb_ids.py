import re
import uuid
from typing import Union
from urllib.parse import urlparse

URN_UUID_RE = re.compile(r"<urn:uuid:([0-9a-fA-F-]+)>")


def fineweb_id_to_int(raw: Union[str, uuid.UUID, None]) -> int:
    """Map a FineWeb corpus id or a bare GT UUID onto uuid.UUID.int."""
    if raw is None:
        raise ValueError("FineWeb id is missing")
    if isinstance(raw, uuid.UUID):
        return raw.int
    text = str(raw).strip()
    match = URN_UUID_RE.fullmatch(text) or URN_UUID_RE.search(text)
    if match:
        return uuid.UUID(match.group(1)).int
    return uuid.UUID(text).int


def url_domain(url: Union[str, None]) -> Union[str, None]:
    if not url:
        return None
    host = urlparse(str(url)).netloc.lower()
    return host or None
