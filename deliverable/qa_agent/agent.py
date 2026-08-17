"""agent.py -- Step 5 of AI-TUTOR-WP-003: the LangChain agent.

The agent answers questions about Lecture 10 of COMP101 using the ontology as
its only source of truth. It has no knowledge of its own that it is allowed to
use: every factual claim must come from a graph tool.

Run it:
    .venv/bin/python agent.py               interactive
    .venv/bin/python agent.py "What is Encapsulation?"    single question
"""

import sys

from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from prompts import SYSTEM_PROMPT
from tools import GRAPH_TOOLS

MODEL_NAME = "gemma4:e2b-mlx"
TEMPERATURE = 0

# Ollama defaults to a 4096-token context. The system prompt and the five tool
# schemas cost roughly 1,500 tokens before the question is even asked, so a
# normal exchange overflowed the window and the model started answering with
# fragments of other questions. 8192 leaves room for a multi-tool answer while
# staying small enough to run on a laptop.
NUM_CTX = 8192


def build_agent(model_name: str = MODEL_NAME, temperature: float = TEMPERATURE):
    """Create the agent: a local Ollama model plus the graph tools."""
    llm = ChatOllama(model=model_name, temperature=temperature, num_ctx=NUM_CTX)
    return create_agent(model=llm, tools=GRAPH_TOOLS, system_prompt=SYSTEM_PROMPT)


def ask(agent, question: str) -> str:
    """Put one question to the agent and return its final answer."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


def _tool_calls_of(result) -> list[str]:
    """The tools the agent actually called, for the run log and the report."""
    names = []
    for message in result["messages"]:
        for call in getattr(message, "tool_calls", None) or []:
            names.append(call["name"])
    return names


def main() -> None:
    agent = build_agent()

    if len(sys.argv) > 1:
        print(ask(agent, " ".join(sys.argv[1:])))
        return

    print(f"COMP101 Lecture 10 tutor ({MODEL_NAME}). Ctrl-C to quit.\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        print(f"\ntools used: {_tool_calls_of(result) or 'NONE'}")
        print(f"tutor> {result['messages'][-1].content}\n")


if __name__ == "__main__":
    main()
