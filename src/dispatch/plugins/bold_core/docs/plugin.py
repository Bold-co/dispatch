"""
.. module: dispatch.plugins.dispatch_google_docs.plugin
    :platform: Unix
    :copyright: (c) 2019 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
.. moduleauthor:: Kevin Glisson <kglisson@netflix.com>
"""
import datetime
import logging

from dispatch.common.utils.date import date_diff, date_to_tz
from dispatch.config import INCIDENT_TRACKING_SHEET_RANGE, INCIDENT_TRACKING_SHEET_LEARNED_LESSONS_RANGE, \
    RISK_TRACKING_SHEET_RANGE
from dispatch.decorators import apply, counter, timer
from dispatch.incident.affected_products import describe_products, get_area_info
from dispatch.incident.models import Incident
from dispatch.plugins.bases import DocumentPlugin
from dispatch.plugins.bold_core.docs.service import create_coda_review, replace_text, add_row, split_values
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

        incident: Incident = kwargs.get("incident")
        name = incident.name
        title = incident.title
        try:
            priority = incident.incident_priority.name
            type = incident.incident_type.name
            description = incident.description
            reported_at = date_to_tz(incident.reported_at)
            stable_at = date_to_tz(incident.stable_at)
            events = sorted(incident.events, key=lambda x: x.started_at, reverse=False)
            started_at = date_to_tz(events[0].started_at)
            report_source = incident.report_source
            team = incident.team_name
            product = incident.product
            platform = incident.platform

            owner, area, process, business_line = describe_products(team=team, product=product)

            mttd = date_diff(start_date=events[0].started_at, end_date=incident.reported_at)
            mttr = date_diff(start_date=events[0].started_at, end_date=incident.stable_at)

            add_row(client=client, document_id=document_id,
                    params=[[name], [title], [priority], [started_at],
                            [reported_at], [stable_at], [type], [description],
                            [mttd], [mttr], [report_source],
                            [team], [owner], [area], [process], [business_line], [platform]],
                    range=INCIDENT_TRACKING_SHEET_RANGE)
        except Exception as e:
            log.exception(e)

        try:
            lessons = split_values(set(o.feedback for o in incident.feedback))
            for lesson in lessons:
                add_row(client=client, document_id=document_id,
                        params=[[lesson.feedback], [name], [title]],
                        range=INCIDENT_TRACKING_SHEET_LEARNED_LESSONS_RANGE)
        except Exception as e:
            log.exception(e)

    def update_risk_sheet(self, document_id: str, **kwargs):
        """Creates a row in the risk sheet."""
        client = get_service("sheets", "v4", self.scopes).spreadsheets()

        incident: Incident = kwargs.get("incident")
        name = incident.name

        try:
            current_time = date_to_tz(datetime.datetime.utcnow())
            priority = incident.incident_priority.name
            description = incident.description
            reported_at = date_to_tz(incident.reported_at)
            stable_at = date_to_tz(incident.stable_at) if incident.stable_at else None
            events = sorted(incident.events, key=lambda x: x.started_at, reverse=False)
            started_at = date_to_tz(events[0].started_at) if events and events[0] else None
            closed = "Sí" if incident.status != "Active" else "No"
            team = incident.team_name
            product = incident.product
            platform = incident.platform
            reporter = incident.reporter.individual.email

            owner, area, process, business_line = describe_products(team=team, product=product)

            tr_size = len(incident.tactical_reports)
            tc_size = len(incident.executive_reports)
            causes = ""
            consequences = ""
            next_steps = ""
            if tr_size > 0:
                reports = sorted(incident.tactical_reports, key=lambda report: report.created_at, reverse=True)
                causes = reports[0].details.get("conditions")
                consequences = reports[0].details.get("needs")
            if tc_size > 0:
                reports = sorted(incident.executive_reports, key=lambda report: report.created_at, reverse=True)
                next_steps = reports[0].details.get("next_steps")
                overview = reports[0].details.get("overview")
                consequences = priority + "\n" + consequences + "\n" + overview

            area_info = get_area_info()
            area = str(area_info.get("area", ""))

            add_row(client=client, document_id=document_id,
                    params=[
                        [current_time], [started_at], [reported_at], [closed],
                        [description], [causes], [consequences], [platform],
                        [process], [area], [business_line], [stable_at],
                        [reporter], [], [],
                        [name], [next_steps]],
                    range=RISK_TRACKING_SHEET_RANGE)
        except Exception as e:
            log.exception(e)
