"""Reads a photographed document into structured data - one vision-model
call, no tools, nothing written. Deciding what to do with the result (and
checking it's safe to) is scan_controller's job, so the model can never
write to a customer record directly."""
import json
import re
from datetime import date

from app.agent.model import call_vision_with_fallback, extract_text


class DocumentReadError(Exception):
    pass


_PROMPT = """You read photos of paper documents for a small business - receipts, invoices, order slips, handwritten notes,
forms, business cards - and turn them into JSON.

Every customer has an ID like CR001 or CR042 (letters then digits), written or printed somewhere on the paper. Find it.

Reply with ONLY this JSON object (use null or [] for anything not on the document - never guess or invent values):
{
  "customer_id": "CR004",            // the customer ID exactly as written, or null if there isn't one
  "customer_name": "Ada Obi",        // the customer's name if written on it, else null
  "document_type": "receipt",        // receipt | invoice | order | note | form | business card | other
  "date": "YYYY-MM-DD",              // the document's date, if any
  "currency": "NGN",                 // 3-letter code if shown (₦ = NGN, $ = USD, £ = GBP, € = EUR), else null
  "transactions": [                  // completed, paid sales
    {"date": "YYYY-MM-DD", "currency": "NGN", "items": [{"item": "Gas Lighter", "qty": 2, "amount": 1000}]}
  ],
  "orders": [                        // things still to be delivered/fulfilled
    {"order_date": "YYYY-MM-DD", "delivery_date": null, "items": [{"name": "Cake", "qty": 1, "price": 15000}],
     "amount": 15000, "currency": "NGN", "paid": false, "delivered": false}
  ],
  "customer_fields": {"phone": null, "email": null, "address": null, "birthday": null, "job": null,
                      "first_name": null, "last_name": null, "interests": null},
  "custom_fields": {},               // other facts about the customer as "Label": "value", e.g. {"Shoe size": "42"}
  "notes": null,                     // anything else on the document worth keeping, as plain text
  "summary": "Receipt for 2 gas lighters"   // one short sentence describing the document
}

Rules:
- "amount" on a transaction line is that line's total (qty x unit price), as a plain number without currency symbols or commas.
- A paid receipt is a transaction; something ordered but not yet delivered is an order. Don't record the same thing as both.
- If a total is written but no line items, use one item named after what was bought (or "Purchase") with the total as its amount.
- Only record facts about the customer and what they bought. Skip the shop's own details (its name, address, phone,
  tax number) and boilerplate like "Thank you", "No refunds" or "Come again" - leave "notes" null if nothing is left.
- Dates in YYYY-MM-DD. Today is {today}."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def read_document(image_data_url: str, hint: str | None = None) -> dict:
    """Returns the JSON object described in _PROMPT. Raises DocumentReadError
    if the model's reply can't be used."""
    prompt = _PROMPT.replace("{today}", date.today().isoformat())
    text = "Read this document." + (f" The person who uploaded it says: {hint}" if hint else "")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": image_data_url}}]},
    ]
    result = call_vision_with_fallback(lambda model: model.invoke(messages))
    raw = _strip_fences(extract_text(result.content))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DocumentReadError(f"unreadable reply: {e}") from e
    if not isinstance(data, dict):
        raise DocumentReadError("reply wasn't a JSON object")
    return data
