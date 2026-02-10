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

import re
import sys
from pathlib import Path
from copy import deepcopy


# ============================================================================
# Data Structures
# ============================================================================

class Section:
    """A heading-delimited section in a structured document.

    Represents a single heading with its direct content (lines between this
    heading and the next heading or child) and any child sections (headings
    at a deeper nesting level).

    Attributes:
        heading_line:  Full heading line as it appears in the file.
        heading_text:  Heading text without the prefix markers.
        level:         Nesting depth (1 = top-level, 2 = sub-section, etc.).
        content_lines: Lines belonging directly to this section.
        children:      Child Section objects at a deeper level.
    """

    def __init__(self, heading_line="", heading_text="", level=0,
                 content_lines=None):
        self.heading_line = heading_line
        self.heading_text = heading_text
        self.level = level
        self.content_lines = content_lines if content_lines is not None else []
        self.children = []

    def __repr__(self):
        return (
            f"Section(level={self.level}, text={self.heading_text!r}, "
            f"content={len(self.content_lines)} lines, "
            f"children={len(self.children)})"
        )


# ============================================================================
# Heading Detection
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


# ============================================================================
# Parsing: Content -> Section Tree
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
            current = Section(heading_line=line, heading_text=text, level=level)
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


# ============================================================================
# Merging: Combine Section Trees
# ============================================================================

