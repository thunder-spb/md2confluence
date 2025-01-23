# Markdown to Confluence

This script can convert Markdown file and publish it to Confluence through REST API

**Warning.** _The search for an existing page is done by title, so if the title has been changed, the page will not be found and a new one will be created!_

# Preparing to run

To run this script, you need to install two libraries:

 * [Markdown](https://python-markdown.github.io/)
 * [requests](https://docs.python-requests.org/en/master/)

These libraries are already listed in the file [requirements.txt](requirements.txt)

It is recommended to install all libraries in Python [Virtualenv](https://docs.python.org/3/tutorial/venv.html)

## Creating virtualenv

Create a Virtualenv with the command

```sh
python3 -m venv venv
```

...and activate

```sh
source ./venv/bin/activate
```

## Installing dependencies

After activating the Virtualenv, install the dependencies from the `requirements.txt` file using `pip`:

```sh
pip install -r requirements.txt
```
The preparation is complete, you can run the script

# Running the script

As usual, help can be obtained by running the script with the `--help` argument.

For convenience when using in CI/CD, some parameters can be set through environment variables. The environment variables and their names are specified in the script help.

## Arguments

| Argument | Abbreviation | Description |
|:-|:-:|-|
| `--markdown-file` | `-m` | Full path to Markdown file |
| `--space` | `-s` | Confluence space key. Can be set through environment variable `CONFLUENCE_SPACE`. Not required if argument `--publish` is given. |
| `--username` | `-u` | Username for authentication in Confluence. This user will be the author of the page. Can be set through environment variable `CONFLUENCE_USR`. Not required if argument `--publish` is given. |
| `--password` | `-p` | Password for authentication in Confluence. Can be set through environment variable `CONFLUENCE_PSW`. Not required if argument `--publish` is given. |
| `--url` | | Confluence address. Can be set through environment variable `CONFLUENCE_URL`. Not required if argument `--publish` is given. |
| `--ancestor-id` | `-a` | (_Optional_) Page ID which will be used as parent for new page |
| `--title` | | (_Optional_) Override title of the page. By default, first found title in Markdown file is used. |
| `--toc` | | (_Optional_) Generate Table of Contents for Markdown file. _**Given without any parameters.**_ |
| `--publish` | | Markdown file will be converted to HTML and written to stdout. _**Given without any parameters.**_ Requires input of `--space`, `--username`, `--password`, `--url` |
| `--force-update` | | Force update of the page in Confluence even if no changes are found. Requires input of `--space`, `--username`, `--password`, `--url`, `--publish` |
| `--out-file` | `-o` | Full path to file, where result of Markdown file conversion will be written |
| `--loglevel` | `-l` | Logging level: INFO, WARN, DEBUG, etc. |
| `--job-url` | | (_Optional_) Link to Jenkins Job, which will be added to notification block about automatic page creation. Can be set through environment variable `JOB_URL`. _This environment variable is automatically set when run from Jenkins_ |
| `--repo-url` | | (_Optional_) Link to repository, which will be added to notification block about automatic page creation. |

# Supported blocks

## Admonition

Usage example:

```
my super text outside admonition

!!! note "my title"
    block 1

    block 2

another super text outside admonition

!!! danger "my title"
    block 1

    block 2
```
