# Project Layout

## Folder layout
The folder layout looks like the following with each sequential indent being another folder deep. `<>` are used to indicate values that would be replaced depending on the container or stack and that multiple entries could exist. Any items that are folders will be in **bold**.

docker-stacks
* **containers** _Folder containing all container sources_
  * **\<imageName>** - _Folder name should be the image name_
    * **config** - _Optional folder for any config needed to run container (e.g. traefik/rules, vector/config)_
    * compose.yaml - _This should only contain a single image, though there could be multiple containers using this image if there are different uses of the image (e.g. agent vs server)_
    * komodo.env - _Only contains items specific to this container_
    * README.md - _Container-level documentation (not used by build.py)_
    * stack-README.md - _Sections to merge into stack README.md files_
    * testing.env - _Container-specific test defaults in KEY: VALUE format_
* **stacks** - _Folder containing all stacks_
  * **\<stackName>** - _Friendly name of stack_
    * **\<imageName>-config** - _Any containers that need config outside of the compose file will store that config in a folder named **\<imageName>-config**_
    * compose.yaml - _This is the compose file that will control the stack. May use `include` to reference other stack compose files._
    * komodo.env - _This file is created by build.py_
    * .env - _This file is created by build.py (gitignored, for local testing)_
    * README.md - _This file is created by build.py_
* **scripts**
    * project-layout.md - _This file_
    * build.py - _Script that will build/update the komodo.env, README.md, and testing .env files for each stack._
    * base-komodo.env - _All sections in this file should be included in every stack's komodo.env_
    * base-README.md - _All sections in this file should be included in every stack's README.md_
    * base-testing.env - _Non-sensitive testing defaults safe to commit (KEY=VALUE format)_
    * .env - _Environment-specific overrides, gitignored (KEY=VALUE format). Values here take priority over base-testing.env._
* .gitignore - _gitignore file ensuring no env or live data files are ever committed to the project_

## build.py

Starting from base files (_base-komodo.env_, _base-README.md_) that contain shared/global sections every stack needs, the script merges in each container's individual _komodo.env_ and _stack-README.md_ sections, matching by heading. Same headings get combined; new headings get appended.

The script loops through all stack folders and reads each one's compose.yaml file. It extracts all enabled `extends` > `file` references to find the containers used in building the local stack files. Docker Compose `include` directives are also followed recursively (with cycle detection) so that containers from included compose files are discovered as well. Each container is only added once, even if referenced multiple times.

### Container Discovery

1. Read the stack's `compose.yaml`.
2. Follow any `include` directives recursively (supports both simple string form and `path:` object form). Visited files are tracked to prevent infinite loops.
3. Extract all `extends > file` references matching `containers/<name>/compose.yaml`.
4. Containers from included files appear first, followed by the current file's containers.
5. Each container name is returned only once, in order of first appearance.

---

## komodo.env
### File Structure

The komodo.env file uses a markdown-like format with headings preceded with `#=` (`#=`, `#==`, etc.) followed by key:value pairings. The following code snippet has an example with `<>` used to indicate values that would be replaced depending on the container or stack. Some of the values may be _[[\<Komodo Key Name>]]_ for referencing Komodo variables.

```env
################################################################
# <notes>
################################################################

#= Project Specific Settings

#= Stack Specific Settings
#== <container 1>
<key>: <value>
<key>: <value>

#== <container 2>
<key>: <value>
<key>: <value>

#= Global Settings
#== <heading 1>
<key>: <value>
<key>: <value>

#== <heading 2>
<key>: <value>
<key>: <value>
```

### How file is generated

1. **Base merge**: Start from _base-komodo.env_ and parse it into a section tree using `#=`/`#==` headings.
2. **Container merge**: For each container, parse its _komodo.env_ and merge sections by heading text. Same headings are combined (only unique non-blank lines are added); new headings are appended.
3. **Deduplication**: After merging, scan all `KEY: VALUE` lines. If a key appears more than once, all occurrences after the first are commented out with `# `.
4. **Output**: Serialize the section tree back to text and write to the stack's _komodo.env_.

---

## .env (Testing)
### File Structure

The .env file is a standard Docker Compose environment file using `KEY=VALUE` format. Headings from komodo.env are converted to regular `#` comments for readability.

