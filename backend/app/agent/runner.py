import json
from uuid import UUID

from langchain.agents import create_agent
from sqlalchemy.orm import Session

from app.agent.checkpointer import get_checkpointer
from app.agent.model import extract_text, get_model, get_vision_model
from app.agent.tools import build_tools
from app.controllers import agent_controller
from app.models.pending_action import PendingAction

SYSTEM_PROMPT = (
    "You are the assistant inside a small business's mini CRM. You can look up, create, "
    "and update customer records and transactions using your tools - do this freely, these "
    "are reversible. Deleting a customer or merging duplicate customers is destructive and "
    "irreversible, so delete_customer and merge_customers never act immediately: they create "
    "a pending confirmation that a human must approve. When you call one of those, tell the "
    "user clearly that nothing has happened yet and they need to confirm it before it takes "
    "effect. Use search_customers or find_duplicate_customers to find the right customer_id "
    "before acting on a specific customer. Use get_dashboard_summary for any question about "
    "totals, sales, or trends instead of counting things yourself.\n\n"
    "You may be shown a photo (e.g. a handwritten note, a receipt, a form, a business card). "
    "Read whatever is relevant to the customer list out of it and tell the user what you found; "
    "if it clearly describes a customer or a purchase, offer to create/update the record with "
    "your tools rather than just transcribing the image back at them - but confirm the details "
    "with the user first if the handwriting or print is unclear rather than guessing.\n\n"
    "Format every reply in markdown for readability: use short paragraphs, bullet or numbered "
    "lists for multiple items, and **bold** for names, amounts, and other key values - but stay "
    "concise, don't pad a one-line answer with headings or unnecessary structure."
)


def _build_user_content(message: str, image_data_url: str | None):
    if not image_data_url:
        return message
    return [
        {"type": "text", "text": message or "What do you see in this image?"},
        {"type": "image_url", "image_url": {"url": image_data_url}},
    ]


def run_chat(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    message: str,
    thread_id: str | None = None,
    image_data_url: str | None = None,
) -> tuple[str, list[PendingAction]]:
    tools = build_tools(db, org_id, user_id)
    model = get_vision_model() if image_data_url else get_model()
    agent = create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=get_checkpointer())
    # thread_id is client-supplied (lets the UI start a genuinely new
    # conversation, not just clear the visible transcript) but always
    # namespaced under org+user server-side, so a client can never read or
    # continue another org/user's conversation by guessing/reusing an id.
    config = {"configurable": {"thread_id": f"{org_id}:{user_id}:{thread_id or 'default'}"}}

    content = _build_user_content(message, image_data_url)
    result = agent.invoke({"messages": [{"role": "user", "content": content}]}, config)
    messages = result["messages"]
    reply = extract_text(messages[-1].content) if messages else ""

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
