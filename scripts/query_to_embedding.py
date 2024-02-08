
import json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

with open('queries.txt', 'r') as queries_file, open('queries.jsonl', 'w') as embeddings_file:
    for query in queries_file:
        vector = model.encode(query.strip())
        embeddings_file.write(json.dumps(vector.tolist())+"\n")
