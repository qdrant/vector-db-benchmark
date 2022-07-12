import importlib
import re
from collections import defaultdict
from typing import Text, Union, Dict

ScenarioReport = Dict[Text, Dict[Text, float]]


class Scenario:
    """
    An abstract scenario for the benchmark. It may consist of several steps, but
    has to measure at least one KPI.
    """

    @classmethod
    def from_string(cls, scenario: Text, backend: "Backend") -> "Scenario":
        package_name, class_name = scenario.rsplit(".", maxsplit=1)
        module = importlib.import_module(package_name)
        clazz = getattr(module, class_name)
        scenario = clazz(backend)
        return scenario

    def __init__(self, backend: "Backend"):
        self.backend = backend
        self._kpis = defaultdict(lambda: defaultdict(list))

    def execute(self, engine: Text, dataset: Text):
        ...

    def collect_kpis(self, output: Union[Text, bytes]):
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

