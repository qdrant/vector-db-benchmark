from redis.commands.search.field import GeoField, NumericField, TextField

REDIS_INDEX_NAME = "benchmark"
REDIS_PORT = 6380

FIELD_MAPPING = {
    "int": NumericField,
    "keyword": TextField,
    "text": TextField,
    "float": NumericField,
    "geo": GeoField,
}
