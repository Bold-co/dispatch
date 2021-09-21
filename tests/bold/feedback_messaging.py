from dispatch.messaging.strings import LEARNED_LESSON_NOTIFICATION, INCIDENT_TITLE_ES, MessageType
from dispatch.plugins.dispatch_slack.plugin import SlackConversationPlugin

plugin = SlackConversationPlugin()

"""
INC-037 -
Lecciones:

"""

notification_kwargs = [
    {
        "name": "INC-",
        "title": "",
        "lessons": "\n",
        "user": ""
    }
]

template = LEARNED_LESSON_NOTIFICATION.copy()
template.insert(1, INCIDENT_TITLE_ES)

for kwargs in notification_kwargs:
    plugin.send(
        "C025WQ7E8MP",  # Test
        # "C0260U01NT0",  # PRO
        "Incident Notification",
        template,
        notification_type=MessageType.incident_notification,
        persist=False,
        **kwargs
    )
