import json
import logging
import pytz
from typing import List

from datetime import datetime
from enum import Enum
from starlette.requests import Request

from fastapi import BackgroundTasks

from sqlalchemy.orm import Session
from slack_sdk.web.client import WebClient

from dispatch.database.core import SessionLocal
from dispatch.database.service import search_filter_sort_paginate
from dispatch.event import service as event_service
from dispatch.feedback import service as feedback_service
from dispatch.feedback.enums import FeedbackRating
from dispatch.feedback.models import FeedbackCreate
from dispatch.incident import flows as incident_flows
from dispatch.incident import service as incident_service
from dispatch.incident.enums import IncidentStatus, IncidentSlackViewBlockId, NewIncidentSubmission
from dispatch.incident.models import Incident
from dispatch.incident.models import IncidentUpdate, IncidentRead
from dispatch.incident_priority import service as incident_priority_service
from dispatch.incident_type import service as incident_type_service
from dispatch.messaging.strings import INCIDENT_WORKFLOW_CREATED_NOTIFICATION
from dispatch.participant import service as participant_service
from dispatch.participant.models import Participant, ParticipantUpdate
from dispatch.plugin import service as plugin_service
from dispatch.plugins.dispatch_slack import service as dispatch_slack_service
from dispatch.workflow import service as workflow_service
from dispatch.workflow.flows import send_workflow_notification
from dispatch.workflow.models import Workflow, WorkflowInstanceCreate
from .messaging import create_incident_reported_confirmation_message
from .service import get_user_profile_by_email, get_user_email
from .decorators import slack_background_task

log = logging.getLogger(__name__)


class Menus(str, Enum):
    tags = "tags_menu"


class UpdateIncidentBlockFields(str, Enum):
    tags = "update_incident_tags"
    status = "update_incident_status"
    description = "update_incident_description"
    title = "update_incident_title"
    incident_type = "update_incident_type"
    incident_priority = "update_incident_priority"


class UpdateIncidentCallbacks(str, Enum):
    submit_form = "update_incident_submit_form"


class UpdateParticipantBlockFields(str, Enum):
    reason_added = "reason_added_field"
    participant = "selected_participant_field"


class UpdateParticipantCallbacks(str, Enum):
    submit_form = "update_participant_submit_form"
    update_view = "update_participant_update_view"


class UpdateNotificationsGroupBlockFields(str, Enum):
    update_members = "update_members_field"


class UpdateNotificationsGroupCallbacks(str, Enum):
    submit_form = "update_notifications_group_submit_form"


class AddTimelineEventBlockFields(str, Enum):
    date = "date_field"
    hour = "hour_field"
    minute = "minute_field"
    timezone = "timezone_field"
    description = "description_field"


class AddTimelineEventCallbacks(str, Enum):
    submit_form = "add_timeline_event_submit_form"


class RunWorkflowBlockFields(str, Enum):
    workflow_select = "run_workflow_select"
    run_reason = "run_workflow_run_reason"
    param = "run_workflow_param"


class RunWorkflowCallbacks(str, Enum):
    submit_form = "run_workflow_submit_form"
    update_view = "run_workflow_update_view"


class IncidentRatingFeedbackBlockFields(str, Enum):
    anonymous = "anonymous_field"
    feedback = "feedback_field"
    rating = "rating_field"


class IncidentRatingFeedbackCallbacks(str, Enum):
    submit_form = "rating_feedback_submit_form"


async def handle_slack_menu(*, db_session: SessionLocal, client: WebClient, request: Request):
    """Handles slack menu message."""
    # We resolve the user's email
    user_id = request["user"]["id"]
    user_email = await dispatch_slack_service.get_user_email_async(client, user_id)

    request["user"]["email"] = user_email

    # When there are no exceptions within the dialog submission, your app must respond with 200 OK with an empty body.
    view_data = request["view"]
    view_data["private_metadata"] = json.loads(view_data["private_metadata"])
    query_str = request["value"]

    incident_id = view_data["private_metadata"].get("incident_id")
    channel_id = view_data["private_metadata"].get("channel_id")
    action_id = request["action_id"]

    f = menu_functions(action_id)
    return f(db_session, user_id, user_email, channel_id, incident_id, query_str, request)


def menu_functions(action_id: str):
    """Handles all menu requests."""
    menu_mappings = {Menus.tags: get_tags}

    for key in menu_mappings.keys():
        if key in action_id:
            return menu_mappings[key]

    raise Exception(f"No menu function found. actionId: {action_id}")


