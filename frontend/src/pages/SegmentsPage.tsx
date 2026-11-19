import { Code2, UsersRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { listSegmentsPaged } from "../api/segments";
import type { Segment } from "../api/types";
import CardHead from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import SegmentBuilder, { describeFilters } from "../components/SegmentBuilder";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { usePagedList } from "../hooks/usePagedList";

const PAGE_SIZE = 20;

export default function SegmentsPage() {
  const [creating, setCreating] = useState(false);
  const list = usePagedList<Segment>({
    fetcher: ({ search, page, pageSize }) => listSegmentsPaged({ search, page, pageSize }),
    pageSize: PAGE_SIZE,
  });
  const { items: segments, error } = list;

  return (
    <div>
      <TopBar title="Segments" backTo="/data" />
      <p className="muted small page-note">
        Define a group of customers by filters - always resolved live, never a stale snapshot. Open a segment to see who is
        in it and to email or WhatsApp them.
      </p>
      <ErrorText message={error} />

      {creating ? (
        <div className="card form-card">
          <SegmentBuilder onCancel={() => setCreating(false)} onSaved={() => { setCreating(false); list.reload(); }} />
        </div>
      ) : (
        <div className="page-actions">
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            + New segment
          </button>
          <SearchBox value={list.search} onChange={list.setSearch} label="Search segments" placeholder="Search segments…" />
        </div>
      )}

      {list.loading ? (
        <Spinner />
      ) : segments.length === 0 ? (
        <p className="muted small page-note">{list.searching ? "No segments match that search." : "No segments yet."}</p>
      ) : (
        <div className="card-grid">
          {segments.map((s) => (
            <Link key={s.id} to={`/segments/${s.id}`} className="card note-card segment-link">
              <CardHead
                icon={s.sql ? <Code2 /> : <UsersRound />}
                tone="violet"
                title={s.name}
                subtitle={s.sql ? "Custom SQL" : undefined}
              />
              {!s.sql && <p className="muted small clamp-text segment-filters">{describeFilters(s.filters)}</p>}
            </Link>
          ))}
        </div>
      )}
      {!list.loading && <Pagination page={list.page} pageSize={PAGE_SIZE} total={list.total} onChange={list.goToPage} />}
    </div>
  );
}
