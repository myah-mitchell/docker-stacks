#!/usr/bin/env python3
"""
build.py - Build script for the docker-stacks project.

Generates stack-level files by merging base templates with container-specific
files. Container membership is discovered from each stack's compose.yaml
via its 'extends' directives.

Generated files per stack:
  - komodo.env  : Merged from base-komodo.env + each container's komodo.env
  - README.md   : Merged from existing/base README + each container's 
                  stack-README.md
  - .env        : Testing file derived from the generated komodo.env

Merging strategy:
  Sections are identified by headings (komodo uses #=/#==, README uses #/##).
  Matching headings are combined; new headings are appended.
  For README: shared H1 headings (present in any container) are rebuilt
  from scratch each run, enabling self-cleanup when containers are removed.
  Stack-only H1 headings are preserved as-is.

See scripts/project-layout.md for full documentation.

Usage:
    python scripts/build.py        # from project root
    python build.py                # from scripts/ directory
"""

import argparse
import re
import secrets
import string
import sys
from pathlib import Path
from copy import deepcopy


# ============================================================================
# region Data Structures
# ============================================================================

class Section:
    """A heading-delimited section in a structured document.

    Represents a single heading with its direct content (lines between this
    heading and the next heading or child) and any child sections (headings
    at a deeper nesting level).

    Attributes:
        heading_line:  Full heading line as it appears in the file (tags stripped).
        heading_text:  Heading text without the prefix markers or tags.
        level:         Nesting depth (1 = top-level, 2 = sub-section, etc.).
        content_lines: Lines belonging directly to this section.
        children:      Child Section objects at a deeper level.
        tags:          Set of tag strings from [tag1, tag2] syntax. Empty
                       set means the section is always included.
    """

    def __init__(self, heading_line="", heading_text="", level=0,
                 content_lines=None, tags=None):
        self.heading_line = heading_line
        self.heading_text = heading_text
        self.level = level
        self.content_lines = content_lines if content_lines is not None else []
        self.children = []
        self.tags = tags if tags is not None else set()

    def __repr__(self):
        tag_str = f", tags={self.tags!r}" if self.tags else ""
        return (
            f"Section(level={self.level}, text={self.heading_text!r}, "
            f"content={len(self.content_lines)} lines, "
            f"children={len(self.children)}{tag_str})"
        )

# endregion
# ============================================================================
# region Heading Detection
# ============================================================================

