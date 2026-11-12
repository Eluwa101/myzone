import { ArrowLeft } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { BASE_URL } from "../api/client";

const API = BASE_URL.replace(/\/$/, "");

const EVENTS = [
  "customer.created",
  "customer.updated",
  "customer.deleted",
  "transaction.created",
  "transaction.updated",
  "transaction.deleted",
  "order.created",
  "order.updated",
  "order.deleted",
  "note.created",
  "note.updated",
  "note.deleted",
];

const ENDPOINTS: { group: string; rows: [string, string, string][] }[] = [
  {
    group: "Customers",
    rows: [
      ["GET", "/api/customers", "List and search - ?search=, ?status_filter=lead|customer|inactive, ?page=, ?page_size="],
      ["POST", "/api/customers", "Create a customer"],
      ["GET", "/api/customers/{id}", "One customer"],
      ["GET", "/api/customers/by-id/{display_id}", "Look up by the ID shown in the app, e.g. CR001"],
      ["PATCH", "/api/customers/{id}", "Update some fields"],
      ["DELETE", "/api/customers/{id}", "Delete a customer and their records"],
      ["GET", "/api/customers/export", "Everything as CSV"],
    ],
  },
  {
    group: "Transactions (completed sales)",
    rows: [
      ["POST", "/api/customers/{id}/transactions", "Record a sale - one or more line items"],
      ["PATCH", "/api/customers/{id}/transactions/{transaction_id}", "Edit a sale"],
      ["DELETE", "/api/customers/{id}/transactions/{transaction_id}", "Remove a sale"],
    ],
  },
  {
    group: "Orders (to be fulfilled)",
    rows: [
      ["GET", "/api/orders", "All orders across customers"],
      ["GET", "/api/customers/{id}/orders", "One customer's orders"],
      ["POST", "/api/customers/{id}/orders", "Create an order"],
      ["PATCH", "/api/customers/{id}/orders/{order_id}", "Update, e.g. mark paid or delivered"],
      ["DELETE", "/api/customers/{id}/orders/{order_id}", "Remove an order"],
    ],
  },
  {
    group: "Notes, segments and email",
    rows: [
      ["GET", "/api/notes", "List notes"],
      ["POST", "/api/notes", "Create a note, optionally attached to customers"],
      ["GET", "/api/segments", "Saved segments"],
      ["GET", "/api/segments/{id}/members", "Who is in a segment right now"],
      ["POST", "/api/messages/send", "Email customers - merge tags are filled in per person"],
    ],
  },
];

const VERIFY_NODE = `import crypto from "node:crypto";

// Use the raw request body - before any JSON parsing.
function isFromMyShop(rawBody, signatureHeader, secret) {
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  return signatureHeader?.length === expected.length &&
    crypto.timingSafeEqual(Buffer.from(signatureHeader), Buffer.from(expected));
}`;

const VERIFY_PYTHON = `import hashlib, hmac

def is_from_myshop(raw_body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")`;

function Code({ children }: { children: string }) {
  return <pre className="dev-code">{children}</pre>;
}

/** /developers - public guide to calling the API with an API key. The
 * full, always-current reference is FastAPI's own /docs page. */
