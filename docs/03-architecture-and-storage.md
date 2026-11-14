# ScoilMate: architecture and storage decision
Status: recommended, pending Dave approval. SQLite is relational, but embedded: no separate RDBMS server to install/administer.

```text
Browser (same origin, HTML/forms)
  → nginx (later: TLS, static assets, request limits)
  → Uvicorn → FastAPI routes + auth/CSRF dependencies
                → learning / publishing / account services
                → SQLAlchemy unit of work → local SQLite file
```

Start with Jinja2 server rendering and optional small JS enhancements, not React plus a second API deployment. Keep public lesson/quiz payloads separate from private answer keys. Modules: accounts, curriculum/content, quizzes/attempts, progress, administration. Routes call services; services own transactions and permissions; repositories do not accept arbitrary student IDs as authority. Synchronous SQLAlchemy work in synchronous handlers/threadpool rather than blocking async event loop. Request-scoped session, never shared globally across threads.

## Embedded options
| Engine | Assessment for this workload |
|---|---|
| SQLite | Recommended: transactions, foreign keys, joins, indexes, backup API, mature Python/SQLAlchemy/Alembic tooling. Suits low/medium traffic with short writes. One writer at a time; benchmark quiz bursts. |
| Berkeley DB (BDB) | Genuine embedded transactional key/value family; Oracle also documents a SQL API incorporating SQLite. Key/value use means implementing joins, indexes and integrity ourselves. Exact distribution licence and Python-binding maintenance need review; do not assume permissive licensing. No compelling benefit for relational learning records. |
| LMDB | Fast memory-mapped ordered key/value store; reader/writer transactions, one writer per environment. Excellent lookup/cache candidate, but relational constraints, migrations and progress queries become bespoke. Not selected. |
| DuckDB | Excellent embedded analytics, not first choice for many small account/attempt writes. Current 2.0 docs describe in-process single writer-process model plus Quack client/server option; do not repeat an obsolete blanket claim that multi-process writes are impossible. Server option violates the simplicity objective. Possible later offline aggregate analysis on de-identified exports. |
| JSON/TinyDB-style document files | Fine content interchange; inadequate default for concurrent durable sessions, relational integrity and submission idempotency. |
| New SQLite-compatible engines/distributed wrappers | No demonstrated requirement; compatibility/operational/licence validation would add risk. Prefer maintained upstream SQLite now. |

## SQLite operating contract
- Local persistent disk only, not NFS/shared network mount; database outside served/static paths and Git.
- Enable and verify foreign_keys on every connection; WAL selected and verified during setup; bounded busy timeout (proposed 5 s); short transactions. WAL permits readers alongside a writer, not many simultaneous writers.
- Explicitly choose/test sqlite3 transaction control on the selected Python version: SQLAlchemy documents legacy behaviour including DDL/savepoints. Do not rely on accidental autocommit.
- Initial one Uvicorn worker; additional workers do not remove SQLite writer limits. Do not update sessions on every request; throttle last-seen writes without losing expiry semantics.
- Answer insert, result and derived-progress update in one atomic transaction; bounded contention retry only around idempotent service operation. Reject overload gracefully, never silently lose progress.
- Alembic named constraints and reviewed batch migrations where SQLite table rebuilds are needed; test populated upgrade and recovery before release. Back up first. Never run migrations concurrently in worker startup.
- Consistent online SQLite backup API or controlled shutdown/checkpoint; copying only the live .db while WAL has changes is unsafe. Encrypt backups, restrict access, verify restore and integrity checks.

Load-test proposed 30 concurrent students submitting within a second, plus session/admin activity, on target hardware. Initial service target: p95 submission under 1 s, no lost/duplicate responses or unhandled locks. These are targets, not measured capability. Reassess with actual concurrency. Sustained writer contention, multi-host availability or multi-school scale triggers a new database decision (possibly PostgreSQL only with Dave's approval). SQLAlchemy reduces migration effort, not guarantees portability.