def get_tags(
    db_session: SessionLocal,
    user_id: int,
    user_email: str,
    channel_id: str,
    incident_id: str,
    query_str: str,
    request: Request,
):
    """Fetches tags based on the current query."""
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)
    # scope to current incident project
    filter_spec = {
        "and": [{"model": "Project", "op": "==", "field": "id", "value": incident.project.id}]
    }

    # attempt to filter by tag type
    if "/" in query_str:
        tag_type, tag_name = query_str.split("/")

        filter_spec["and"].append(
            {"model": "TagType", "op": "==", "field": "name", "value": tag_type}
        )

        if not len(tag_name):
            query_str = None

        tags = search_filter_sort_paginate(
            db_session=db_session, model="Tag", query_str=query_str, filter_spec=filter_spec
        )
    else:
        tags = search_filter_sort_paginate(
            db_session=db_session, model="Tag", query_str=query_str, filter_spec=filter_spec
        )

    options = []
    for t in tags["items"]:
        options.append(
            {
                "text": {"type": "plain_text", "text": f"{t.tag_type.name}/{t.name}"},
                "value": str(
                    t.id
                ),  # NOTE slack doesn't not accept int's as values (fails silently)
            }
        )

    return {"options": options}


def handle_modal_action(action: dict, background_tasks: BackgroundTasks):
    """Handles all modal actions."""
    view_data = action["view"]
    view_data["private_metadata"] = json.loads(view_data["private_metadata"])

    action_id = view_data["callback_id"]
    incident_id = view_data["private_metadata"].get("incident_id")

    channel_id = view_data["private_metadata"].get("channel_id")
    user_id = action["user"]["id"]
    user_email = action["user"]["email"]

    for f in action_functions(action_id):
        background_tasks.add_task(f, user_id, user_email, channel_id, incident_id, action)


def action_functions(action_id: str):
    """Determines which function needs to be run."""
    action_mappings = {
        AddTimelineEventCallbacks.submit_form: [add_timeline_event_from_submitted_form],
        NewIncidentSubmission.form_slack_view: [report_incident_from_submitted_form],
        UpdateParticipantCallbacks.submit_form: [update_participant_from_submitted_form],
        UpdateIncidentCallbacks.submit_form: [update_incident_from_submitted_form],
        UpdateNotificationsGroupCallbacks.submit_form: [
            update_notifications_group_from_submitted_form
        ],
        RunWorkflowCallbacks.submit_form: [run_workflow_submitted_form],
        IncidentRatingFeedbackCallbacks.submit_form: [rating_feedback_from_submitted_form],
    }

    # this allows for unique action blocks e.g. invite-user or invite-user-1, etc
    for key in action_mappings.keys():
        if key in action_id:
            return action_mappings[key]
    return []


def parse_submitted_form(view_data: dict):
    """Parse the submitted data and return important / required fields for Dispatch to create an incident."""
    parsed_data = {}
    state_elem = view_data.get("state")
    state_values = state_elem.get("values")

    for state in state_values:
        state_key_value_pair = state_values[state]

        for elem_key in state_key_value_pair:
            elem_key_value_pair = state_values[state][elem_key]

            if elem_key_value_pair.get("selected_option") and elem_key_value_pair.get(
                "selected_option"
            ).get("value"):
                parsed_data[state] = {
                    "name": elem_key_value_pair.get("selected_option").get("text").get("text"),
                    "value": elem_key_value_pair.get("selected_option").get("value"),
                }
            elif "selected_options" in elem_key_value_pair.keys():
                name = "No option selected"
                value = ""

                if elem_key_value_pair.get("selected_options"):
                    options = []
                    for selected in elem_key_value_pair["selected_options"]:
                        name = selected.get("text").get("text")
                        value = selected.get("value")
                        options.append({"name": name, "value": value})

                    parsed_data[state] = options
            elif elem_key_value_pair.get("selected_date"):
                parsed_data[state] = elem_key_value_pair.get("selected_date")
            else:
                parsed_data[state] = elem_key_value_pair.get("value")

    return parsed_data


@slack_background_task
def report_incident_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session: Session = None,
    slack_client=None,
):
    default_project_id = 1
    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    requested_form_title = parsed_form_data.get(IncidentSlackViewBlockId.title)
    requested_form_description = parsed_form_data.get(IncidentSlackViewBlockId.description)
    requested_form_incident_type = parsed_form_data.get(IncidentSlackViewBlockId.type)
    requested_form_incident_priority = parsed_form_data.get(IncidentSlackViewBlockId.priority)

    # Send a confirmation to the user
    blocks = create_incident_reported_confirmation_message(
        title=requested_form_title,
        description=requested_form_description,
        incident_type=requested_form_incident_type.get("value"),
        incident_priority=requested_form_incident_priority.get("value"),
    )

    dispatch_slack_service.send_ephemeral_message(
        client=slack_client,
        conversation_id=channel_id,
        user_id=user_id,
        text="",
        blocks=blocks,
    )

    # Create the incident
    incident = incident_service.create(
        db_session=db_session,
        title=requested_form_title,
        status=IncidentStatus.active,
        description=requested_form_description,
        incident_type=requested_form_incident_type,
        incident_priority=requested_form_incident_priority,
        reporter_email=user_email,
        tags=[],  # The modal does not currently support tags
    )

    incident_flows.incident_create_flow(incident_id=incident.id)


