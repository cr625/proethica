"""
Cited Case Ingestor Service

Discovers and ingests cases cited in existing case documents.
Uses the existing CaseUrlProcessor to fetch and process NSPE case pages.

Flow:
1. Scan case_precedent_features for unresolved citations
2. Check if cited cases exist in database
3. Build NSPE URL for missing cases
4. Fetch and process missing cases using CaseUrlProcessor
5. Update cited_case_ids with resolved references

Usage:
    from app.services.precedent import CitedCaseIngestor

    ingestor = CitedCaseIngestor()
    results = ingestor.ingest_missing_citations()

References:
    - NSPE BER Case Archive: https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy import text

from app.models import db
from app.models.case_precedent_features import CasePrecedentFeatures

logger = logging.getLogger(__name__)


class CitedCaseIngestor:
    """
    Discovers and ingests cases cited in existing case documents.
    """

    # NSPE URL patterns for BER cases
    BER_URL_PATTERNS = [
        r'https://www\.nspe\.org/resources/ethics/ethics-resources/board-ethical-review-cases/[a-z0-9-]+',
        r'https://www\.nspe\.org/career-growth/ethics/board-ethical-review-cases/[a-z0-9-]+',
    ]

    def __init__(self):
        """Initialize the ingestor."""
        self._processor = None

    def _run_ingestion_pipeline(self, url: str) -> Optional[Dict]:
        """
        Run the proper NSPE case ingestion pipeline.

        Uses the same pipeline as /cases/new/url for proper extraction.

        Args:
            url: NSPE case URL

        Returns:
            Dict with extracted case data, or None if failed
        """
        from app.services.case_processing.pipeline_manager import PipelineManager
        from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
        from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep

        pipeline = PipelineManager()
        pipeline.register_step('url_retrieval', URLRetrievalStep())
        pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())

        steps_to_run = ['url_retrieval', 'nspe_extraction']

        logger.info(f"Running pipeline for URL: {url}")
        result = pipeline.run_pipeline({'url': url}, steps_to_run)

        if result.get('status') == 'error':
            logger.error(f"Pipeline failed for {url}: {result.get('error')}")
            return None

        # The actual extracted data is in 'final_result'
        return result.get('final_result', {})

    def find_missing_citations(self) -> List[Dict]:
        """
        Find all cited cases that don't exist in the database.

        Returns:
            List of dicts: [{'case_number': '92-1', 'citing_cases': [1, 5, 10]}, ...]
        """
        # Get all unique cited case numbers and which cases cite them
        query = text("""
            WITH cited_numbers AS (
                SELECT
                    cpf.case_id as citing_case_id,
                    unnest(cpf.cited_case_numbers) as cited_case
                FROM case_precedent_features cpf
                WHERE cpf.cited_case_numbers IS NOT NULL
            ),
            extracted_numbers AS (
                SELECT
                    citing_case_id,
                    regexp_replace(cited_case, '[^0-9-]', '', 'g') as case_number
                FROM cited_numbers
            ),
            aggregated AS (
                SELECT
                    case_number,
                    array_agg(DISTINCT citing_case_id) as citing_cases,
                    count(DISTINCT citing_case_id) as citation_count
                FROM extracted_numbers
                WHERE case_number != ''
                GROUP BY case_number
            )
            SELECT
                a.case_number,
                a.citing_cases,
                a.citation_count,
                d.id as existing_id
            FROM aggregated a
            LEFT JOIN documents d ON (
                d.title ~* ('Case\\s+' || a.case_number)
                OR d.doc_metadata->>'case_number' = a.case_number
            )
            WHERE d.id IS NULL
            ORDER BY a.citation_count DESC
        """)

        results = db.session.execute(query).fetchall()

        return [
            {
                'case_number': row[0],
                'citing_cases': row[1],
                'citation_count': row[2]
            }
            for row in results
        ]

    def build_case_urls(self, case_number: str) -> List[str]:
        """
        Build NSPE URLs for a case number.

        Args:
            case_number: Case number (e.g., '92-1', '2010-3')

        Returns:
            List of possible URLs to try
        """
        return [
            template.format(case_number=case_number)
            for template in self.NSPE_URL_TEMPLATES
        ]

    def check_url_exists(self, url: str) -> bool:
        """
        Check if a URL returns a valid page (not 404).

        Args:
            url: URL to check

        Returns:
            True if page exists
        """
        import requests

        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def ingest_case(self, case_number: str, world_id: int = None) -> Optional[Dict]:
        """
        Attempt to ingest a single cited case.

        Args:
            case_number: Case number to ingest
            world_id: World ID for the new case

        Returns:
            Dict with result, or None if failed
        """
        urls = self.build_case_urls(case_number)
        logger.info(f"Attempting to ingest Case {case_number}")

        for url in urls:
            if self.check_url_exists(url):
                logger.info(f"Found valid URL: {url}")
                try:
                    # Process the URL
                    result = self.processor.process_url(url, world_id=world_id)

                    if result and result.get('title'):
                        # Save to database
                        new_case_id = self._save_processed_case(result)

                        if new_case_id:
                            return {
                                'success': True,
                                'case_number': case_number,
                                'new_case_id': new_case_id,
                                'title': result.get('title'),
                                'url': url
                            }

                except Exception as e:
                    logger.warning(f"Failed to process {url}: {e}")
                    continue

        # No valid URL found
        logger.warning(f"Could not find Case {case_number} on NSPE website")
        return {
            'success': False,
            'case_number': case_number,
            'reason': 'not_found_online',
            'urls_tried': urls
        }

    def _save_processed_case(self, result: Dict, url: str, world_id: int = None) -> Optional[int]:
        """
        Save a processed case to the database.

        Args:
            result: Processed case data from pipeline
            url: Original URL
            world_id: World ID for the new case

        Returns:
            New document ID or None
        """
        from app.models import Document

        try:
            # Check if document already exists by source URL
            existing = Document.query.filter_by(source=url).first()
            if existing:
                logger.info(f"Document already exists: {existing.id}")
                return existing.id

            # Build content from sections (similar to cases.py process_url_pipeline)
            sections = result.get('sections', {})
            sections_dual = result.get('sections_dual', {})

            # Build full content from sections
            content_parts = []
            if result.get('title'):
                content_parts.append(f"<h1>{result['title']}</h1>")

            for section_name in ['facts', 'question', 'references', 'discussion', 'conclusion', 'dissenting_opinion']:
                section_html = sections.get(section_name, '')
                if section_html:
                    content_parts.append(f"<h2>{section_name.replace('_', ' ').title()}</h2>")
                    content_parts.append(section_html)

            content = '\n'.join(content_parts)

            # Build metadata
            doc_metadata = {
                'case_number': result.get('case_number'),
                'year': result.get('year'),
                'full_date': result.get('full_date'),
                'date_parts': result.get('date_parts'),
                'pdf_url': result.get('pdf_url'),
                'subject_tags': result.get('subject_tags', []),
                'questions_list': result.get('questions_list', []),
                'conclusion_items': result.get('conclusion_items', []),
                'sections': sections,
                'sections_dual': sections_dual,
                'sections_text': result.get('sections_text', {}),
                'ingestion_method': 'cited_case_ingestor',
                'case_source': 'precedent',  # Mark as precedent (not primary)
                'ingested_at': datetime.utcnow().isoformat()
            }

            # Create new document
            doc = Document(
                title=result.get('title', 'Untitled Case'),
                source=url,
                content=content,
                doc_metadata=doc_metadata,
                document_type='case',
                processing_status='completed',
                world_id=world_id
            )

            db.session.add(doc)
            db.session.flush()  # Get the ID

            # Create precedent features record
            features = CasePrecedentFeatures(case_id=doc.id)
            db.session.add(features)

            db.session.commit()
            logger.info(f"Created new document: {doc.id} - {doc.title} (Case {result.get('case_number')})")

            return doc.id

        except Exception as e:
            logger.error(f"Failed to save case: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return None

    def update_resolved_citations(self):
        """
        Update cited_case_ids for all cases based on current database state.

        This re-resolves all citations to pick up newly ingested cases.
        """
        # Get all features with citations
        features_list = CasePrecedentFeatures.query.filter(
            CasePrecedentFeatures.cited_case_numbers.isnot(None)
        ).all()

        updated_count = 0
        for features in features_list:
            if not features.cited_case_numbers:
                continue

            resolved_ids = []
            for case_ref in features.cited_case_numbers:
                # Extract case number
                match = re.search(r'(\d{2,4}-\d+)', case_ref)
                if not match:
                    continue

                case_num = match.group(1)

                # Try to find in database
                query = text("""
                    SELECT id FROM documents
                    WHERE title ~* :pattern
                       OR doc_metadata->>'case_number' = :case_num
                    LIMIT 1
                """)
                result = db.session.execute(query, {
                    'pattern': f'Case\\s+{case_num}',
                    'case_num': case_num
                }).fetchone()

                if result:
                    resolved_ids.append(result[0])

            # Update if changed
            if resolved_ids != features.cited_case_ids:
                features.cited_case_ids = resolved_ids if resolved_ids else None
                updated_count += 1

        if updated_count > 0:
            db.session.commit()
            logger.info(f"Updated resolved citations for {updated_count} cases")

        return updated_count

    def ingest_missing_citations(
        self,
        max_cases: int = 10,
        world_id: int = None
    ) -> Dict:
        """
        Main entry point: ingest missing cited cases.

        Args:
            max_cases: Maximum number of cases to ingest
            world_id: World ID for new cases

        Returns:
            Summary dict with results
        """
        # Find missing citations
        missing = self.find_missing_citations()
        logger.info(f"Found {len(missing)} missing cited cases")

        if not missing:
            return {
                'total_missing': 0,
                'ingested': [],
                'failed': [],
                'skipped': []
            }

        # Limit to max_cases
        to_process = missing[:max_cases]
        skipped = missing[max_cases:]

        ingested = []
        failed = []

        for citation in to_process:
            result = self.ingest_case(citation['case_number'], world_id)

            if result and result.get('success'):
                ingested.append(result)
            else:
                failed.append(result or {'case_number': citation['case_number'], 'reason': 'unknown'})

        # Update resolved citations
        self.update_resolved_citations()

        return {
            'total_missing': len(missing),
            'ingested': ingested,
            'failed': failed,
            'skipped': [{'case_number': s['case_number'], 'citation_count': s['citation_count']} for s in skipped]
        }

    def extract_case_urls_from_content(self) -> List[Dict]:
        """
        Extract BER case URLs from all document content.

        Scans case content for hyperlinks to other NSPE BER cases.

        Returns:
            List of dicts: [{'url': '...', 'citing_cases': [1, 5], 'exists': False}, ...]
        """
        from app.models import Document

        # Get all documents with content
        docs = Document.query.filter(
            Document.content.isnot(None),
            Document.content != ''
        ).all()

        url_citations = {}  # url -> set of citing case IDs

        for doc in docs:
            content = doc.content or ''

            # Extract all BER case URLs
            for pattern in self.BER_URL_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for url in matches:
                    # Normalize URL
                    url = url.lower().rstrip('/')

                    if url not in url_citations:
                        url_citations[url] = set()
                    url_citations[url].add(doc.id)

        # Check which URLs already exist in database
        results = []
        for url, citing_cases in url_citations.items():
            exists = Document.query.filter_by(source=url).first() is not None

            results.append({
                'url': url,
                'citing_cases': list(citing_cases),
                'citation_count': len(citing_cases),
                'exists': exists
            })

        # Sort by citation count (most cited first)
        results.sort(key=lambda x: x['citation_count'], reverse=True)

        return results

    def find_missing_case_urls(self) -> List[Dict]:
        """
        Find BER case URLs that are cited but not in the database.

        Returns:
            List of missing URLs with citation info
        """
        all_urls = self.extract_case_urls_from_content()
        return [u for u in all_urls if not u['exists']]

    def ingest_from_url(self, url: str, world_id: int = None) -> Optional[Dict]:
        """
        Ingest a single case from a URL.

        Args:
            url: NSPE BER case URL
            world_id: World ID for the new case

        Returns:
            Dict with result, or None if failed
        """
        logger.info(f"Ingesting case from URL: {url}")

        try:
            # Run the proper pipeline
            result = self._run_ingestion_pipeline(url)

            if result and result.get('title'):
                # Save to database
                new_case_id = self._save_processed_case(result, url, world_id)

                if new_case_id:
                    return {
                        'success': True,
                        'url': url,
                        'new_case_id': new_case_id,
                        'title': result.get('title'),
                        'case_number': result.get('case_number')
                    }

        except Exception as e:
            logger.warning(f"Failed to ingest {url}: {e}")
            import traceback
            traceback.print_exc()

        return {
            'success': False,
            'url': url,
            'reason': 'processing_failed'
        }

    def ingest_missing_urls(
        self,
        max_cases: int = 10,
        world_id: int = None
    ) -> Dict:
        """
        Ingest missing cases by extracting URLs from existing case content.

        This is more reliable than constructing URLs from case numbers.

        Args:
            max_cases: Maximum number of cases to ingest
            world_id: World ID for new cases

        Returns:
            Summary dict with results
        """
        # Find missing URLs
        missing = self.find_missing_case_urls()
        logger.info(f"Found {len(missing)} missing case URLs")

        if not missing:
            return {
                'total_missing': 0,
                'ingested': [],
                'failed': [],
                'skipped': []
            }

        # Limit to max_cases
        to_process = missing[:max_cases]
        skipped = missing[max_cases:]

        ingested = []
        failed = []

        for url_info in to_process:
            result = self.ingest_from_url(url_info['url'], world_id)

            if result and result.get('success'):
                ingested.append(result)
            else:
                failed.append(result or {'url': url_info['url'], 'reason': 'unknown'})

        # Update resolved citations
        self.update_resolved_citations()

        return {
            'total_missing': len(missing),
            'ingested': ingested,
            'failed': failed,
            'skipped': [{'url': s['url'], 'citation_count': s['citation_count']} for s in skipped]
        }

    def extract_urls_from_case(self, case_id: int) -> List[Dict]:
        """
        Extract BER case URLs from a single case's content.

        Args:
            case_id: Document ID to scan

        Returns:
            List of dicts: [{'url': '...', 'exists': bool, 'existing_id': int or None}, ...]
        """
        from app.models import Document

        doc = Document.query.get(case_id)
        if not doc or not doc.content:
            return []

        content = doc.content
        found_urls = []

        # Extract all BER case URLs
        for pattern in self.BER_URL_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for url in matches:
                # Normalize URL
                url = url.lower().rstrip('/')

                # Skip if already found
                if any(u['url'] == url for u in found_urls):
                    continue

                # Check if exists in database
                existing = Document.query.filter_by(source=url).first()

                found_urls.append({
                    'url': url,
                    'exists': existing is not None,
                    'existing_id': existing.id if existing else None
                })

        return found_urls

    def ingest_cited_cases_for_primary(
        self,
        case_id: int,
        world_id: int = None,
        max_cases: int = 20
    ) -> Dict:
        """
        Ingest cited cases for a single primary case (one level depth).

        This is called after a primary case is ingested via /cases/new.
        Only ingests cases that don't already exist.
        Does NOT recursively ingest precedents of precedents.

        Args:
            case_id: The primary case ID
            world_id: World ID for new cases
            max_cases: Maximum cases to ingest

        Returns:
            Dict with results
        """
        from app.models import Document

        # Verify this is a primary case (not a precedent)
        doc = Document.query.get(case_id)
        if not doc:
            return {'error': f'Case {case_id} not found'}

        # Check if this case was already ingested as a precedent
        case_source = (doc.doc_metadata or {}).get('case_source', 'primary')
        if case_source == 'precedent':
            logger.info(f"Case {case_id} is a precedent case - skipping recursive ingestion")
            return {
                'primary_case_id': case_id,
                'skipped_reason': 'precedent_case',
                'cited_urls': [],
                'ingested': [],
                'failed': [],
                'pending': []
            }

        # Extract URLs from this case
        cited_urls = self.extract_urls_from_case(case_id)
        logger.info(f"Found {len(cited_urls)} cited URLs in case {case_id}")

        # Separate into existing and missing
        missing_urls = [u for u in cited_urls if not u['exists']]
        existing_urls = [u for u in cited_urls if u['exists']]

        logger.info(f"  - {len(existing_urls)} already in database")
        logger.info(f"  - {len(missing_urls)} missing (will ingest up to {max_cases})")

        # Limit ingestion
        to_ingest = missing_urls[:max_cases]
        pending = missing_urls[max_cases:]

        ingested = []
        failed = []

        for url_info in to_ingest:
            result = self.ingest_from_url(url_info['url'], world_id)

            if result and result.get('success'):
                ingested.append(result)
            else:
                failed.append(result or {'url': url_info['url'], 'reason': 'unknown'})

        # Update resolved citations for the primary case
        self.update_resolved_citations()

        # Store pending URLs in the primary case's metadata
        if pending:
            self._store_pending_precedents(case_id, [p['url'] for p in pending])

        return {
            'primary_case_id': case_id,
            'cited_urls_found': len(cited_urls),
            'already_existed': len(existing_urls),
            'ingested': ingested,
            'failed': failed,
            'pending': [p['url'] for p in pending]
        }

    def _store_pending_precedents(self, case_id: int, urls: List[str]):
        """Store pending precedent URLs in the case's metadata."""
        from app.models import Document

        doc = Document.query.get(case_id)
        if not doc:
            return

        metadata = dict(doc.doc_metadata) if doc.doc_metadata else {}
        metadata['pending_precedent_urls'] = urls
        doc.doc_metadata = metadata
        db.session.commit()
        logger.info(f"Stored {len(urls)} pending precedent URLs for case {case_id}")

    def get_pending_precedents(self, case_id: int = None) -> List[Dict]:
        """
        Get pending precedent URLs (cited but not ingested).

        Args:
            case_id: Optional specific case ID. If None, returns all pending.

        Returns:
            List of dicts with pending URL info
        """
        from app.models import Document

        if case_id:
            doc = Document.query.get(case_id)
            if not doc or not doc.doc_metadata:
                return []
            pending = doc.doc_metadata.get('pending_precedent_urls', [])
            return [{'url': url, 'from_case_id': case_id} for url in pending]

        # Get all pending from all cases
        query = text("""
            SELECT id, doc_metadata->'pending_precedent_urls' as pending
            FROM documents
            WHERE doc_metadata ? 'pending_precedent_urls'
              AND jsonb_array_length(doc_metadata->'pending_precedent_urls') > 0
        """)
        results = db.session.execute(query).fetchall()

        all_pending = []
        for row in results:
            case_id = row[0]
            urls = row[1] or []
            for url in urls:
                all_pending.append({'url': url, 'from_case_id': case_id})

        return all_pending

    def get_all_pending_url_summary(self) -> Dict:
        """
        Get summary of all pending precedent URLs across the system.

        Returns:
            Dict with summary statistics and URL list
        """
        pending = self.get_pending_precedents()

        # Deduplicate URLs and count occurrences
        url_counts = {}
        for p in pending:
            url = p['url']
            if url not in url_counts:
                url_counts[url] = {'url': url, 'from_cases': []}
            url_counts[url]['from_cases'].append(p['from_case_id'])

        unique_urls = list(url_counts.values())
        unique_urls.sort(key=lambda x: len(x['from_cases']), reverse=True)

        return {
            'total_pending': len(unique_urls),
            'urls': unique_urls
        }


def get_ingestion_summary() -> Dict:
    """
    Get a summary of cited case ingestion status.

    Returns:
        Dict with citation statistics
    """
    try:
        # Count citations and resolutions
        query = text("""
            SELECT
                COUNT(*) as total_features,
                COUNT(NULLIF(array_length(cited_case_numbers, 1), 0)) as with_citations,
                COALESCE(SUM(array_length(cited_case_numbers, 1)), 0) as total_citations,
                COALESCE(SUM(COALESCE(array_length(cited_case_ids, 1), 0)), 0) as resolved_citations
            FROM case_precedent_features
        """)
        result = db.session.execute(query).fetchone()

        return {
            'total_cases': result[0],
            'cases_with_citations': result[1],
            'total_citations': result[2],
            'resolved_citations': result[3],
            'unresolved_citations': result[2] - result[3]
        }

    except Exception as e:
        logger.error(f"Error getting ingestion summary: {e}")
        return {}
