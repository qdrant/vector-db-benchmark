import json
from datetime import datetime

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.search import BaseSearcher
from engine.base_client.upload import BaseUploader


class BaseClient:
    def __init__(
        self,
        name: str,  # name of the experiment
        configurator: BaseConfigurator,
        uploader: BaseUploader,
        searcher: BaseSearcher,
    ):
        self.name = name
        self.configurator = configurator
        self.uploader = uploader
        self.searcher = searcher

    def save_experiment_results(self, dataset_name: str, results: dict):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        experiments_file = f"{self.name}-{dataset_name}-{timestamp}.json"
        with open(experiments_file, "w") as out:
            out.write(
                json.dumps(results, indent=2)
            )

    def run_experiment(self, dataset: Dataset):
        self.configurator.configure(
            distance=dataset.config.distance,
            vector_size=dataset.config.vector_size,
        )

        reader = dataset.get_reader()
        upload_stats = self.uploader.upload(reader.read_data())
        search_stats = self.searcher.search_all(reader.read_queries())

        self.save_experiment_results(
            dataset.config.name,
            {
                "upload": upload_stats,
                "search": search_stats
            }
        )