```env
################################################################
# <notes>
################################################################

# Project Specific Settings

# Stack Specific Settings
## <container 1>
<KEY>=<value>
<KEY>=<value>

## <container 2>
<KEY>=<value>
<KEY>=<value>

# Global Settings
## <heading 1>
<KEY>=<value>
<KEY>=<value>
```

### How file is generated

1. **Transform**: The generated komodo.env content (before dedup) is transformed line-by-line:
   - Komodo headings (`#=`, `#==`) become regular comment lines (`#`, `##`).
   - `KEY: VALUE` lines become `KEY=VALUE` lines.
   - `[[Variable]]` Komodo references are stripped.
   - Regular comment lines are preserved.

2. **Value resolution**: For each key, the first non-empty value wins from this priority chain:
   1. **Existing .env values** - preserves values the user already set, so they are not overwritten on rebuild.
   2. **Override values** - from `scripts/base-testing.env` and `scripts/.env` (scripts/.env takes priority).
   3. **Raw value** from komodo.env (with `[[...]]` refs stripped).
   4. **Container testing defaults** - from each container's _testing.env_ file.
   5. **`_VERSION` fallback** - keys ending in `_VERSION` with no value default to `latest`.

3. **Password generation**: Keys ending in `_PASSWORD` or `_PASS` whose resolved value is empty get a random 16-character alphanumeric password generated via Python's `secrets` module.

4. **Deduplication**: The first occurrence of each key is kept. Subsequent occurrences are commented out with `# `. Duplicate `_PASSWORD`/`_PASS` keys use the same password value as the first occurrence.

---

## README.md
### File Structure
#### Containers (stack-README.md)

```markdown
# Initial Deployment Requirements
## <imageName> Requirements
<content from imageName stack-README.md>
```

#### Stacks

```markdown
# <stackName> Overview
<information about the stack>

# Initial Deployment Requirements
## <imageName> Requirements
<content from imageName stack-README.md>

## <imageName> Requirements
<content from imageName stack-README.md>
```

### How file is generated

1. **Starting point**: If an existing stack _README.md_ exists, it is used as the starting point. Otherwise, _base-README.md_ is used (with `<stackName>` substituted).

2. **Source collection**: The _base-README.md_ (always) and each container's _stack-README.md_ are parsed into section trees. Base sections are treated as the first source, followed by container sections in discovery order.

3. **Shared vs. stack-only H1s**: Any H1 heading that appears in _base-README.md_ or ANY container's _stack-README.md_ is considered "shared". H1 headings that exist only in the stack's existing _README.md_ are considered "stack-only" (manually added by the user).

4. **Merge-level deduplication**: When two containers contribute identical lines under the same heading, only unique lines are kept. Blank lines are always preserved for formatting.

5. **H1 ordering**: The final README enforces this order for top-level headings:
   1. **Stack-only H1s** - preserved as-is from the existing README, in their original order.
   2. **Base H1s** - in the order they appear in _base-README.md_, rebuilt from all sources (base + containers). Only included if at least one container contributes to that heading; base-only H1s (where no container references the heading) are dropped.
   3. **Container-only H1s** - H1s unique to containers (not in base), rebuilt from all sources, in container discovery order.

6. **Shared H1 rebuilding**: Shared H1 sections are rebuilt entirely from base + container content each run. This enables automatic cleanup when a container is removed from a stack, and ensures global base content stays up to date. Base H1s that no container references are excluded entirely, so scaffolding sections like "Create and Setup Required Folders" only appear when containers actually need them.

7. **Empty section pruning**: After all merging, any sections that have no content (all blank lines) and no children (after their children are also pruned) are removed from the output.

8. **Output**: The section tree is serialized back to markdown and written to the stack's _README.md_.

### Important behavior notes

- Stack-only H1 headings (manually created) persist across rebuilds.
- Container _stack-README.md_ files should ideally use H1 headings that exist in _base-README.md_. If a container introduces a unique H1 and is later removed from the stack, that H1 will not be cleaned up on the next build since it is would no longer be treated as shared.
- _base-README.md_ is always applied as a source, so global README content can be updated centrally and will propagate to all stacks on the next build.
