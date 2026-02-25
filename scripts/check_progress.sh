#!/bin/bash
# Check pipeline extraction progress for a given case
# Usage: ./scripts/check_progress.sh <case_id>

CASE_ID=${1:?Usage: check_progress.sh <case_id>}

echo "=== Case $CASE_ID Progress ==="
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "
SELECT extraction_type, COUNT(*) as total,
       SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published
FROM temporary_rdf_storage
WHERE case_id = $CASE_ID
GROUP BY extraction_type
ORDER BY extraction_type;
"

echo ""
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "
SELECT COUNT(*) as total,
       SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published,
       COUNT(DISTINCT extraction_type) as types
FROM temporary_rdf_storage WHERE case_id = $CASE_ID;
"

echo ""
RUNNING=$(ps aux | grep "run_pipeline.py $CASE_ID" | grep -v grep | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "Pipeline: RUNNING"
else
    echo "Pipeline: NOT RUNNING"
fi
