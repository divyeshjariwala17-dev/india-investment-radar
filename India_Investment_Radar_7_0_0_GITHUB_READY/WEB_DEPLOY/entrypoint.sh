#!/bin/sh
set -eu
PORT="${PORT:-8501}"
# For permanent hosted data, mount a persistent disk/volume at /radar-data.
# If mounted, the app's existing BASE/data paths transparently use that volume.
if [ -d /radar-data ]; then
  if [ ! -f /radar-data/.initialized ]; then
    cp -a /app/data/. /radar-data/ 2>/dev/null || true
    touch /radar-data/.initialized
  fi
  rm -rf /app/data
  ln -s /radar-data /app/data
fi
exec python -m streamlit run /app/app.py \
  --server.address=0.0.0.0 \
  --server.port="$PORT" \
  --server.headless=true \
  --browser.gatherUsageStats=false \
  --runner.magicEnabled=false
