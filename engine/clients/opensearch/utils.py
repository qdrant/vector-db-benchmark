from opensearchpy import OpenSearch


def get_index_thread_qty_for_force_merge(client: OpenSearch):
    processors_per_node = get_cores_for_data_nodes(client=client)
    # since during force merge only 1 shard will be doing the merge we can be aggressive in parallelization factor
    index_thread_qty = max(1, processors_per_node // 2)
    print(f"Index thread qty for force merge: {index_thread_qty}")
    return index_thread_qty


def get_index_thread_qty(client: OpenSearch):
    processors_per_node = get_cores_for_data_nodes(client=client)
    # since during index more than 1 shard will be doing indexing, we are becoming conservative in parallelization factor
    index_thread_qty = max(1, processors_per_node // 8)
    print(f"Index thread qty for indexing: {index_thread_qty}")
    return index_thread_qty


def get_cores_for_data_nodes(client: OpenSearch):
    # Sample nodes info response which is getting parsed.
    # {
    #     "nodes": {
    #         "Or9Nm4UJR3-gcMOGwJhHHQ": {
    #             "roles": [
    #                 "data",
    #                 "ingest",
    #                 "master",
    #                 "remote_cluster_client"
    #             ],
    #             "os": {
    #                 "refresh_interval_in_millis": 1000,
    #                 "available_processors": 8,
    #                 "allocated_processors": 8
    #             }
    #         },
    #         "A-cqbeekROeR3kzKhOXpRw": {
    #             "roles": [
    #                 "data",
    #                 "ingest",
    #                 "master",
    #                 "remote_cluster_client"
    #             ],
    #             "os": {
    #                 "refresh_interval_in_millis": 1000,
    #                 "available_processors": 8,
    #                 "allocated_processors": 8
    #             }
    #         },
    #         "FrDs-vOMQ8yDZ0HEkDwRHA": {
    #             "roles": [
    #                 "data",
    #                 "ingest",
    #                 "master",
    #                 "remote_cluster_client"
    #             ],
    #             "os": {
    #                 "refresh_interval_in_millis": 1000,
    #                 "available_processors": 8,
    #                 "allocated_processors": 8
    #             }
    #         }
    #     }
    # }

    nodes_stats_res = client.nodes.info(filter_path="nodes.*.roles,nodes.*.os")
    nodes_data = nodes_stats_res.get("nodes")
    data_node_count = 0
    total_processors = 0
    for node_id in nodes_data:
        node_info = nodes_data.get(node_id)
        roles = node_info["roles"]
        os_info = node_info["os"]
        if "data" in roles:
            data_node_count += 1
            total_processors += int(os_info["allocated_processors"])
    processors_per_node = total_processors // data_node_count
    return processors_per_node


def update_force_merge_threads(client: OpenSearch, index_thread_qty=1):
    cluster_settings_body = {
        "persistent": {"knn.algo_param.index_thread_qty": index_thread_qty}
    }
    client.cluster.put_settings(cluster_settings_body)
