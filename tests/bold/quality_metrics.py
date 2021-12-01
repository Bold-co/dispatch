import logging

import requests

from dispatch.config import INCIDENT_DEVOPS_ENDPOINT

log = logging.getLogger(__name__)


def send_created_incident_quality_event(name: str,
                                        reporter_email: str,
                                        report_source: str,
                                        creation_time: str,
                                        team_id: str):
    try:
        events_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/dispatch"
        data = {
            "id": name,
            "reporter_email": reporter_email,
            "report_source": report_source,
            "creation_time": creation_time,  # strftime('%Y-%m-%dT%H:%M:%S%Z'),
            "team_id": team_id
        }
        response = requests.post(url=events_url, json=data)
        if not response.ok:
            log.error(f"Error posting to bold API: {response.text}")
    except ConnectionError:
        log.error(f"Error posting to bold API")


def send_stabilized_incident_quality_event(name: str, stabilization_time: str):
    try:
        events_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/dispatch"
        data = {
            "id": name,
            "stabilization_time": stabilization_time
        }
        response = requests.patch(url=events_url, json=data)
        if not response.ok:
            log.error(f"Error posting to bold API: {response.text}")
    except ConnectionError:
        log.error(f"Error posting to bold API")


def send_closed_incident_quality_event(name: str, close_time: str, outage_start_time: str):
    try:
        events_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/dispatch"
        data = {
            "id": name,
            "close_time": close_time,
            "outage_start_time": outage_start_time
        }
        response = requests.patch(url=events_url, json=data)
        if not response.ok:
            log.error(f"Error posting to bold API: {response.text}")
    except ConnectionError:
        log.error(f"Error posting to bold API")