def detect_komodo_heading(line):
    """Detect a komodo.env heading: #= for H1, #== for H2, etc.

    Regular comment lines (# without =) are NOT headings.

    Returns:
        (level, text) tuple on match, or None.
    """
    m = re.match(r'^#(=+)\s*(.*)', line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None


def detect_markdown_heading(line):
    """Detect a standard markdown heading: # for H1, ## for H2, etc.

    Returns:
        (level, text) tuple on match, or None.
    """
    m = re.match(r'^(#{1,6})\s+(.*)', line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None


_TAG_RE = re.compile(r'\s*\[([^\]]+)\]\s*$')


def extract_tags(text):
    """Extract [tag1, tag2] from the end of heading text.

    Tags are optional annotations in square brackets at the end of a
    heading that control conditional inclusion based on which service
    variant a stack uses.

    Args:
        text: Heading text (without prefix markers like # or #=).

    Returns:
        (clean_text, tags) where clean_text has the [tags] removed
        and tags is a set of stripped tag strings. Empty set means
        "always include" (no tags present).

    Examples:
        >>> extract_tags("Crowdsec Server [crowdsec-server]")
        ('Crowdsec Server', {'crowdsec-server'})
        >>> extract_tags("Shared [crowdsec-server, crowdsec-agent]")
        ('Shared', {'crowdsec-server', 'crowdsec-agent'})
        >>> extract_tags("No Tags Here")
        ('No Tags Here', set())
    """
    m = _TAG_RE.search(text)
    if m:
        tags = {t.strip() for t in m.group(1).split(',') if t.strip()}
        clean_text = text[:m.start()].rstrip()
        return clean_text, tags
    return text, set()

# endregion
# ============================================================================
# region Parsing: Content -> Section Tree
# ============================================================================

def parse_sections(content, heading_detector):
    """Parse document content into a preamble and a tree of Sections.

    Lines before the first heading become the preamble. Each heading starts
    a new Section. Deeper-level headings become children of the preceding
    shallower heading, forming a tree.

    Args:
        content:          Full file content as a string.
        heading_detector: Function(line) -> (level, text) or None.

    Returns:
        (preamble_lines, top_level_sections)
    """
    lines = content.splitlines()
    preamble = []
    flat = []       # All sections in document order (flat, before tree-building)
    current = None  # Section currently accumulating content lines

    for line in lines:
        heading = heading_detector(line)
        if heading:
            level, text = heading
            clean_text, tags = extract_tags(text)
            # Strip tags from the heading line so output files are clean
            clean_line = _TAG_RE.sub('', line).rstrip()
            current = Section(
                heading_line=clean_line, heading_text=clean_text,
                level=level, tags=tags,
            )
            flat.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current.content_lines.append(line)

    # ---- Build tree from flat list ----
    # Use a stack to track the current ancestry chain. When we encounter a
    # section at level N, pop everything >= N off the stack. Whatever remains
    # on top is the parent (or the stack is empty -> top-level).
    top_level = []
    stack = []

    for section in flat:
        while stack and stack[-1].level >= section.level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
        else:
            top_level.append(section)

        stack.append(section)

    return preamble, top_level


def filter_sections_by_tags(sections, active_tags):
    """Remove sections whose tags don't match any active service tag.

    Filtering rules:
      - Sections with no tags (empty set) are always kept.
      - Sections with tags are kept only if at least one tag is in
        active_tags.
      - When a section is filtered out, ALL its children are removed
        too, regardless of their own tags.
      - Children of a kept section are recursively filtered.

    Args:
        sections:    List of Section objects.
        active_tags: Set of active service tag strings.

    Returns:
        Filtered list of Section objects (new list; originals not modified).
    """
    result = []
    for section in sections:
        if section.tags and not (section.tags & active_tags):
            # Has tags but none match -> exclude with all children
            continue
        filtered = deepcopy(section)
        filtered.children = filter_sections_by_tags(
            section.children, active_tags
        )
        result.append(filtered)
    return result

# endregion
# ============================================================================
# region Merging: Combine Section Trees
# ============================================================================

_KEY_VALUE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.*)')


def merge_sections(base_sections, new_sections):
    """Merge new_sections into base_sections by matching heading text.

    For each section in new_sections:
      - If a section with the same heading_text exists in base: append
        only unique content lines and recursively merge children.
      - If no match: append as a new section.

    Deduplication rules for content lines within a section:
      - Blank lines are always kept to preserve formatting.
      - Identical non-blank lines are not repeated.
      - KEY: VALUE / KEY=VALUE lines are deduplicated by key:
          * Same key, same value (or both blank) -> skip duplicate.
          * Same key, existing blank, new has value -> replace with new.
          * Same key, existing has value, new blank -> skip new.
          * Same key, different non-empty values -> keep both (no data loss).

    Returns a new list; inputs are not modified.
    """
    result = deepcopy(base_sections)

    for new_sec in new_sections:
        # Find a section in result with the same heading text
        match = next(
            (s for s in result if s.heading_text == new_sec.heading_text),
            None,
        )

        if match:
            existing_lines = set(l for l in match.content_lines if l.strip())
            # Track keys already present: key -> (index, value)
            existing_keys = {}
            for i, line in enumerate(match.content_lines):
                km = _KEY_VALUE_RE.match(line.strip())
                if km:
                    existing_keys[km.group(1)] = (i, km.group(2).strip())

            for line in new_sec.content_lines:
                if not line.strip():
                    match.content_lines.append(line)
                    continue

                km = _KEY_VALUE_RE.match(line.strip())
                if km:
                    key, new_val = km.group(1), km.group(2).strip()
                    if key in existing_keys:
                        idx, old_val = existing_keys[key]
                        if old_val == new_val:
                            # Same value (or both blank) -> skip
                            continue
                        if not old_val and new_val:
                            # Existing blank, new has value -> replace
                            match.content_lines[idx] = line
                            existing_keys[key] = (idx, new_val)
                            continue
                        if old_val and not new_val:
                            # Existing has value, new blank -> skip
                            continue
                        # Different non-empty values -> keep both
                    existing_keys[key] = (len(match.content_lines), new_val)
                    match.content_lines.append(line)
                    existing_lines.add(line)
                elif line not in existing_lines:
                    match.content_lines.append(line)
                    existing_lines.add(line)

            match.children = merge_sections(match.children, new_sec.children)
        else:
            result.append(deepcopy(new_sec))

    return result

# endregion
# ============================================================================
# region Serialization: Section Tree -> String
# ============================================================================

def prune_empty_sections(sections):
    """Recursively remove sections that have no content and no children.

    A section is considered empty if all its content_lines are blank
    and it has no children (after its own children have been pruned).

    Args:
        sections: List of Section objects.

    Returns:
        Filtered list with empty sections removed.
    """
    pruned = []
    for section in sections:
        section.children = prune_empty_sections(section.children)
        has_content = any(line.strip() for line in section.content_lines)
        if has_content or section.children:
            pruned.append(section)
    return pruned


def serialize_sections(preamble, sections):
    """Convert a preamble and section tree back into a string.

    Formatting rules to keep output readable:
      - A blank line is inserted before sibling/parent-level headings (same
        or shallower level) when the previous line isn't already blank.
      - No blank line is inserted before a first-child heading (deeper level)
        so the parent -> child flow stays tight.
      - Trailing blank lines are trimmed; one final newline is appended.

    Args:
        preamble: Lines before the first heading.
        sections: Top-level Section list.

    Returns:
        Serialized document string.
    """
    lines = list(preamble)
    prev_heading_level = 0

    def write(section):
        nonlocal prev_heading_level

        # Insert a blank line before same-level or shallower headings when
        # the preceding line has content (avoids double-blanks).
        needs_separator = (
            lines
            and lines[-1].strip() != ''
            and prev_heading_level > 0
            and section.level <= prev_heading_level
        )
        if needs_separator:
            lines.append('')

        prev_heading_level = section.level
        lines.append(section.heading_line)
        lines.extend(section.content_lines)

        for child in section.children:
            write(child)

    for section in sections:
        write(section)

    # Trim trailing blank lines
    while lines and lines[-1].strip() == '':
        lines.pop()

    return '\n'.join(lines) + '\n'

# endregion
# ============================================================================
# region Compose Parsing: Discover Container References
# ============================================================================

def _parse_include_paths(content, base_dir):
    """Extract include file paths from a compose.yaml's content.

    Supports two Docker Compose include formats:
      - Simple:  ``include: [../other/compose.yaml]``  (list of strings)
      - Object:  ``include: [{path: ../other/compose.yaml}]``

    Paths are resolved relative to *base_dir* (the directory containing the
    compose file that declares the include).

    Args:
        content:  Full compose.yaml content string.
        base_dir: Directory of the compose file (for path resolution).

    Returns:
        List of resolved Path objects for each include.
    """
    paths = []
    in_include = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith('#'):
            continue

        # Detect the start of the include: block
        if re.match(r'^include\s*:', stripped):
            in_include = True
            continue

        if in_include:
            if stripped.startswith('-'):
                # "- path: <value>" (object form)
                m = re.match(r'^-\s+path\s*:\s*(.+)', stripped)
                if m:
                    raw = m.group(1).strip().strip('"').strip("'")
                    paths.append(base_dir / raw)
                else:
                    # "- <path>" (simple string form)
                    m = re.match(r'^-\s+(.+)', stripped)
                    if m:
                        raw = m.group(1).strip().strip('"').strip("'")
                        # Skip sub-keys (e.g. "env_file: ..." on same line)
                        if ':' not in raw:
                            paths.append(base_dir / raw)
            elif stripped:
                # Non-blank, non-list line: we've left the include block
                in_include = False

    return paths


def extract_container_refs(compose_path, _visited=None):
    """Extract container names and service variants from a compose.yaml.

    Scans for 'extends > file' references matching the pattern
    containers/<name>/compose.yaml and also extracts the ``service:``
    value from each extends block. Follows Docker Compose ``include``
    directives recursively so that containers from included compose
    files are discovered as well.

    Skips YAML comment lines. Each container is returned only once,
    even if multiple services extend from the same container directory.
    Visited files are tracked to prevent infinite loops.

    Args:
        compose_path: Path to the stack's compose.yaml.

    Returns:
        (container_names, service_map) where:
          container_names: List of container dir names in first-appearance order.
          service_map:     Dict mapping container dir name to set of service
                           variant names (leading '.' stripped). Used for
                           tag-based section filtering.
    """
    if _visited is None:
        _visited = set()

    resolved = compose_path.resolve()
    if resolved in _visited:
        return [], {}
    _visited.add(resolved)

    content = compose_path.read_text(encoding='utf-8')
    seen = set()
    containers = []
    service_map = {}

    # Recursively process included compose files first so that base
    # containers appear before the current file's own containers.
    for inc_path in _parse_include_paths(content, compose_path.parent):
        if inc_path.exists():
            inc_containers, inc_services = extract_container_refs(
                inc_path, _visited
            )
            for name in inc_containers:
                if name not in seen:
                    seen.add(name)
                    containers.append(name)
            for name, svcs in inc_services.items():
                service_map.setdefault(name, set()).update(svcs)

    # Extract container refs and service names from extends directives
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('#'):
            continue
        m = re.search(r'containers/([^/]+)/compose\.yaml', line)
        if m:
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                containers.append(name)

            # Look at nearby lines for the service: directive
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                svc_m = re.match(r'\s+service:\s+\.?([\w-]+)', lines[j])
                if svc_m:
                    service_map.setdefault(name, set()).add(svc_m.group(1))
                    break

    return containers, service_map


_PROJECT_NAME_RE = re.compile(
    r'^#\s*Project\s+Name\s*:\s*"([^"]+)"', re.MULTILINE
)


def extract_project_name(compose_path):
    """Extract the project name from a compose.yaml comment.

    Looks for a line matching ``# Project Name: "<name>"`` in the
    compose file. This value is used to populate the PROJECT_NAME
    variable in generated komodo.env and .env files.

    Args:
        compose_path: Path to the stack's compose.yaml.

    Returns:
        The project name string, or None if not found.
    """
    content = compose_path.read_text(encoding='utf-8')
    m = _PROJECT_NAME_RE.search(content)
    return m.group(1) if m else None

# endregion
# ============================================================================
# region komodo.env Builder
# ============================================================================

def build_komodo_env(base_content, containers_dir, container_names,
                     service_map=None, project_name=None):
    """Build a stack's komodo.env from base + container komodo.env files.

    Starts from base-komodo.env content and merges each container's
    komodo.env by heading. Same headings are combined; new headings
    are appended. Tagged sections are filtered based on which service
    variants the stack uses.

    Args:
        base_content:    Content string of base-komodo.env.
        containers_dir:  Path to the containers/ directory.
        container_names: Ordered list of container names to merge.
        service_map:     Optional dict mapping container name to set of
                         active service variant names for tag filtering.
        project_name:    Optional project name extracted from compose.yaml.
                         Sets the PROJECT_NAME value in the output.

    Returns:
        Generated komodo.env content string.
    """
    if service_map is None:
        service_map = {}

    preamble, sections = parse_sections(base_content, detect_komodo_heading)

    for name in container_names:
        env_path = containers_dir / name / 'komodo.env'
        if not env_path.exists():
            continue
        content = env_path.read_text(encoding='utf-8')
        _, container_sections = parse_sections(content, detect_komodo_heading)

        active_tags = service_map.get(name, set())
        if active_tags:
            container_sections = filter_sections_by_tags(
                container_sections, active_tags
            )

        sections = merge_sections(sections, container_sections)

    output = serialize_sections(preamble, sections)

    # Set PROJECT_NAME from compose.yaml if available and currently empty
    if project_name:
        output = re.sub(
            r'^(PROJECT_NAME:\s*)$', f'PROJECT_NAME: {project_name}',
            output, count=1, flags=re.MULTILINE,
        )

    return output

# endregion
# ============================================================================
# region README.md Builder
# ============================================================================

def build_readme(base_content, existing_content, containers_dir,
                 container_names, stack_name, service_map=None):
    """Build a stack's README.md from existing/base + container READMEs.

    Merge rules:
      1. If an existing stack README.md is available, it is used as the
         starting point. Otherwise the base-README.md template is used.
      2. H1 headings that appear in the base-README.md or ANY container
         README are considered "shared" -- they are rebuilt entirely from
         base + container content each run. Base sections are applied
         first, then container sections are layered on top. This enables
         automatic cleanup when a container is removed from the stack
         and ensures global base content stays up to date.
      3. Base H1 headings are only included if at least one container
         contributes non-empty content or children to that heading.
         Base-only sections (where no container adds real content) are
         dropped so scaffolding headings only appear when needed.
      4. H1 headings that exist ONLY in the stack README (manually added)
         are preserved untouched.
      5. New H1 headings from base or containers not yet in the result
         are appended.
      6. Tagged sections in container READMEs are filtered based on which
         service variants the stack uses.

    Args:
        base_content:    Content string of base-README.md.
        existing_content: Content of existing stack README.md, or None.
        containers_dir:  Path to the containers/ directory.
        container_names: Ordered list of container names to merge.
        stack_name:      Stack directory name (for template substitution).
        service_map:     Optional dict mapping container name to set of
                         active service variant names for tag filtering.

    Returns:
        Generated README.md content string.
    """
    if service_map is None:
        service_map = {}
    pretty_name = stack_name.replace('-', ' ').title()
    base_substituted = base_content.replace('<stackName>', pretty_name)

    # --- Determine starting content ---
    if existing_content is not None:
        start_content = existing_content
    else:
        start_content = base_substituted

    preamble, existing_sections = parse_sections(
        start_content, detect_markdown_heading
    )

    # --- Parse base README sections (always used as shared source) ---
    _, base_sections = parse_sections(base_substituted, detect_markdown_heading)

    # --- Collect all container README sections ---
    container_section_lists = []
    for name in container_names:
        readme_path = containers_dir / name / 'stack-README.md'
        if not readme_path.exists():
            continue
        content = readme_path.read_text(encoding='utf-8')
        _, sections = parse_sections(content, detect_markdown_heading)

        active_tags = service_map.get(name, set())
        if active_tags:
            sections = filter_sections_by_tags(sections, active_tags)

        container_section_lists.append(sections)

    # Base sections come first, then container sections layer on top
    all_section_lists = [base_sections] + container_section_lists

    # --- Identify which H1 texts are "shared" (appear in base or any container) ---
    shared_h1_texts = set()
    for section_list in all_section_lists:
        for section in section_list:
            shared_h1_texts.add(section.heading_text)

    # Helper: rebuild a section by merging content from all sources
    def rebuild_from_sources(heading_line, heading_text, level):
        rebuilt = Section(
            heading_line=heading_line,
            heading_text=heading_text,
            level=level,
        )
        for section_list in all_section_lists:
            for src_sec in section_list:
                if src_sec.heading_text == heading_text:
                    rebuilt.content_lines.extend(src_sec.content_lines)
                    rebuilt.children = merge_sections(
                        rebuilt.children, src_sec.children
                    )
                    break
        return rebuilt

    # --- Build result with enforced H1 ordering ---
    # Order: 1) Stack-only  2) Base (in base order)  3) Container-only
    result = []
    seen = set()

    # 1) Stack-only H1s: preserve as-is, in their existing order
    for existing_sec in existing_sections:
        if existing_sec.heading_text not in shared_h1_texts:
            result.append(deepcopy(existing_sec))
            seen.add(existing_sec.heading_text)

    # 2) Base H1s: in base-README.md order, rebuilt from all sources.
    #    Only include if at least one container contributes to this heading;
    #    base-only sections are dropped when no containers need them.
    for base_sec in base_sections:
        if base_sec.heading_text not in seen:
            # Build a temporary merge of only container contributions to
            # this H1.  If no container adds non-empty children or content,
            # the base section is unnecessary for this stack.
            container_only = Section(
                heading_line=base_sec.heading_line,
                heading_text=base_sec.heading_text,
                level=base_sec.level,
            )
            for sl in container_section_lists:
                for src_sec in sl:
                    if src_sec.heading_text == base_sec.heading_text:
                        container_only.content_lines.extend(
                            src_sec.content_lines
                        )
                        container_only.children = merge_sections(
                            container_only.children, src_sec.children
                        )
                        break
            container_only.children = prune_empty_sections(
                container_only.children
            )
            has_content = any(
                line.strip() for line in container_only.content_lines
            )
            if not has_content and not container_only.children:
                seen.add(base_sec.heading_text)
                continue
            # Use the existing heading line if available (preserves any
            # manual heading-level tweaks the user made in the stack README)
            heading_line = base_sec.heading_line
            for existing_sec in existing_sections:
                if existing_sec.heading_text == base_sec.heading_text:
                    heading_line = existing_sec.heading_line
                    break
            result.append(rebuild_from_sources(
                heading_line, base_sec.heading_text, base_sec.level
            ))
            seen.add(base_sec.heading_text)

    # 3) Container-only H1s: not in base, rebuilt from all sources
    for section_list in container_section_lists:
        for cont_sec in section_list:
            if cont_sec.heading_text not in seen:
                heading_line = cont_sec.heading_line
                for existing_sec in existing_sections:
                    if existing_sec.heading_text == cont_sec.heading_text:
                        heading_line = existing_sec.heading_line
                        break
                result.append(rebuild_from_sources(
                    heading_line, cont_sec.heading_text, cont_sec.level
                ))
                seen.add(cont_sec.heading_text)

    # --- Remove sections that have no content and no children ---
    result = prune_empty_sections(result)

    return serialize_sections(preamble, result)

# endregion
# ============================================================================
# region Testing .env Generator
# ============================================================================

def parse_env_file(path):
    """Parse a KEY=VALUE file into a dictionary.

    Skips blank lines and comments. Values are taken as-is (no quote
    stripping) to preserve the user's exact input.

    Args:
        path: Path to the .env file.

    Returns:
        Dict of {key: value} pairs. Empty dict if file doesn't exist.
    """
    values = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)', stripped)
        if m:
            values[m.group(1)] = m.group(2)

    return values


