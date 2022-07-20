import time

from weaviate import Client


class Uploader:
    client = None

    @classmethod
    def init_client(cls):
        cls.client = Client("http://weaviate_server")

    @classmethod
    def update(cls, batch: list):
        for obj in batch:
            cls.client.batch.add_data_object(
                data_object=obj["data"],
                class_name="Bench",
                uuid=obj["id"],
                vector=obj["vector"],
            )
        start = time.monotonic()
        cls.client.batch.create_objects()
        end = time.monotonic()
        return end - start
