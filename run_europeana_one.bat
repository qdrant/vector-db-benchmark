rem script intended to run experiments for one engine and one datasets
rem configure the ENGINE_NAME and the DATASETS with the wished values and run the script
rem NOTE: the database service needs to be run manually using the corresponding docker-compose command

set DATASETS="europeana-100"
rem all milvusw m-16
rem set ENGINE_NAME="milvusw-m-16-*"
rem all redisw m-16
set ENGINE_NAME="redisw-m-16-*"
rem all qdrantw m-16
rem set ENGINE_NAME="qdrantw-m-16-*"
rem all milvus
rem ENGINE_NAME="milvusw-m-*"

echo "Running experiment for engine(s): %ENGINE_NAME% using dataset: %DATASETS%"
python run.py --engines "%ENGINE_NAME%" --datasets "%DATASETS%"

pause ..


