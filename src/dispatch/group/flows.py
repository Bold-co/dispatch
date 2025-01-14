from typing import Any, List
import logging

from dispatch.database.core import SessionLocal
from dispatch.database.core import get_table_name_by_class_instance
from dispatch.event import service as event_service
from dispatch.plugin import service as plugin_service

from .enums import GroupType, GroupAction
from .models import Group, GroupCreate
from .service import create


log = logging.getLogger(__name__)


def create_group(
    subject: Any, group_type: str, group_participants: List[str], db_session: SessionLocal
):
    """Creates a group."""
    plugin = plugin_service.get_active_instance(
        db_session=db_session, project_id=subject.project.id, plugin_type="participant-group"
    )
    if not plugin:
        log.warning("Group not created. No group plugin enabled.")
        return

    # we create the external group
    try:
        external_group = plugin.instance.create(name=subject.name, participants=group_participants)
    except Exception as e:
        log.exception(e)
        return

    if not external_group:
        log.error(f"Group not created. Plugin {plugin.plugin.slug} encountered an error.")
        return

    external_group.update(
        {
            "resource_type": f"{plugin.plugin.slug}-{group_type}-group",
            "resource_id": external_group["id"],
        }
    )

    # we create the internal group
    group_in = GroupCreate(
        name=external_group["name"],
        email=external_group["email"],
        resource_type=external_group["resource_type"],
        resource_id=external_group["resource_id"],
        weblink=external_group["weblink"],
    )
    group = create(db_session=db_session, group_in=group_in)
    subject.groups.append(group)

    if group_type == GroupType.tactical:
        subject.tactical_group_id = group.id
    else:
        subject.notifications_group_id = group.id

    db_session.add(subject)
    db_session.commit()

    subject_type = get_table_name_by_class_instance(subject)
    if subject_type == "case":
        event_service.log_case_event(
            db_session=db_session,
            source=plugin.plugin.title,
            description="Case group created",
            case_id=subject.id,
        )
    if subject_type == "incident":
        event_service.log_incident_event(
            db_session=db_session,
            source=plugin.plugin.title,
            description="Incident group created",
            incident_id=subject.id,
        )

    return group


def update_group(
    subject: Any,
    group: Group,
    group_action: GroupAction,
    group_member: str,
    db_session: SessionLocal,
):
    """Updates an existing group."""
    plugin = plugin_service.get_active_instance(
        db_session=db_session, project_id=subject.project.id, plugin_type="participant-group"
    )
    if not plugin:
        log.warning("Group not updated. No group plugin enabled.")
        return

    # we get the list of group members
    try:
        group_members = plugin.instance.list(email=group.email)
    except Exception as e:
        log.exception(e)
        return

    # we add the member to the group if it's not a member
    if group_action == GroupAction.add_member and group_member not in group_members:
        try:
            plugin.instance.add(email=group.email, participants=[group_member])
        except Exception as e:
            log.exception(e)
            return

    # we remove the member from the group if it's a member
    if group_action == GroupAction.remove_member and group_member in group_members:
        try:
            plugin.instance.remove(email=group.email, participants=[group_member])
        except Exception as e:
            log.exception(e)
            return


def delete_group(group: Group, db_session: SessionLocal):
    """Deletes an existing group."""
    plugin = plugin_service.get_active_instance(
        db_session=db_session, project_id=group.case.project.id, plugin_type="participant-group"
    )
    if plugin:
        try:
            plugin.instance.delete(email=group.email)
        except Exception as e:
            log.exception(e)
    else:
        log.warning("Group not deleted. No group plugin enabled.")
