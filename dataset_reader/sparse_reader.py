import os
from pathlib import Path
from typing import Iterator, Tuple, Union, List

import numpy as np

from dataset_reader.base_reader import BaseReader, Query, Record, SparseVector


def read_sparse_matrix_fields(filename: Union[Path, str]) -> Tuple[np.array, np.array, np.array]:
    """Read the fields of a CSR matrix without instantiating it"""

    with open(filename, "rb") as f:
        sizes = np.fromfile(f, dtype="int64", count=3)
        n_row, n_col, n_non_zero = sizes
        index_pointer = np.fromfile(f, dtype="int64", count=n_row + 1)
        assert n_non_zero == index_pointer[-1]
        columns = np.fromfile(f, dtype="int32", count=n_non_zero)
        assert np.all(columns >= 0) and np.all(columns < n_col)
        values = np.fromfile(f, dtype="float32", count=n_non_zero)
        return values, columns, index_pointer


def csr_to_sparse_vectors(values: List[float], columns: List[int], index_pointer: List[int]) -> Iterator[SparseVector]:
    num_rows = len(index_pointer) - 1

    for i in range(num_rows):
        start = index_pointer[i]
        end = index_pointer[i + 1]
        row_values, row_indices = [], []
        for j in range(start, end):
            row_values.append(values[j])
            row_indices.append(columns[j])
        yield SparseVector(indices=row_indices, values=row_values)


def read_csr_matrix(filename: Union[Path, str]) -> Iterator[SparseVector]:
    """Read a CSR matrix in spmat format"""
    values, columns, index_pointer = read_sparse_matrix_fields(filename)
    values = values.tolist()
    columns = columns.tolist()
    index_pointer = index_pointer.tolist()

    yield from csr_to_sparse_vectors(values, columns, index_pointer)


def knn_result_read(filename: Union[Path, str]) -> Tuple[List[List[int]], List[List[float]]]:
    n, d = map(int, np.fromfile(filename, dtype="uint32", count=2))
    assert os.stat(filename).st_size == 8 + n * d * (4 + 4)
    with open(filename, "rb") as f:
        f.seek(4 + 4)
        ids = np.fromfile(f, dtype="int32", count=n * d).reshape(n, d).tolist()
        scores = np.fromfile(f, dtype="float32", count=n * d).reshape(n, d).tolist()
    return ids, scores


class SparseReader(BaseReader):
    def __init__(self, path, normalize=False):
        self.path = path
        self.normalize = normalize

    def read_queries(self) -> Iterator[Query]:
        queries_path = self.path / "queries.csr"
        X = read_csr_matrix(queries_path)

        gt_path = self.path / "results.gt"
        gt_indices, _ = knn_result_read(gt_path)

        for i, sparse_vector in enumerate(X):
            yield Query(
                vector=None,
                sparse_vector=sparse_vector,
                meta_conditions=None,
                expected_result=gt_indices[i],
            )

    def read_data(self) -> Iterator[Record]:
        data_path = self.path / "data.csr"
        X = read_csr_matrix(data_path)

        for i, sparse_vector in enumerate(X):
            yield Record(id=i, vector=None, sparse_vector=sparse_vector, metadata=None)


if __name__ == '__main__':
    vals = [1, 3, 2, 3, 6, 4, 5]
    cols = [0, 2, 2, 1, 3, 0, 2]
    pointers = [0, 2, 3, 5, 7]
    vecs = [vec for vec in csr_to_sparse_vectors(vals, cols, pointers)]

    assert vecs[0] == SparseVector(indices=[0, 2], values=[1, 3])
    assert vecs[1] == SparseVector(indices=[2], values=[2])
    assert vecs[2] == SparseVector(indices=[1, 3], values=[3, 6])
    assert vecs[3] == SparseVector(indices=[0, 2], values=[4, 5])
