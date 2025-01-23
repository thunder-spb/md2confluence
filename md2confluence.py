import os
import sys
import re
import argparse
import codecs
import logging
import markdown
import textwrap
from html import unescape as html_unescape
from confluence import Confluence

# logger configuration
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s] %(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)


def sls(s):
    """Stupidly simple leading white space remover :)
    This is required to compare page contents in confluence and
    generated one from README.md to make a desicion about page update.

    Keyword arguments:
        s {str} -- Input string or multiline string

    Return:
        {str} clear string without leading whitespaces

    sls abbreviation is for strip_leading_spaces :)
    """
    return s


def convert_code_block(html):
    """
    Convert html code blocks to Confluence macros

    Arguments:
      html {str} -- input html

    Return:
      Modified html string
    """
    code_blocks = re.findall(r"<pre><code.*?>.*?</code></pre>", html, re.DOTALL)
    if code_blocks:
        for tag in code_blocks:
            code_parsed = re.search(r"<pre><code(.*?)>(.*?)</code></pre>", tag, re.DOTALL)
            code = code_parsed.group(2).strip()
            code_language = re.search(r".*class=\"language-(.*)\".*", code_parsed.group(1), re.DOTALL)
            if code_language is not None:
                code_language = code_language.group(1)
            else:
                code_language = "java"

            """Unescape code after markdown since Confluence macro renders this as is"""

            conf_macro = """
                <ac:structured-macro ac:name="code" ac:schema-version="1">
                  <ac:parameter ac:name="language">{code_language}</ac:parameter>
                  <ac:parameter ac:name="theme">Midnight</ac:parameter>
                  <ac:parameter ac:name="linenumbers">true</ac:parameter>
                  <ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>
                </ac:structured-macro>
                """.format(code=html_unescape(code), code_language=code_language)
            html = html.replace(tag, conf_macro)

    return html


def convert_admonition_block(html):
    # html = '''
    # <div class="admonition note">
    # <p class="admonition-title">my title</p>
    # <p>You should note that the title will be automatically capitalized.</p>
    # </div>
    # '''
    note_block = textwrap.dedent(
    """
        <ac:structured-macro ac:name="{type}" ac:schema-version="1">
        <ac:parameter ac:name="title">{title}</ac:parameter>
        <ac:rich-text-body>
        <p>{body}</p>
        </ac:rich-text-body>
        </ac:structured-macro>
    """
    )
    admonition_blocks = re.findall(r'<div class="admonition.*?<p.*?</p>.</div>', html, re.DOTALL)
    if (admonition_blocks):
        RE_COMPILE = re.compile(
        r'<div class="admonition(?: (?P<type>info|danger|important|note))?"(?:.*?)>\n(?:<p class="admonition-title">(?P<title>.*?)</p>\n)?<p>(?P<body>.*?)</p>\n</div>',
        re.DOTALL)
        for admonition_block in admonition_blocks:
            admonition = RE_COMPILE.search(admonition_block).groupdict()
            html = html.replace(admonition_block, note_block.format(type=admonition.get("type"), title=admonition.get("title"), body=admonition.get("body")))
    return html


def create_toc(html):
    """
    Create toc confluence macro

    Arguments:
      html {str} -- html string

    Return:
      Modified html string
    """

    toc_tag = textwrap.dedent(
        """
  <h1>Table of Contents</h1>
  <p>
  <ac:structured-macro ac:name="toc">
    <ac:parameter ac:name="printable">true</ac:parameter>
    <ac:parameter ac:name="style">disc</ac:parameter>
    <ac:parameter ac:name="maxLevel">7</ac:parameter>
    <ac:parameter ac:name="minLevel">1</ac:parameter>
    <ac:parameter ac:name="type">list</ac:parameter>
    <ac:parameter ac:name="outline">clear</ac:parameter>
    <ac:parameter ac:name="include">.*</ac:parameter>
    <ac:parameter ac:name="exclude">^(Authors|Table of Contents|This is Important!)$</ac:parameter>
  </ac:structured-macro>
  </p>"""
    )

    html = """<ac:layout>
    <ac:layout-section ac:type="two_right_sidebar">
      <ac:layout-cell>
        {content}
      </ac:layout-cell>
      <ac:layout-cell>
        {toc}
      </ac:layout-cell>
    </ac:layout-section>
  </ac:layout>
  """.format(content=html, toc=toc_tag)

    return html


