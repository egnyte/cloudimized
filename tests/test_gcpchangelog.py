import logging
import unittest
import mock
import datetime as dt

import time_machine

from cloudimized.gcpcore.gcpchangelog import GcpChangeLog, getChangeLogs


class GcpChangeLogTestCase(unittest.TestCase):
    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24)) #This is needed to mock datetime
    def setUp(self):
        logging.disable(logging.WARNING)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    # @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24)) #This is needed to mock datetime
    @mock.patch("cloudimized.gcpcore.gcpchangelog.gcp_logging")
    def testAllFields(self, mock_gcp_logging):
        # Mock GcpQuery object
        gcp_query = mock.MagicMock()
        type(gcp_query).gcp_log_resource_type = mock.PropertyMock(return_value="gce_route")
        type(gcp_query).resource_name = mock.PropertyMock(return_value="route")

        # Mock entry.to_api_repr()
        mock_gcp_log_entry = mock.MagicMock()
        mock_gcp_log_entry.to_api_repr.return_value = test_entry_to_api
        # Mock gcp_logging.Client, gcp_logger.list_entries
        # Complex return value needed for 'next(entries.pages)'
        type(mock_gcp_logging.Client.return_value.list_entries.return_value).pages =\
            mock.PropertyMock(return_value=iter([[mock_gcp_log_entry]]))
        result = getChangeLogs(project='test-project',
                               gcp_query=gcp_query,
                               change_time=dt.datetime.utcnow(),
                               time_window=30)
        expected_gcpchangelog = [GcpChangeLog(
            resourceName="projects/test-project-123/global/routes/test-route",
            resourceType="gce_route",
            changer="user@example.com",
            timestamp=dt.datetime.strptime("1985-10-26T01:15:58", "%Y-%m-%dT%H:%M:%S"),
            methodName="v1.compute.routes.delete",
            requestType="type.googleapis.com/compute.routes.delete")]
        self.assertEqual(expected_gcpchangelog, result)


    # @time_machine.travel(dt.datetime(1985,10,26,1,24))
    @mock.patch("cloudimized.gcpcore.gcpchangelog.gcp_logging")
    def testEmptyFields(self, mock_gcp_logging):
        # Mock GcpQuery object
        gcp_query = mock.MagicMock()
        type(gcp_query).gcp_log_resource_type = mock.PropertyMock(return_value="gce_route")
        type(gcp_query).resource_name = mock.PropertyMock(return_value="route")

        # Mock entry.to_api_repr()
        mock_gcp_log_entry = mock.MagicMock()
        mock_gcp_log_entry.to_api_repr.return_value = test_entry_empty_fields
        # Mock gcp_logging.Client, gcp_logger.list_entries
        # Complex return value needed for 'next(entries.pages)'
        type(mock_gcp_logging.Client.return_value.list_entries.return_value).pages =\
            mock.PropertyMock(return_value=iter([[mock_gcp_log_entry]]))
        result = getChangeLogs(project='test-project',
                               gcp_query=gcp_query,
                               change_time=dt.datetime.utcnow(),
                               time_window=30)
        expected_gcpchangelog = [GcpChangeLog (
            resourceName=None,
            resourceType=None,
            changer=None,
            timestamp=None,
            methodName=None,
            requestType=None)]
        self.assertEqual(expected_gcpchangelog, result)

#TODO Add a test that verifies there was a call with proper filter string




test_entry_to_api = {
    'logName': 'projects/test-project/logs/cloudaudit.googleapis.com%2Factivity',
    'resource': {
        'type': 'gce_route',
        'labels': {
            'project_id': 'test-project-123',
            'route_id': '0000000000000000000'
        }
    },
    'insertId': '000000aaaaaa',
    'severity': 'NOTICE',
    'timestamp': '1985-10-26T01:15:58.465104Z',
    'operation': {
        'id': 'operation-11111111111111-1111111111111-1111111-11111',
        'producer': 'compute.googleapis.com',
        'last': True
    },
    'protoPayload': {
        '@type': 'type.googleapis.com/google.cloud.audit.AuditLog',
        'authenticationInfo': {
            'principalEmail': 'user@example.com'
        },
        'requestMetadata': {
            'callerIp': '8.8.8.8',
            'callerSuppliedUserAgent': 'TestAgentChrome'
        },
        'serviceName': 'compute.googleapis.com',
        'methodName': 'v1.compute.routes.delete',
        'resourceName': 'projects/test-project-123/global/routes/test-route',
        'request': {
            '@type': 'type.googleapis.com/compute.routes.delete'
        }
    }
}

test_entry_empty_fields = {}
