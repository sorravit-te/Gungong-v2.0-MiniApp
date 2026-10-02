# Community and deployment storage

Community is a shared public feed. Verified server-side identity is required for
posting, heart reactions, comments, reports, editing, and deletion. Only the
verified author can edit/delete. Public responses never include owner/reporter
IDs; viewer state is private and is not stored in the public feed cache.

Reactions and comments update counters in the same atomic Firestore batch as the
child document. A parent update-time precondition serializes mutations; bounded
retries re-read ownership/deletion and counters after contention. Comment retry
IDs are user-scoped. Edits require the current revision.

Reports are private pending-review records, not automatic scam verdicts. There
is no moderator processing UI in this change. Deletion hides the post/image and
removes its content/image from the parent. A tombstone prevents create retries
from resurrecting it; child records remain server-only, not a complete erasure.

## Free-tier deployment storage

Function Storage is deployment output, separate from Firestore History and
Community data. Deleting scan history does not reduce Vercel Function Storage.
Never delete the project/current deployment to address a storage warning.

The Docker image retains Python dependencies and BOTH bundled Chromium modes.
It omits precompiled `.pyc` files and apt package lists. Python compiles source
on import; this can add some cold-start work, not remove detection capabilities.
Do not remove browser/AI/Thai-language dependencies without separate testing.

Batch small changes into one release. Inspect current aliases before deleting
an obsolete deployment: historical alias metadata alone is not a live mapping.
Preserve the current release and a verified rollback release. Deleted releases
are no longer available at their generated URL or as rollback targets unless
successfully recovered. Storage accounting can lag; compare the same team,
metric and date range after Usage refreshes. Do not upgrade, create replacement
accounts, or repeatedly deploy to bypass a free-tier limit.

Sources: [Vercel storage](https://vercel.com/docs/deployment-storage),
[optimization](https://vercel.com/docs/deployment-storage/optimize).
