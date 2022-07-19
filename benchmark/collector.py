import re
from collections import defaultdict
from typing import Dict, List, Text

from benchmark.backend import LogsGenerator


class LogCollector:
    """
    Takes all the logs generators and combine their results together, by
    calculating the statistics of each KPI.
    """

    REGEX_KPI = re.compile(r"([a-zA-Z_]+::[a-zA-Z_]+) = ([0-9\.]+)", re.UNICODE)

    def __init__(self):
        self.generators = []

    def append(self, generator: LogsGenerator):
        self.generators.append(generator)

    def collect(self) -> Dict[Text, List[float]]:
        kpi_values = defaultdict(list)
        for generator in self.generators:
            for entry in generator:
                results = self.REGEX_KPI.findall(entry)
                for kpi, kpi_value in results:
                    kpi_values[kpi].append(float(kpi_value))
        return kpi_values
