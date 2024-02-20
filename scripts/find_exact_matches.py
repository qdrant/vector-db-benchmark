import json
import clickhouse_connect


client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password='')

with open('queries.jsonl', 'r') as queries_file, open('neighbours.jsonl', 'w') as neighbours_file:
    for line in queries_file:
        query = json.loads(line.strip())
        result = client.query(f'SELECT id FROM bench ORDER BY cosineDistance(vector, {query}) ASC LIMIT 100')
        ids = [int(row[0]) for row in result.result_rows]
        neighbours_file.write(json.dumps(ids)+"\n")
        neighbours_file.flush()