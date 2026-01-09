"""
MCP Entity Enrichment Service

Enriches LLM prompts with entity definitions by calling OntServe MCP server,
with fallback to ProEthica's local TemporaryRDFStorage for unsynced entities.

This provides Claude with contextual understanding of ProEthica ontology entities
without requiring in-prompt tool use.

Lookup Strategy (Option A - Hybrid):
1. First try OntServe MCP (for base ontology + synced case entities)
2. Fall back to local TemporaryRDFStorage for case URIs not yet synced

Usage:
    enricher = MCPEntityEnrichmentService()
    enriched_text = enricher.enrich_text_with_definitions(prompt_text)
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Optional, Set, Tuple
from functools import lru_cache
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _get_local_entity(uri: str) -> Optional[Dict]:
    """
    Look up entity in ProEthica's local TemporaryRDFStorage.

    This is used as fallback for case entities not yet synced to OntServe.
    Must be called within Flask app context.
    """
    try:
        from app.models import TemporaryRDFStorage

        # Query by entity_uri
        entity = TemporaryRDFStorage.query.filter_by(entity_uri=uri).first()

        if entity:
            return {
                "uri": uri,
                "label": entity.entity_label or uri.split("#")[-1],
                "definition": entity.entity_definition or "",
                "entity_type": entity.extraction_type or "Entity",
                "source_ontology": f"proethica-case-{entity.case_id}",
                "found": True,
                "source": "local"  # Mark as from local DB
            }

        return None

    except Exception as e:
        logger.debug(f"Local entity lookup failed for {uri}: {e}")
        return None


def _extract_case_id_from_uri(uri: str) -> Optional[int]:
    """Extract case ID from a case-scoped URI."""
    match = re.search(r'/case/(\d+)#', uri)
    if match:
        return int(match.group(1))
    return None


class MCPEntityEnrichmentService:
    """
    Service for enriching text with entity definitions from OntServe MCP.

    Extracts ProEthica URIs from text, looks up their definitions via MCP,
    and can either append a glossary or inline the definitions.
    """

    # Regex pattern for ProEthica URIs
    URI_PATTERN = re.compile(
        r'http://proethica\.org/ontology/(?:case/\d+|intermediate)#[\w_-]+',
        re.IGNORECASE
    )

    def __init__(self, mcp_url: str = None, timeout: int = 30):
        """
        Initialize the enrichment service.

        Args:
            mcp_url: OntServe MCP server URL (defaults to env var or production)
            timeout: Request timeout in seconds
        """
        self.mcp_url = mcp_url or os.environ.get(
            "ONTSERVE_MCP_URL",
            "https://mcp.proethica.org"
        )
        self.timeout = timeout
        self._cache: Dict[str, Dict] = {}

        logger.info(f"MCPEntityEnrichmentService initialized with URL: {self.mcp_url}")

    def extract_uris(self, text: str) -> List[str]:
        """
        Extract all ProEthica URIs from text.

        Args:
            text: Text to search for URIs

        Returns:
            List of unique URIs found
        """
        uris = self.URI_PATTERN.findall(text)
        return list(dict.fromkeys(uris))  # Remove duplicates, preserve order

    def lookup_entities(self, uris: List[str]) -> Dict[str, Dict]:
        """
        Look up entity definitions using hybrid strategy:
        1. First try OntServe MCP (for base ontology + synced case entities)
        2. Fall back to local TemporaryRDFStorage for case URIs not found in MCP

        Args:
            uris: List of URIs to look up

        Returns:
            Dict mapping URI to entity data (label, definition, entity_type, etc.)
        """
        if not uris:
            return {}

        # Check cache first
        uncached = [uri for uri in uris if uri not in self._cache]

        if uncached:
            # Step 1: Batch lookup from MCP (max 20 per request)
            not_found_in_mcp = []

            for i in range(0, len(uncached), 20):
                batch = uncached[i:i+20]
                try:
                    result = self._call_mcp_tool("get_entities_by_uris", {"uris": batch})

                    for entity in result.get("entities", []):
                        uri = entity.get("uri")
                        if uri:
                            entity["source"] = "mcp"  # Mark source
                            self._cache[uri] = entity

                    # Track URIs not found in MCP for local fallback
                    not_found_in_mcp.extend(result.get("not_found", []))

                except Exception as e:
                    logger.warning(f"MCP lookup failed for batch: {e}")
                    # All URIs in failed batch need local fallback
                    not_found_in_mcp.extend(batch)

            # Step 2: Local fallback for case URIs not found in MCP
            if not_found_in_mcp:
                local_found = 0
                for uri in not_found_in_mcp:
                    if uri in self._cache:
                        continue  # Already cached

                    # Only try local lookup for case-scoped URIs
                    if '/case/' in uri:
                        local_entity = _get_local_entity(uri)
                        if local_entity:
                            self._cache[uri] = local_entity
                            local_found += 1
                            continue

                    # Mark as not found
                    self._cache[uri] = {"uri": uri, "found": False}

                if local_found > 0:
                    logger.info(f"Found {local_found} entities via local fallback")

        return {uri: self._cache.get(uri, {"uri": uri, "found": False}) for uri in uris}

    def _call_mcp_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool on the OntServe server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = requests.post(
            self.mcp_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()

        # Extract tool result from MCP response format
        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"]
            if content and len(content) > 0:
                text = content[0].get("text", "{}")
                return json.loads(text)

        return {"error": "Unexpected MCP response format"}

    def build_glossary(self, entities: Dict[str, Dict]) -> str:
        """
        Build a glossary section from entity definitions.

        Args:
            entities: Dict mapping URI to entity data

        Returns:
            Formatted glossary text
        """
        if not entities:
            return ""

        # Group by entity type
        by_type: Dict[str, List[Tuple[str, Dict]]] = {}
        for uri, entity in entities.items():
            if entity.get("found", True) and entity.get("definition"):
                entity_type = entity.get("entity_type", "Entity")
                if entity_type not in by_type:
                    by_type[entity_type] = []
                by_type[entity_type].append((uri, entity))

        if not by_type:
            return ""

        lines = ["## Entity Definitions\n"]
        lines.append("The following entities are referenced in this analysis:\n")

        for entity_type in sorted(by_type.keys()):
            items = by_type[entity_type]
            lines.append(f"\n### {entity_type}s\n")
            for uri, entity in items:
                label = entity.get("label", uri.split("#")[-1])
                definition = entity.get("definition", "")
                if definition:
                    lines.append(f"- **{label}**: {definition}")
                else:
                    lines.append(f"- **{label}**: (no definition available)")

        return "\n".join(lines)

    def enrich_text_with_definitions(
        self,
        text: str,
        mode: str = "glossary",
        max_entities: int = 30
    ) -> str:
        """
        Enrich text with entity definitions.

        Args:
            text: Original text containing URIs
            mode: "glossary" (append glossary) or "inline" (add definitions inline)
            max_entities: Maximum number of entities to look up

        Returns:
            Enriched text with definitions
        """
        # Extract URIs
        uris = self.extract_uris(text)

        if not uris:
            logger.debug("No ProEthica URIs found in text")
            return text

        # Limit number of lookups
        if len(uris) > max_entities:
            logger.warning(f"Found {len(uris)} URIs, limiting to {max_entities}")
            uris = uris[:max_entities]

        # Look up entities
        entities = self.lookup_entities(uris)

        # Count successful lookups
        found_count = sum(1 for e in entities.values() if e.get("found", True) and e.get("definition"))
        logger.info(f"Enriched text with {found_count}/{len(uris)} entity definitions")

        if mode == "glossary":
            glossary = self.build_glossary(entities)
            if glossary:
                return f"{glossary}\n\n---\n\n{text}"
            return text

        elif mode == "inline":
            # Replace URIs with URI + definition
            enriched = text
            for uri, entity in entities.items():
                if entity.get("found", True) and entity.get("definition"):
                    label = entity.get("label", "")
                    definition = entity.get("definition", "")
                    # Replace [URI] with [URI: "definition"]
                    enriched = enriched.replace(
                        f"[{uri}]",
                        f"[{uri}] ({definition[:100]}{'...' if len(definition) > 100 else ''})"
                    )
            return enriched

        return text

    def clear_cache(self):
        """Clear the entity cache."""
        self._cache.clear()
        logger.debug("Entity cache cleared")


# Singleton instance for easy access
_enrichment_service: Optional[MCPEntityEnrichmentService] = None


def get_enrichment_service() -> MCPEntityEnrichmentService:
    """Get or create the singleton enrichment service."""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = MCPEntityEnrichmentService()
    return _enrichment_service


def enrich_prompt_with_entities(prompt: str, mode: str = "glossary") -> str:
    """
    Convenience function to enrich a prompt with entity definitions.

    Args:
        prompt: The LLM prompt text
        mode: "glossary" or "inline"

    Returns:
        Enriched prompt
    """
    service = get_enrichment_service()
    return service.enrich_text_with_definitions(prompt, mode=mode)


@dataclass
class EnrichmentResult:
    """Result of entity enrichment with metadata for provenance tracking."""
    enriched_text: str
    entities_resolved: Dict[str, Dict]  # URI -> entity data
    mcp_resolved_count: int
    local_resolved_count: int
    not_found_count: int
    resolution_log: List[Dict]  # Detailed log of each resolution


def enrich_prompt_with_metadata(prompt: str, mode: str = "glossary") -> EnrichmentResult:
    """
    Enrich a prompt and return metadata about entity resolution for provenance.

    Args:
        prompt: The LLM prompt text
        mode: "glossary" or "inline"

    Returns:
        EnrichmentResult with enriched text and resolution metadata
    """
    service = get_enrichment_service()

    # Extract URIs
    uris = service.extract_uris(prompt)

    if not uris:
        return EnrichmentResult(
            enriched_text=prompt,
            entities_resolved={},
            mcp_resolved_count=0,
            local_resolved_count=0,
            not_found_count=0,
            resolution_log=[]
        )

    # Look up entities
    entities = service.lookup_entities(uris)

    # Build resolution log with source tracking
    resolution_log = []
    mcp_count = 0
    local_count = 0
    not_found_count = 0

    for uri, entity in entities.items():
        source = entity.get("source", "unknown")
        found = entity.get("found", True)

        log_entry = {
            "uri": uri,
            "label": entity.get("label", uri.split("#")[-1]),
            "source": source,
            "found": found,
            "has_definition": bool(entity.get("definition")),
            "entity_type": entity.get("entity_type", "Unknown")
        }
        resolution_log.append(log_entry)

        if not found:
            not_found_count += 1
        elif source == "mcp":
            mcp_count += 1
        elif source == "local":
            local_count += 1

    # Build enriched text
    enriched_text = service.enrich_text_with_definitions(prompt, mode=mode)

    return EnrichmentResult(
        enriched_text=enriched_text,
        entities_resolved=entities,
        mcp_resolved_count=mcp_count,
        local_resolved_count=local_count,
        not_found_count=not_found_count,
        resolution_log=resolution_log
    )
