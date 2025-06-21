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

# If explicitly calling valkey-server and running as root, drop privileges
if [ "$1" = 'valkey-server' ] && [ "$(id -u)" = '0' ]; then
    find . \! -user valkey -exec chown valkey '{}' +
    exec setpriv --reuid=valkey --regid=valkey --clear-groups -- "$0" "$@"
fi

# Set a restrictive umask if not already set
um="$(umask)"
if [ "$um" = '0022' ]; then
    umask 0077
fi

# first arg is `-f` or `--some-option`
# or first arg is `something.conf`
if [ "${1#-}" != "$1" ] || [ "${1%.conf}" != "$1" ]; then
    set -- valkey-server "$@"
fi

# If explicitly calling valkey-server, append modules and extra args
if [ "$1" = "valkey-server" ]; then
    shift
    exec valkey-server "$@" $MODULE_ARGS $EXTRA_ARGS
fi

# Else, run the provided command (e.g., bash)
exec "$@" $VALKEY_EXTRA_FLAGS
