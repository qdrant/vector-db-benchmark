import time
import swagger_client
from swagger_client.models import *
config = swagger_client.Configuration()
server = "192.168.99.40" #"192.168.99.33"
config.host = f"http://{server}:7760/v1.0"
config.verify_ssl = False
api_config = swagger_client.ApiClient(config)
alloc = "fvs-automation"
api_config.default_headers['allocationToken'] = alloc
datasets_apis = swagger_client.DatasetsApi(api_config)
search_apis = swagger_client.SearchApi(api_config)

importDataset=True
loadDataset=True

records = "/mnt/nas1/fvs_benchmark_datasets/deep-10K.npy"
qpath = "/mnt/nas1/fvs_benchmark_datasets/deep-queries-10.npy"
# records = "/home/public/tmpQdrant.npy"
# qpath = "/home/public/oneVecQdrant.npy"
top = 10
search_type = "clusters"
nbits = 768
m = None
efc = None
train_ind=True

# import dataset
if importDataset:
    dataset_id = datasets_apis.controllers_dataset_controller_import_dataset(
        ImportDatasetRequest(records=records, search_type=search_type, nbits=nbits, train_ind=train_ind, \
                             m_number_of_edges=m, ef_construction=efc),
        allocation_token=alloc
    ).dataset_id
else:
    dataset_id="tmp"
    
print("dataset id =", dataset_id, "\ntraining...")

status = datasets_apis.controllers_dataset_controller_get_dataset_status(
    dataset_id=dataset_id, allocation_token=alloc
).dataset_status
print(status)
while status != "completed":
    status = datasets_apis.controllers_dataset_controller_get_dataset_status(
        dataset_id=dataset_id, allocation_token=alloc
    ).dataset_status
    print('status currently:', status)
    time.sleep(3)

print("loading...")
loaded = datasets_apis.controllers_dataset_controller_load_dataset(
    LoadDatasetRequest(allocation_id=alloc, dataset_id=dataset_id, topk=top),
    allocation_token=alloc
)
print(loaded)

response = search_apis.controllers_search_controller_search(
    SearchRequest(allocation_id=alloc, dataset_id=dataset_id, queries_file_path=qpath, topk=top),
    alloc
)
print(response)
quit()