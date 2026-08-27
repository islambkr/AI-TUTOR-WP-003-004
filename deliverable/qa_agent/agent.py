"""agent.py -- Step 5 of AI-TUTOR-WP-003: the LangChain agent.

The agent answers questions about Lecture 10 of COMP101 using the ontology as
its only source of truth. It has no knowledge of its own that it is allowed to
use: every factual claim must come from a graph tool

It also has short-term memory: within one conversation it remembers the earlier
turns, so "What does it depend on?" can follow "What is Encapsulation?". The
memory is held by a checkpointer and addressed by a thread id

"""

import sys
import uuid

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver

from prompts import SYSTEM_PROMPT
from tools import GRAPH_TOOLS

MODEL_NAME = "gemma4:e2b-mlx"
TEMPERATURE = 0

# Ollama defaults to a 4096-token context. Before the prompt and tool
# descriptions were trimmed they cost about 2,700 tokens before the question was
# even asked, and one tool result added ~900 more, so a normal exchange
# overflowed the window and the model began answering with fragments of other
# questions. They now cost about 1,600; 8192 leaves room for a multi-tool answer
# while staying small enough to run on a laptop.
#
# Conversation memory spends this same budget: every remembered turn, including
# its tool results, is re-sent on the next turn. That is why the interactive
# loop offers "/new" -- a long thread will eventually overflow the window, and
# the symptom is the fragment-answering described above.
NUM_CTX = 8192


def build_agent(
    model_name: str = MODEL_NAME,
    temperature: float = TEMPERATURE,
    checkpointer=None,
):
    """Create the agent: a local Ollama model plus the graph tools.

    Pass a checkpointer (for example InMemorySaver()) to give the agent
    short-term memory. The checkpointer stores the message history of each
    conversation under the thread id supplied at invoke time, so one agent can
    hold several independent conversations at once.

    It is None by default on purpose. evaluation.py reuses a single agent across
    all its cases, and those cases are independent by design -- a shared memory
    would let one case see another's history and would make the run order
    matter. Only the interactive loop turns memory on.
    """
    llm = ChatOllama(model=model_name, temperature=temperature, num_ctx=NUM_CTX)
    return create_agent(
        model=llm,
        tools=GRAPH_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def conversation_config(thread_id: str) -> dict:
    """The pointer to one conversation, passed to invoke as config=.
    Everything asked under the same thread id shares a history; a new id starts
    a conversation with no memory of the previous one
    """
    return {"configurable": {"thread_id": thread_id}}


def ask(agent, question: str, config: dict | None = None) -> str:
    """Put one question to the agent and return its final answer.
    
    Only the new message is sent. When the agent has a checkpointer and config
    names a thread, the stored history is prepended automatically.
    """
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}, config=config
    )
    return result["messages"][-1].content


def _tool_calls_of(result) -> list[str]:
    """The tools the agent actually called, for the run log and the report."""
    names = []
    for message in result["messages"]:
        for call in getattr(message, "tool_calls", None) or []:
            names.append(call["name"])
    return names


def main() -> None:
    # One question from the command line is not a conversation, so it gets no
    # memory and needs no thread.
    if len(sys.argv) > 1:
        print(ask(build_agent(), " ".join(sys.argv[1:])))
        return

    agent = build_agent(checkpointer=InMemorySaver())
    thread_id = str(uuid.uuid4())

    print(f"COMP101 Lecture 10 tutor ({MODEL_NAME}). Ctrl-C to quit.")
    print("Follow-up questions work; /new forgets the conversation.\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        if question == "/new":
            thread_id = str(uuid.uuid4())
            print("\nstarted a new conversation\n")
            continue

        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=conversation_config(thread_id),
        )
        print(f"\ntools used: {_tool_calls_of(result) or 'NONE'}")
        print(f"tutor> {result['messages'][-1].content}\n")


if __name__ == "__main__":
    main()
