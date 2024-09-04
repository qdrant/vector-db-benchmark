import json
from pymilvus import Collection, connections

milvus_host="localhost"
milvus_port="19530"
milvus_collection="apr2024"
number_or_entries_to_return_per_call=1000
milvus_collection_fields_to_return=["about","vector"]

# Connect to Milvus server
connections.connect(host=milvus_host, port=milvus_port) # Change to your Milvus server IP and port

# Get existing collection
collection = Collection(milvus_collection)

iterator = collection.query_iterator(
    batch_size=number_or_entries_to_return_per_call, # Controls the size of the return each time you call next()
    output_fields=milvus_collection_fields_to_return # Here write all fields you want to return
)

results = []
counter_files=1
with open("milvus_data_europeana.json", "w") as outfile:
    while True:
        result = iterator.next()
        if not result:
            iterator.close()
            break
        
        #results.extend(result)
        #save to json file
        for elem in result:
            outfile.write(str(elem['vector'])+'\n')
        #json.dump(str(result), outfile, indent=2)

