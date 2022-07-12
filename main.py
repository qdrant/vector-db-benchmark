import logging
from pathlib import Path

from benchmark.backend.docker import DockerBackend
from parser import parser
from benchmark.scenario import Scenario

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Run the benchmark scenario using a selected backend. Backend is a specific
# way of setting up all the containers required by the benchmark, while the
# scenario decides how many instances of each type it requires.

args = parser.parse_args()
current_dir = Path(__file__).parent
with DockerBackend(current_dir) as backend:
    try:
        scenario = Scenario.from_string(args.scenario, backend)
        results = scenario.execute(args.engine, args.dataset)

        # Iterate and display all the metrics
        # TODO: make the KPI metrics more configurable
        for phase, kpis_dict in results.items():
            for kpi_name, values in kpis_dict.items():
                print(f"mean({phase}::{kpi_name}) = {sum(values) / len(values)}")
    except FileNotFoundError as e:
        logger.error("Could not find a file: %s", e.filename)