def parse_args():
    """
    ArgumentParser to parse arguments and options

    Return:
      Parsed Arguments
    """
    parser = argparse.ArgumentParser(
        description="Converts and deploys a markdown post to Confluence"
    )

    parser.add_argument(
        "-m",
        "--markdown-file",
        dest="markdown_file",
        required=True,
        help="Full path of the markdown file to convert and upload",
    )
    parser.add_argument(
        "-s",
        "--space",
        dest="space",
        default=os.getenv("CONFLUENCE_SPACE"),
        help="Confluence Space key, if $CONFLUENCE_SPACE not set. Unnecessary if '--publish' is not set.",
    )
    parser.add_argument(
        "-u",
        "--username",
        dest="username",
        default=os.getenv("CONFLUENCE_USR"),
        help="Confluence username, if $CONFLUENCE_USR not set. Unnecessary if '--publish' is not set. For API token, use your full email address.",
    )
    parser.add_argument(
        "-p",
        "--password",
        dest="password",
        default=os.getenv("CONFLUENCE_PSW"),
        help="Confluence password or API token, if $CONFLUENCE_PSW not set. Unnecessary if '--publish' is not set.",
    )
    parser.add_argument(
        "--url",
        dest="url",
        default=os.getenv("CONFLUENCE_URL"),
        help="Confluence URL, if $CONFLUENCE_URL not set. Unnecessary if '--publish' is not set. For cloud instances, use following pattern 'https://mycompanyname.atlassian.net/wiki'",
    )
    parser.add_argument(
        "-a",
        "--ancestor-id",
        dest="ancestor_id",
        help="Confluence Parent page ID under which page will be created",
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        dest="loglevel",
        default="INFO",
        help="Set the log verbosity",
    )
    parser.add_argument(
        "--title",
        dest="title",
        help="Optional. Set page title, otherwise will be taken from first existing header in markdown file",
    )
    parser.add_argument(
        "--toc",
        action="store_true",
        default=False,
        help="Optional. Generate Table of Contents block. Default is False",
    )
    parser.add_argument(
        "--no-notice",
        action="store_true",
        dest="no_notice",
        default=False,
        help="Optional. Skip generation of the notice block about autoupdate. Generated by default",
    )
    parser.add_argument(
        "-o",
        "--out-file",
        dest="out_file",
        help="Optional. Set file name to save parsed content",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=False,
        help="Publish to Confluence. Require credentials to be defined via --space, --username, --password, --url or corresponding environment variables (see --help)",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        dest="force_update",
        default=False,
        help="Force update page, even if not changed. Require --publish argument. Also, require credentials to be defined via --space, --username, --password, --url or corresponding environment variables (see --help)",
    )
    parser.add_argument(
        "--job-url",
        dest="job_url",
        default=os.getenv("JOB_URL"),
        help="Optional. Full link to Jenkins Job. Could be provided via environment variable 'JOB_URL'",
    )
    parser.add_argument(
        "--repo-url",
        dest="repo_url",
        help="Optional. Full link to Git Repository"
    )

    args = parser.parse_args()

    log.setLevel(getattr(logging, args.loglevel.upper(), None))

    is_creds_error = False

    if args.publish:
        if not args.url:
            log.error(
                "Please provide a valid Confluence URL via '--url' or environment variable 'CONFLUENCE_URL', e.g. 'https://my.confluence.local/wiki'"
            )
            is_creds_error = True

        if not args.space:
            log.error(
                "Please provide a valid Confluence Space key via '--space' or environment variable 'CONFLUENCE_SPACE'"
            )
            is_creds_error = True

        if not args.username or not args.password:
            log.error(
                "Please provide a valid Username and Password via arguments or environment variables. See help."
            )
            is_creds_error = True
    else:
        if args.force_update:
            log.warning(
                "Force update (--force-update) argument passed, while --publish is not."
            )
        log.info(
            "Provided Markdown file will be only rendered and wrote to stdout. No push to Confluence will be performed."
        )

    if is_creds_error:
        log.warning(
            "Some of the required credentials were not defined, therefore forcing render-only mode."
        )
        args.publish = False

    if not os.path.exists(args.markdown_file):
        log.error("Markdown file '%s' does not exist.", args.markdown_file)
        sys.exit(1)

    return args


