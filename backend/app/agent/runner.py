import json
from uuid import UUID

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.agent.model import get_model
from app.agent.tools import build_tools
from app.controllers import agent_controller
from app.models.pending_action import PendingAction

# One process-lifetime checkpointer shared across requests, keyed per
# org+user thread below - same idea as src/03_agent_with_memory.py, just
# scoped so different users/orgs don't share a conversation.
_checkpointer = InMemorySaver()

SYSTEM_PROMPT = (
    "You are the assistant inside a small business's mini CRM. You can look up, create, "
    "and update customer records and transactions using your tools - do this freely, these "
    "are reversible. Deleting a customer or merging duplicate customers is destructive and "
    "irreversible, so delete_customer and merge_customers never act immediately: they create "
    "a pending confirmation that a human must approve. When you call one of those, tell the "
    "user clearly that nothing has happened yet and they need to confirm it before it takes "
    "effect. Use search_customers or find_duplicate_customers to find the right customer_id "
    "before acting on a specific customer. Use get_dashboard_summary for any question about "
    "totals, sales, or trends instead of counting things yourself. Be concise."
)


def run_chat(db: Session, org_id: UUID, user_id: UUID, message: str) -> tuple[str, list[PendingAction]]:
    tools = build_tools(db, org_id, user_id)
    agent = create_agent(model=get_model(), tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=_checkpointer)
    config = {"configurable": {"thread_id": f"{org_id}:{user_id}"}}

    result = agent.invoke({"messages": [{"role": "user", "content": message}]}, config)
    messages = result["messages"]
    reply = messages[-1].content if messages else ""

    pending: list[PendingAction] = []
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        content = m.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (ValueError, TypeError):
                continue
        if isinstance(content, dict) and content.get("status") == "confirm_required" and content.get("action_id"):
            try:
                pending.append(agent_controller.get_pending_action(db, org_id, UUID(content["action_id"])))
            except agent_controller.PendingActionNotFoundError:
                continue

    return reply, pending
