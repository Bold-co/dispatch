"""
.. module: dispatch.plugins.dispatch_jira.plugin
    :platform: Unix
    :copyright: (c) 2019 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
"""

import requests
from jinja2 import Template

from dispatch.decorators import apply, counter, timer
from dispatch.plugins import bold_azure as azure_plugin
from dispatch.plugins.bases import TicketPlugin
from .config import (
    AZURE_DEVOPS_ORGANIZATION,
    AZURE_DEVOPS_PROJECT,
    AZURE_DEVOPS_PAT, AZURE_DEVOPS_PREFIX, AZURE_DEVOPS_AREA
)

AZURE_DEVOPS_URL = f"https://dev.azure.com/{AZURE_DEVOPS_ORGANIZATION}/{AZURE_DEVOPS_PROJECT}/"

ISSUE_SUMMARY_TEMPLATE = """
<div>
 <span style="color:rgb(134, 17, 6);">
     <b>Confidential Information - For Internal Use Only</b>
 </span>
</div>
<br/>
<b>Incident Details</b>
<br/>
Description: {{description}}
<br/>
Type: {{incident_type}}
<br/>
Priority: {{priority}}
<br/>
<br/>
<b>Incident Resources</b>
<br/>
<b><a href="{{conversation_weblink}}">Conversation</a><br/></b>
<b><a href="{{storage_weblink}}">Storage</a><br/></b>
<b><a href="{{conference_weblink}}">Conference</a><br/></b>
<br/>
Incident Commander: <b>{{commander_username}}</b>
<br/>
Incident Reporter: <b>{{reporter}}</b>

"""


@apply(counter, exclude=["__init__"])
@apply(timer, exclude=["__init__"])
class AzureTicketPlugin(TicketPlugin):
    title = "Azure Plugin - Ticket Management"
    slug = "azure-ticket"
    description = "Uses Azure to help manage external tickets."
    version = azure_plugin.__version__

    author = "Bold"
    author_url = "https://github.com/bold/dispatch.git"

    _schema = None

    def create(
        self,
        incident_id: int,
        title: str,
        incident_type: str,
        incident_priority: str,
        commander_email: str,
        reporter_email: str,
        incident_type_plugin_metadata: dict = {},
        db_session=None,
    ):
        """Creates an Azure issue."""
        url = f'{AZURE_DEVOPS_URL}_apis/wit/workitems/$User Story?api-version=5.1'
        data = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": title
            },
            {
                "op": "add",
                "path": "/fields/System.AreaPath",
                "value": AZURE_DEVOPS_AREA
            }
        ]

        response = requests.post(url, json=data,
                                 headers={'Content-Type': 'application/json-patch+json'},
                                 auth=('', AZURE_DEVOPS_PAT)).json()
        incident_id = AZURE_DEVOPS_PREFIX + str(response["id"])
        return {"resource_id": incident_id, "weblink": f"{AZURE_DEVOPS_URL}/_workitems/edit/{response['id']}"}

    def update(
        self,
        ticket_id: str,
        title: str,
        description: str,
        incident_type: str,
        priority: str,
        status: str,
        commander_email: str,
        reporter_email: str,
        conversation_weblink: str,
        document_weblink: str,
        storage_weblink: str,
        conference_weblink: str,
        cost: float,
        incident_type_plugin_metadata: dict = {},
    ):
        """Updates Azure issue fields."""

        description = Template(ISSUE_SUMMARY_TEMPLATE).render(
            description=description,
            incident_type=incident_type,
            priority=priority,
            cost=cost,
            commander_username=commander_email,
            reporter=reporter_email,
            document_weblink=document_weblink,
            conference_weblink=conference_weblink,
            conversation_weblink=conversation_weblink,
            storage_weblink=storage_weblink,
        )

        azure_id = ticket_id.split("-")[1]

        url = f'{AZURE_DEVOPS_URL}_apis/wit/workitems/{azure_id}?api-version=6.1-preview.3'

        if status != 'Active' or status != 'Closed':
            status = 'Active'

        data = [
            {
                "op": "add",
                "path": "/fields/System.State",
                "value": status
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": description
            },
            {
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": commander_email
            },
            {
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "Incidents"
            }
        ]

        requests.patch(url, json=data,
                       headers={'Content-Type': 'application/json-patch+json'},
                       auth=('', AZURE_DEVOPS_PAT))
