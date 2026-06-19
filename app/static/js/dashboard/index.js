    function syncOntologies() {
        if (!confirm('Sync TTL files to database? This will update the database with the latest ontology definitions.')) {
            return;
        }

        alert('Please run: python scripts/sync_ontology_to_database.py\n\nThis operation should be run from the command line.');
    }
