import importlib
import re
from collections import defaultdict
from typing import Dict, Text, Union

from benchmark.backend import Backend
from benchmark.dataset import Dataset
from benchmark.engine import Engine

ScenarioReport = Dict[Text, Dict[Text, float]]


class Scenario:
    """
    An abstract scenario for the benchmark. It may consist of several steps, but
    has to measure at least one KPI.
    """

    @classmethod
    def load_class(cls, scenario: Text) -> "Scenario":
        package_name, class_name = scenario.rsplit(".", maxsplit=1)
        module = importlib.import_module(package_name)
        clazz = getattr(module, class_name)
        scenario = clazz()
        return scenario

    def __init__(self):
        self._kpis = defaultdict(lambda: defaultdict(list))

    def execute(self, backend: Backend, engine: Engine, dataset: Dataset):
        ...

    def collect_kpis(self, output: Union[Text, bytes]):
        """
        Iterate through the output lines, extract the logged KPIs info and
        combine them into the format of ScenarioReport.
        :param output:
        :return:
        """
        if isinstance(output, bytes):
            output = output.decode("utf-8")
        results = re.findall(
            r"([a-zA-Z_]+)::([a-zA-Z_]+) = ([0-9\.]+)", output, re.UNICODE
        )
        for phase, kpi, time in results:
            self._kpis[phase][kpi].append(float(time))

    def process_results(self) -> ScenarioReport:
        # TODO: need to think about better structure
        return self._kpis