def create_block_option_from_template(text: str, value: str):
    """Helper function which generates the option block for modals / views"""
    return {"text": {"type": "plain_text", "text": str(text), "emoji": True}, "value": str(value)}


def build_report_incident_blocks(channel_id: str, db_session: Session):
    """Builds all blocks required for the reporting incident modal."""
    default_project_id = 1
    incident_type_options = []
    for incident_type in incident_type_service.get_all(db_session=db_session, project_id=default_project_id):
        incident_type_options.append(
            create_block_option_from_template(text=incident_type.name, value=incident_type.name)
        )

    incident_priority_options = []
    for incident_priority in incident_priority_service.get_all(db_session=db_session, project_id=default_project_id):
        incident_priority_options.append(
            create_block_option_from_template(
                text=incident_priority.name, value=incident_priority.name
            )
        )

    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Report"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "If you suspect an incident and require help, "
                                "please fill out the following to the best of your abilities.",
                    }
                ],
            },
            {
                "block_id": IncidentSlackViewBlockId.title.value,
                "type": "input",
                "label": {"type": "plain_text", "text": "Title"},
                "element": {
                    "type": "plain_text_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "A brief explanatory title. You can change this later.",
                    },
                },
            },
            {
                "block_id": IncidentSlackViewBlockId.description.value,
                "type": "input",
                "label": {"type": "plain_text", "text": "Description"},
                "element": {
                    "type": "plain_text_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "A summary of what you know so far. It's all right if this is incomplete.",
                    },
                    "multiline": True,
                },
            },
            {
                "block_id": IncidentSlackViewBlockId.type.value,
                "type": "input",
                "label": {"type": "plain_text", "text": "Type"},
                "element": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select Incident Type"},
                    "options": incident_type_options,
                },
            },
            {
                "block_id": IncidentSlackViewBlockId.priority.value,
                "type": "input",
                "label": {"type": "plain_text", "text": "Priority", "emoji": True},
                "element": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select Incident Priority"},
                    "options": incident_priority_options,
                },
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "callback_id": NewIncidentSubmission.form_slack_view.value,
        "private_metadata": json.dumps({"channel_id": str(channel_id)}),
    }

    return modal_template


@slack_background_task
def create_report_incident_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict = None,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for reporting an incident."""
    trigger_id = command.get("trigger_id")

    modal_create_template = build_report_incident_blocks(
        channel_id=channel_id, db_session=db_session
    )

    dispatch_slack_service.open_modal_with_user(
        client=slack_client, trigger_id=trigger_id, modal=modal_create_template
    )


def build_incident_participants_select_block(incident: Incident, participant: Participant = None):
    """Builds a static select with all current participants."""
    selected_option = None
    participant_options = []
    for p in incident.participants:
        current_option = {
            "text": {"type": "plain_text", "text": p.individual.name},
            "value": str(p.id),
        }

        participant_options.append(current_option)

        if participant:
            if p.id == participant.id:
                selected_option = current_option

    if participant:
        select_block = {
            "block_id": UpdateParticipantBlockFields.participant.value,
            "type": "input",
            "element": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select Participant"},
                "options": participant_options,
                "initial_option": selected_option,
                "action_id": UpdateParticipantBlockFields.participant.value,
            },
            "label": {"type": "plain_text", "text": "Participant"},
        }

    else:
        select_block = {
            "block_id": UpdateParticipantBlockFields.participant.value,
            "type": "actions",
            "elements": [
                {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select Participant"},
                    "options": participant_options,
                }
            ],
        }

    return select_block


def build_update_participant_blocks(incident: Incident, participant: Participant = None):
    """Builds all blocks required for updating the participant modal."""
    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Edit Participant"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Use this form to edit why a particpant was added to this incident.",
                    }
                ],
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "callback_id": UpdateParticipantCallbacks.update_view.value,
        "private_metadata": json.dumps(
            {"incident_id": str(incident.id), "channel_id": str(incident.conversation.channel_id)}
        ),
    }

    select_block = build_incident_participants_select_block(
        incident=incident, participant=participant
    )
    modal_template["blocks"].append(select_block)

    # we need to show the reason if we're updating
    if participant:
        modal_template["blocks"].append(
            {
                "block_id": UpdateParticipantBlockFields.reason_added.value,
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "initial_value": participant.added_reason or "",
                    "action_id": UpdateParticipantBlockFields.reason_added.value,
                },
                "label": {"type": "plain_text", "text": "Reason Added"},
            }
        )

        modal_template["callback_id"] = UpdateParticipantCallbacks.submit_form.value

    return modal_template


@slack_background_task
def update_participant_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Saves form data."""
    submitted_form = action.get("view")

    parsed_form_data = parse_submitted_form(submitted_form)

    added_reason = parsed_form_data.get(UpdateParticipantBlockFields.reason_added)
    participant_id = int(parsed_form_data.get(UpdateParticipantBlockFields.participant)["value"])
    selected_participant = participant_service.get(
        db_session=db_session, participant_id=participant_id
    )
    participant_service.update(
        db_session=db_session,
        participant=selected_participant,
        participant_in=ParticipantUpdate(added_reason=added_reason),
    )

    dispatch_slack_service.send_ephemeral_message(
        client=slack_client,
        conversation_id=channel_id,
        user_id=user_id,
        text="You have successfully updated the participant.",
    )


