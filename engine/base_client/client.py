import json
from datetime import datetime
from typing import List

from benchmark.dataset import Dataset
from benchmark import ROOT_DIR
from engine.base_client.configure import BaseConfigurator
from engine.base_client.search import BaseSearcher
from engine.base_client.upload import BaseUploader

RESULTS_DIR = ROOT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


class BaseClient:
    def __init__(
        self,
        name: str,  # name of the experiment
        configurator: BaseConfigurator,
        uploader: BaseUploader,
        searchers: List[BaseSearcher],
    ):
        self.name = name
        self.configurator = configurator
        self.uploader = uploader
        self.searchers = searchers

    def save_search_results(
        self, dataset_name: str, results: dict, search_id: int, search_params: dict
    ):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        experiments_file = (
            f"{self.name}-{dataset_name}-search-{search_id}-{timestamp}.json"
        )
        with open(RESULTS_DIR / experiments_file, "w") as out:
            out.write(
                json.dumps({"params": search_params, "results": results}, indent=2)
            )

    def save_upload_results(self, dataset_name: str, results: dict):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        experiments_file = f"{self.name}-{dataset_name}-upload-{timestamp}.json"
        with open(RESULTS_DIR / experiments_file, "w") as out:
            out.write(json.dumps(results, indent=2))

    def run_experiment(self, dataset: Dataset):
        print("Experiment stage: Configure")
        self.configurator.configure(
            distance=dataset.config.distance, vector_size=dataset.config.vector_size,
        )

        reader = dataset.get_reader()
        print("Experiment stage: Upload")
        upload_stats = self.uploader.upload(reader.read_data())
        self.save_upload_results(dataset.config.name, upload_stats)

        print("Experiment stage: Search")
        for search_id, searcher in enumerate(self.searchers):
            search_params = {**searcher.search_params}
            search_stats = searcher.search_all(reader.read_queries())
            self.save_search_results(
                dataset.config.name, search_stats, search_id, search_params
            )