def parse_komodo_values(path):
    """Parse a komodo-format file (KEY: VALUE) into a dictionary.

    These files use the same KEY: VALUE format as komodo.env but are
    used as testing defaults. Headings and comments are skipped; only
    key-value pairs are extracted. [[...]] Komodo variable references
    are stripped from values.

    Args:
        path: Path to the komodo-format file.

    Returns:
        Dict of {key: value} pairs. Empty dict if file doesn't exist.
    """
    values = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)', stripped)
        if m:
            value = re.sub(r'\[\[.*?\]\]', '', m.group(2)).strip()
            values[m.group(1)] = value

    return values


def parse_komodo_values_filtered(path, active_tags=None):
    """Parse a komodo-format file with optional tag-based filtering.

    When active_tags is provided, the file is parsed into sections,
    tagged sections that don't match are removed, then KEY: VALUE
    pairs are extracted from the surviving sections. When active_tags
    is None or empty, delegates to parse_komodo_values() (no filtering).

    Args:
        path:        Path to the komodo-format file.
        active_tags: Optional set of active service names for filtering.

    Returns:
        Dict of {key: value} pairs. Empty dict if file doesn't exist.
    """
    if not active_tags:
        return parse_komodo_values(path)

    if not path.exists():
        return {}

    content = path.read_text(encoding='utf-8')
    preamble, sections = parse_sections(content, detect_komodo_heading)
    sections = filter_sections_by_tags(sections, active_tags)

    # Extract KEY: VALUE pairs from preamble + surviving sections
    all_lines = list(preamble)

    def collect_lines(section_list):
        for sec in section_list:
            all_lines.extend(sec.content_lines)
            collect_lines(sec.children)

    collect_lines(sections)

    values = {}
    for line in all_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)', stripped)
        if m:
            value = re.sub(r'\[\[.*?\]\]', '', m.group(2)).strip()
            values[m.group(1)] = value

    return values