@slack_background_task
def update_update_participant_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Pushes an updated view to the update participant modal."""
    trigger_id = action["trigger_id"]
    participant_id = action["actions"][0]["selected_option"]["value"]

    selected_participant = participant_service.get(
        db_session=db_session, participant_id=participant_id
    )
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    modal_update_template = build_update_participant_blocks(
        incident=incident, participant=selected_participant
    )

    dispatch_slack_service.update_modal_with_user(
        client=slack_client,
        trigger_id=trigger_id,
        view_id=action["view"]["id"],
        modal=modal_update_template,
    )


@slack_background_task
def create_update_incident_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict = None,
    db_session=None,
    slack_client=None,
):
    """Creates a dialog for updating incident information."""
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    type_options = []
    for t in incident_type_service.get_all_enabled(
        db_session=db_session, project_id=incident.project.id
    ):
        type_options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": t.name,
                    "emoji": False,
                },
                "value": t.name,
            }
        )

    priority_options = []
    for priority in incident_priority_service.get_all_enabled(
        db_session=db_session, project_id=incident.project.id
    ):
        priority_options.append(
            {
                "text": {"type": "plain_text", "text": priority.name, "emoji": False},
                "value": priority.name,
            }
        )

    status_options = []
    for status in IncidentStatus:
        status_options.append(
            {
                "text": {"type": "plain_text", "text": status.value, "emoji": False},
                "value": status.value,
            }
        )

    selected_tags = []
    for t in incident.tags:
        selected_tags.append(
            {
                "text": {"type": "plain_text", "text": f"{t.tag_type.name}/{t.name}"},
                "value": str(
                    t.id
                ),  # NOTE slack doesn't not accept int's as values (fails silently)
            }
        )

    modal = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Update Incident"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Use this form to update the details of the incident.",
                    }
                ],
            },
            {
                "type": "input",
                "block_id": UpdateIncidentBlockFields.title.value,
                "element": {
                    "type": "plain_text_input",
                    "multiline": False,
                    "initial_value": incident.title or "",
                },
                "label": {"type": "plain_text", "text": "Title"},
            },
            {
                "type": "input",
                "block_id": UpdateIncidentBlockFields.description.value,
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "initial_value": incident.description or "",
                },
                "label": {"type": "plain_text", "text": "Description"},
            },
            {
                "type": "section",
                "block_id": UpdateIncidentBlockFields.incident_type.value,
                "text": {
                    "type": "mrkdwn",
                    "text": "*Type*",
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select type"},
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": incident.incident_type.name,
                            "emoji": False,
                        },
                        "value": incident.incident_type.name,
                    },
                    "options": type_options,
                },
            },
            {
                "type": "section",
                "block_id": UpdateIncidentBlockFields.incident_priority.value,
                "text": {
                    "type": "mrkdwn",
                    "text": "*Priority*",
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select priority"},
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": incident.incident_priority.name,
                            "emoji": False,
                        },
                        "value": incident.incident_priority.name,
                    },
                    "options": priority_options,
                },
            },
            {
                "type": "section",
                "block_id": UpdateIncidentBlockFields.status.value,
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*",
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "Select status"},
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": incident.status,
                            "emoji": False,
                        },
                        "value": incident.status,
                    },
                    "options": status_options,
                },
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Update"},
        "callback_id": UpdateIncidentCallbacks.submit_form.value,
        "private_metadata": json.dumps(
            {
                "incident_id": str(incident.id),
                "channel_id": str(incident.conversation.channel_id),
            }
        ),
    }

    dispatch_slack_service.open_modal_with_user(
        client=slack_client, trigger_id=command["trigger_id"], modal=modal
    )


@slack_background_task
def update_incident_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Massages slack dialog data into something that Dispatch can use."""
    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    tags = []
    for t in parsed_form_data.get("update_incident_tags", []):
        tags.append({"id": t["value"]})

    incident_in = IncidentUpdate(
        title=parsed_form_data.get("update_incident_title"),
        description=parsed_form_data.get("update_incident_description"),
        incident_type={"name": parsed_form_data.get("update_incident_type")["value"]},
        incident_priority={"name": parsed_form_data.get("update_incident_priority")["value"]},
        status=parsed_form_data.get("update_incident_status")["value"],
        tags=tags,
    )

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)
    existing_incident = IncidentRead.from_orm(incident)
    incident_service.update(db_session=db_session, incident=incident, incident_in=incident_in)
    incident_flows.incident_update_flow(user_email, incident_id, existing_incident)

    dispatch_slack_service.send_ephemeral_message(
        slack_client, channel_id, user_id, "You have sucessfully updated the incident."
    )


