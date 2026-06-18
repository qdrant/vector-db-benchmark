#!/usr/bin/env bash
# shellcheck disable=SC2016
# Run turbopuffer cold DBpedia benchmark.
# Creates a guaranteed-cold namespace via copy_from, then immediately
# fires run.py against it before anything warms up.

set -euo pipefail
cd "$(dirname "$0")/.."

set -a && source .env && set +a

# Use the poetry virtualenv python (has turbopuffer + all deps installed)
VENV_PY=$(find ~/.cache/pypoetry/virtualenvs -name python3.12 2>/dev/null | grep -v __pycache__ | head -1)
VENV_PY="${VENV_PY:-python3}"
echo "Using python: $VENV_PY"

SOURCE_NS="dbpedia-openai-100K-1536-angular"
COLD_NS="dbpedia-coldtest"

echo "=== Creating cold copy '$COLD_NS' from '$SOURCE_NS' ==="
"$VENV_PY" - <<PYEOF
import asyncio, os, time, turbopuffer as tpuf

async def main():
    client = tpuf.AsyncTurbopuffer(
        api_key=os.environ["TURBOPUFFER_API_KEY"],
        region=os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2"),
    )
    ns = client.namespace("$COLD_NS")
    # Delete if already exists so we get a guaranteed-cold fresh copy
    try:
        await ns.delete_all_indexes()
        print(f"Deleted existing '$COLD_NS'")
        await asyncio.sleep(2)  # brief pause before re-creating
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower() or "does not exist" in str(e).lower():
            pass  # namespace didn't exist, fine
        else:
            print(f"Note: delete returned: {e}")
    t0 = time.perf_counter()
    await ns.copy_from(source_namespace="$SOURCE_NS")
    print(f"copy_from done in {(time.perf_counter()-t0)*1000:.0f}ms")

asyncio.run(main())
PYEOF

echo ""
echo "=== Firing benchmark immediately (cold namespace) ==="
"$VENV_PY" run.py \
    --engines "turbopuffer-cold" \
    --datasets "dbpedia-openai-100K-1536-angular" \
    --skip-upload
