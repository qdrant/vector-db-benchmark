import numpy as np
import json

# Adjust these parameters based on your data
array_shape = 1024  # Example shape, replace with the actual shape of arrays in your NDJSON
dtype = np.float32  # Adjust based on your data
ndjson_file_path = 'vectors.jsonl'
output_npy_path = 'vectors.npy'

# Preprocess to estimate number of lines/arrays for memory map size
print("Estimating size...")
num_lines = sum(1 for _ in open(ndjson_file_path, 'r'))

with open(ndjson_file_path, 'r') as ndjson_file:
    sample = json.loads(ndjson_file.readline())
    array_shape = len(sample)
print("Estimating shape...")

# Setup memory map
mmapped_array = np.memmap('temp_memmap.dat', dtype=dtype, mode='w+', shape=(num_lines, array_shape))

# Process NDJSON and write to memory-mapped array
print("Processing NDJSON...")
with open(ndjson_file_path, 'r') as file:
    for i, line in enumerate(file):
        arr = np.array(json.loads(line), dtype=dtype)
        mmapped_array[i] = arr

# Optionally, save the memory-mapped array to a .npy file
print("Saving to NPY...")
np.save(output_npy_path, mmapped_array)

# Cleanup
del mmapped_array  # Make sure changes are written to disk
# Optionally remove the temporary memory-mapped file if not needed
import os
os.remove('temp_memmap.dat')

print("Conversion complete.")