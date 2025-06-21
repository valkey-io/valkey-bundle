#!/bin/sh
set -e

MODULE_DIR="/usr/lib/valkey"
MODULE_ARGS=""

# Auto-discover and append all .so modules in MODULE_DIR
for module in "$MODULE_DIR"/*.so; do
    if [ -f "$module" ]; then
        MODULE_ARGS="$MODULE_ARGS --loadmodule $module"
    fi
done

# Optional: Add extra flags via env var (e.g., logging, maxmemory, etc.)
EXTRA_ARGS="${VALKEY_EXTRA_FLAGS:-}"

# If first argument starts with a dash, prepend valkey-server
if [ "${1#-}" != "$1" ]; then
    set -- valkey-server $MODULE_ARGS $EXTRA_ARGS "$@"
fi

# If explicitly calling valkey-server, append modules
if [ "$1" = "valkey-server" ]; then
    shift # remove valkey-server from $1
    exec valkey-server $MODULE_ARGS $EXTRA_ARGS "$@"
fi

# Else, run whatever is passed (e.g., bash)
exec "$@"
