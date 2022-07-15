import re
from collections import defaultdict
from typing import Generator, Tuple, Text, Dict, List

from benchmark.backend import LogsGenerator


class LogCollector:
    def __init__(self):
        self.generators = []

    def append(self, generator: LogsGenerator):
        self.generators.append(generator)

    def collect(self) -> Dict[Text, List[float]]:
        kpi_values = defaultdict(list)
        for generator in self.generators:
            for entry in generator:
                results = re.findall(
                    r"([a-zA-Z_]+::[a-zA-Z_]+) = ([0-9\.]+)", entry, re.UNICODE
                )
                for kpi, kpi_value in results:
                    kpi_values[kpi].append(float(kpi_value))
        return kpi_values
