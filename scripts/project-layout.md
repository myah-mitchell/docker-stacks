# Project Layout

## Folder layout
The folder layout looks like the following with each sequential indent being another folder deep. `<>` are used to indicate values that would be replaced depending on the container or stack and that multiple entries could exist. Any items that are folders will be in **bold**.

docker-stacks
* **containers** _Folder containing all container sources_
  * **\<imageName>** - _Folder name should be the image name_
    * **config** - _Folder for any config needed to run container_
    * compose.yaml - _This should only contain a single image, though there could be multiple containers using this image if there are different uses of the image (e.g. agent vs server)_
    * komodo.env - _Only contains items specific to this container_
    * README.md - _Only contains items specific to this container_
  * base-komodo.env - _All sections in this file should be included in every stacks komodo.env_
  * base-README.md - _All sections in this file should be included in every stacks README.md_
* **stacks** - _Folder containing all stacks_
  * **\<stackName>** - _Friendly name of stack_
    * **\<imageName>-config** - _Any containers that need config outside of the compose file will store that config in a folder named **\<imageName>-config**_
    * compose.yaml - _This is the compose file that will control the stack_
    * komodo.env - _This file is created by build.sh_
    * README.md - _This file is created by build.sh_
* **scripts**
    * project-layout.md - _This file_
    * build.sh - _Script that will build/update the komodo.env, README.md, and testing .env files for each stack.
* .gitignore - _gitignore file ensuring no env or live data files are ever commited to the project_

## komodo.env 
### File Structure

The Komodo.env file will use a markdown like format with markdown headings following by key:value parings. The following code snippet has an example with `<>` used to indicate values that would be replaced depending on the container or stack. Some of the values may be _[[\<Komodo Key Name]]_ for referencing Komodo variables

```env
################################################################
# <notes>
################################################################

# Project Specific Settings

# Stack Specific Settings
## <container 1>
<key>: <value>
<key>: <value>

## <container 2>
<key>: <value>
<key>: <value>

# Global Settings
## <heading 1>
<key>: <value>
<key>: <value>

## <heading 2>
<key>: <value>
<key>: <value>
```

### How file is generated

The _build.sh_ will use _base-komodo.env_ as the starting file to build the stack specific _komodo.env_. The script will then merge all sections from each containers local _komodo.env_ into the stacks _komodo.env_. The merging will happen at each heading so the same headings will be combinded and any extra headings will be appended.

## README.md 
### File Structure
#### Containers

```markdown
# Initial Deployment Requirements
## <imageName> Requirements
<content from imageName README.md>

## <imageName> Requirements
<content from imageName README.md>
```

#### Stacks

```markdown
# <stackName> Overview
<information about the stack>

# Initial Deployment Requirements
## <imageName> Requirements
<content from imageName README.md>

## <imageName> Requirements
<content from imageName README.md>
```

### How file is generated

The _build.sh_ will use the existing stacks _README.md_ as the starting file to update with any changes. The script will then merge all sections from each containers local _README.md_ into the stacks _README.md_. The merging will happen at each heading so the same headings will be combinded and any extra headings will be appended. 

Any top level `#` headings that only exist in the stacks _README.md_ will be maintained however, for any top level headings where any of the containers local _README.md_ also had an identical heading, any text that no longer exists in all the included containers will be removed.

The idea being if you manually create a new top level heading, it will persist. However any top level headings created/updated by the merges will self-cleanup any removals and will be completely replaced each time.
