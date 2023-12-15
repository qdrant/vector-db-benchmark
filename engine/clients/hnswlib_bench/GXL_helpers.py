import os
from struct import *
from subprocess import run
from datetime import datetime

def convert_np_to_fbin(arr, out):
    print("convert np to fbin")
    if not os.path.exists(out):
        run(f"touch {out}", shell=True)
    else:
        os.remove(out)
        run(f"touch {out}", shell=True)
    f = open(out, "wb")
    header = pack("<II", arr.shape[0], arr.shape[1])
    
    f.write(header)
    for i in range(arr.shape[0]):
        if i % 100000 == 0: print("writing %d/%d" % (i + 1, arr.shape[0]))
        elin = arr[i]
        for d in range(arr.shape[1]):
            fval_in = elin[d]
            fval_out = pack("<f", fval_in)
            f.write(fval_out)
    
    f.flush()
    f.close()
    
def gen_labels(db_path, out):
    print("gen labels")
    f = open(db_path, "rb")
    header = f.read(8)
    vals = unpack("<II", header)
    print("header=", vals)
    f.close()
    print("size=", vals[0], vals[1])

    # open lbl file for write
    f = open(out, "wb")
    # create the fbin header
    header = pack("<II", vals[0], 8)
    print("header bytes =", len(header))
    # write header 
    f.write(header)
    for i in range(vals[0]):
        if i % 10000 == 0: print("writing %d/%d" % (i+1, vals[0]))
        fval_out = pack("<Q", i)
        f.write(fval_out)

    f.flush()
    f.close()
    print("Closed %s" % out)

def gxl_upload(db, m, efc):
    ret = {"cen_gen":None, "knn_gen": None, "knn_sym": None, "idx_gen": None}
    
    gxl_tmp = "/home/jacob/GXL/tmp"
    os.chdir(gxl_tmp)
    
    cen = "generated_q_centroids.bin"
    knn = "knn_graph.bin"
    dists = "distances.bin"
    s_knn = "s_knn_graph.bin"
    labels = "labels.lbl"
    
    if not os.path.exists(f"{gxl_tmp}/{labels}"):
        gen_labels(db, f"{gxl_tmp}/{labels}")
    
    if not os.path.exists(f"{gxl_tmp}/{cen}"):
        s = datetime.now()
        run(f"/home/jacob/GXL/bin/run-gxl-cen-gen {db}", shell=True) # produces centroids bin
        e = datetime.now()
        ret['cen_gen'] = (e-s).total_seconds()
    if not os.path.exists(f"{gxl_tmp}/{knn}"):
        s = datetime.now()
        run(f"/home/jacob/GXL/bin/run-gxl --db {db} --cent {gxl_tmp}/{cen}", shell=True) # produces knn_graph and distances
        e = datetime.now()
        ret['knn_gen'] = (e-s).total_seconds()
    if not os.path.exists(f"{gxl_tmp}/{s_knn}"):
        s = datetime.now()
        run(f"/home/jacob/GXL/bin/run-make-symmetric {gxl_tmp}/{knn} {gxl_tmp}/{dists}", shell=True) # produces s_knn_graph
        e = datetime.now()
        ret['knn_sym'] = (e-s).total_seconds()
    s = datetime.now()
    run(f"/home/jacob/GXL/bin/gxl-hnsw-idx-gen {db} {gxl_tmp}/{labels} {gxl_tmp}/{s_knn} {m} {efc}", shell=True) # produces deep1B_%dm_ef_%d_M_%d_gxl.bin
    e = datetime.now()
    ret['idx_gen'] = (e-s).total_seconds()
    
    ls = os.listdir(gxl_tmp)
    idx_name = [x for x in ls if f"ef_{efc}_M_{m}_gxl.bin" in x][0]
    os.environ["GXL_IDX"] = f"{gxl_tmp}/{idx_name}"
    
    return ret
    