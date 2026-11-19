import { Code2, Copy, ExternalLink, Mail, MessageCircle, Pencil, Trash2, UsersRound } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { deleteSegment, getSegment, getSegmentMembers } from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import { getDefaultCountryCode } from "../api/settings";
import type { Segment, SegmentMember, SegmentResult } from "../api/types";
import CardHead from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import SegmentBuilder, { describeFilters } from "../components/SegmentBuilder";
import Spinner from "../components/Spinner";
import Tabs from "../components/Tabs";
import TopBar from "../components/TopBar";
import { buildWaLink, normalizePhone } from "../utils/whatsapp";

// pulls in the rich-text editor, so only load it once the Email tab is opened
const EmailComposer = lazy(() => import("../components/EmailComposer"));

const EMAIL_BATCH_SIZE = 40;
const PAGE_SIZE = 25;

const TABS = [
  { key: "members", label: "Members" },
  { key: "email", label: "Email" },
  { key: "whatsapp", label: "WhatsApp" },
];

function personalize(message: string, member: SegmentMember): string {
  const firstName = member.first_name || member.name.split(" ")[0] || "";
  return message.replaceAll("{first_name}", firstName);
}

/** One segment on its own page: who is in it, and everything for reaching
 * them (email composer, WhatsApp chats) in one place. */
export default function SegmentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = TABS.some((t) => t.key === searchParams.get("tab")) ? (searchParams.get("tab") as string) : "members";

  const [segment, setSegment] = useState<Segment | null>(null);
  const [members, setMembers] = useState<SegmentResult | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    Promise.all([getSegment(id), getSegmentMembers(id)])
      .then(([s, m]) => {
        setSegment(s);
        setMembers(m);
        setError(null);
      })
      .catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, [id]);

  async function remove() {
    try {
      await deleteSegment(id);
      navigate("/segments", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function setTab(next: string) {
    setSearchParams(next === "members" ? {} : { tab: next }, { replace: true });
  }

  return (
    <div>
      <TopBar title={segment?.name ?? "Segment"} backTo="/segments" />
      <ErrorText message={error} />
      {!segment || !members ? (
        error ? null : <Spinner />
      ) : editing ? (
        <div className="card form-card">
          <SegmentBuilder
            initial={segment}
            onCancel={() => setEditing(false)}
            onSaved={() => {
              setEditing(false);
              load();
            }}
          />
        </div>
      ) : (
        <>
          <div className="card">
            <CardHead
              icon={segment.sql ? <Code2 /> : <UsersRound />}
              tone="violet"
              title={segment.name}
              subtitle={`${members.total} customer${members.total === 1 ? "" : "s"} right now`}
              items={[
                { key: "edit", label: "Edit segment", icon: <Pencil />, onSelect: () => setEditing(true) },
                { key: "div", divider: true },
                { key: "delete", label: "Delete segment", icon: <Trash2 />, danger: true, confirm: "Really delete?", onSelect: remove },
              ]}
            />
            {segment.sql ? (
              <details className="sql-reference">
                <summary className="muted small">
                  <Code2 size={12} className="h3-icon" /> Custom SQL
                </summary>
                <pre className="sql-snippet">{segment.sql}</pre>
              </details>
            ) : (
              <p className="muted small" style={{ overflowWrap: "anywhere" }}>
                {describeFilters(segment.filters)}
              </p>
            )}
          </div>

          <Tabs tabs={TABS} active={tab} onChange={setTab} />

          {tab === "members" && <MembersTab members={members.members} />}
          {tab === "email" && <EmailTab segmentId={segment.id} members={members.members} />}
          {tab === "whatsapp" && <WhatsappTab segmentId={segment.id} members={members.members} />}
        </>
      )}
    </div>
  );
}

function MembersTab({ members }: { members: SegmentMember[] }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return members;
    return members.filter((m) => [m.name, m.email, m.phone].some((v) => v?.toLowerCase().includes(q)));
  }, [members, search]);
  const last = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
  const current = Math.min(page, last);
  const shown = matches.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <div>
      <div className="page-actions">
        <SearchBox
          value={search}
          onChange={(v) => {
            setSearch(v);
            setPage(1);
          }}
          label="Search members"
          placeholder="Search name, email, phone…"
        />
      </div>
      {members.length === 0 ? (
        <p className="muted small">No one is in this segment yet.</p>
      ) : matches.length === 0 ? (
        <p className="muted small">No members match that search.</p>
      ) : (
        <div className="card submissions-list">
          {shown.map((m) => (
            <Link key={m.id} to={`/customers/${m.id}`} className="row-between">
              <span>{m.name}</span>
              <span className="muted small">{m.email ?? m.phone ?? "—"}</span>
            </Link>
          ))}
        </div>
      )}
      <Pagination page={current} pageSize={PAGE_SIZE} total={matches.length} onChange={setPage} />
    </div>
  );
}

