import logging
import time

from benchmark.backend import Backend
from benchmark.dataset import Dataset
from benchmark.engine import Engine
from benchmark.scenario import Scenario, ScenarioReport

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MeasureLoadTimeSingleClient(Scenario):
    """
    The simplest scenario, loading the data into selected backend with just a
    single client instance and measuring the time spent on that.
    """

    WAIT_TIME_SEC = 5.0

    def execute(self, backend: Backend, engine: Engine, dataset: Dataset):
        # Initialize the server first, so the client can communicate with it
        server = backend.initialize_server(engine)
        server.run()
        while not server.is_ready():
            time.sleep(self.WAIT_TIME_SEC)
        logger.debug("Initialized %s server", server)

        # Now create a single client instance
        client = backend.initialize_client(engine)
        client.mount(dataset.path(), "/dataset")
        client.run()
        logger.debug("Initialized %s client", client)

        # Finally load the data and track the container output
        for output_entry in client.load_data("vectors.jsonl"):
            self.collect_kpis(output_entry)

        # Generate the scenario report
        return self.process_results()
