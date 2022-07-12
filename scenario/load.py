import logging
import time
from typing import Text

from benchmark.scenario import Scenario, ScenarioReport

logger = logging.getLogger(__name__)


class MeasureLoadTimeSingleClient(Scenario):
    """
    The simplest scenario, loading the data into selected backend with just a
    single client instance and measuring the time spent on that.
    """

    WAIT_TIME_SEC = 5.0

    def execute(self, engine: Text, dataset: Text):
        # Initialize the server first, so the client can communicate with it
        server = self.backend.initialize_server(engine)
        server.run()
        while not server.is_ready():
            time.sleep(self.WAIT_TIME_SEC)
        logger.debug("Initialized %s server", server)

        # Now create a single client instance
        client = self.backend.initialize_client(engine)
        client.mount(self.backend.root_dir / "dataset" / dataset, "/dataset")
        client.run()
        logger.debug("Initialized %s client", client)

        # Finally load the data and track the container output
        for output_entry in client.load_data("vectors.jsonl"):
            self.collect_kpis(output_entry)

        # Generate the scenario report
        return self.process_results()
