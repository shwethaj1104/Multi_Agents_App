import { useState, type ChangeEvent } from "react";
import { useAppDispatch } from "../../app/hooks";
import { caseSelected } from "../../app/workspaceSlice";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  ErrorState,
  LoadingState,
  formatMoney,
  statusLabel,
} from "../../components/ui/Feedback";
import { Icon } from "../../components/ui/Icon";
import { useGetApplicationsQuery } from "../../services/api/loanDeskApi";
import "./applicationsWorkspace.css";

/** Present submitted applications with search, compact rows and client-side pagination. */
export function ApplicationsWorkspace({ onCreate }: { onCreate: () => void }) {
  const dispatch = useAppDispatch();
  const {
    data: applications = [],
    error,
    isLoading,
    refetch,
  } = useGetApplicationsQuery();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const filtered = applications.filter(
    (item) =>
      !item.is_sample &&
      `${item.business_name} ${item.id} ${item.industry}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const first = (currentPage - 1) * pageSize;
  const visible = filtered.slice(first, first + pageSize);
  const pages = Array.from(
    { length: pageCount },
    (_, index) => index + 1,
  ).filter(
    (number) =>
      number === 1 ||
      number === pageCount ||
      Math.abs(number - currentPage) <= 1,
  );
  /** Reset pagination when the search changes so matching applications appear immediately. */
  function search(event: ChangeEvent<HTMLInputElement>) {
    setQuery(event.target.value);
    setPage(1);
  }
  /** Restart at the first page when the user changes how many rows to display. */
  function changePageSize(event: ChangeEvent<HTMLSelectElement>) {
    setPageSize(Number(event.target.value));
    setPage(1);
  }
  if (isLoading) return <LoadingState label="Loading applications…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <section
      className="application-register"
      aria-label="Applications register"
    >
      <div className="register-toolbar">
        <label className="search-field">
          <Icon name="search" />
          <span className="sr-only">Search applications</span>
          <input
            type="search"
            value={query}
            onChange={search}
            placeholder="Search applications…"
          />
        </label>
        <div className="register-actions">
          <Button variant="secondary" onClick={refetch}>
            Refresh
          </Button>
          <Button onClick={onCreate}>
            <Icon name="plus" />
            New application
          </Button>
        </div>
      </div>
      {visible.length ? (
        <div className="table-scroll">
          <table className="register-table">
            <thead>
              <tr>
                <th scope="col">No.</th>
                <th scope="col">Business</th>
                <th scope="col">Industry</th>
                <th scope="col">Requested amount</th>
                <th scope="col">Term</th>
                <th scope="col">Documents</th>
                <th scope="col">Status</th>
                <th scope="col">Submitted</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item, index) => (
                <tr key={item.id}>
                  <td>{first + index + 1}</td>
                  <td>
                    <button
                      className="register-business"
                      onClick={() =>
                        dispatch(caseSelected({ caseId: item.id }))
                      }
                    >
                      {item.business_name}
                    </button>
                    <small>{item.id.slice(0, 8)}</small>
                  </td>
                  <td>{item.industry}</td>
                  <td className="amount-cell">{formatMoney(item.amount)}</td>
                  <td>{item.term_months} months</td>
                  <td>
                    <span className="register-documents">
                      <Icon name="document" />
                      {item.document_count} file
                      {item.document_count === 1 ? "" : "s"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`application-status application-status--${item.review_status ?? "not_reviewed"}`}
                    >
                      {["queued", "running", "resuming"].includes(
                        item.review_status ?? "",
                      )
                        ? "In review"
                        : statusLabel(item.review_status ?? "not_reviewed")}
                    </span>
                  </td>
                  <td>
                    {new Date(item.created_at).toLocaleDateString(undefined, {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </td>
                  <td>
                    <button
                      className="register-open"
                      onClick={() =>
                        dispatch(caseSelected({ caseId: item.id }))
                      }
                      aria-label={`View ${item.business_name}`}
                    >
                      View
                      <Icon name="arrow" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon="applications"
          title={query ? "No matching applications" : "No applications yet"}
          description={
            query
              ? "Try another business name, industry or application ID."
              : "Create an application, attach its documents and begin your review."
          }
        />
      )}
      <div className="register-pagination">
        <div className="register-page-size">
          <label>
            Rows per page{" "}
            <select value={pageSize} onChange={changePageSize}>
              {[10, 25, 50].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <span>
            {filtered.length ? first + 1 : 0}–
            {Math.min(first + pageSize, filtered.length)} of {filtered.length}
          </span>
        </div>
        <nav aria-label="Application pages">
          <Button
            variant="secondary"
            disabled={currentPage === 1}
            onClick={() => setPage(currentPage - 1)}
          >
            ← Previous
          </Button>
          {pages.map((number, index) => (
            <span key={number}>
              {index > 0 && number - pages[index - 1] > 1 && (
                <span className="register-ellipsis">…</span>
              )}
              <button
                className="register-page"
                aria-label={`Page ${number}`}
                aria-current={number === currentPage ? "page" : undefined}
                onClick={() => setPage(number)}
              >
                {number}
              </button>
            </span>
          ))}
          <Button
            variant="secondary"
            disabled={currentPage === pageCount}
            onClick={() => setPage(currentPage + 1)}
          >
            Next →
          </Button>
        </nav>
      </div>
    </section>
  );
}
