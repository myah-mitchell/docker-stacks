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
    * setup.yaml - _Optional host setup: folders, seeded config files, and firewall ports. Rendered into stack README.md files and applied by the ansible `stacks` role_
    * testing.env - _Container-specific non-sensitive testing defaults in KEY: VALUE format_
* **stacks** - _Folder containing all stacks_
  * **\<stackName>** - _Friendly name of stack_
    * **config** - _Any containers that need config outside of the compose file will store that config in a folder named **config**_
    * compose.yaml - _This is the compose file that will control the stack. May use `include` to reference other stack compose files._
    * komodo.env - _This file is created by build.py_
    * .env - _This file is created by build.py (gitignored, for local testing)_
    * README.md - _This file is created by build.py_
    * setup.yaml - _This file is created by build.py from the setup.yaml of each container the stack uses. Read by the ansible `stacks` role_
* **scripts**
    * project-layout.md - _This file_
    * build.py - _Script that will build/update the komodo.env, README.md, setup.yaml, and testing .env files for each stack._
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
4. For each extends block, also extract the `service:` value (with leading `.` stripped) to build a service map used for tag-based section filtering.
5. Containers from included files appear first, followed by the current file's containers.
6. Each container name is returned only once, in order of first appearance.

### Tag-Based Conditional Sections

Headings in container files (_komodo.env_, _testing.env_, _stack-README.md_) can include tags in square brackets to conditionally include/exclude sections based on which service variant the stack uses.

Syntax:

```markdown
## Heading Text [service-name]
## Multi-variant Heading [service-a, service-b]
## Always Included Heading
```

Rules:
- Tags appear at the end of any heading line in square brackets.
- Multiple tags are comma-separated.
- Headings with no tags are always included.
- Tags are matched against the `service:` names from the stack's compose.yaml (with leading `.` stripped). For example, if a stack references `service: .crowdsec-server`, the active tag is `crowdsec-server`.
- When a heading is filtered out, all its sub-headings are also removed regardless of their own tags.
- Tags are stripped from headings in the generated output files.
- This works across all three file types: markdown (`## Heading [tag]`), komodo (`#== Heading [tag]`), and testing.env (`#== Heading [tag]`).

Example of a container with server/agent variants:

```ini
#== Crowdsec Common Settings
CROWDSEC_IMAGE: crowdsecurity/crowdsec

#== Crowdsec Server [crowdsec-server]
CROWDSEC_LAPI_KEY: ...

#== Crowdsec Agent [crowdsec-agent]
CROWDSEC_AGENT_PASSWORD: ...
```
A stack using `service: .crowdsec-server` would include "Common Settings" and "Server" sections, but exclude "Agent".

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
   5. `_VERSION` fallback: keys ending in `_VERSION` with no value default to `latest`.

3. **Password/secret generation**: Keys ending in `_PASSWORD` or `_PASS` whose resolved value is empty get a random 48-character alphanumeric value. Keys ending in `_PASSKEY`, `_SECRET_KEY`, or `_LAPI_KEY` get a random 96-character alphanumeric value. Both generated via Python's `secrets` module. This deliberately does not cover every `*_KEY`/`*_SECRET`/`*_TOKEN`-shaped name. `*_API_KEY`/`*_API_TOKEN`/`*_LICENSE_KEY` (issued by an external service; a random value would silently look filled in but not work) and `*_KEY_ENCRYPTION` (must be a base64-encoded 32-byte key, not plain alphanumeric, per `SEMAPHORE_ACCESS_KEY_ENCRYPTION`'s own stack-README.md) stay blank as documented manual steps instead. See `DB_PASSWORD_SUFFIXES`/`OTHER_SECRET_SUFFIXES` in `build.py` for the exact lists.

4. **Deduplication**: The first occurrence of each key is kept. Subsequent occurrences are commented out with `# `. Duplicate keys use the same generated value as the first occurrence.

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

## setup.yaml

A container's _setup.yaml_ lists what a host needs before that container's first deploy. It is the single source for those steps: build.py renders it into the manual commands in every stack README that uses the container, and the ansible `stacks` role applies it to a host.

```yaml
folders:
  - path: mailrise-secrets
    owner: 101000
    group: 101000
    mode: "0700"
files:
  - path: mailrise-secrets/mailrise.conf
    source: containers/mailrise/config/mailrise.conf.example
    owner: 101000
    group: 101000
    mode: "0600"
firewall:
  - port: 8025
    proto: tcp
    allow_from: internal
    comment: Mailrise SMTP
```

| Key | Meaning |
| --- | --- |
| `folders[].path` | Folder under the root below, inside `<projectName>/`. Created if missing, never recursively re-owned |
| `folders[].root` | Optional, `volumes` (the default) for `${DOCKER_VOLUMES}` or `logs` for `${DOCKER_LOGS}` |
| `folders[].owner`, `group` | Numeric host IDs. A container's own UID 1000 is `101000` under userns-remap |
| `folders[].mode` | Optional, a quoted octal string such as `"0700"` |
| `files[].path` | File under `${DOCKER_VOLUMES}/<projectName>/`, inside one of the `volumes` folders above |
| `files[].source` | Repo-relative file to copy there. Copied only when the destination does not exist yet |
| `files[].owner`, `group`, `mode` | As for folders, with `mode` optional |
| `firewall[].port`, `proto` | Port number, and `tcp` or `udp` |
| `firewall[].allow_from` | `internal`, scoped to the internal subnet, or `any` |
| `firewall[].comment` | UFW rule comment |
| `services` | Optional on any entry, a list of service names. The entry applies only to stacks that run one of them, such as `redis-public` but not `redis-replica` |