def generate_test_env(komodo_content, existing_values, override_values,
                      container_values, reset_env=False):
    """Generate a docker-compose-compatible .env from komodo.env content.

    Transforms the komodo.env format into standard KEY=VALUE pairs:
      - Komodo headings (#=, #==) become # comment separators.
      - KEY: VALUE lines become KEY=VALUE lines.
      - [[Variable]] Komodo references are resolved by looking up the
        referenced key name in the override and container value sources.
        If found, the reference is replaced with that value. Otherwise
        the reference is replaced with an empty string.
      - Regular comment lines are preserved.

    Value resolution order for each KEY (first non-empty wins):

    Normal mode:
      1. existing_values   - preserves values the user already set in the
         stack's local .env so they are not overwritten on rebuild.
      2. override_values   - fills in defaults from scripts/base-testing.env
         and scripts/.env for any variables still empty.
      3. The raw value from komodo.env (with [[...]] refs resolved).
      4. container_values  - values from each container's testing.env file,
         providing container-specific test defaults.

    Reset mode (--reset-env):
      1. override_values
      2. The raw value from komodo.env
      3. container_values
      4. existing_values   - only used as a last resort when no default
         exists from any other source.

    Args:
        komodo_content:   The generated komodo.env content string.
        existing_values:  Dict of KEY=VALUE from the stack's current .env.
        override_values:  Dict of KEY=VALUE from the scripts override files.
        container_values: Dict of KEY=VALUE from each container's testing.env.
        reset_env:        When True, use reset mode resolution order.

    Returns:
        Standard .env file content string.
    """
    output_lines = []
    # Track resolved values so [[KEY]] references can resolve to values
    # from earlier in the same file (e.g. POSTGRES_PASSWORD: [[KOMODO_DB_PASSWORD]]
    # resolves to whatever KOMODO_DB_PASSWORD was resolved to).
    resolved_values = {}
    # Map of key -> referenced komodo key for [[KEY]] references, so
    # dedup_env can cross-resolve after password generation.
    ref_map = {}

    for line in komodo_content.splitlines():
        stripped = line.strip()

        # Blank lines pass through
        if not stripped:
            output_lines.append('')
            continue

        # Convert komodo headings to regular comments
        heading = detect_komodo_heading(stripped)
        if heading:
            level, text = heading
            prefix = '#' * level
            output_lines.append(f"{prefix} {text}")
            continue

        # Preserve regular comment lines as-is
        if stripped.startswith('#'):
            output_lines.append(stripped)
            continue

        # Convert KEY: VALUE to KEY=VALUE with value resolution
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)', stripped)
        if m:
            key = m.group(1)
            raw_value = m.group(2).strip()
            # Resolve [[KEY]] Komodo references by looking up the
            # referenced key in override files, container testing files,
            # and already-resolved values from earlier in this file.
            def _resolve_ref(ref_match):
                ref_key = ref_match.group(1)
                if ref_key in override_values and override_values[ref_key] != '':
                    return override_values[ref_key]
                if ref_key in container_values and container_values[ref_key] != '':
                    return container_values[ref_key]
                if ref_key in resolved_values and resolved_values[ref_key] != '':
                    return resolved_values[ref_key]
                return ''
            base_value = re.sub(r'\[\[([^\]]+)\]\]', _resolve_ref, raw_value)

            # Resolve value from sources (first non-empty wins)
            if reset_env:
                # Reset: override > base > container > VERSION > existing
                if key in override_values and override_values[key] != '':
                    value = override_values[key]
                elif base_value:
                    value = base_value
                elif key in container_values and container_values[key] != '':
                    value = container_values[key]
                elif key.endswith('_VERSION'):
                    value = 'latest'
                elif key in existing_values and existing_values[key] != '':
                    value = existing_values[key]
                else:
                    value = ''
            else:
                # Normal: existing > override > base > container > VERSION
                if key in existing_values and existing_values[key] != '':
                    value = existing_values[key]
                elif key in override_values and override_values[key] != '':
                    value = override_values[key]
                elif base_value:
                    value = base_value
                elif key in container_values and container_values[key] != '':
                    value = container_values[key]
                elif key.endswith('_VERSION'):
                    value = 'latest'
                else:
                    value = ''

            resolved_values[key] = value
            # Track [[KEY]] references for post-processing resolution
            refs = re.findall(r'\[\[([^\]]+)\]\]', raw_value)
            if refs:
                for ref_key in refs:
                    ref_map[key] = ref_key
            output_lines.append(f"{key}={value}")
            continue

        # Any other line: preserve as-is
        output_lines.append(stripped)

    # Trim trailing blank lines
    while output_lines and output_lines[-1].strip() == '':
        output_lines.pop()

    return '\n'.join(output_lines) + '\n', ref_map

