from engine.clients.weaviate.config import weaviate_payload_properties


def test_drops_reserved_id_when_no_allow_list():
    props = weaviate_payload_properties(
        {"id": 1000, "title": "Cristiano Ronaldo", "vector": [0.1]}
    )
    assert "id" not in props
    assert "vector" not in props
    assert props["title"] == "Cristiano Ronaldo"


def test_empty_allow_list_sends_no_properties():
    props = weaviate_payload_properties(
        {"id": 1000, "title": "Cristiano Ronaldo"},
        allowed_names=frozenset(),
    )
    assert props == {}


def test_keep_only_declared_properties():
    props = weaviate_payload_properties(
        {"id": 1000, "title": "Cristiano Ronaldo", "langs": 156},
        allowed_names=frozenset({"title"}),
    )
    assert props == {"title": "Cristiano Ronaldo"}