if __name__ == "__main__":

    log.info("------------------------------------------")
    log.info("Markdown to Confluence publisher tool")
    log.info("------------------------------------------\n\n")

    ARGS = parse_args()

    log.info("Markdown file:\t%s", ARGS.markdown_file)
    if ARGS.publish:
        log.info("Space Key:\t\t%s", ARGS.space)

    """
  Get title from Markdown file if not provided via cli argument
  """
    title = ARGS.title
    if not title:
        with open(ARGS.markdown_file, "r") as mdfile:
            for line in mdfile:
                if line.strip().startswith("#"):
                    title = line.lstrip("#").strip()
                    break

    log.info("Title:\t\t%s", title)

    with codecs.open(ARGS.markdown_file, "r", "utf-8") as mdfile:
        html = markdown.markdown(
            mdfile.read(),
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
                "markdown.extensions.admonition",
            ],
        )
    if not ARGS.title:
        html = "\n".join(html.split("\n")[1:])

    if not title:
        log.error(
            "Can not determine title for this page. Please fix README.md or provide one via --title argument."
        )
        sys.exit(1)

    links_block = ""

    if ARGS.job_url:
        links_block = (
            links_block
            + textwrap.dedent(
                """
    <p><strong>Jenkins job:</strong> <a href='{job_url}'>{job_url}</a></p>
    """
            ).format(job_url=ARGS.job_url)
        )
    if ARGS.repo_url:
        links_block = (
            links_block
            + textwrap.dedent(
                """
    <p><strong>Repository:</strong> <a href='{repo_url}'>{repo_url}</a></p>
    """
            ).format(repo_url=ARGS.repo_url)
        )

    if ARGS.no_notice == False:
        note_block = textwrap.dedent(
            """<ac:structured-macro ac:name="warning" ac:schema-version="1">
            <ac:parameter ac:name="title">This is Important!</ac:parameter>
            <ac:rich-text-body>
            <p>This page has been created automatically via Markdown Publisher Script. If this script is a part of any automation, any manual change will be removed on next run.</p>
            {links}
            </ac:rich-text-body>
        </ac:structured-macro>
        """
        ).format(links=links_block)

        html = note_block + html

    if ARGS.toc:
        html = create_toc(html)

    html = sls(convert_code_block(html))
    html = sls(convert_admonition_block(html))

    if ARGS.out_file:
        f = open(ARGS.out_file, "w")
        f.write(html)
        f.close()
        log.info("Writing rendered Markdown to file '%s' succeed." % ARGS.out_file)

    if not ARGS.publish:
        log.info("Here is rendered Markdown file:")
        print(html)
    else:
        confluence = Confluence(
            api_url=ARGS.url,
            username=ARGS.username,
            password=ARGS.password,
            loglevel=ARGS.loglevel,
        )

        page = confluence.exists(
            title=title, ancestor_id=ARGS.ancestor_id, space=ARGS.space
        )

        if page:
            if ARGS.force_update:
                log.info("Forcing page update since '--force-update' flag passed")
                has_changes = True
            else:
                has_changes = confluence.compare_content(
                    post_id=page["id"], content=html
                )

            if has_changes:
                log.info(
                    "Found changes in '%s' content against the page, published in Confluence."
                    % ARGS.markdown_file
                )
                confluence.update(
                    page["id"],
                    content=html,
                    title=title,
                    space=ARGS.space,
                    ancestor_id=ARGS.ancestor_id,
                    page=page,
                )
            else:
                log.info(
                    "No changes detected. Page update skipped. To force page update, use '--force-update' flag"
                )
        else:
            confluence.create(
                content=html,
                title=title,
                space=ARGS.space,
                ancestor_id=ARGS.ancestor_id,
            )
