"""Generation context management for code generation agents.

This module provides utilities to:
1. Track generated files to prevent duplicates
2. Build folder structure context for LLM prompts
3. Track available components and their exports
4. Provide import suggestions based on existing files
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FileEntry:
    """A tracked file entry with metadata."""

    path: str
    content: str
    language: str
    category: str  # project, migration, api, frontend, utility, test, etc.
    exports: list[str] = field(default_factory=list)  # Exported functions/components
    imports: list[str] = field(default_factory=list)  # Import statements
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()[:12]


@dataclass
class ComponentInfo:
    """Information about an available component/module."""

    name: str
    path: str
    exports: list[str]
    description: str = ""


class GenerationContext:
    """
    Tracks generated files and provides context for code generation.

    Usage:
        ctx = GenerationContext()

        # Add files as they are generated
        ctx.add_file("lib/db.ts", content, "typescript", "utility",
                     exports=["db", "query"])

        # Get context for next generation step
        folder_structure = ctx.get_folder_structure()
        available_components = ctx.get_available_components("utility")
        import_suggestions = ctx.get_import_suggestions("app/api/users/route.ts")

        # Check for duplicates before adding
        if ctx.has_file("lib/db.ts"):
            print("File already exists!")
    """

    def __init__(self):
        self._files: dict[str, FileEntry] = {}
        self._components: dict[str, ComponentInfo] = {}
        self._categories: dict[str, list[str]] = {}  # category -> [paths]

    def add_file(
        self,
        path: str,
        content: str,
        language: str,
        category: str,
        exports: Optional[list[str]] = None,
        imports: Optional[list[str]] = None,
    ) -> bool:
        """
        Add a file to the registry.

        Returns:
            True if file was added, False if duplicate was skipped.
        """
        normalized_path = self._normalize_path(path)

        # Check for duplicate path
        if normalized_path in self._files:
            existing = self._files[normalized_path]
            new_hash = hashlib.md5(content.encode()).hexdigest()[:12]

            if existing.content_hash == new_hash:
                logger.debug(f"Skipping duplicate file: {path}")
                return False

            logger.warning(
                f"Overwriting file with different content: {path} "
                f"(old hash: {existing.content_hash}, new hash: {new_hash})"
            )

        entry = FileEntry(
            path=normalized_path,
            content=content,
            language=language,
            category=category,
            exports=exports or [],
            imports=imports or [],
        )

        self._files[normalized_path] = entry

        # Track by category
        if category not in self._categories:
            self._categories[category] = []
        if normalized_path not in self._categories[category]:
            self._categories[category].append(normalized_path)

        # Extract and track components
        if exports:
            component_name = Path(normalized_path).stem
            self._components[component_name] = ComponentInfo(
                name=component_name,
                path=normalized_path,
                exports=exports,
            )

        return True

    def has_file(self, path: str) -> bool:
        """Check if a file already exists in the registry."""
        return self._normalize_path(path) in self._files

    def get_file(self, path: str) -> Optional[FileEntry]:
        """Get a file entry by path."""
        return self._files.get(self._normalize_path(path))

    def get_files_by_category(self, category: str) -> list[FileEntry]:
        """Get all files in a category."""
        paths = self._categories.get(category, [])
        return [self._files[p] for p in paths if p in self._files]

    def get_all_files(self) -> list[FileEntry]:
        """Get all tracked files."""
        return list(self._files.values())

    def get_folder_structure(self, include_content_preview: bool = False) -> str:
        """
        Generate a folder structure string for LLM context.

        Returns a tree-like structure showing all generated files.
        """
        if not self._files:
            return "(no files generated yet)"

        # Build tree structure
        tree: dict = {}
        for path in sorted(self._files.keys()):
            parts = path.split("/")
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Mark file with its category
            entry = self._files[path]
            current[parts[-1]] = f"[{entry.category}]"

        # Convert to string
        lines = []
        self._format_tree(tree, "", lines)

        result = "\n".join(lines)

        if include_content_preview:
            result += "\n\n## File Summaries:\n"
            for path, entry in sorted(self._files.items()):
                preview = entry.content[:100].replace("\n", " ")
                result += f"\n### {path}\n{preview}...\n"

        return result

    def _format_tree(self, node: dict, prefix: str, lines: list[str]):
        """Recursively format tree structure."""
        items = sorted(node.items())
        for i, (name, value) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "

            if isinstance(value, dict):
                lines.append(f"{prefix}{connector}{name}/")
                extension = "    " if is_last else "│   "
                self._format_tree(value, prefix + extension, lines)
            else:
                lines.append(f"{prefix}{connector}{name} {value}")

    def get_available_components(
        self,
        category: Optional[str] = None,
        for_import_from: Optional[str] = None,
    ) -> str:
        """
        Get a formatted string of available components for LLM context.

        Args:
            category: Filter by category (utility, frontend, api, etc.)
            for_import_from: File path that will be importing (for relative path calculation)
        """
        if not self._components:
            return "(no components available yet)"

        lines = ["Available components/modules you can import:"]

        for name, comp in sorted(self._components.items()):
            # Filter by category if specified
            if category:
                file_entry = self._files.get(comp.path)
                if file_entry and file_entry.category != category:
                    continue

            exports_str = ", ".join(comp.exports[:5])
            if len(comp.exports) > 5:
                exports_str += f", ... (+{len(comp.exports) - 5} more)"

            import_path = comp.path
            if for_import_from:
                import_path = self._get_relative_import(for_import_from, comp.path)

            lines.append(f"  - {import_path}: {{ {exports_str} }}")

        return "\n".join(lines)

    def get_import_suggestions(self, target_file: str) -> str:
        """
        Get import suggestions for a target file based on available components.

        Returns formatted import statements that could be useful.
        """
        suggestions = []
        target_path = self._normalize_path(target_file)

        # Suggest utilities
        for path, entry in self._files.items():
            if entry.category == "utility" and entry.exports:
                import_path = self._get_relative_import(target_path, path)
                exports = ", ".join(entry.exports[:3])
                suggestions.append(f'import {{ {exports} }} from "{import_path}";')

        if not suggestions:
            return ""

        return "Suggested imports (use as needed):\n" + "\n".join(suggestions[:10])

    def get_context_for_generation(
        self,
        target_category: str,
        target_file: Optional[str] = None,
    ) -> str:
        """
        Get comprehensive context for generating files in a category.

        This combines folder structure, available components, and import suggestions.
        """
        sections = []

        # Current folder structure
        sections.append("## Current Project Structure\n")
        sections.append(self.get_folder_structure())

        # Available components
        if self._components:
            sections.append("\n\n## Available Components\n")
            sections.append(self.get_available_components(for_import_from=target_file))

        # Category-specific context
        if target_category == "frontend":
            utility_files = self.get_files_by_category("utility")
            if utility_files:
                sections.append("\n\n## Available Utilities\n")
                for f in utility_files:
                    sections.append(f"- {f.path}: {', '.join(f.exports)}")

        elif target_category == "api":
            # Include database schema context
            migration_files = self.get_files_by_category("migration")
            if migration_files:
                sections.append("\n\n## Database Schema (from migrations)\n")
                for f in migration_files:
                    # Extract table names from migration
                    tables = self._extract_table_names(f.content)
                    if tables:
                        sections.append(f"- Tables: {', '.join(tables)}")

        elif target_category == "test":
            # Include all source files for test coverage
            source_files = (
                self.get_files_by_category("api")
                + self.get_files_by_category("frontend")
                + self.get_files_by_category("utility")
            )
            if source_files:
                sections.append("\n\n## Files to Test\n")
                for f in source_files:
                    sections.append(f"- {f.path}")

        return "\n".join(sections)

    def get_deduplication_instructions(self) -> str:
        """
        Get instructions for the LLM to avoid generating duplicates.
        """
        if not self._files:
            return ""

        existing_paths = sorted(self._files.keys())
        return f"""
