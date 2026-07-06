#!/usr/bin/env sh
set -eu

RUNS_DIR="${RUNS_DIR:-/tmp/deck-master-demo}"
RUN_ID="${RUN_ID:-oss-demo}"
FORCE="${DECK_MASTER_DEMO_FORCE:-1}"

FORCE_ARGS=""
if [ "$FORCE" != "0" ]; then
  FORCE_ARGS="--force"
fi

python3 scripts/deck_master.py autoplan \
  --brief-file examples/briefs/retail_digital_transformation.txt \
  --industry retail \
  --library-mode fixture \
  --run-mode fixture \
  --dev-allow-unsetup \
  --runs-dir "$RUNS_DIR" \
  --run-id "$RUN_ID" \
  $FORCE_ARGS

cat <<EOF

Demo run created:
  $RUNS_DIR/$RUN_ID

Next checks:
  python3 scripts/deck_master.py preview-gate --run-dir "$RUNS_DIR/$RUN_ID" --expect-unconfigured-backend-ok
  python3 scripts/preview/server.py --run-dir "$RUNS_DIR/$RUN_ID"
EOF
