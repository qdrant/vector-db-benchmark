import os
from pathlib import Path
from typing import Iterator, List, Tuple, Union

import numpy as np

from dataset_reader.base_reader import BaseReader, Query, Record, SparseVector


def read_sparse_matrix_fields(
    filename: Union[Path, str]
) -> Tuple[np.array, np.array, np.array]:
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


def mmap_sparse_matrix_fields(fname):
    """mmap the fields of a CSR matrix without instantiating it"""
    with open(fname, "rb") as f:
        sizes = np.fromfile(f, dtype="int64", count=3)
        n_row, _n_col, n_non_zero = sizes
    offset = sizes.nbytes
    index_pointer = np.memmap(
        fname, dtype="int64", mode="r", offset=offset, shape=n_row + 1
    )
    offset += index_pointer.nbytes
    columns = np.memmap(fname, dtype="int32", mode="r", offset=offset, shape=n_non_zero)
    offset += columns.nbytes
    values = np.memmap(
        fname, dtype="float32", mode="r", offset=offset, shape=n_non_zero
    )
    return values, columns, index_pointer


def csr_to_sparse_vectors(
    values: List[float], columns: List[int], index_pointer: List[int]
) -> Iterator[SparseVector]:
    """Convert a CSR matrix to a list of SparseVectors"""
    num_rows = len(index_pointer) - 1

    for i in range(num_rows):
        start = index_pointer[i]
        end = index_pointer[i + 1]
        row_values, row_indices = [], []
        for j in range(start, end):
            row_values.append(values[j])
            row_indices.append(columns[j])
        yield SparseVector(indices=row_indices, values=row_values)


def read_csr_matrix(filename: Union[Path, str], do_mmap=True) -> Iterator[SparseVector]:
    """Read a CSR matrix in spmat format"""
    if do_mmap:
        values, columns, index_pointer = mmap_sparse_matrix_fields(filename)
    else:
        values, columns, index_pointer = read_sparse_matrix_fields(filename)

    yield from csr_to_sparse_vectors(values, columns, index_pointer)


def knn_result_read(
    filename: Union[Path, str]
) -> Tuple[List[List[int]], List[List[float]]]:
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


if __name__ == "__main__":
    vals = [1, 3, 2, 3, 6, 4, 5]
    cols = [0, 2, 2, 1, 3, 0, 2]
    pointers = [0, 2, 3, 5, 7]
    vecs = [vec for vec in csr_to_sparse_vectors(vals, cols, pointers)]

    assert vecs[0] == SparseVector(indices=[0, 2], values=[1, 3])
    assert vecs[1] == SparseVector(indices=[2], values=[2])
    assert vecs[2] == SparseVector(indices=[1, 3], values=[3, 6])
    assert vecs[3] == SparseVector(indices=[0, 2], values=[4, 5])
