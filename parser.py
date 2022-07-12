from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument(
    "--engine",
    "-e",
    required=True,
    help="An engine to be benchmarked. It has to match one of the directory "
         "names in ./engine",
)
parser.add_argument(
    "--scenario",
    "-s",
    required=True,
    help="A scenario class, that will execute all the benchmark steps. For "
         "example `scenario.load.MeasureLoadTimeSingleClient`."
)
parser.add_argument(
    "--dataset",
    "-d",
    required=True,
    help="A dataset name, matching one of the directories in ./dataset"
)
