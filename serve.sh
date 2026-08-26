#!/usr/bin/env sh

set -eu

SITE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PORT=${1:-4000}

case "$PORT" in
    *[!0-9]*|'')
        echo "Usage: ./serve.sh [port]" >&2
        exit 2
        ;;
esac

command -v jekyll >/dev/null 2>&1 || {
    echo "Error: Jekyll is not installed." >&2
    exit 1
}

command -v python3 >/dev/null 2>&1 || {
    echo "Error: Python 3 is not installed." >&2
    exit 1
}

cd "$SITE_DIR"

echo "Building twohalv.es..."
jekyll build

echo "Serving at http://127.0.0.1:$PORT/"
echo "Press Ctrl-C to stop."
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$SITE_DIR/_site"
