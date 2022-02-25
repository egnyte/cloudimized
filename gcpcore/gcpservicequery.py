import logging
import google.auth
import google.auth.transport.requests
from .gcpquery import GcpQuery

from os import getenv
from typing import List, Dict
from itertools import filterfalse
from googleapiclient import discovery

logger = logging.getLogger(__name__)

SERVICE_SECTION = "services"
SERVICE_NAME = "serviceName"
VERSION = "version"
QUERIES = "queries"
RETRIES = "retries"

PROJECTS_DISCOVERY_SERVICE_NAME = "cloudresourcemanager"
PROJECTS_DISCOVERY_SERVICE_CONFIG = [
    {
        SERVICE_NAME: PROJECTS_DISCOVERY_SERVICE_NAME,
        VERSION: "v1",
        QUERIES: [

        ]
    }
]


class GcpServiceQuery:
    """Class describing GCP API service and its queries"""

    def __init__(self, serviceName: str, version: str):
        """
        :param serviceName: GCP service API name
        :param version: GCP API version
        :param num_retries: number of retries for each request
        """
        self.serviceName = serviceName
        self.version = version
        self.service = None
        self.queries = {}

    def build(self) -> None:
        """Build resource for interacting with Google Cloud API"""
        if not self.queries:
            raise GcpServiceQueryError(f"Queries not configured for service {self.serviceName}")
        if getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            logger.info(f"Authenticating using GOOGLE_APPLICATION_CREDENTIALS env var")
            self.service = discovery.build(self.serviceName,
                                           self.version) #TODO: exception handling
        else:
            logger.info(f"Authenticating using Google's Application Default Credentials (ADC)")
            credentials, project = google.auth.default(scopes=["https://googleapis.com/auth/cloud-platform"])
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            self.service = discovery.build(self.serviceName,
                                           self.version,
                                           credentials=credentials)
        # Set GCP service object in all queries
        for _, query in self.queries.items():
            query.service = self.service


def configure_services(config: List[Dict]) -> Dict[str, GcpServiceQuery]:
    """
    Generate GcpServiceQuery list from config
    :param config: list with GcpServieQuery's configuration
    :return: mapping of service name to GcpServiceQuery objects
    """
    if not isinstance(config, list):
        raise GcpServiceQueryConfigError(f"Invalid GcpServiceQuery config {config}")
    result = {}
    for entry in config:
        if not isinstance(entry, dict):
            raise GcpServiceQueryConfigError(f"Invalid GcpServiceQuery entry type: '{entry}'. "
                                             f"Should be dict, is {type(entry)}")
        serviceName = entry.get(SERVICE_NAME, None)
        version = entry.get(VERSION, None)
        queries = entry.get(QUERIES, None)
        if not serviceName or not version or not queries:
            raise GcpServiceQueryConfigError(f"Missing required key for entry {entry}")
        gcp_service_query = GcpServiceQuery(serviceName, version)
        # Check multiple entries with same name
        if serviceName in result:
            raise GcpServiceQueryConfigError(f"Multiple GCP service with same name: {serviceName}")
        result[serviceName] = gcp_service_query
    return result


class GcpServiceQueryError(Exception):
    pass


class GcpServiceQueryConfigError(GcpServiceQueryError):
    pass
