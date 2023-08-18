from enum import Enum


# report + update blocks
class IncidentBlockId(str, Enum):
    cf = "cf_field"
    description = "description_field"
    priority = "incident_priority_field"
    product = "product_field"
    project = "project_field"
    report_source = "report_source"
    status = "status_field"
    tags = "tags_select_field"
    team = "team_field"
    title = "title_field"
    type = "incident_type_field"


# report incident
class ReportIncidentCallbackId(str, Enum):
    submit_form = "report_incident_submit_form"
    update_view = "report_incident_update_view"


# update incident
class UpdateIncidentCallbackId(str, Enum):
    submit_form = "update_incident_submit_form"


# update participant
class UpdateParticipantBlockId(str, Enum):
    reason_added = "reason_added_field"
    participant = "selected_participant_field"


class UpdateParticipantCallbackId(str, Enum):
    submit_form = "update_participant_submit_form"
    update_view = "update_participant_update_view"


# update notification
class UpdateNotificationsGroupBlockId(str, Enum):
    update_members = "update_members_field"


class UpdateNotificationsGroupCallbackId(str, Enum):
    submit_form = "update_notifications_group_submit_form"


# add timeline
class AddTimelineEventBlockId(str, Enum):
    date = "date_field"
    hour = "hour_field"
    minute = "minute_field"
    am_pm = "am_pm"
    timezone = "timezone_field"
    description = "description_field"


class AddTimelineEventCallbackId(str, Enum):
    submit_form = "add_timeline_event_submit_form"
