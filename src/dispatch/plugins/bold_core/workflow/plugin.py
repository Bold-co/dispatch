import logging
from typing import List

from dispatch.plugin import service as plugin_service
from dispatch.plugins.bases import WorkflowPlugin
from dispatch.plugins.bold_core import workflow as bold_workflow
from dispatch.plugins.bold_core.workflow.check_sites import get_sites_info

log = logging.getLogger(__name__)


def send_workflow_notification(conversation_id: str,
                               db_session: None,
                               project_id: str,
                               notification_text: str,
                               blocks: List):
    """Sends a workflow notification."""
    plugin = plugin_service.get_active_instance(db_session=db_session,
                                                project_id=project_id,
                                                plugin_type="conversation")
    plugin.instance.send(
        conversation_id=conversation_id, text=notification_text, blocks=blocks
    )


class BoldWorkflowPlugin(WorkflowPlugin):
    title = "Bold Plugin - Workflow plugin"
    slug = "bold-workflow"
    description = "Uses bold plugin to execute workflows."
    version = bold_workflow.__version__

    author = "Bold"
    author_url = "https://github.com/netflix/dispatch.git"

    def get_instance(self, workflow_id: str, instance_id: str, **kwargs):
        return BoldWorkflowPlugin()

    def run(self, workflow_name: str, workflow_id: str, params: dict, **kwargs):

        print(f"*** Wkflow params: {params}")

        db_session = params["db_session"]
        conversation_id = params["conversation_id"]
        project_id = params["project_id"]

        blocks = get_sites_info()

        try:
            send_workflow_notification(conversation_id=conversation_id,
                                       db_session=db_session,
                                       notification_text="Verify Sites",
                                       project_id=project_id,
                                       blocks=blocks)
        except Exception as e:
            log.error("** Error in workflow")
            log.exception(e)

        print(project_id, conversation_id, params)
