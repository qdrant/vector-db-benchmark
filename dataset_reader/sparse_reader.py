import os
from typing import Iterator

import numpy as np
from scipy.sparse import csr_matrix

from dataset_reader.base_reader import BaseReader, Query, Record

# credit: code extracted from neuIPS 2023 benchmarks


def read_sparse_matrix_fields(fname):
    """read the fields of a CSR matrix without instantiating it"""
    with open(fname, "rb") as f:
        sizes = np.fromfile(f, dtype="int64", count=3)
        nrow, ncol, nnz = sizes
        indptr = np.fromfile(f, dtype="int64", count=nrow + 1)
        assert nnz == indptr[-1]
        indices = np.fromfile(f, dtype="int32", count=nnz)
        assert np.all(indices >= 0) and np.all(indices < ncol)
        data = np.fromfile(f, dtype="float32", count=nnz)
        return data, indices, indptr, ncol


def mmap_sparse_matrix_fields(fname):
    """mmap the fields of a CSR matrix without instantiating it"""
    with open(fname, "rb") as f:
        sizes = np.fromfile(f, dtype="int64", count=3)
        nrow, ncol, nnz = sizes
    ofs = sizes.nbytes
    indptr = np.memmap(fname, dtype="int64", mode="r", offset=ofs, shape=nrow + 1)
    ofs += indptr.nbytes
    indices = np.memmap(fname, dtype="int32", mode="r", offset=ofs, shape=nnz)
    ofs += indices.nbytes
    data = np.memmap(fname, dtype="float32", mode="r", offset=ofs, shape=nnz)
    return data, indices, indptr, ncol


def read_sparse_matrix(fname, do_mmap=False):
    """read a CSR matrix in spmat format, optionally mmapping it instead"""
    if not do_mmap:
        data, indices, indptr, ncol = read_sparse_matrix_fields(fname)
    else:
        data, indices, indptr, ncol = mmap_sparse_matrix_fields(fname)

    return csr_matrix((data, indices, indptr), shape=(len(indptr) - 1, ncol))


def knn_result_read(fname):
    n, d = map(int, np.fromfile(fname, dtype="uint32", count=2))
    assert os.stat(fname).st_size == 8 + n * d * (4 + 4)
    f = open(fname, "rb")
    f.seek(4 + 4)
    ids = np.fromfile(f, dtype="int32", count=n * d).reshape(n, d)
    scores = np.fromfile(f, dtype="float32", count=n * d).reshape(n, d)
    f.close()
    return ids, scores


class SparseReader(BaseReader):
    def __init__(self, path, normalize=False):
        self.path = path
        self.normalize = normalize

    def read_queries(self) -> Iterator[Query]:
        queries_path = self.path / "queries.csr"
        X = read_sparse_matrix(queries_path)

        gt_path = self.path / "results.gt"
        gt_indices, _ = knn_result_read(gt_path)

        print(f"Read sparse queries with shape {X.shape}")
        for i in range(X.shape[0]):
            yield Query(
                vector=None,
                sparse_vector=X[i],
                meta_conditions=None,
                expected_result=gt_indices[i].tolist(),
            )

    def read_data(self) -> Iterator[Record]:
        data_path = self.path / "data.csr"
        X = read_sparse_matrix(data_path)

        print(f"Read sparse data with shape {X.shape}")
        for i in range(X.shape[0]):
            yield Record(id=i, vector=None, sparse_vector=X[i], metadata=None)