# endregion
# ============================================================================
# region Post-Processing: Deduplication & Password Generation
# ============================================================================

def generate_password(length=16):
    """Generate a random alphanumeric password.

    Args:
        length: Number of characters (default 16).

    Returns:
        Random string of ASCII letters and digits.
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# Keys ending in one of these get an auto-generated 48-character alphanumeric
# value when blank — DB users' own passwords, chosen by us, no external issuer
# and no format/length restriction of their own.
DB_PASSWORD_SUFFIXES = ('_PASSWORD', '_PASS')
DB_PASSWORD_LENGTH = 48

# Keys ending in one of these get an auto-generated 96-character alphanumeric
# value when blank — other self-issued application secrets (API passkeys,
# internal signing/session keys, inter-service shared secrets). Deliberately
# narrow and does NOT include every *_KEY/*_SECRET/*_TOKEN-shaped name:
#   - *_API_KEY / *_API_TOKEN / *_LICENSE_KEY are issued by an external service
#     (Cloudflare, MaxMind, etc.) — a random value here would silently look
#     "filled in" but not actually work, so these stay blank for a human to
#     paste a real one in.
#   - *_KEY_ENCRYPTION (SEMAPHORE_ACCESS_KEY_ENCRYPTION) must be a
#     base64-encoded 32-byte key, not plain alphanumeric — see its own
#     stack-README.md (`head -c32 /dev/urandom | base64`) — so it's excluded
#     here and stays a documented manual step.
OTHER_SECRET_SUFFIXES = ('_PASSKEY', '_SECRET_KEY', '_LAPI_KEY')
OTHER_SECRET_LENGTH = 96


def dedup_komodo_env(content):
    """Comment out duplicate KEY: VALUE lines in komodo.env content.

    Scans through the content line by line. For each KEY: VALUE line,
    if the key has already appeared, the line is prefixed with '# ' to
    comment it out. The first occurrence of each key is kept as-is.

    Args:
        content: The generated komodo.env content string.

    Returns:
        Content with duplicate keys commented out.
    """
    seen_keys = set()
    lines = content.splitlines()
    result = []

    for line in lines:
        stripped = line.strip()
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:', stripped)
        if m:
            key = m.group(1)
            if key in seen_keys:
                result.append(f'# {line}')
            else:
                seen_keys.add(key)
                result.append(line)
        else:
            result.append(line)

    # Preserve original trailing newline
    if content.endswith('\n'):
        return '\n'.join(result) + '\n'
    return '\n'.join(result)


def dedup_env(content, ref_map=None):
    """Comment out duplicate keys and generate passwords in .env content.

    Three post-processing steps applied to the generated .env:

    1. Password/secret generation: For keys ending in one of
       DB_PASSWORD_SUFFIXES ('_PASSWORD', '_PASS') whose resolved value is
       empty, a random 48-character alphanumeric value is generated. For
       keys ending in one of OTHER_SECRET_SUFFIXES ('_PASSKEY',
       '_SECRET_KEY', '_LAPI_KEY'), a random 96-character alphanumeric
       value is generated. See those constants' definitions for why the
       second list deliberately excludes lookalike external-API-credential
       and fixed-format keys.

    2. Deduplication: The first occurrence of each key is kept. Subsequent
       occurrences are commented out with '# '. Duplicate _PASSWORD entries
       use the same password value as the first occurrence.

    3. Cross-reference resolution: Keys that referenced another key via
       [[KEY]] in the komodo.env are updated to match the referenced
       key's final value (e.g. POSTGRES_PASSWORD referencing
       [[KOMODO_DB_PASSWORD]] will get the same generated password).

    Args:
        content:  The generated .env content string.
        ref_map:  Optional dict mapping key -> referenced komodo key name.
                  Used to resolve [[KEY]] cross-references after passwords
                  are generated.

    Returns:
        Content with passwords filled, references resolved, and duplicates
        commented out.
    """
    if ref_map is None:
        ref_map = {}

    seen_keys = {}  # key -> resolved value (for consistent duplicate values)
    lines = content.splitlines()
    result = []
    # Track line index for each key so we can update values in place
    key_line_idx = {}  # key -> index in result list

    for line in lines:
        stripped = line.strip()
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)', stripped)
        if m:
            key = m.group(1)
            value = m.group(2)

            if key in seen_keys:
                # Duplicate: comment out with the first occurrence's value
                result.append(f'# {key}={seen_keys[key]}')
            else:
                # First occurrence
                if key.endswith(DB_PASSWORD_SUFFIXES) and value == '':
                    value = generate_password(DB_PASSWORD_LENGTH)
                elif key.endswith(OTHER_SECRET_SUFFIXES) and value == '':
                    value = generate_password(OTHER_SECRET_LENGTH)
                seen_keys[key] = value
                key_line_idx[key] = len(result)
                result.append(f'{key}={value}')
        else:
            result.append(line)

    # Resolve cross-references: if key A referenced [[KEY_B]], update A's
    # value to match B's final resolved value.
    for key, ref_key in ref_map.items():
        if ref_key in seen_keys and key in seen_keys:
            ref_value = seen_keys[ref_key]
            if ref_value and seen_keys[key] != ref_value:
                seen_keys[key] = ref_value
                if key in key_line_idx:
                    result[key_line_idx[key]] = f'{key}={ref_value}'

    # Preserve original trailing newline
    if content.endswith('\n'):
        return '\n'.join(result) + '\n'
    return '\n'.join(result)

# endregion
# ============================================================================
# region Project Root Discovery
# ============================================================================

def find_project_root():
    """Locate the docker-stacks project root directory.

    Strategy:
      1. The script lives in scripts/, so its grandparent should have
         both containers/ and stacks/ directories.
      2. Fallback: check the current working directory.

    Returns:
        Path to the project root.

    Raises:
        SystemExit: If the root cannot be found.
    """
    # Primary: scripts/build.py -> parent of scripts/ is project root
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent
    if (candidate / 'containers').is_dir() and (candidate / 'stacks').is_dir():
        return candidate

    # Fallback: current working directory
    cwd = Path.cwd()
    if (cwd / 'containers').is_dir() and (cwd / 'stacks').is_dir():
        return cwd

    print("Error: Could not find project root directory.")
    print("Expected 'containers/' and 'stacks/' directories.")
    print(f"  Checked: {candidate}")
    print(f"  Checked: {cwd}")
    sys.exit(1)

# endregion
# ============================================================================
# region Per-Stack Build
# ============================================================================

def build_stack(stack_dir, containers_dir, base_komodo, base_readme,
                override_values, reset_env=False):
    """Build all generated files for a single stack.

    Reads the stack's compose.yaml to discover which containers it uses,
    then generates komodo.env, README.md, and .env in the stack directory.

    Args:
        stack_dir:       Path to the stack directory.
        containers_dir:  Path to the containers/ directory.
        base_komodo:     Content string of base-komodo.env.
        base_readme:     Content string of base-README.md.
        override_values: Dict of default KEY=VALUE pairs from scripts/
                         override files (base-testing.env, .env).
        reset_env:       When True, reset .env values to defaults.
    """
    stack_name = stack_dir.name
    compose_path = stack_dir / 'compose.yaml'

    if not compose_path.exists():
        print(f"  Skipping '{stack_name}': no compose.yaml found")
        return

    # --- Discover containers and service variants ---
    container_names, service_map = extract_container_refs(compose_path)
    if not container_names:
        print(f"  Skipping '{stack_name}': no container extends references found")
        return

    # --- Extract project name from compose.yaml ---
    project_name = extract_project_name(compose_path)

    print(f"  Stack: {stack_name}")
    print(f"    Containers: {', '.join(container_names)}")

    # --- Generate komodo.env ---
    komodo_output = build_komodo_env(
        base_komodo, containers_dir, container_names, service_map,
        project_name=project_name,
    )
    komodo_deduped = dedup_komodo_env(komodo_output)
    (stack_dir / 'komodo.env').write_text(komodo_deduped, encoding='utf-8')
    print("    Created: komodo.env")

    # --- Generate README.md ---
    existing_readme_path = stack_dir / 'README.md'
    existing_readme = None
    if existing_readme_path.exists():
        existing_readme = existing_readme_path.read_text(encoding='utf-8')

    readme_output = build_readme(
        base_readme, existing_readme, containers_dir,
        container_names, stack_name, service_map
    )
    (stack_dir / 'README.md').write_text(readme_output, encoding='utf-8')
    print("    Created: README.md")

    # --- Generate testing .env ---
    # Read any existing .env values the user has already filled in
    existing_env = parse_env_file(stack_dir / '.env')
    # Collect testing defaults from each container's testing.env
    # These files use komodo format (KEY: VALUE), not standard .env format
    container_env = {}
    for name in container_names:
        active_tags = service_map.get(name, set())
        container_env.update(
            parse_komodo_values_filtered(
                containers_dir / name / 'testing.env',
                active_tags=active_tags if active_tags else None,
            )
        )
    # Use the original (non-deduped) komodo content so that duplicate KEY:
    # VALUE lines are converted to KEY=VALUE before dedup_env processes them.
    env_output, ref_map = generate_test_env(
        komodo_output, existing_env, override_values, container_env,
        reset_env=reset_env,
    )
    env_output = dedup_env(env_output, ref_map)
    (stack_dir / '.env').write_text(env_output, encoding='utf-8')
    print("    Created: .env (testing)")

# endregion
# ============================================================================
# region Entry Point
# ============================================================================

def main():
    """Discover all stacks and build their generated files."""
    parser = argparse.ArgumentParser(
        description='Build stack files from base templates and containers.'
    )
    parser.add_argument(
        '--reset-env', action='store_true',
        help='Reset .env values to defaults. Existing values are only '
             'preserved for keys that have no default from any other source.'
    )
    args = parser.parse_args()

    root = find_project_root()
    containers_dir = root / 'containers'
    stacks_dir = root / 'stacks'
    scripts_dir = root / 'scripts'

    print(f"Project root: {root}")

    # --- Load base files ---
    base_komodo_path = scripts_dir / 'base-komodo.env'
    base_readme_path = scripts_dir / 'base-README.md'

    if not base_komodo_path.exists():
        print(f"Error: base file not found: {base_komodo_path}")
        sys.exit(1)
    if not base_readme_path.exists():
        print(f"Error: base file not found: {base_readme_path}")
        sys.exit(1)

    base_komodo = base_komodo_path.read_text(encoding='utf-8')
    base_readme = base_readme_path.read_text(encoding='utf-8')

    # --- Load .env override files from scripts/ ---
    # base-testing.env: non-sensitive defaults safe to commit (loaded first).
    # .env:         environment-specific overrides, gitignored (loaded second,
    #               so its values take priority over base-testing.env).
    override_values = parse_env_file(scripts_dir / 'base-testing.env')
    override_values.update(parse_env_file(scripts_dir / '.env'))

    # --- Discover and build each stack ---
    stack_dirs = sorted(
        d for d in stacks_dir.iterdir() if d.is_dir()
    )

    if not stack_dirs:
        print("No stack directories found.")
        return

    print(f"Found {len(stack_dirs)} stack(s)")
    if args.reset_env:
        print("Mode: --reset-env (resetting .env values to defaults)")
    print()

    for stack_dir in stack_dirs:
        build_stack(
            stack_dir, containers_dir, base_komodo, base_readme,
            override_values, reset_env=args.reset_env,
        )
        print()

    print("Build complete.")

# endregion


if __name__ == '__main__':
    main()
