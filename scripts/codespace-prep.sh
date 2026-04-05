#!/bin/bash
set -e

# Run this locally before creating/rebuilding a Codespace.
# Dumps both databases and uploads them as a GitHub release on cr625/proethica.

echo "Dumping ProEthica database (ai_ethical_dm)..."
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
  --clean --if-exists --no-owner --no-privileges | gzip > /tmp/ai_ethical_dm.sql.gz

echo "Dumping OntServe database..."
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ontserve \
  --clean --if-exists --no-owner --no-privileges | gzip > /tmp/ontserve.sql.gz

echo "Dump sizes:"
ls -lh /tmp/ai_ethical_dm.sql.gz /tmp/ontserve.sql.gz

# Create or update the GitHub release
echo "Uploading to GitHub release 'codespace-db'..."
gh release delete codespace-db -R cr625/proethica -y 2>/dev/null || true
gh release create codespace-db \
  -R cr625/proethica \
  --title "Codespace DB Dumps" \
  --notes "Auto-generated database dumps for Codespace setup. Updated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  /tmp/ai_ethical_dm.sql.gz \
  /tmp/ontserve.sql.gz

rm -f /tmp/ai_ethical_dm.sql.gz /tmp/ontserve.sql.gz

echo ""
echo "Done. You can now create or rebuild your Codespace."
