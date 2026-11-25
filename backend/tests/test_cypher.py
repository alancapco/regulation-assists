from backend.app import cypher

# Live Cypher templates used by the API (status ping, LLM context, graph viz)
TEMPLATES = {
    "Q_PING": cypher.Q_PING,
    "Q_REGULATIONS": cypher.Q_REGULATIONS,
    "Q_GRAPH": cypher.Q_GRAPH,
}


def test_templates_present():
    assert len(TEMPLATES) == 3


def test_subgraph_isolation_guard():
    # Q_PING is RETURN 1 (no MATCH). Any MATCH on :Regulation must isolate by instrument_id.
    for name, q in TEMPLATES.items():
        if "MATCH (r:Regulation)" in q:
            assert "r.instrument_id IS NOT NULL" in q, name


def test_no_string_interpolation():
    for name, q in TEMPLATES.items():
        assert "${" not in q, name
