import logging
import json
import requests
import os
import re
import sys

from urllib.parse import urljoin

API_HEADERS = {
    "User-Agent": "md2confluence",
}


class MissingArgumentException(Exception):
    def __init__(self, arg):
        self.message = "Missing required argument: {}".format(arg)


class Confluence:
    def __init__(
        self,
        api_url=None,
        username=None,
        password=None,
        headers=None,
        loglevel="info",
        _client=None,
    ):
        """Creates a new Confluence API client.

        Keyword arguments:
            api_url {str} -- The URL to the Confluence API root (e.g. https://my.confluence.local/wiki or https://my.confluence.local/wiki/rest/api)
            username {str} -- The Confluence service account username
            password {str} -- The Confluence service account password
            headers {list(str)} -- The HTTP headers which will be set for all requests
            loglevel {Logger Loglevel} -- Loglevel from logger class
        """

        self.log = logging.getLogger("confluence")
        self.loglevel = loglevel.upper()
        self.log.setLevel(getattr(logging, self.loglevel, None))


        # A common gotcha will be given a URL that doesn't end with a /, so we
        # can account for this
        if not api_url.endswith("/"):
            api_url = api_url + "/"
        if not api_url.endswith("/rest/api/"):
            api_url = urljoin(api_url, "rest/api/")
        self.api_url = api_url

        self.log.info("API URL:\t\t%s" % self.api_url)

        self.username = username
        self.password = password

        if _client is None:
            _client = requests.Session()

        self._session = _client
        self._session.auth = (self.username, self.password)
        for header in headers or []:
            try:
                name, value = header.split(":", 1)
            except ValueError:
                name, value = header, ""
            self._session.headers[name] = value.lstrip()

    def _require_kwargs(self, kwargs):
        """Ensures that certain kwargs have been provided

        Arguments:
            kwargs {dict} -- The dict of required kwargs
        """
        missing = []
        for k, v in kwargs.items():
            if not v:
                missing.append(k)
        if missing:
            raise MissingArgumentException(missing)

    def _request(self, method="GET", path="", params=None, data=None, headers=None):

        url = urljoin(self.api_url, path)

        self.log.debug(
            """API Call:
            {method} {url}:
            Params: {params}
            Data: {data}""".format(
                method=method, url=url, params=params, data=data
            )
        )

        if not headers:
            headers = {}
        headers.update(API_HEADERS)

        if data:
            headers.update({"Content-Type": "application/json"})

        response = self._session.request(
            method=method, url=url, params=params, json=data, headers=headers
        )

        if not response.ok:
            try:
                response_err = json.loads(response.text)
            except Exception as e:
                self.log.error("Can not parse response as JSON")
                response_err = {'message': response.text}

            self.log.error(
                "{method} {url}: {status_code} - {reason}".format(
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    reason=response_err.get("message"),
                )
            )
            self.log.debug(
                """Params: {params}
            Data: {data}""".format(
                    params=params, data=data
                )
            )
            sys.exit(1)
            return {}
        # Will probably want to be more robust here, but this should work for now
        return response.json()

    def get(self, path=None, params=None):
        return self._request(method="GET", path=path, params=params)

    def post(self, path=None, params=None, data=None, files=None):
        return self._request(method="POST", path=path, params=params, data=data)

    def put(self, path=None, params=None, data=None):
        return self._request(method="PUT", path=path, params=params, data=data)

    def exists(self, space=None, title=None, ancestor_id=None):
        """Returns the Confluence page that matches the provided metdata, if it exists.

        Specifically, this leverages a Confluence Query Language (CQL) query
        against the Confluence API. We assume that each slug is unique, at
        least to the provided space/ancestor_id.

        Keyword arguments:
            space {str} -- The Confluence space to use for filtering posts
            title {str} -- The page title
            ancestor_id {str} -- The ID of the parent page
        """
        self._require_kwargs({"title": title})

        self.log.debug("Getting page info")

        cql_args = []
        if title:
            cql_args.append("title={!r}".format(title))
        if ancestor_id:
            cql_args.append("ancestor={}".format(ancestor_id))
        if space:
            cql_args.append("space={!r}".format(space))

        self.log.debug("CQL params: %s" % cql_args)

        cql = " and ".join(cql_args)

        params = {"expand": "version", "cql": cql}
        response = self.get(path="content/search", params=params)

        if not response.get("size", None):
            self.log.info("We didn't find any page satisfied our query. Assuming this is new page.")
            return None

        return response["results"][0]

    def sls(self, s):
        """Stupidly simple leading white space remover :)
        This is required to compare page contents in confluence and
        generated one from README.md to make a desicion about page update.

        sls abbreviation is for strip_leading_spaces :)
        """
        return "\n".join([l.strip() for l in s.splitlines()])

    def get_page_contents(self, post_id=None):
        """Get page contents

        Arguments:
            post_id {str} -- The ID of the Confluence post
        """
        self._require_kwargs({"post_id": post_id})

        path = "content/{}?expand=body.storage".format(post_id)
        response = self.get(path=path)

        return response.get("body", {}).get("storage", {}).get("value", "")

    def compare_content(self, post_id=None, content=None):
        """Compare our content with content in Confluence

        Keyword arguments:
            post_id {str} - Existing post ID in Confluence
            content {str} - Content to compare to

        Return:
            {bool} Comparison results, true if different, false is the same
        """
        self._require_kwargs({"post_id": post_id, "content": content})
        # item to find and cleanup -- 'ac:macro-id="bb96c594-fad4-4efd-86c4-5754db6ff55d"'
        """Parse with Confluence and cleanup our page version"""
        html = self.sls(self._convert_html_to_storage(content))
        macro_ids = re.findall(r" ac:macro-id=\".*?\"", html, re.DOTALL)
        if macro_ids:
            for macro_id in macro_ids:
                html = html.replace(macro_id, "")
        else:
            self.log.warning("No macro IDs found in our converted xhtml!")

        """Get page and cleanup page from Confluence.
        Note, no page existance checks!
        """
        confluence_page = self.sls(
            self._convert_html_to_storage(self.get_page_contents(post_id))
        )
        macro_ids = re.findall(r" ac:macro-id=\".*?\"", confluence_page, re.DOTALL)
        if macro_ids:
            for macro_id in macro_ids:
                confluence_page = confluence_page.replace(macro_id, "")
        else:
            self.log.warning("No macro IDs found in Confluence page!")

        """This block is only for easier debug"""
        if self.loglevel == "DEBUG":
            self.log.debug("Writing Confluence page content into 'page_confluence.html'")
            f = open("page_confluence.html", "w")
            f.write(confluence_page)
            f.close()

            self.log.debug("Writing Generated content into 'page_generated.html'")
            f = open("page_generated.html", "w")
            f.write(html)
            f.close()

        return html != confluence_page

    def _convert_html_to_storage(self, html=None):
        """Dummy conversion from generated xhtml to xhtml via Confluence API call for
        proper comparison to have same layout and structure as Confluence save post/page contents in database.
        So, we're converting from type storage to same type :)

        Also, Confluence generates macro IDs on save for any macro used in post body. We'll clean up
        them, because they're different each time

        Keyword arguments:
            html {str} -- The HTML content to parse within Confluence API

        Return:
            {str} -- Parsed xHTML content
        """
        self._require_kwargs({"html": html})
        data = {"value": html, "representation": "storage"}
        converted = self.post(path="contentbody/convert/storage", data=data)
        return converted.get("value", "")

    def _create_page_payload(
        self, content=None, title=None, ancestor_id=None, space=None, type="page"
    ):
        """Generate JSON payload for API call

        Keyword Arguments:
            content {str} -- The HTML content to upload (required)
            space {str} -- The Confluence space where the page should reside
            title {str} -- The page title
            ancestor_id {str} -- The ID of the parent Confluence page

        Return
            {dict} Combined Dict to use in API call
        """
        content = self._convert_html_to_storage(content)
        return {
            "type": type,
            "title": title,
            "space": {"key": space},
            "body": {"storage": {"representation": "storage", "value": content}},
            "ancestors": [{"id": str(ancestor_id)}],
        }

    def create(
        self, content=None, space=None, title=None, ancestor_id=None, type="page"
    ):
        """Creates a new page with the provided content.

        If an ancestor_id is specified, then the page will be created as a
        child of that ancestor page.

        Keyword Arguments:
            content {str} -- The HTML content to upload (required)
            space {str} -- The Confluence space where the page should reside
            title {str} -- The page title
            ancestor_id {str} -- The ID of the parent Confluence page

        Return:
            {bool} Returns boolean representation of result
        """
        self._require_kwargs({"content": content, "title": title, "space": space})

        page = self._create_page_payload(
            content=content,
            title=title,
            ancestor_id=ancestor_id,
            space=space,
            type=type,
        )
        response = self.post(path="content/", data=page)

        if not (response.get("_links", None)):
            self.log.error("Can't get link to page. See errors above.")
            return False
        else:
            page_url = response["_links"]["base"] + response["_links"]["tinyui"]
            self.log.info(
                'Page "{title}" (id {page_id}) created successfully at {url}'.format(
                    title=title, page_id=response.get("id"), url=page_url
                )
            )
            return True

    def update(
        self,
        post_id=None,
        content=None,
        space=None,
        title=None,
        ancestor_id=None,
        page=None,
        type="page",
    ):
        """Updates an existing page with new content.

        This involves updating the attachments stored on Confluence, uploading
        the page content, and finally updating the labels.

        Keyword Arguments:
            post_id {str} -- The ID of the Confluence post
            content {str} -- The page represented in Confluence storage format
            space {str} -- The Confluence space where the page should reside
            title {str} -- The page title
            ancestor_id {str} -- The ID of the parent Confluence page
        Return:
            {bool} Returns boolean representation of result
        """
        self._require_kwargs(
            {"content": content, "title": title, "post_id": post_id, "space": space}
        )

        # Next, we can create the updated page structure
        new_page = self._create_page_payload(
            content=content,
            title=title,
            ancestor_id=ancestor_id,
            space=space,
            type=type,
        )
        # Increment the version number, as required by the Confluence API
        # https://docs.atlassian.com/ConfluenceServer/rest/7.1.0/#api/content-update
        new_version = page["version"]["number"] + 1
        new_page["version"] = {"number": new_version}

        path = "content/{}".format(page["id"])
        response = self.put(path=path, data=new_page)

        if not (response.get("_links", None)):
            self.log.error("Can't get link to page. See errors above.")
            return False
        else:
            page_url = response["_links"]["base"] + response["_links"]["tinyui"]
            self.log.info(
                'Page "{title}" (id {page_id}) updated successfully at {url}'.format(
                    title=title, page_id=post_id, url=page_url
                )
            )
            return True
