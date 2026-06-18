#!/usr/bin/env bash
# Run turbopuffer cold DBpedia benchmark.
# Creates a guaranteed-cold namespace via copy_from, then immediately
# fires run.py against it before anything warms up.

set -euo pipefail
cd "$(dirname "$0")/.."

set -a && source .env && set +a

SOURCE_NS="dbpedia-openai-100K-1536-angular"
COLD_NS="dbpedia-coldtest"

echo "=== Creating cold copy '$COLD_NS' from '$SOURCE_NS' ==="
python3 - <<PYEOF
import asyncio, os, time, turbopuffer as tpuf

async def main():
    client = tpuf.AsyncTurbopuffer(
        api_key=os.environ["TURBOPUFFER_API_KEY"],
        region=os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2"),
    )
    ns = client.namespace("$COLD_NS")
    t0 = time.perf_counter()
    await ns.copy_from(source_namespace="$SOURCE_NS")
    print(f"copy_from done in {(time.perf_counter()-t0)*1000:.0f}ms")

asyncio.run(main())
PYEOF

echo ""
echo "=== Firing benchmark immediately (cold namespace) ==="
python3 run.py \
    --engines "turbopuffer-cold" \
    --datasets "dbpedia-openai-100K-1536-angular" \
    --skip-upload
