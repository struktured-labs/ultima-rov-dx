#!/usr/bin/env bash
# Convenience alias for the guarded launcher (never call mgba-qt directly).
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$PROJECT_DIR/scripts/launch_mgba.sh" "$@"