@slack_background_task
def create_update_participant_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for updating a participant."""
    trigger_id = command["trigger_id"]

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    modal_create_template = build_update_participant_blocks(incident=incident)

    dispatch_slack_service.open_modal_with_user(
        client=slack_client, trigger_id=trigger_id, modal=modal_create_template
    )


def build_update_notifications_group_blocks(incident: Incident, db_session: SessionLocal):
    """Builds all blocks required to update the membership of the notifications group."""
    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Update Group Membership"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Use this form to update the membership of the notifications group.",
                    }
                ],
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Update"},
        "callback_id": UpdateNotificationsGroupCallbacks.submit_form.value,
        "private_metadata": json.dumps(
            {"incident_id": str(incident.id), "channel_id": incident.conversation.channel_id}
        ),
    }

    group_plugin = plugin_service.get_active_instance(
        db_session=db_session, project_id=incident.project.id, plugin_type="participant-group"
    )
    members = group_plugin.instance.list(incident.notifications_group.email)

    members_block = {
        "type": "input",
        "block_id": UpdateNotificationsGroupBlockFields.update_members,
        "label": {"type": "plain_text", "text": "Members"},
        "element": {
            "type": "plain_text_input",
            "action_id": UpdateNotificationsGroupBlockFields.update_members.value,
            "multiline": True,
            "initial_value": (", ").join(members),
        },
    }
    modal_template["blocks"].append(members_block)

    modal_template["blocks"].append(
        {
            "type": "context",
            "elements": [{"type": "plain_text", "text": "Separate email addresses with commas."}],
        },
    )

    return modal_template


@slack_background_task
def create_update_notifications_group_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for editing members of the notifications group."""
    trigger_id = command["trigger_id"]

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    modal_create_template = build_update_notifications_group_blocks(
        incident=incident, db_session=db_session
    )

    dispatch_slack_service.open_modal_with_user(
        client=slack_client, trigger_id=trigger_id, modal=modal_create_template
    )


