#!/bin/sh
# Open in the system browser. No server or language runtime is needed.
cd -- "$(dirname -- "$0")" || exit 1
exec xdg-open "$PWD/index.html"