incidents = [

    {'name': 'INC-027', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Alert',
     'creation_time': '2021-07-15T22:14:27', 'stabilization_time': '2021-07-15T22:50:38',
     'close_time': None, 'outage_start_time': '2021-07-15T22:10:00',
     'team_id': '8ae1631c-3b5e-4cd1-9ece-c10f8a3f560d'},

    {'name': 'INC-026', 'reporter_email': 'julian.hernandez@bold.co', 'report_source': 'Alerts',
     'creation_time': '2021-07-14T18:21:02', 'stabilization_time': '2021-07-15T16:06:30',
     'close_time': '2021-07-19T15:53:41', 'outage_start_time': '2021-07-14T07:45:00',
     'team_id': '1e1201e3-13a7-4011-bf79-e4279000800a'},

    {'name': 'INC-025', 'reporter_email': 'andres.oviedo@bold.co', 'report_source': 'Tech Team',
     'creation_time': '2021-07-13T19:54:12', 'stabilization_time': '2021-07-14T16:01:09',
     'close_time': '2021-07-21T14:37:07', 'outage_start_time': '2021-07-13T16:00:00',
     'team_id': '085aa84b-a6c9-46a1-90fd-5dd6379ee8cd'},

    {'name': 'INC-024', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Tech Team',
     'creation_time': '2021-07-07T17:17:03', 'stabilization_time': '2021-07-13T20:34:32',
     'close_time': '2021-07-13T20:34:32', 'outage_start_time': '2021-07-01T05:00:00',
     'team_id': '1e1201e3-13a7-4011-bf79-e4279000800a'},

    {'name': 'INC-023', 'reporter_email': 'david.lopez@bold.co', 'report_source': 'Tech Team',
     'creation_time': '2021-07-01T22:20:08', 'stabilization_time': '2021-07-08T16:20:10',
     'close_time': '2021-07-08T16:20:10', 'outage_start_time': '2021-06-30T04:20:00',
     'team_id': '085aa84b-a6c9-46a1-90fd-5dd6379ee8cd'},

    {'name': 'INC-022', 'reporter_email': 'julio.indriago@bold.co', 'report_source': 'Bold Team',
     'creation_time': '2021-07-01T13:36:25', 'stabilization_time': '2021-07-01T15:09:28',
     'close_time': None, 'outage_start_time': '2021-07-01T12:40',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-021', 'reporter_email': 'ricardo.alejo@bold.co', 'report_source': 'Sales Team',
     'creation_time': '2021-06-30T00:51:33', 'stabilization_time': '2021-06-30T02:17:03',
     'close_time': '2021-07-16T18:00:24', 'outage_start_time': '2021-06-29T23:30:00',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-020', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Tech Support',
     'creation_time': '2021-06-25T21:37:09', 'stabilization_time': '2021-07-21T20:51:54',
     'close_time': None, 'outage_start_time': '2021-06-25T20:50:00',
     'team_id': 'bd7f9b31-8bb4-4ea4-886d-02f41ee7adc3'},

    {'name': 'INC-019', 'reporter_email': 'brayan.patino@bold.co', 'report_source': 'Bold Team',
     'creation_time': '2021-06-22T21:07:27', 'stabilization_time': '2021-06-23T16:38:46',
     'close_time': '2021-07-07T18:01:37', 'outage_start_time': '2021-06-22T20:00:00',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-018', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Tech Support',
     'creation_time': '2021-06-22T14:41:12', 'stabilization_time': None,
     'close_time': None, 'outage_start_time': '2021-06-21T08:15:00',
     'team_id': 'f832811c-8a3e-4830-91fe-202a78d8089a'},

    {'name': 'INC-017', 'reporter_email': 'vladimir.vasquez@bold.co', 'report_source': 'Bold Team',
     'creation_time': '2021-06-15T22:32:52', 'stabilization_time': '2021-06-23T14:32:16',
     'close_time': '2021-06-23T19:49:12', 'outage_start_time': '2021-06-15T14:00:00',
     'team_id': '1e1201e3-13a7-4011-bf79-e4279000800a'},

    {'name': 'INC-016', 'reporter_email': 'brayan.patino@bold.co', 'report_source': 'Bold Team',
     'creation_time': '2021-06-15T21:44:18', 'stabilization_time': '2021-07-01T16:36:40',
     'close_time': '2021-07-01T16:36:41', 'outage_start_time': '2021-06-15T13:00:00',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-015', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Alerts',
     'creation_time': '2021-06-11T22:38:40', 'stabilization_time': '2021-06-15T20:38:31',
     'close_time': '2021-06-15T20:39:00', 'outage_start_time': '2021-06-11T10:10:00',
     'team_id': '8ae1631c-3b5e-4cd1-9ece-c10f8a3f560d'},

    {'name': 'INC-014', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Support Channel',
     'creation_time': '2021-06-11T20:25:56', 'stabilization_time': '2021-06-15T21:18:55',
     'close_time': '2021-06-15T21:19:35', 'outage_start_time': '2021-06-11T07:20:00',
     'team_id': 'bd7f9b31-8bb4-4ea4-886d-02f41ee7adc3'},

    {'name': 'INC-013', 'reporter_email': 'vladimir.vasquez@bold.co', 'report_source': 'Alerts',
     'creation_time': '2021-06-08T21:53:16', 'stabilization_time': '2021-06-09T23:24:05',
     'close_time': '2021-06-09T23:24:36', 'outage_start_time': '2021-06-08T14:30:00',
     'team_id': 'bd7f9b31-8bb4-4ea4-886d-02f41ee7adc3'},

    {'name': 'INC-012', 'reporter_email': 'nohora.meneses@bold.co', 'report_source': 'Alerts',
     'creation_time': '2021-06-08T20:47:43', 'stabilization_time': '2021-06-22T16:28:50',
     'close_time': '2021-06-28T21:24:09', 'outage_start_time': '2021-06-08T15:00:00',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-11', 'reporter_email': 'nataly.martinez@bold.co', 'report_source': 'Support Channel',
     'creation_time': '2021-06-02T17:35:32', 'stabilization_time': '2021-06-04T20:53:53',
     'close_time': '2021-06-04T20:54:29', 'outage_start_time': '2021-06-02T15:30:00',
     'team_id': '7f336a05-74da-467f-b77e-973279492033'},

    {'name': 'INC-10', 'reporter_email': 'lina.toquica@bold.co', 'report_source': 'Support Channel',
     'creation_time': '2021-05-26T16:55:27', 'stabilization_time': '2021-05-31T21:38:17',
     'close_time': '2021-05-31T21:38:27', 'outage_start_time': '2021-05-26T15:20:00',
     'team_id': 'bd7f9b31-8bb4-4ea4-886d-02f41ee7adc3'},

    {'name': 'INC-09', 'reporter_email': 'santiago.duque@bold.co', 'report_source': 'Final User',
     'creation_time': '2021-04-15T13:45:00', 'stabilization_time': '2021-05-20T20:32:07',
     'close_time': '2021-05-20T20:32:38', 'outage_start_time': '2021-04-15T13:45:00',
     'team_id': 'bd7f9b31-8bb4-4ea4-886d-02f41ee7adc3'}
]

# for incident in incidents:
# send_created_incident_quality_event(name=incident.get("name"),
#                                     reporter_email=incident.get("reporter_email"),
#                                     report_source=incident.get("report_source"),
#                                     team_id=incident.get("team_id"),
#                                     creation_time=incident.get("creation_time"))
# if incident.get("stabilization_time"):
#     send_stabilized_incident_quality_event(name=incident.get("name"),
#                                            stabilization_time=incident.get("stabilization_time"))

# if incident.get("close_time") and incident.get("outage_start_time"):
# print(f"{incident.get('name')} must be closed")
# send_closed_incident_quality_event(name=incident.get("name"),
#                                    close_time=incident.get("close_time"),
#                                    outage_start_time=incident.get("outage_start_time"))
