import json
import clickhouse_connect


client = clickhouse_connect.get_client(host='w60d4cvz06.eu-central-1.aws.clickhouse.cloud', port=8443, username='default', password='r89_1Hiyf~NgB')

with open('queries.jsonl', 'r') as queries_file, open('neighbours.jsonl', 'w') as neighbours_file:
    for line in queries_file:
        query = json.loads(line.strip())
        result = client.query(f'SELECT id FROM hackernews_embeddings_annoy3 ORDER BY cosineDistance(vector, {query}) ASC LIMIT 100')
        ids = [row[0] for row in result.result_rows]
        neighbours_file.write(json.dumps(ids)+"\n")