build.py rejects unknown keys, missing keys, paths containing `..`, and sources that do not exist. It needs PyYAML to read these files.

In a stack README, the rendered commands go under `# Create and Setup Required Folders`, as `## Create needed folders for <imageName>` and `## Open the firewall for <imageName>`. A container's own _stack-README.md_ can use either heading to add prose, which follows the generated commands.

Each stack's own logs and volumes folders come from _base-README.md_, and the `stacks` role creates those too.

build.py also writes a stack's _setup.yaml_, next to its _README.md_. It holds the stack's project name and the entries from every container the stack uses, following `include`, with `services` already applied and dropped. Entries two containers share, such as `postgres-data`, appear once, and build.py stops if the two disagree on owner, group, mode, or source.

### What a stack provides and needs

Each container also says what it offers and what it expects to find, in the same _setup.yaml_:

```yaml
needs_stack:
  - name: socket-proxy
    services: [dozzle, dozzle-agent]
needs_host:
  - name: traefik
    services: [dozzle-server]
```

| Key | Meaning |
| --- | --- |
| `provides` | What this container is, when that is not its directory name, or how far it can be reached from |
| `needs_stack` | A service that has to be in the same stack, such as the Postgres an application connects to by container name |
| `needs_host` | A service another stack on the same host may answer for, such as the Traefik whose router labels it sets |
| `needs_fleet` | A service anywhere in the fleet, such as the vmauth a vmagent writes through |

A container provides its own directory name without saying so, which is what keeps the vocabulary to names that exist: build.py rejects a need naming a service no container provides. A `provides` entry may name another container, which says this variant stands in for it, as ferretdb's postgres-documentdb does for `postgres`. Each entry takes the same optional `services` list as the rest of the file, so a variant can differ from its container.

The three needs differ in where the answer may come from, and they are not interchangeable. Another stack on the host having a `postgres` says nothing about whether this stack can reach it, so an application's database is `needs_stack` and build.py resolves it there. What survives a `needs_stack` is a container the stack forgot, and the build fails by name rather than leaving it to ansible.

#### Reach

A `provides` entry carries a `reach`, which defaults to `stack` and follows the networks the container sits on:

| Reach | Where it can be reached from | Example |
| --- | --- | --- |
| `stack` | Its own stack only | A postgres on `${PROJECT_NAME}_backend`, which is `internal: true` |
| `host` | Any stack on the same host | A traefik on the external `proxy` network |
| `fleet` | Anywhere | The `redis-public` that publishes 6379, or a vmauth published through Traefik |

A need must name something provided at its own reach or wider, so `needs_host: postgres` is an error while nothing publishes a Postgres past its own stack. The generated stack file lists only what reaches past the stack, which is what makes matching a neighbour's `needs_host` against it sound: a stack's own Postgres is not in there and can never be mistaken for one another stack could open a socket to.

Reach is declared rather than derived, so build.py checks each declaration against the compose file it describes:

- A `needs_stack` is only answered by a container the needing one shares a network with. A consumer on `proxy` and a Postgres on `backend` sit in the same stack and satisfy the name check, but cannot open a socket, and the build says so.
- `reach: host` wants a network the stack declares `external`, or a port published to the host. Those are the two ways another stack's containers are on the same wire.
- `reach: fleet` wants a published port or a Traefik router, which are the only ways in from another host.

Working out a service's networks means following `extends` through the container file, and a variant written that way **adds** to what it extends rather than replacing it. `.authentik-server` declares `networks: [proxy]` on top of `.authentik`'s `[frontend, backend]` and ends up on all three, which is the only reason it can reach its Postgres. Dropping a network from a base variant on the assumption that the child re-declares what it needs will break every variant under it.

Declare every container a container genuinely cannot run without, not only the ones that might live elsewhere. Almost all of them cancel inside their own stack and cost nothing, and that is the point: a new stack that forgets a container it depends on fails the build by name instead of deploying and half working. Its own `depends_on` list is the place to read them off. Leave out what only degrades: dozzle-server works with no agents, and a Traefik works with no Authentik, which is what traefik-bootstrap relies on.

build.py rolls all four up to the stack, then cancels each need the stack satisfies itself, at any reach, because anything in the stack is reachable from inside it. A stack running both halves of something asks for nothing, which is why victoriametrics-server carries the same host agents as system-agent without being held back by them, and traefik-server runs traefik-kop against its own Redis. The generated _setup.yaml_ records the container list beside the result, so a wrong rollup shows in the diff:

```yaml
project: "traefik"
containers: ["error-pages", "logrotate", "redis", "socket-proxy", "traefik", "traefik-kop"]
needs_host: []
needs_fleet: []
provides:
  - name: "kop-redis"
    reach: "fleet"
  - name: "traefik"
    reach: "host"
```

The `stacks` role uses what is left. On a run with `docker_stacks_bootstrap` true it drops every stack still listing a `needs_fleet` service, then fills any `needs_host` nothing left provides from `docker_stacks_standins`, which maps `traefik` to _traefik-bootstrap_. On any run, a `needs_host` still unmet at the end stops the role, because the host's stack list cannot be right.

The `stacks` role reads only this generated file, from a docker-stacks checkout on the control node. CI fails when it is out of date, so commit it together with the container change that produced it.
