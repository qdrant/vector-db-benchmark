from typing import Iterator

import h5py

from dataset_reader.base_reader import BaseReader, Record, Query


class H5Reader(BaseReader):

    def __init__(self, path):
        self.path = path

    def read_queries(self) -> Iterator[Query]:
        pass

    def read_data(self) -> Iterator[Record]:
        data = h5py.File(self.path)

        for idx, vector in enumerate(data['train']):
            yield Record(
                id=idx,
                vector=vector.tolist(),
                metadata=None
            )


if __name__ == '__main__':
    import os
    from benchmark.settings import DATASET_DIR
    test_path = os.path.join(DATASET_DIR, 'glove-100-angular', 'glove-100-angular.hdf5')
    record = next(H5Reader(test_path).read_data())
    print(record)