## IMPORTANT: Avoid Duplicates

The following files have ALREADY been generated. Do NOT generate these again:
{chr(10).join('- ' + p for p in existing_paths)}

If you need functionality from these files, import from them instead of recreating.
"""

    def _normalize_path(self, path: str) -> str:
        """Normalize file path for consistent comparison."""
        # Remove leading ./
        path = path.lstrip("./")
        # Normalize separators
        path = path.replace("\\", "/")
        return path

    def _get_relative_import(self, from_path: str, to_path: str) -> str:
        """Calculate relative import path between two files."""
        from_parts = from_path.split("/")[:-1]  # Directory of source file
        to_parts = to_path.split("/")

        # Remove file extension from target
        to_parts[-1] = Path(to_parts[-1]).stem

        # Find common prefix
        common_length = 0
        for i, (a, b) in enumerate(zip(from_parts, to_parts)):
            if a != b:
                break
            common_length = i + 1

        # Build relative path
        up_count = len(from_parts) - common_length
        if up_count == 0:
            return "./" + "/".join(to_parts[common_length:])
        else:
            return "../" * up_count + "/".join(to_parts[common_length:])

    def _extract_table_names(self, sql_content: str) -> list[str]:
        """Extract table names from SQL migration content."""
        import re

        tables = []
        # Match CREATE TABLE statements
        pattern = r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?[\"']?(\w+)[\"']?"
        matches = re.findall(pattern, sql_content, re.IGNORECASE)
        tables.extend(matches)
        return tables

    @staticmethod
    def extract_exports_from_typescript(content: str) -> list[str]:
        """Extract exported names from TypeScript/JavaScript content."""
        import re

        exports = []

        # Match: export function name
        exports.extend(re.findall(r"export\s+function\s+(\w+)", content))

        # Match: export const name
        exports.extend(re.findall(r"export\s+const\s+(\w+)", content))

        # Match: export class name
        exports.extend(re.findall(r"export\s+class\s+(\w+)", content))

        # Match: export interface name
        exports.extend(re.findall(r"export\s+interface\s+(\w+)", content))

        # Match: export type name
        exports.extend(re.findall(r"export\s+type\s+(\w+)", content))

        # Match: export default function name
        exports.extend(re.findall(r"export\s+default\s+function\s+(\w+)", content))

        # Match: export { name1, name2 }
        bracket_exports = re.findall(r"export\s*\{([^}]+)\}", content)
        for group in bracket_exports:
            names = [n.strip().split(" as ")[0].strip() for n in group.split(",")]
            exports.extend(names)

        return list(set(exports))

    @staticmethod
    def extract_imports_from_typescript(content: str) -> list[str]:
        """Extract import statements from TypeScript/JavaScript content."""
        import re

        imports = []
        # Match import statements
        pattern = r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"
        imports.extend(re.findall(pattern, content))
        return imports
