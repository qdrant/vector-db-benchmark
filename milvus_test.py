import random
import multiprocessing as mp
from multiprocessing import Pool


import tqdm
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection,
    utility
)

_HOST = '49.12.245.80'
_PORT = '19530'

# Const names
_COLLECTION_NAME = 'demo1'
_ID_FIELD_NAME = 'id_field'
_VECTOR_FIELD_NAME = 'float_vector_field'

# Vector parameters
_DIM = 960

# Create a Milvus connection
def create_connection():
    print(f"\nCreate connection...")
    connections.connect(host=_HOST, port=_PORT)
    print(f"\nList connections:")
    print(connections.list_connections())


# Create a collection named 'demo'
def create_collection(name, id_field, vector_field):
    field1 = FieldSchema(name=id_field, dtype=DataType.INT64, description="int64", is_primary=True)
    field2 = FieldSchema(name=vector_field, dtype=DataType.FLOAT_VECTOR, description="float vector", dim=_DIM,
                         is_primary=False)
    schema = CollectionSchema(fields=[field1, field2], description="collection description")
    collection = Collection(name=name, data=None, schema=schema)
    print("\ncollection created:", name)
    return collection


def has_collection(name):
    return utility.has_collection(name)


# Drop a collection in Milvus
def drop_collection(name):
    collection = Collection(name)
    collection.drop()
    print("\nDrop collection: {}".format(name))


# List all collections in Milvus
def list_collections():
    print("\nlist collections:")
    print(utility.list_collections())


def insert(collection: Collection, offset, num, dim):
    data = [
        [i + offset for i in range(num)],
        [[random.random() for _ in range(dim)] if i != 33 else ([0.0] * dim) for i in range(num)],
    ]
    collection.insert(data)
    return data[1]


def get_entity_num(collection):
    print("\nThe number of entity:")
    print(collection.num_entities)


def create_index(collection, filed_name):
    index_param = {
        "index_type": "HNSW",
        "params": {"efConstruction": 100, "M": 16},
        "metric_type": "L2"}
    collection.create_index(filed_name, index_param)
    print("\nCreated index:\n{}".format(collection.index().params))


def drop_index(collection):
    collection.drop_index()
    print("\nDrop index sucessfully")


def load_collection(collection):
    collection.load()


def release_collection(collection):
    collection.release()


def search(collection, vector_field, id_field, search_vectors):
    search_param = {
        "data": search_vectors,
        "anns_field": vector_field,
        "param": {"metric_type": "L2", "params": {"ef": 100}},
        "limit": 10}
    results = collection.search(**search_param)
    for i, result in enumerate(results):
        print("\nSearch result for {}th vector: ".format(i))
        for j, res in enumerate(result):
            print("Top {}: {}".format(j, res))


def init_parallel():
    create_connection()


def upload_parallel(batch_id):
    collection = Collection(_COLLECTION_NAME)
    insert(collection, batch_id * 100, 100, _DIM)


def main():
    # create a connection
    create_connection()

    # drop collection if the collection exists
    if has_collection(_COLLECTION_NAME):
        drop_collection(_COLLECTION_NAME)

    # create collection
    collection = create_collection(_COLLECTION_NAME, _ID_FIELD_NAME, _VECTOR_FIELD_NAME)

    # show collections
    list_collections()

    context = mp.get_context('forkserver')
    # insert 10000 vectors with _DIM dimension
    with context.Pool(8, initializer=init_parallel) as pool:
        res = list(pool.imap(upload_parallel, tqdm.tqdm(range(100))))

    # get the number of entities
    get_entity_num(collection)

    # create index
    create_index(collection, _VECTOR_FIELD_NAME)

    # load data to memory
    load_collection(collection)

    # search
    search(collection, _VECTOR_FIELD_NAME, _ID_FIELD_NAME, [[1.0] * _DIM])

    # drop collection index
    drop_index(collection)

    # release memory
    release_collection(collection)

    # drop collection
    drop_collection(_COLLECTION_NAME)


if __name__ == '__main__':
    main()
