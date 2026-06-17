#!/bin/sh
set -e

# Run as the owner of the bind-mounted evaluation/ so result files are written
# as the host user, not root. Adapts to any host uid; falls back to root if the
# dir is absent.
TARGET=$(stat -c '%u:%g' /app/evaluation 2>/dev/null || echo "0:0")

if [ "$TARGET" = "0:0" ]; then
    exec "$@"
fi

exec gosu "$TARGET" "$@"
