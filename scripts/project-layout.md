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
    * komodo.env - _This file is created by buld.py_
    * README.md - _This file is created by buld.py_
* **scripts**
    * project-layout.md - _This file_
    * buld.py - _Script that will build/update the komodo.env, README.md, and testing .env files for each stack._
* .gitignore - _gitignore file ensuring no env or live data files are ever committed to the project_

## buld.py

Starting from base files (_base-komodo.env_, _base-README.md_) that contain shared/global sections every stack needs.
Merging in each container's individual _komodo.env_ and _README.md_ sections, matching by heading. Same headings get combined; new headings get appended.

This script will loop through all stack folders and read each ones compose.yaml file. It will extract all the enabled `extends` > `file` references to find all the containers to use in building the local stacks files. Each container will only be added once, even if referenced multiple times.

## komodo.env 
### File Structure

The Komodo.env file will use a markdown like format with markdown headings prceeded with a `#` (`#=`, `#==`, etc) followed by key:value parings. The following code snippet has an example with `<>` used to indicate values that would be replaced depending on the container or stack. Some of the values may be _[[\<Komodo Key Name]]_ for referencing Komodo variables

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

The _buld.py_ will use _base-komodo.env_ as the starting file to build the stack specific _komodo.env_. The script will then merge all sections from each containers local _komodo.env_ into the stacks _komodo.env_. The merging will happen at each heading so the same headings will be combined and any extra headings will be appended.

## README.md 
### File Structure
#### Containers

```markdown
# Initial Deployment Requirements
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

The _buld.py_ will use the existing stacks _README.md_ if it exists as the starting file to update with any changes. If a local _README.md_ does not exist, then the _base-README.md_ will be used. The script will then merge all sections from each containers local _README.md_ into the stacks _README.md_. The merging will happen at each heading so the same headings will be combined and any extra headings will be appended. 

Any top level `#` headings that only exist in the stacks _README.md_ will be maintained however, for any top level headings where any of the containers local _README.md_ also had an identical heading, any text that no longer exists in all the included containers will be removed. Node, container _README.md_ should only use H1 headings that are included in the _base-README.md_. If a new H1 was used in the container _README.md_ and then after adding this container to a stack and removing the container, these unique H1's would persist.

The idea being if you manually create a new top level heading, it will persist. However any top level headings created/updated by the merges will self-cleanup any removals and will be completely replaced each time.