@slack_background_task
def update_notifications_group_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Updates notifications group based on submitted form data."""
    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    current_members = (
        submitted_form["blocks"][1]["element"]["initial_value"].replace(" ", "").split(",")
    )
    updated_members = (
        parsed_form_data.get(UpdateNotificationsGroupBlockFields.update_members)
            .replace(" ", "")
            .split(",")
    )

    members_added = list(set(updated_members) - set(current_members))
    members_removed = list(set(current_members) - set(updated_members))

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    group_plugin = plugin_service.get_active_instance(
        db_session=db_session, project_id=incident.project.id, plugin_type="participant-group"
    )

    group_plugin.instance.add(incident.notifications_group.email, members_added)
    group_plugin.instance.remove(incident.notifications_group.email, members_removed)

    dispatch_slack_service.send_ephemeral_message(
        client=slack_client,
        conversation_id=channel_id,
        user_id=user_id,
        text="You have successfully updated the notifications group.",
    )


def build_add_timeline_event_blocks(incident: Incident):
    """Builds all blocks required to add an event to the incident timeline."""
    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Add Timeline Event"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Use this form to add an event to the incident timeline.",
                    }
                ],
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Add"},
        "callback_id": AddTimelineEventCallbacks.submit_form.value,
        "private_metadata": json.dumps(
            {"incident_id": str(incident.id), "channel_id": str(incident.conversation.channel_id)}
        ),
    }

    date_picker_block = {
        "type": "input",
        "block_id": AddTimelineEventBlockFields.date,
        "label": {"type": "plain_text", "text": "Date"},
        "element": {"type": "datepicker"},
        "optional": False,
    }
    modal_template["blocks"].append(date_picker_block)

    hour_picker_options = []
    for h in range(0, 24):
        h = str(h).zfill(2)
        hour_picker_options.append(create_block_option_from_template(text=f"{h}:00", value=h))

    hour_picker_block = {
        "type": "input",
        "block_id": AddTimelineEventBlockFields.hour.value,
        "label": {"type": "plain_text", "text": "Hour"},
        "element": {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select an hour"},
            "options": hour_picker_options,
        },
        "optional": False,
    }
    modal_template["blocks"].append(hour_picker_block)

    minute_picker_options = []
    for m in range(0, 60):
        minute_picker_options.append(
            create_block_option_from_template(text=m, value=str(m).zfill(2))
        )

    minute_picker_block = {
        "type": "input",
        "block_id": AddTimelineEventBlockFields.minute.value,
        "label": {"type": "plain_text", "text": "Minute"},
        "element": {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select a minute"},
            "options": minute_picker_options,
        },
        "optional": False,
    }
    modal_template["blocks"].append(minute_picker_block)

    timezone_block = {
        "type": "input",
        "block_id": AddTimelineEventBlockFields.timezone.value,
        "label": {"type": "plain_text", "text": "Time Zone"},
        "element": {
            "type": "radio_buttons",
            "initial_option": {
                "value": "profile",
                "text": {"type": "plain_text", "text": "Local time from Slack profile"},
            },
            "options": [
                {
                    "text": {"type": "plain_text", "text": "Local time from Slack profile"},
                    "value": "profile",
                },
                {
                    "text": {"type": "plain_text", "text": "Coordinated Universal Time (UTC)"},
                    "value": "UTC",
                },
            ],
        },
    }
    modal_template["blocks"].append(timezone_block)

    description_block = {
        "type": "input",
        "block_id": AddTimelineEventBlockFields.description.value,
        "label": {"type": "plain_text", "text": "Description"},
        "element": {
            "type": "plain_text_input",
            "action_id": AddTimelineEventBlockFields.description.value,
            "placeholder": {"type": "plain_text", "text": "A description of the event"},
        },
        "optional": False,
    }
    modal_template["blocks"].append(description_block)

    return modal_template


@slack_background_task
def create_add_timeline_event_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for adding events to the incident timeline."""
    trigger_id = command["trigger_id"]

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    modal_create_template = build_add_timeline_event_blocks(incident=incident)

    dispatch_slack_service.open_modal_with_user(
        client=slack_client, trigger_id=trigger_id, modal=modal_create_template
    )


@slack_background_task
def add_timeline_event_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Adds event to incident timeline based on submitted form data."""
    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    event_date = parsed_form_data.get(AddTimelineEventBlockFields.date)
    event_hour = parsed_form_data.get(AddTimelineEventBlockFields.hour)["value"]
    event_minute = parsed_form_data.get(AddTimelineEventBlockFields.minute)["value"]
    event_timezone_selection = parsed_form_data.get(AddTimelineEventBlockFields.timezone)["value"]
    event_description = parsed_form_data.get(AddTimelineEventBlockFields.description)

    participant = participant_service.get_by_incident_id_and_email(
        db_session=db_session, incident_id=incident_id, email=user_email
    )

    event_timezone = event_timezone_selection
    if event_timezone_selection == "profile":
        participant_profile = get_user_profile_by_email(slack_client, user_email)
        if participant_profile.get("tz"):
            event_timezone = participant_profile.get("tz")

    event_dt = datetime.fromisoformat(f"{event_date}T{event_hour}:{event_minute}")
    event_dt_utc = pytz.timezone(event_timezone).localize(event_dt).astimezone(pytz.utc)

    event_service.log(
        db_session=db_session,
        source="Slack Plugin - Conversation Management",
        started_at=event_dt_utc,
        description=f'"{event_description}," said {participant.individual.name}',
        incident_id=incident_id,
        individual_id=participant.individual.id,
    )

    dispatch_slack_service.send_ephemeral_message(
        client=slack_client,
        conversation_id=channel_id,
        user_id=user_id,
        text="Event successfully added to timeline.",
    )


def build_workflow_blocks(
    incident: Incident, workflows: List[Workflow], selected_workflow: Workflow = None
):
    """Builds all blocks required to run a workflow."""
    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Run workflow"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Use this form to run a workflow.",
                    }
                ],
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Run"},
        "callback_id": RunWorkflowCallbacks.update_view.value,
        "private_metadata": json.dumps(
            {"incident_id": str(incident.id), "channel_id": incident.conversation.channel_id}
        ),
    }

    selected_option = None
    workflow_options = []
    for w in workflows:
        # don't show disable workflows or workflows with disabled plugins
        # if not w.plugin.enabled or not w.enabled:
        if not w.enabled:
            continue

        current_option = {
            "text": {
                "type": "plain_text",
                "text": w.name,
            },
            "value": str(w.id),
        }

        workflow_options.append(current_option)

        if selected_workflow:
            if w.id == selected_workflow.id:
                selected_option = current_option

    if selected_workflow:
        select_block = {
            "block_id": RunWorkflowBlockFields.workflow_select.value,
            "type": "input",
            "element": {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select Workflow",
                },
                "initial_option": selected_option,
                "options": workflow_options,
                "action_id": RunWorkflowBlockFields.workflow_select.value,
            },
            "label": {"type": "plain_text", "text": "Workflow"},
        }
    else:
        select_block = {
            "block_id": RunWorkflowBlockFields.workflow_select.value,
            "type": "actions",
            "elements": [
                {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Workflow",
                    },
                    "options": workflow_options,
                }
            ],
        }

    modal_template["blocks"].append(select_block)

    return modal_template


@slack_background_task
def create_run_workflow_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    command: dict,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for running a workflow."""
    trigger_id = command.get("trigger_id")

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)
    workflows = workflow_service.get_enabled(db_session=db_session)

    if workflows:
        modal_create_template = build_workflow_blocks(incident=incident, workflows=workflows)

        dispatch_slack_service.open_modal_with_user(
            client=slack_client, trigger_id=trigger_id, modal=modal_create_template
        )
    else:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No workflows are enabled. You can enable one in the Dispatch UI at /workflows.",
                },
            }
        ]
        dispatch_slack_service.send_ephemeral_message(
            slack_client,
            command["channel_id"],
            command["user_id"],
            "No workflows enabled.",
            blocks=blocks,
        )