export default function DevelopersPage() {
  useEffect(() => {
    document.title = "Developers - MyShop";
    window.scrollTo(0, 0);
    return () => {
      document.title = "MyShop";
    };
  }, []);

  return (
    <div className="legal-page dev-page">
      <header className="legal-header">
        <Link to="/" className="legal-back">
          <ArrowLeft size={15} /> MyShop
        </Link>
        <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="small">
          Full API reference
        </a>
      </header>

      <article>
        <h1>Developers</h1>
        <p>
          Connect MyShop to your website, a spreadsheet, Zapier or your own code. Everything you can do in the app - customers, sales,
          orders, notes, segments, email - is available over a simple JSON API, and webhooks tell your systems the moment something changes.
        </p>

        <nav className="legal-toc" aria-label="Contents">
          <ol>
            <li><a href="#auth">Authentication</a></li>
            <li><a href="#quickstart">Quick start</a></li>
            <li><a href="#conventions">Conventions</a></li>
            <li><a href="#endpoints">Endpoints</a></li>
            <li><a href="#webhooks">Webhooks</a></li>
            <li><a href="#reference">Full reference</a></li>
          </ol>
        </nav>

        <section id="auth">
          <h2>1. Authentication</h2>
          <p>
            Create an API key in <Link to="/settings">Settings → API keys</Link>, give it a name you'll recognise (e.g. "Website form"),
            and copy it - it's shown once. Send it as a bearer token on every request:
          </p>
          <Code>{`Authorization: Bearer msk_live_...`}</Code>
          <ul>
            <li>A key acts as the person who created it, with full access to your business's data - treat it like a password.</li>
            <li>Keep it on a server. Never put it in a website's JavaScript or a mobile app, where anyone can read it.</li>
            <li>Use a separate key for each integration, so you can revoke one without breaking the others.</li>
            <li>Revoked or mistyped keys get <code>401 Invalid or revoked API key</code>. Keys can't create or revoke other keys.</li>
          </ul>
          <p>Base URL:</p>
          <Code>{API}</Code>
        </section>

        <section id="quickstart">
          <h2>2. Quick start</h2>
          <p>Find customers:</p>
          <Code>{`curl "${API}/api/customers?search=ada&page_size=20" \\
  -H "Authorization: Bearer $MYSHOP_KEY"`}</Code>
          <p>The reply is a page of results:</p>
          <Code>{`{ "items": [ { "id": "6f1c…", "display_id": "CR001", "name": "Ada Obi", … } ],
  "total": 1, "page": 1, "page_size": 20 }`}</Code>

          <p>Add a customer:</p>
          <Code>{`curl -X POST "${API}/api/customers" \\
  -H "Authorization: Bearer $MYSHOP_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"first_name": "Ada", "last_name": "Obi", "phone": "+2348012345678",
       "email": "ada@example.com", "consent_date": "2026-11-12"}'`}</Code>

          <p>Record a sale - one transaction with all its line items; each line's <code>amount</code> is that line's total:</p>
          <Code>{`curl -X POST "${API}/api/customers/CUSTOMER_ID/transactions" \\
  -H "Authorization: Bearer $MYSHOP_KEY" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: sale-20261112-0042" \\
  -d '{"date": "2026-11-12", "currency": "NGN",
       "items": [{"item": "Gas Lighter", "qty": 2, "amount": 1000},
                 {"item": "Cooking Gas 6kg", "amount": 9500}]}'`}</Code>

          <p>Look someone up by the customer ID printed on a receipt or card:</p>
          <Code>{`curl "${API}/api/customers/by-id/CR001" -H "Authorization: Bearer $MYSHOP_KEY"`}</Code>
        </section>

        <section id="conventions">
          <h2>3. Conventions</h2>
          <ul>
            <li>Requests and responses are JSON. Dates are <code>YYYY-MM-DD</code>; timestamps are ISO 8601 in UTC.</li>
            <li>Currencies are 3-letter codes (<code>NGN</code>, <code>USD</code>). If you leave one out, nothing is assumed for you.</li>
            <li>
              Lists that can grow are paged with <code>page</code> (from 1) and <code>page_size</code>, and return <code>total</code>.
            </li>
            <li>
              <b>Safe retries:</b> add an <code>Idempotency-Key</code> header (any unique string) to a <code>POST</code>,{" "}
              <code>PATCH</code> or <code>DELETE</code>. If you send the same key again within 7 days - say your request timed out - you
              get the original response back instead of a duplicate sale or customer.
            </li>
            <li>
              Errors use normal HTTP status codes with a <code>detail</code> field: <code>401</code> bad or missing key, <code>403</code>{" "}
              not allowed with a key, <code>404</code> not found (or not yours), <code>422</code> invalid input (the detail says which
              field).
            </li>
            <li>
              Emailing through <code>/api/messages/send</code> follows the same rules as the app: by default customers without a recorded
              consent date are skipped.
            </li>
          </ul>
        </section>

        <section id="endpoints">
          <h2>4. Endpoints</h2>
          <p>The ones most integrations need. The full reference lists every field and endpoint.</p>
          {ENDPOINTS.map((g) => (
            <div key={g.group} className="dev-table-wrap">
              <table className="dev-table">
                <caption>{g.group}</caption>
                <tbody>
                  {g.rows.map(([method, path, what]) => (
                    <tr key={method + path}>
                      <td>
                        <span className={`dev-method dev-method-${method.toLowerCase()}`}>{method}</span>
                      </td>
                      <td>
                        <code>{path}</code>
                      </td>
                      <td>{what}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>

        <section id="webhooks">
          <h2>5. Webhooks</h2>
          <p>
            Instead of asking for changes, let MyShop tell you. In the app, open <b>Data → Webhooks</b>, add the URL that should receive
            events, and pick which ones. We <code>POST</code> each event as JSON:
          </p>
          <Code>{`POST https://your-server.example/myshop
X-MyShop-Event: transaction.created
X-MyShop-Signature: 5d41402abc4b2a76b9719d911017c592…
Content-Type: application/json

{ "event": "transaction.created", "data": { …the record… } }`}</Code>
          <p>Events:</p>
          <p className="dev-events">
            {EVENTS.map((e) => (
              <code key={e}>{e}</code>
            ))}
          </p>
          <p>
            <b>Check the signature</b> before trusting an event: it's the hex HMAC-SHA256 of the raw request body, using the secret shown
            on the webhook in the app. Each delivery's result is listed there too.
          </p>
          <Code>{VERIFY_NODE}</Code>
          <Code>{VERIFY_PYTHON}</Code>
          <p>Reply with any 2xx status quickly; do slow work after responding.</p>
        </section>

        <section id="reference">
          <h2>6. Full reference</h2>
          <p>
            Every endpoint, field and error is listed - and can be tried live with your key - at{" "}
            <a href={`${API}/docs`} target="_blank" rel="noreferrer">
              {API}/docs
            </a>
            . The machine-readable OpenAPI description is at{" "}
            <a href={`${API}/openapi.json`} target="_blank" rel="noreferrer">
              {API}/openapi.json
            </a>
            , for generating a client in your language.
          </p>
          <p className="muted small">
            Use of the API is covered by our <Link to="/terms">Terms of Service</Link> and <Link to="/privacy">Privacy Policy</Link>.
          </p>
        </section>
      </article>

      <footer className="legal-footer small muted">
        <Link to="/developers">Developers</Link> · <Link to="/privacy">Privacy Policy</Link> · <Link to="/terms">Terms of Service</Link>
      </footer>
    </div>
  );
}
