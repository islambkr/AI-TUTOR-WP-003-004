"""Check how the agent is wired for conversation memory, without calling a model.

The agent remembers a conversation when it is built with a checkpointer and
invoked with a thread id. Whether the model then *uses* that history is a
question about the model, and it belongs in evaluation.py; these tests only
check the wiring, so they stay in the no-LLM suite.
"""

import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import build_agent, conversation_config  # noqa: E402


def test_build_agent_has_no_memory_by_default():
    """Evaluation cases are independent, and that depends on this default."""
    assert build_agent().checkpointer is None


def test_checkpointer_is_attached_when_asked_for():
    saver = InMemorySaver()
    assert build_agent(checkpointer=saver).checkpointer is saver


def test_memory_requires_a_thread_id():
    """An agent with memory cannot be invoked without naming a conversation.

    This is what makes the thread id impossible to forget: the failure is a
    ValueError at once, not a silently memoryless answer.
    """
    agent = build_agent(checkpointer=InMemorySaver())

    with pytest.raises(ValueError, match="thread_id"):
        agent.invoke({"messages": [{"role": "user", "content": "hello"}]})


def test_conversation_config_names_the_thread():
    assert conversation_config("abc") == {"configurable": {"thread_id": "abc"}}
