# Main-compatible delivery reorganization

Scope: Echo-Smith / Marsh Echo-owned pull requests only. PR #2 and #29 stay open; other authors' PRs and branches are untouched. Mirror is a separate project.

## Build and deployment foundation

Base: upstream main 255169f. Keep Dockerfile and docker-compose.yml, including the default 8000 port and Redis service. The server Compose variant keeps its existing data volumes. Container builds use the lockfile and install the project after its source is copied.

Migration assets have one canonical home in src/psych_support_bot/infra/db/migrations, included in the installed wheel. The root alembic.ini remains a checkout CLI entrypoint. Startup and CLI use those same revisions. Supported database upgrades include main's versioned migration schema and its unversioned create_all schema. Unknown or partial schemas stop instead of guessing a revision.

For an existing default Compose deployment whose database is inside the old container at /app/psych_support_bot.db, back it up and copy it into the new app-data volume before replacing that container. Existing server Compose data at /app/data keeps its location. This change does not deploy, reset or erase any environment.

Local validation: 74 unit tests passed; installed wheel startup/health/static passed. Package versions equal the previously audited lock; the registry changes to upstream PyPI. Main's older conversation integration tests call an external model and expose its existing fallback bug; that implementation is carried into the dialogue replacement, not hidden by this infrastructure change. Verification: fresh, versioned and unversioned main database upgrades; existing-user preservation; installed-wheel startup; default/server Compose validation and container smoke. Docker is unavailable locally, so container validation runs in GitHub CI and its result is recorded separately.

## Review order

The first replacement PR targets upstream main. Dependent replacements target the previous branch in Echo-Smith's fork so their review diffs show only their own increment. Promote them to upstream after the prerequisite is merged; avoid creating several cumulative PRs against the same unchanged upstream main.