@slack_background_task
def update_workflow_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Pushes an updated view to the run workflow modal."""
    log.info("*** Updating workflow modal")

    trigger_id = action["trigger_id"]
    incident_id = action["view"]["private_metadata"]["incident_id"]
    workflow_id = action["actions"][0]["selected_option"]["value"]

    selected_workflow = workflow_service.get(db_session=db_session, workflow_id=workflow_id)
    workflows = workflow_service.get_enabled(db_session=db_session)
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    modal_template = build_workflow_blocks(
        incident=incident, workflows=workflows, selected_workflow=selected_workflow
    )

    modal_template["blocks"].append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Description* \n {selected_workflow.description}"},
        },
    )

    modal_template["blocks"].append(
        {
            "block_id": RunWorkflowBlockFields.run_reason.value,
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": RunWorkflowBlockFields.run_reason.value,
            },
            "label": {"type": "plain_text", "text": "Run Reason"},
        },
    )

    modal_template["blocks"].append(
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Parameters*"}}
    )

    if selected_workflow.parameters:
        for p in selected_workflow.parameters:
            modal_template["blocks"].append(
                {
                    "block_id": f"{RunWorkflowBlockFields.param}-{p['key']}",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "Value"},
                    },
                    "label": {"type": "plain_text", "text": p["key"]},
                }
            )

    else:
        modal_template["blocks"].append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "This workflow has no parameters."},
            }
        )

    modal_template["callback_id"] = RunWorkflowCallbacks.submit_form.value

    dispatch_slack_service.update_modal_with_user(
        client=slack_client,
        trigger_id=trigger_id,
        view_id=action["view"]["id"],
        modal=modal_template,
    )


@slack_background_task
def run_workflow_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Runs an external flow."""
    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    params = {}
    named_params = []
    for i in parsed_form_data.keys():
        if i.startswith(RunWorkflowBlockFields.param):
            key = i.split("-")[1]
            value = parsed_form_data[i]
            params.update({key: value})
            named_params.append({"key": key, "value": value})

    workflow_id = parsed_form_data.get(RunWorkflowBlockFields.workflow_select)["value"]
    run_reason = parsed_form_data.get(RunWorkflowBlockFields.run_reason)
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)
    workflow = workflow_service.get(db_session=db_session, workflow_id=workflow_id)

    creator_email = get_user_email(slack_client, action["user"]["id"])

    instance = workflow_service.create_instance(
        db_session=db_session,
        instance_in=WorkflowInstanceCreate(
            workflow={"id": workflow.id},
            incident={"id": incident.id},
            creator={"email": creator_email},
            run_reason=run_reason,
            parameters=named_params,
        ),
    )

    params.update(
        {"incident_id": incident.id, "incident_name": incident.name, "instance_id": instance.id,
         "db_session": db_session, "conversation_id": incident.conversation.channel_id,
         "project_id": workflow.project_id}
    )

    plugin = plugin_service.get_active_instance(db_session=db_session,
                                                project_id=workflow.project_id,
                                                plugin_type="workflow")

    if plugin:
        plugin.instance.run(workflow.name, workflow.resource_id, params)

    send_workflow_notification(
        incident.conversation.channel_id,
        INCIDENT_WORKFLOW_CREATED_NOTIFICATION,
        db_session,
        workflow.project_id,
        instance_creator_name=instance.creator.individual.name,
        workflow_name=instance.workflow.name,
        workflow_description=instance.workflow.description,
    )


