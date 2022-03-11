import logging

from typing import List
from datetime import datetime, timedelta
from cloudimized.gcpcore.gcpquery import GcpQuery
from google.cloud import logging as gcp_logging

logger = logging.getLogger(__name__)


class GcpChangeLog:
    """Individual GCP Log entry representing resource change"""

    def __init__(self, resourceName: str, resourceType: str, changer: str, timestamp: datetime,
                 methodName: str, requestType: str):
        """
        :param resourceName: GCP Resource name
        :param resourceType: GCP Resource type
        :param changer: Identity of changer
        :param timestamp: Timestamp of configuration change
        :param methodName: GCP method name for configuration change
        :param requestType: GCP request type for configuration change
        """
        self.resourceName = resourceName
        self.resourceType = resourceType
        self.changer = changer
        self.timestamp = timestamp
        self.methodName = methodName
        self.requestType = requestType

    def __eq__(self, other):
        # return True
        return self.resourceName == other.resourceName and \
            self.resourceType == other.resourceType and \
            self.changer == other.changer and \
            self.timestamp == other.timestamp and \
            self.methodName == other.methodName and \
            self.requestType == other.requestType

    def __repr__(self):
        return (f"{self.resourceName} {self.resourceType} {self.changer} "
                f"{self.timestamp} {self.methodName} {self.requestType}")


def getChangeLogs(project: str,
                  gcp_query: GcpQuery,
                  change_time: datetime = None,
                  time_window: int = 30) -> List[GcpChangeLog]:
    """
    :param project: GCP project ID in which query logs
    :param gcp_query: GCP Query for which identify change author
    :param change_time: point in time from which to look for change
    :param time_window: size of time window to look for change (in minutes)
    :return:
    """
    # Filter string to be used in GCP Logs Explorer
    if not change_time:
        change_time = datetime.utcnow()
    start_time = (change_time - timedelta(minutes=time_window)).strftime("%Y-%m-%dT%H:%M:%S")
    filter_str = (f'timestamp>="{start_time}" AND '
                  f'logName: "cloudaudit.googleapis.com" AND '
                  f'logName: "activity" AND '
                  f'resource.type="{gcp_query.gcp_log_resource_type}" AND '
                  f'NOT protoPayload.response.@type="type.googleapis.com/error"')
    # Running GCP query
    changeLogs = []
    gcp_logger = gcp_logging.Client(project=project, _use_grpc=0)  # This fixes pagination issue
    entries = gcp_logger.list_entries(filter_=filter_str, page_size=6, order_by=gcp_logging.DESCENDING)
    for entry in next(entries.pages):
        change_log = entry.to_api_repr()
        resourceName = change_log.get("protoPayload", {}).get("resourceName", None)
        resourceType = change_log.get("resource", {}).get("type", None)
        changer = change_log.get("protoPayload", {}).get("authenticationInfo", {}).get("principalEmail", None)
        methodName = change_log.get("protoPayload", {}).get("methodName", None)
        requestType = change_log.get("protoPayload", {}).get("request", {}).get("@type", None)
        try:
            timestamp = datetime.strptime(change_log["timestamp"].split(".")[0], "%Y-%m-%dT%H:%M:%S")
        except:
            logger.warning(f"Issue parsing GCP log timestamp for resource '{resourceName}' for project "
                           f"{project}")
            timestamp = None
        changeLogs.append(GcpChangeLog(resourceName,
                                       resourceType,
                                       changer,
                                       timestamp,
                                       methodName,
                                       requestType))
    return changeLogs