function EmailTab({ segmentId, members }: { segmentId: string; members: SegmentMember[] }) {
  const emails = members.map((m) => m.email).filter((e): e is string => !!e);
  const recipients = useMemo(() => members.map((m) => ({ id: m.id, name: m.name, email: m.email, phone: m.phone })), [members]);

  const batches: string[][] = [];
  for (let i = 0; i < emails.length; i += EMAIL_BATCH_SIZE) batches.push(emails.slice(i, i + EMAIL_BATCH_SIZE));

  if (members.length === 0) return <p className="muted small">No one is in this segment yet.</p>;

  return (
    <div className="card">
      <p className="small" style={{ margin: "0 0 6px" }}>
        <Mail size={13} className="h3-icon" /> {emails.length} of {members.length} have an email address. Each person gets
        their own copy, with merge tags filled in for them.
      </p>
      <Suspense fallback={<Spinner />}>
        <EmailComposer embedded segmentId={segmentId} recipients={recipients} />
      </Suspense>
      {emails.length > 0 && (
        <details className="small" style={{ marginTop: 10 }}>
          <summary className="muted">Or write it in your own email app (BCC, no merge tags)</summary>
          <div className="row" style={{ marginTop: 8 }}>
            {batches.map((batch, i) => (
              <a key={i} href={`mailto:?bcc=${encodeURIComponent(batch.join(","))}`} className="btn-ghost">
                Open email{batches.length > 1 ? ` (batch ${i + 1}/${batches.length}, ${batch.length})` : ` (${batch.length})`}
              </a>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function WhatsappTab({ segmentId, members }: { segmentId: string; members: SegmentMember[] }) {
  const [message, setMessage] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  // members whose chat link was opened this session, so a long list can be
  // worked through without losing your place or messaging anyone twice
  const [opened, setOpened] = useState<Set<string>>(new Set());

  useEffect(() => {
    getDefaultCountryCode().then(setCountryCode);
  }, []);

  // only numbers wa.me can actually open; the rest are counted, not silently dropped
  const withPhone = members.filter((m) => m.phone);
  const chatMembers = withPhone.flatMap((m) => {
    const result = normalizePhone(m.phone, countryCode);
    return result.ok ? [{ member: m, digits: result.digits }] : [];
  });
  const unusableCount = withPhone.length - chatMembers.length;
  const last = Math.max(1, Math.ceil(chatMembers.length / PAGE_SIZE));
  const current = Math.min(page, last);
  const shown = chatMembers.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  async function copyNumbers() {
    try {
      await navigator.clipboard.writeText(chatMembers.map((c) => `+${c.digits}`).join("\n"));
      setCopyStatus("Phone numbers copied.");
    } catch {
      setCopyStatus("Could not copy - select the list manually.");
    }
  }

  return (
    <div className="card">
      <p className="small" style={{ margin: "0 0 6px" }}>
        <MessageCircle size={13} className="h3-icon" /> <b>WhatsApp</b> - {chatMembers.length} with a usable number
      </p>
      {unusableCount > 0 && (
        <p className="muted small">
          {unusableCount} {unusableCount === 1 ? "person has a number" : "people have numbers"} that can't open a chat (missing
          country code, too short, or not a number)
          {countryCode ? "" : " - set a default country code in Settings to fix local-format numbers like 0801…"}.
        </p>
      )}
      {chatMembers.length === 0 ? (
        <p className="muted small">No one in this segment has a usable phone number on file.</p>
      ) : (
        <>
          <label htmlFor={`seg-message-${segmentId}`}>Message</label>
          <textarea
            id={`seg-message-${segmentId}`}
            rows={3}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              setOpened(new Set());
            }}
          />
          <p className="muted small" style={{ marginTop: -6 }}>
            Use <code>{"{first_name}"}</code> to personalize each chat link below. People you have opened are marked, but that
            resets if you edit the message or leave the page - WhatsApp itself is the record of what was sent.
          </p>
          <p className="muted small">
            WhatsApp doesn't support one link for many recipients at once - copy these numbers and the message above into a
            broadcast list in your WhatsApp app.
          </p>
          <button type="button" onClick={copyNumbers}>
            <Copy size={14} /> Copy {chatMembers.length} phone number{chatMembers.length === 1 ? "" : "s"}
          </button>
          {copyStatus && <p className="muted small">{copyStatus}</p>}

          <p className="muted small" style={{ marginTop: 10 }}>
            Or open a personalized chat one at a time:
          </p>
          <div className="submissions-list">
            {shown.map(({ member: m, digits }) => {
              const link = buildWaLink(digits, personalize(message, m));
              return (
                <a
                  key={m.id}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="row-between"
                  onClick={() => setOpened((prev) => new Set(prev).add(m.id))}
                >
                  <span>
                    {m.name}
                    {opened.has(m.id) && <span className="muted small"> · opened</span>}
                  </span>
                  <span className="muted small">
                    {link.tooLong && <span className="tag-problems">message too long · </span>}
                    <ExternalLink size={12} className="h3-icon" /> +{digits}
                  </span>
                </a>
              );
            })}
          </div>
          <Pagination page={current} pageSize={PAGE_SIZE} total={chatMembers.length} onChange={setPage} />
        </>
      )}
    </div>
  );
}
