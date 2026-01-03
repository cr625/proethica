"""
Test to verify the nine-concept to nine-component rename was completed correctly.

This test suite verifies that:
1. Old "nine-concept" terminology has been completely removed
2. New "nine-component" terminology is correctly used
3. Documentation files reference the correct terminology
4. Templates use correct IDs for framework references
"""

import os
import re
from pathlib import Path


class TestNineComponentTerminology:
    """Verify nine-component terminology consistency across the codebase."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures."""
        cls.project_root = Path(__file__).parent.parent.parent
        cls.excluded_dirs = {
            'venv-proethica',
            '__pycache__',
            '.git',
            'site',
            'docs-internal/archive'
        }

    def _is_excluded_path(self, path):
        """Check if path should be excluded from search."""
        path_str = str(path)
        for excluded in self.excluded_dirs:
            if f"/{excluded}/" in path_str or path_str.endswith(excluded):
                return True
        # Exclude this test file itself since it references old terminology in comments/docstrings
        if "test_terminology_consistency.py" in path_str:
            return True
        return False

    def _search_files(self, pattern, file_extensions=None, exclude_dirs=True):
        """
        Search for pattern in files.

        Args:
            pattern: regex pattern to search for
            file_extensions: list of file extensions to check (e.g., ['.py', '.md', '.html'])
            exclude_dirs: whether to exclude common directories

        Returns:
            dict mapping file paths to list of (line_num, line_text) tuples
        """
        results = {}
        regex = re.compile(pattern, re.IGNORECASE)

        for root, dirs, files in os.walk(self.project_root):
            # Modify dirs in-place to skip excluded directories
            if exclude_dirs:
                dirs[:] = [d for d in dirs if not self._is_excluded_path(os.path.join(root, d))]

            for file in files:
                file_path = os.path.join(root, file)

                # Filter by extension if specified
                if file_extensions and not any(file.endswith(ext) for ext in file_extensions):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                if file_path not in results:
                                    results[file_path] = []
                                results[file_path].append((line_num, line.strip()))
                except Exception:
                    # Skip files that can't be read
                    pass

        return results

    def test_no_nine_concept_terminology(self):
        """Verify old 'nine-concept' terminology has been removed from main code."""
        # This pattern looks for "nine-concept" or "9-concept" variations
        pattern = r'nine-concept|9-concept'

        results = self._search_files(
            pattern,
            file_extensions=['.py', '.md', '.html', '.jinja2'],
            exclude_dirs=True
        )

        # Filter out archived files, site files, and this test file itself
        main_results = {
            path: matches for path, matches in results.items()
            if 'docs-internal/archive' not in path
            and 'site/' not in path
            and 'test_terminology_consistency.py' not in path
        }

        # Construct error message with found instances
        error_msg_parts = []
        if main_results:
            error_msg_parts.append(
                "Found old 'nine-concept' terminology that should be 'nine-component':"
            )
            for file_path, matches in sorted(main_results.items()):
                error_msg_parts.append(f"\n  {file_path}:")
                for line_num, line in matches:
                    error_msg_parts.append(f"    Line {line_num}: {line}")

        assert not main_results, "\n".join(error_msg_parts)

    def test_nine_components_doc_exists(self):
        """Verify nine-components.md documentation file exists."""
        doc_path = self.project_root / "docs" / "concepts" / "nine-components.md"
        assert doc_path.exists(), f"Expected documentation file {doc_path} not found"

    def test_nine_concepts_doc_does_not_exist(self):
        """Verify old nine-concepts.md documentation file does not exist."""
        old_doc_path = self.project_root / "docs" / "concepts" / "nine-concepts.md"
        assert not old_doc_path.exists(), (
            f"Old documentation file {old_doc_path} should have been renamed/deleted"
        )

    def test_documentation_uses_nine_component(self):
        """Verify key documentation files use 'Nine-Component' terminology."""
        doc_files = {
            "docs/index.md": "Nine-Component",
            "docs/concepts/nine-components.md": "Nine-Component",
            "docs/getting-started/welcome.md": "Nine-Component",
            "docs/how-to/phase1-extraction.md": "nine-component",
        }

        missing_terminology = []

        for doc_file, terminology in doc_files.items():
            file_path = self.project_root / doc_file
            if not file_path.exists():
                missing_terminology.append(f"File not found: {file_path}")
                continue

            content = file_path.read_text(encoding='utf-8')
            # Do case-insensitive check for the base terminology
            if "nine-component" not in content.lower():
                missing_terminology.append(
                    f"File {doc_file} does not contain 'nine-component' terminology"
                )

        assert not missing_terminology, "\n".join(missing_terminology)

    def test_references_template_uses_nine_component_id(self):
        """Verify references.html template uses 'nine-component' as ID."""
        template_path = self.project_root / "app" / "templates" / "tools" / "references.html"
        assert template_path.exists(), f"Template {template_path} not found"

        content = template_path.read_text(encoding='utf-8')

        # Check for the framework section ID
        assert 'id="nine-component"' in content, (
            "Expected id='nine-component' not found in references.html template"
        )

        # Verify no old ID exists
        assert 'id="nine-concept"' not in content, (
            "Found old id='nine-concept' in references.html, should be 'nine-component'"
        )

    def test_references_template_uses_nine_component_terminology(self):
        """Verify references.html uses 'Nine-Component' or '9-Component' terminology."""
        template_path = self.project_root / "app" / "templates" / "tools" / "references.html"
        content = template_path.read_text(encoding='utf-8')

        # Check for correct terminology variations
        has_nine_component = (
            '9-Component' in content or
            'Nine-Component' in content or
            'nine-component' in content
        )

        assert has_nine_component, (
            "references.html should contain 'Nine-Component', '9-Component', or 'nine-component'"
        )

    def test_extraction_files_no_old_terminology(self):
        """Verify Python extraction files do not use old '9-concept' terminology."""
        extraction_dir = self.project_root / "app" / "services" / "extraction"
        extraction_files = [
            "base.py",
            "roles.py",
            "resources.py",
            "enhanced_prompts_states_capabilities.py",
            "enhanced_prompts_principles.py",
        ]

        files_with_old_terminology = []

        for filename in extraction_files:
            file_path = extraction_dir / filename
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding='utf-8')

            # Check that file doesn't have old '9-concept' terminology
            if re.search(r'\b9-concept\b', content, re.IGNORECASE):
                files_with_old_terminology.append(f"{file_path}: contains '9-concept'")

        assert not files_with_old_terminology, (
            "Extraction files should not use old '9-concept' terminology:\n" +
            "\n".join(files_with_old_terminology)
        )

    def test_no_nine_concept_in_main_code_and_templates(self):
        """Comprehensive check: no 'nine-concept' in active code/templates."""
        # Search only in main source code and templates
        code_extensions = ['.py', '.html', '.jinja2', '.js']
        pattern = r'nine-concept|9-concept'

        results = self._search_files(
            pattern,
            file_extensions=code_extensions,
            exclude_dirs=True
        )

        # Remove archived, generated files, and this test file itself
        active_results = {
            path: matches for path, matches in results.items()
            if 'docs-internal/archive' not in path
            and 'site/' not in path
            and 'test_terminology_consistency.py' not in path
        }

        assert not active_results, (
            "Found 'nine-concept' or '9-concept' in active code/templates:\n" +
            "\n".join(
                f"{path} line {line_num}: {line}"
                for path, matches in sorted(active_results.items())
                for line_num, line in matches
            )
        )

    def test_consistent_framework_references_in_docs(self):
        """Verify framework references are consistent across documentation."""
        docs_dir = self.project_root / "docs"
        md_files = list(docs_dir.rglob("*.md"))

        inconsistencies = []

        for md_file in md_files:
            if not md_file.exists():
                continue

            try:
                content = md_file.read_text(encoding='utf-8')

                # Check for old terminology
                if re.search(r'\bnine-concept\b', content, re.IGNORECASE):
                    inconsistencies.append(
                        f"{md_file.relative_to(self.project_root)}: contains 'nine-concept'"
                    )

                # For files that discuss the framework, verify they use new terminology
                if 'framework' in content.lower() and any(
                    term in content.lower() for term in ['role', 'obligation', 'principle', 'state']
                ):
                    if 'nine-component' not in content.lower():
                        # Only warn if this looks like a framework discussion file
                        if any(name in str(md_file).lower() for name in ['concept', 'framework', 'extraction']):
                            inconsistencies.append(
                                f"{md_file.relative_to(self.project_root)}: discusses framework but lacks 'nine-component'"
                            )
            except Exception:
                pass

        assert not inconsistencies, (
            "Documentation inconsistencies found:\n" +
            "\n".join(f"  - {inc}" for inc in inconsistencies)
        )

    def test_nine_components_framework_described_correctly(self):
        """Verify nine-components.md accurately describes the framework."""
        doc_path = self.project_root / "docs" / "concepts" / "nine-components.md"
        assert doc_path.exists(), "nine-components.md documentation file not found"

        content = doc_path.read_text(encoding='utf-8')

        # Verify key components are mentioned
        required_components = ['Roles', 'Principles', 'Obligations', 'States', 'Resources',
                              'Actions', 'Events', 'Capabilities', 'Constraints']

        missing_components = []
        for component in required_components:
            if component not in content:
                missing_components.append(component)

        assert not missing_components, (
            f"nine-components.md is missing documentation for: {', '.join(missing_components)}"
        )

        # Verify D = (R, P, O, S, Rs, A, E, Ca, Cs) notation is present
        assert 'D = (R, P, O, S, Rs, A, E, Ca, Cs)' in content, (
            "nine-components.md should contain the formal framework notation D = (R, P, O, S, Rs, A, E, Ca, Cs)"
        )
