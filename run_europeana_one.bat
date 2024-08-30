rem script intended to run experiments for one engine and one datasets
rem configure the ENGINE_NAME and the DATASETS with the wished values and run the script
rem NOTE: the database service needs to be run manually using the corresponding docker-compose command

set DATASETS="random-100"
rem all milvus m-16
set ENGINE_NAME="milvusw-m-16-*"
rem all redis m-16
rem set ENGINE_NAME="redis-m-16-*"
rem all qdrant m-16
rem set ENGINE_NAME="qdrant-m-16-*"
rem all milvus
rem ENGINE_NAME="milvus-m-*"

echo "Running experiment for engine(s): %ENGINE_NAME% using dataset: %DATASETS%"
py run.py --engines "%ENGINE_NAME%" --datasets "%DATASETS%"

pause ..


