import logging

from benchmark.backend.docker import DockerBackend
from benchmark.dataset import Dataset
from benchmark.engine import Engine
from parser import parser
from benchmark.scenario import Scenario

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Run the benchmark scenario using a selected backend. Backend is a specific
# way of setting up all the containers required by the benchmark, while the
# scenario decides how many instances of each type it requires.

args = parser.parse_args()
with DockerBackend() as backend:
    try:
        engine = Engine.from_name(args.engine)
        dataset = Dataset.from_name(args.dataset)
        scenario = Scenario.load_class(args.scenario)
        results = scenario.execute(backend, engine, dataset)

        # Iterate and display all the metrics
        # TODO: make the KPI metrics more configurable
        for phase, kpis_dict in results.items():
            for kpi_name, values in kpis_dict.items():
                print(f"mean({phase}::{kpi_name}) = {sum(values) / len(values)}")
    except FileNotFoundError as e:
        logger.error("Could not find a file: %s", e.filename)
