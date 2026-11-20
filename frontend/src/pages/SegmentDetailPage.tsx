import { Code2, Mail, Pencil, Trash2, UsersRound } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { deleteSegment, getSegment, getSegmentMembers } from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import type { Segment, SegmentMember, SegmentResult } from "../api/types";
import CardHead from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import InfoTip from "../components/InfoTip";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import SegmentBuilder, { describeFilters } from "../components/SegmentBuilder";
import Spinner from "../components/Spinner";
import Tabs from "../components/Tabs";
import TopBar from "../components/TopBar";
import { useComposer, type ComposerState } from "../hooks/useComposer";
import WhatsappPane from "../components/WhatsappPane";

// pulls in the rich-text editor, so only load it once the Email tab is opened (the draft itself
// lives in useComposer, which is light, so it can be shared with the WhatsApp tab)
const EmailPane = lazy(() => import("../components/EmailPane"));

const EMAIL_BATCH_SIZE = 40;
const PAGE_SIZE = 25;

const TABS = [
  { key: "members", label: "Members" },
  { key: "email", label: "Email" },
  { key: "whatsapp", label: "WhatsApp" },
];

/** One segment on its own page: who is in it, and everything for reaching
 * them (email composer, WhatsApp chats) in one place. */
export default function SegmentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = TABS.some((t) => t.key === searchParams.get("tab")) ? (searchParams.get("tab") as string) : "members";

  const [segment, setSegment] = useState<Segment | null>(null);
  const [members, setMembers] = useState<SegmentResult | null>(null);
  // ONE draft for both channels: what's written in the Email tab is where the WhatsApp tab starts
  const recipients = useMemo(
    () => (members ? members.members.map((m) => ({ id: m.id, name: m.name, email: m.email, phone: m.phone })) : null),
    [members]
  );
  const composer = useComposer({ recipients, segmentId: id });
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
          {tab === "email" && <EmailTab composer={composer} members={members.members} />}
          {tab === "whatsapp" && (members.members.length === 0 ? <p className="muted small">No one is in this segment yet.</p> : <WhatsappPane composer={composer} />)}
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

function EmailTab({ composer, members }: { composer: ComposerState; members: SegmentMember[] }) {
  const emails = members.map((m) => m.email).filter((e): e is string => !!e);

  const batches: string[][] = [];
  for (let i = 0; i < emails.length; i += EMAIL_BATCH_SIZE) batches.push(emails.slice(i, i + EMAIL_BATCH_SIZE));

  if (members.length === 0) return <p className="muted small">No one is in this segment yet.</p>;

  return (
    <div className="card">
      <p className="small" style={{ margin: "0 0 6px" }}>
        <Mail size={13} className="h3-icon" /> {emails.length} of {members.length} have an email address.{" "}
        <InfoTip>Each person gets their own copy, with merge tags filled in for them.</InfoTip>
      </p>
      <Suspense fallback={<Spinner />}>
        <EmailPane embedded composer={composer} />
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
