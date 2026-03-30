from unittest.mock import MagicMock
from burr.core import State
from zorkburr.actions.knowledge import update_knowledge
from zorkburr.state import S

def test_update_knowledge_synthesizes():
    mock_client = MagicMock()
    mock_raw = MagicMock()
    mock_client.client = mock_raw
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "## Strategic Insights\n- The mailbox contains a leaflet\n"
    mock_raw.chat.completions.create.return_value = mock_response
    state = State({
        S.KNOWLEDGE_BASE: "", S.ACTION_HISTORY: [{"turn": i, "action": f"a{i}", "response": f"r{i}"} for i in range(1, 11)],
        S.DISCOVERED_OBJECTIVES: ["Find treasure"], S.COMPLETED_OBJECTIVES: [],
        S.SCORE: 10, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })
    _, new_state = update_knowledge.run(state, client=mock_client, config=MagicMock(analysis_model="test"))
    assert "mailbox" in new_state[S.KNOWLEDGE_BASE].lower()

def test_update_knowledge_fallback_on_error():
    mock_client = MagicMock()
    mock_client.client.chat.completions.create.side_effect = Exception("API error")
    state = State({
        S.KNOWLEDGE_BASE: "existing", S.ACTION_HISTORY: [], S.DISCOVERED_OBJECTIVES: [],
        S.COMPLETED_OBJECTIVES: [], S.SCORE: 0, S.TURN_COUNT: 50, S.MEMORIES_BY_LOCATION: {},
    })
    result, new_state = update_knowledge.run(state, client=mock_client, config=MagicMock(analysis_model="test"))
    assert result["knowledge_length"] == 0
    assert new_state[S.KNOWLEDGE_BASE] == "existing"
