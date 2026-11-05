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
    "You are the assistant inside a small business's mini CRM. You have full authority to "
    "freely create and update every kind of writable record with your tools - customers, "
    "transactions, orders, and notes (including a note explicitly instructed by the user, "
    "attached to one or many named customers, via create_shared_note) - do this immediately, "
    "without asking permission first, these are all reversible. Deleting a customer or merging "
    "duplicate customers is the one destructive and irreversible case, so delete_customer and "
    "merge_customers never act immediately: they create a pending confirmation that a human "
    "must approve. When you call one of those, tell the user clearly that nothing has happened "
    "yet and they need to confirm it before it takes effect. Use search_customers or "
    "find_duplicate_customers to find the right customer_id(s) before acting on a specific "
    "customer. Use get_dashboard_summary for any question about totals, sales, or trends "
    "instead of counting things yourself.\n\n"
    "When you learn a new piece of information about a customer that isn't one of their "
    "standard fields (name, phone, email, job, nationality, pet, birthday, address, interests, "
    "status), decide whether it is a short, clearly-named fact - in which case call "
    "set_customer_custom_field - or whether it's free-form, ambiguous, multi-part, or you're "
    "not confident it's a clean field - in which case call add_customer_note instead. When in "
    "doubt, prefer add_customer_note: it's reviewed by a human later rather than silently "
    "creating a messy or wrong field. Use create_order (not add_transaction) when the user is "
    "describing something being ordered/fulfilled in the future rather than a completed sale.\n\n"
    "You may be shown a photo (e.g. a handwritten note, a receipt, a form, a business card). "
    "Read whatever is relevant to the customer list out of it and tell the user what you found; "
    "if it clearly describes a customer or a purchase, offer to create/update the record with "
    "your tools rather than just transcribing the image back at them - but confirm the details "
    "with the user first if the handwriting or print is unclear rather than guessing.\n\n"
    "Format every reply in markdown for readability: use short paragraphs, bullet or numbered "
    "lists for multiple items, and **bold** for amounts and other key values - but stay concise, "
    "don't pad a one-line answer with headings or unnecessary structure.\n\n"
    "CRITICAL FORMATTING RULE, apply it every single time, no exceptions: never write a specific, "
    "identified customer's name as plain text or **bold** text. Instead write it as a markdown "
    "link using their id from a tool result (search_customers, create_customer, add_transaction, "
    "etc.) in this exact form: [Full Name](customer:<id>). For example, instead of writing "
    "'**Lina Links** (ID: 3fae1c2a-1234-4a3b-9b21-abcdef123456)' or just 'Lina Links', write "
    "'[Lina Links](customer:3fae1c2a-1234-4a3b-9b21-abcdef123456)' - never show the raw id as "
    "visible text, it belongs only inside the link target. This applies in every sentence, "
    "bullet, and heading where a specific customer is named, not just the first mention. If you "
    "don't have that customer's id, write their name as plain text instead of guessing one."
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