def build_rating_feedback_blocks(incident: Incident):
    """Builds all blocks required to rate and provide feedback about an incident."""
    modal_template = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Feedback"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Use this form to rate your experience and provide feedback about the incident.",
                    }
                ],
            },
        ],
        "close": {"type": "plain_text", "text": "Cancel"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "callback_id": IncidentRatingFeedbackCallbacks.submit_form.value,
        "private_metadata": json.dumps(
            {"incident_id": str(incident.id), "channel_id": incident.conversation.channel_id}
        ),
    }

    rating_picker_options = []
    for rating in FeedbackRating:
        rating_picker_options.append(
            {"text": {"type": "plain_text", "text": rating.value}, "value": rating.value}
        )

    rating_picker_block = {
        "type": "input",
        "block_id": IncidentRatingFeedbackBlockFields.rating.value,
        "label": {"type": "plain_text", "text": "Rate your experience"},
        "element": {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select a rating"},
            "options": rating_picker_options,
        },
        "optional": False,
    }
    modal_template["blocks"].append(rating_picker_block)

    feedback_block = {
        "type": "input",
        "block_id": IncidentRatingFeedbackBlockFields.feedback.value,
        "label": {"type": "plain_text", "text": "Give us feedback"},
        "element": {
            "type": "plain_text_input",
            "action_id": IncidentRatingFeedbackBlockFields.feedback.value,
            "placeholder": {
                "type": "plain_text",
                "text": "How would you describe your experience?",
            },
            "multiline": True,
        },
        "optional": True,
    }
    modal_template["blocks"].append(feedback_block)

    anonymous_checkbox_block = {
        "type": "input",
        "block_id": IncidentRatingFeedbackBlockFields.anonymous.value,
        "label": {
            "type": "plain_text",
            "text": "Check the box if you wish to provide your feedback anonymously",
        },
        "element": {
            "type": "checkboxes",
            "action_id": IncidentRatingFeedbackBlockFields.anonymous.value,
            "options": [
                {
                    "value": "anonymous",
                    "text": {"type": "plain_text", "text": "Anonymize my feedback"},
                },
            ],
        },
        "optional": True,
    }
    modal_template["blocks"].append(anonymous_checkbox_block)

    return modal_template


@slack_background_task
def create_rating_feedback_modal(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict = None,
    command: dict = None,
    db_session=None,
    slack_client=None,
):
    """Creates a modal for rating and providing feedback about an incident."""

    if action:
        trigger_id = action["trigger_id"]
    else:
        trigger_id = command["trigger_id"]

    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    if not incident:
        message = "Sorry, you cannot submit feedback about this incident it does not exist."
        dispatch_slack_service.send_ephemeral_message(slack_client, channel_id, user_id, message)
    else:
        modal_create_template = build_rating_feedback_blocks(incident=incident)

        dispatch_slack_service.open_modal_with_user(
            client=slack_client, trigger_id=trigger_id, modal=modal_create_template
        )


@slack_background_task
def rating_feedback_from_submitted_form(
    user_id: str,
    user_email: str,
    channel_id: str,
    incident_id: int,
    action: dict,
    db_session=None,
    slack_client=None,
):
    """Adds rating and feeback to incident based on submitted form data."""
    incident = incident_service.get(db_session=db_session, incident_id=incident_id)

    participant = participant_service.get_by_incident_id_and_email(
        db_session=db_session, incident_id=incident_id, email=user_email
    )

    submitted_form = action.get("view")
    parsed_form_data = parse_submitted_form(submitted_form)

    feedback = parsed_form_data.get(IncidentRatingFeedbackBlockFields.feedback)
    rating = parsed_form_data.get(IncidentRatingFeedbackBlockFields.rating)["value"]

    if parsed_form_data.get(IncidentRatingFeedbackBlockFields.anonymous):
        anonymous = parsed_form_data.get(IncidentRatingFeedbackBlockFields.anonymous)[0]
    else:
        anonymous = ""

    feedback_in = FeedbackCreate(rating=rating, feedback=feedback, project=incident.project)
    feedback = feedback_service.create(db_session=db_session, feedback_in=feedback_in)

    incident.feedback.append(feedback)

    if anonymous == "":
        participant.feedback.append(feedback)
        db_session.add(participant)

    db_session.add(incident)
    db_session.commit()

    dispatch_slack_service.send_message(
        client=slack_client,
        conversation_id=user_id,
        text="Thank you for your feedback!",
    )
