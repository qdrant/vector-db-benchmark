from typing import Iterator

import h5py

from dataset_reader.base_reader import BaseReader, Record, Query


class H5Reader(BaseReader):

    def __init__(self, path):
        self.path = path

    def read_queries(self) -> Iterator[Query]:
        data = h5py.File(self.path)
        for vector, expected_result in zip(data['test'], data['neighbors']):
            yield Query(
                vector=vector.tolist(),
                meta_conditions=None,
                expected_result=expected_result.tolist(),
            )

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

    # h5py file 4 keys:
    # `train` - float vectors (num vectors 1183514)
    # `test` - float vectors (num vectors 10000)
    # `neighbors` - int - indices of nearest neighbors for test (num items 10k, each item
    # contains info about 100 nearest neighbors)
    # `distances` - float - distances for nearest neighbors for test vectors

    test_path = os.path.join(DATASET_DIR, 'glove-100-angular', 'glove-100-angular.hdf5')
    record = next(H5Reader(test_path).read_data())
    print(record, end='\n\n')

    query = next(H5Reader(test_path).read_queries())
    print(query)
