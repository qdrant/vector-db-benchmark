from qdrant_client.http.models import SparseVector

from dataset_reader.base_reader import SparseMatrix


def csr_to_sparse_vector(point_csr: SparseMatrix) -> SparseVector:
    indices = point_csr.indices.tolist()
    values = point_csr.data.tolist()
    return SparseVector(indices=indices, values=values)
