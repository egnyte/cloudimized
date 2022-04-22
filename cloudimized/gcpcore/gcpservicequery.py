import logging
import google.auth
import google.auth.transport.requests
import google_auth_httplib2
import httplib2
from googleapiclient.discovery import Resource

from os import getenv
from typing import List, Dict
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
        self.queries = {}

    def build(self) -> Resource:
        """Build resource for interacting with Google Cloud API"""
        if getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            logger.info("Env var 'GOOGLE_APPLICATION_CREDENTIALS' set. Authenticating using credentials file")
        else:
            logger.info("Env var 'GOOGLE_APPLICATION_CREDENTIALS' not set. Authenticating using default credentials")

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        authorized_http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=60))
        service = discovery.build(self.serviceName,
                                  self.version,
                                  http=authorized_http)
        return service


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
