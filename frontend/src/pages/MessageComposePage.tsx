import { Check, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getCustomer, listCustomers } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import { getSegmentMembers } from "../api/segments";
import type { Customer } from "../api/types";
import EmailComposer, { type Recipient } from "../components/EmailComposer";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

export default function MessageComposePage() {
  const [searchParams] = useSearchParams();
  const customerId = searchParams.get("customer_id");
  const segmentId = searchParams.get("segment_id");

  const [recipients, setRecipients] = useState<Recipient[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (customerId) {
      getCustomer(customerId)
        .then((c: Customer) => setRecipients([{ id: c.id, name: c.name, email: c.email ?? null, phone: c.phone ?? null }]))
        .catch((err) => setError(errorMessage(err)));
    } else if (segmentId) {
      getSegmentMembers(segmentId)
        .then((r) => setRecipients(r.members.map((m) => ({ id: m.id, name: m.name, email: m.email, phone: m.phone }))))
        .catch((err) => setError(errorMessage(err)));
    } else {
      setRecipients([]);
    }
  }, [customerId, segmentId]);

  const withoutEmail = (recipients ?? []).filter((r) => !r.email).length;

  return (
    <div>
      <TopBar title="Compose email" backTo="/messages" />

      <div className="card">
        <h3>Recipients</h3>
        {recipients === null ? (
          <Spinner />
        ) : (
          <>
            <p className="small">
              {recipients.length} customer{recipients.length === 1 ? "" : "s"} selected
              {withoutEmail > 0 && <span className="muted"> ({withoutEmail} without an email on file)</span>}
            </p>
            {!customerId && !segmentId && <RecipientPicker selected={recipients} onChange={setRecipients} />}
          </>
        )}
      </div>
      <ErrorText message={error} />

      <EmailComposer recipients={recipients} segmentId={segmentId} initialTemplateId={searchParams.get("template_id")} />
    </div>
  );
}

function RecipientPicker({ selected, onChange }: { selected: Recipient[]; onChange: (r: Recipient[]) => void }) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      listCustomers({ search, pageSize: 10 })
        .then((r) => setResults(r.items))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [search]);

  function add(c: Customer) {
    if (selected.some((r) => r.id === c.id)) return;
    onChange([...selected, { id: c.id, name: c.name, email: c.email ?? null, phone: c.phone ?? null }]);
  }

  function remove(id: string) {
    onChange(selected.filter((r) => r.id !== id));
  }

  return (
    <div>
      <div className="search-wrap">
        <Search size={16} className="search-icon" aria-hidden="true" />
        <input
          aria-label="Search customers to add"
          className="search-input"
          placeholder="Search customers to add…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {loading && <p className="muted small">Searching…</p>}
      {!loading && results.length > 0 && (
        <div className="quick-create-results">
          {results.map((c) => (
            <button key={c.id} type="button" className="quick-create-result" onClick={() => add(c)}>
              <Check size={13} /> {c.name}
            </button>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <div className="recipient-chips">
          {selected.map((r) => (
            <span key={r.id} className="chip">
              {r.name}
              <button type="button" aria-label={`Remove ${r.name}`} onClick={() => remove(r.id)}>
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
