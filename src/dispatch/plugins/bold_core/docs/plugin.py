"""
.. module: dispatch.plugins.dispatch_google_docs.plugin
    :platform: Unix
    :copyright: (c) 2019 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
.. moduleauthor:: Kevin Glisson <kglisson@netflix.com>
"""
import logging

from dispatch.common.utils.date import date_to_tz
from dispatch.decorators import apply, counter, timer
from dispatch.plugins.bases import DocumentPlugin
from dispatch.plugins.bold_core.docs.service import create_coda_review, replace_text, add_row
from dispatch.plugins.dispatch_google import docs as google_docs_plugin
from dispatch.plugins.dispatch_google.common import get_service

log = logging.getLogger(__name__)


@apply(timer, exclude=["__init__"])
@apply(counter, exclude=["__init__"])
class BoldDocumentPlugin(DocumentPlugin):
    title = "Bold Docs Plugin - Document Management"
    slug = "bold-docs-document"
    description = "Uses Google docs and Coda to manage document contents."
    version = google_docs_plugin.__version__

    author = "Bold"
    author_url = "https://github.com/netflix/dispatch.git"

    def __init__(self):
        self.scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive",
        ]

    def update(self, document_id: str, **kwargs):
        """Replaces text in document."""
        # TODO escape and use f strings? (kglisson)
        kwargs = {"{{" + k + "}}": v for k, v in kwargs.items()}
        client = get_service("docs", "v1", self.scopes).documents()
        return replace_text(client, document_id, kwargs)

    def create_review(self, document_id: str, **kwargs):
        """Creates the review document."""
        try:
            create_coda_review(document_id, **kwargs)
        except Exception as e:
            log.exception(e)

    def update_review_sheet(self, document_id: str, **kwargs):
        """Creates a row in the review sheet."""
        client = get_service("sheets", "v4", self.scopes).spreadsheets()

        incident = kwargs.get("incident")

        name = incident.name
        priority = incident.incident_priority.name
        type = incident.incident_type.name
        title = incident.title
        description = incident.description
        reported_at = date_to_tz(incident.reported_at)

        try:
            add_row(client=client, document_id=document_id,
                    params=[[name], [title], [priority], [reported_at], [type], [description]])
        except Exception as e:
            log.exception(e)
