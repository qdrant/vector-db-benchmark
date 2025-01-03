# lancedb Parameters

See https://lancedb.github.io/lancedb/ann_indexes/#how-to-choose-num_partitions-and-num_sub_vectors-for-ivf_pq-index

## search_params
    "parallel": 1,8,100,
    "config": {}

## upload_params
    "parallel": 16,
    "batch_size": 1024,
    "indices": [
        {
            "num_partitions": 256,512,
            "num_sub_vectors": 8,16,64
        }
    ]