def merge_sections(base_sections, new_sections):
    """Merge new_sections into base_sections by matching heading text.

    For each section in new_sections:
      - If a section with the same heading_text exists in base: append
        content lines and recursively merge children.
      - If no match: append as a new section.

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
            match.content_lines.extend(new_sec.content_lines)
            match.children = merge_sections(match.children, new_sec.children)
        else:
            result.append(deepcopy(new_sec))

    return result


# ============================================================================
# Serialization: Section Tree -> String
# ============================================================================

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


# ============================================================================
# Compose Parsing: Discover Container References
# ============================================================================

def extract_container_refs(compose_path):
    """Extract unique container names from a stack's compose.yaml.

    Scans for 'extends > file' references matching the pattern
    containers/<name>/compose.yaml. Skips YAML comment lines.
    Each container is returned only once, even if multiple services
    extend from the same container directory.

    Args:
        compose_path: Path to the stack's compose.yaml.

    Returns:
        List of container directory names in order of first appearance.
    """
    content = compose_path.read_text(encoding='utf-8')
    seen = set()
    containers = []

    for line in content.splitlines():
        if line.strip().startswith('#'):
            continue
        m = re.search(r'containers/([^/]+)/compose\.yaml', line)
        if m:
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                containers.append(name)

    return containers


# ============================================================================
# komodo.env Builder
# ============================================================================

def build_komodo_env(base_content, containers_dir, container_names):
    """Build a stack's komodo.env from base + container komodo.env files.

    Starts from base-komodo.env content and merges each container's
    komodo.env by heading. Same headings are combined; new headings
    are appended.

    Args:
        base_content:    Content string of base-komodo.env.
        containers_dir:  Path to the containers/ directory.
        container_names: Ordered list of container names to merge.

    Returns:
        Generated komodo.env content string.
    """
    preamble, sections = parse_sections(base_content, detect_komodo_heading)

    for name in container_names:
        env_path = containers_dir / name / 'komodo.env'
        if not env_path.exists():
            continue
        content = env_path.read_text(encoding='utf-8')
        _, container_sections = parse_sections(content, detect_komodo_heading)
        sections = merge_sections(sections, container_sections)

    return serialize_sections(preamble, sections)


# ============================================================================
# README.md Builder
# ============================================================================

def build_readme(base_content, existing_content, containers_dir,
                 container_names, stack_name):
    """Build a stack's README.md from existing/base + container READMEs.

    Merge rules:
      1. If an existing stack README.md is available, it is used as the
         starting point. Otherwise the base-README.md template is used
         (with <stackName> replaced by the formatted stack directory name).
      2. H1 headings that appear in ANY container README are considered
         "shared" -- they are rebuilt entirely from container content each
         run. This enables automatic cleanup when a container is removed
         from the stack.
      3. H1 headings that exist ONLY in the stack README (manually added)
         are preserved untouched.
      4. New H1 headings from containers not yet in the result are appended.

    Args:
        base_content:    Content string of base-README.md.
        existing_content: Content of existing stack README.md, or None.
        containers_dir:  Path to the containers/ directory.
        container_names: Ordered list of container names to merge.
        stack_name:      Stack directory name (for template substitution).

    Returns:
        Generated README.md content string.
    """
    # --- Determine starting content ---
    if existing_content is not None:
        start_content = existing_content
    else:
        # First build: replace the <stackName> placeholder in the base
        pretty_name = stack_name.replace('-', ' ').title()
        start_content = base_content.replace('<stackName>', pretty_name)

    preamble, existing_sections = parse_sections(
        start_content, detect_markdown_heading
    )

    # --- Collect all container README sections ---
    container_section_lists = []
    for name in container_names:
        readme_path = containers_dir / name / 'stack-README.md'
        if not readme_path.exists():
            continue
        content = readme_path.read_text(encoding='utf-8')
        _, sections = parse_sections(content, detect_markdown_heading)
        container_section_lists.append(sections)

    # --- Identify which H1 texts are "shared" (appear in any container) ---
    shared_h1_texts = set()
    for section_list in container_section_lists:
        for section in section_list:
            shared_h1_texts.add(section.heading_text)

    # --- Rebuild shared headings; preserve stack-only headings ---
    result = []
    seen = set()

    for existing_sec in existing_sections:
        if existing_sec.heading_text in shared_h1_texts:
            # Shared: rebuild entirely from current containers
            rebuilt = Section(
                heading_line=existing_sec.heading_line,
                heading_text=existing_sec.heading_text,
                level=existing_sec.level,
            )
            for section_list in container_section_lists:
                for cont_sec in section_list:
                    if cont_sec.heading_text == rebuilt.heading_text:
                        rebuilt.content_lines.extend(cont_sec.content_lines)
                        rebuilt.children = merge_sections(
                            rebuilt.children, cont_sec.children
                        )
                        break
            result.append(rebuilt)
        else:
            # Stack-only: preserve as-is
            result.append(deepcopy(existing_sec))

        seen.add(existing_sec.heading_text)

    # --- Append new container H1 headings not already present ---
    for section_list in container_section_lists:
        for cont_sec in section_list:
            if cont_sec.heading_text not in seen:
                result.append(deepcopy(cont_sec))
                seen.add(cont_sec.heading_text)

    return serialize_sections(preamble, result)


# ============================================================================
# Testing .env Generator
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


def generate_test_env(komodo_content, existing_values, override_values,
                      container_values):
    """Generate a docker-compose-compatible .env from komodo.env content.

    Transforms the komodo.env format into standard KEY=VALUE pairs:
      - Komodo headings (#=, #==) become # comment separators.
      - KEY: VALUE lines become KEY=VALUE lines.
      - [[Variable]] Komodo references are replaced with empty strings
        so users can fill in local test values.
      - Regular comment lines are preserved.

    Value resolution order for each KEY (first non-empty wins):
      1. existing_values   - preserves values the user already set in the
         stack's local .env so they are not overwritten on rebuild.
      2. override_values   - fills in defaults from scripts/base-testing.env
         and scripts/.env for any variables still empty.
      3. The raw value from komodo.env (with [[...]] refs stripped).
      4. container_values  - values from each container's testing.env file,
         providing container-specific test defaults.

    Args:
        komodo_content:   The generated komodo.env content string.
        existing_values:  Dict of KEY=VALUE from the stack's current .env.
        override_values:  Dict of KEY=VALUE from the scripts override files.
        container_values: Dict of KEY=VALUE from each container's testing.env.

    Returns:
        Standard .env file content string.
    """
    output_lines = []

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
            # Strip [[...]] Komodo references to get the base value
            base_value = re.sub(r'\[\[.*?\]\]', '', raw_value)

            # Resolve: existing > override > base > container > VERSION default
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

            output_lines.append(f"{key}={value}")
            continue

        # Any other line: preserve as-is
        output_lines.append(stripped)

    # Trim trailing blank lines
    while output_lines and output_lines[-1].strip() == '':
        output_lines.pop()

    return '\n'.join(output_lines) + '\n'


# ============================================================================
# Project Root Discovery
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


# ============================================================================
# Per-Stack Build
# ============================================================================

def build_stack(stack_dir, containers_dir, base_komodo, base_readme,
                override_values):
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
    """
    stack_name = stack_dir.name
    compose_path = stack_dir / 'compose.yaml'

    if not compose_path.exists():
        print(f"  Skipping '{stack_name}': no compose.yaml found")
        return

    # --- Discover containers referenced by this stack ---
    container_names = extract_container_refs(compose_path)
    if not container_names:
        print(f"  Skipping '{stack_name}': no container extends references found")
        return

    print(f"  Stack: {stack_name}")
    print(f"    Containers: {', '.join(container_names)}")

    # --- Generate komodo.env ---
    komodo_output = build_komodo_env(
        base_komodo, containers_dir, container_names
    )
    (stack_dir / 'komodo.env').write_text(komodo_output, encoding='utf-8')
    print("    Created: komodo.env")

    # --- Generate README.md ---
    existing_readme_path = stack_dir / 'README.md'
    existing_readme = None
    if existing_readme_path.exists():
        existing_readme = existing_readme_path.read_text(encoding='utf-8')

    readme_output = build_readme(
        base_readme, existing_readme, containers_dir,
        container_names, stack_name
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
        container_env.update(
            parse_komodo_values(containers_dir / name / 'testing.env')
        )
    env_output = generate_test_env(
        komodo_output, existing_env, override_values, container_env
    )
    (stack_dir / '.env').write_text(env_output, encoding='utf-8')
    print("    Created: .env (testing)")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Discover all stacks and build their generated files."""

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

    print(f"Found {len(stack_dirs)} stack(s)\n")

    for stack_dir in stack_dirs:
        build_stack(
            stack_dir, containers_dir, base_komodo, base_readme,
            override_values,
        )
        print()

    print("Build complete.")


if __name__ == '__main__':
    main()
