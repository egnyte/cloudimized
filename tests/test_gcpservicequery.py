import unittest
import mock

from cloudimized.gcpcore.gcpservicequery import GcpServiceQuery, configure_services
from cloudimized.gcpcore.gcpservicequery import GcpServiceQueryError, GcpServiceQueryConfigError


class GcpServiceQueryTestCase(unittest.TestCase):
    def setUp(self):
        self.gcpservice = GcpServiceQuery(serviceName="compute", version="v1")
        test_queries = {
            "test_resource": mock.MagicMock()
        }
        self.gcpservice.queries = test_queries

    def testBuild_no_queries(self):
        with self.assertRaises(GcpServiceQueryError) as cm:
            self.gcpservice.queries = {}
            self.gcpservice.build()
        self.assertEqual(f"Queries not configured for service compute", str(cm.exception))

    @mock.patch("cloudimized.gcpcore.gcpservicequery.google.auth")
    @mock.patch("cloudimized.gcpcore.gcpservicequery.discovery")
    @mock.patch("cloudimized.gcpcore.gcpservicequery.getenv")
    def testBuild(self, mock_getenv, mock_discovery, mock_auth):
        self.gcpservice.queries
        mock_getenv.return_value = "/creds/secret.file"
        mock_discovery.build.return_value = mock.MagicMock()
        self.gcpservice.build()
        mock_getenv.assert_called_with("GOOGLE_APPLICATION_CREDENTIALS")
        mock_discovery.build.assert_called_with(self.gcpservice.serviceName,
                                                self.gcpservice.version)

        mock_getenv.reset_mock(return_value=True, side_effect=True)
        mock_discovery.reset_mock(return_value=True, side_effect=True)
        mock_getenv.return_value = None
        mock_auth.default.return_value = (mock.MagicMock(), mock.MagicMock())
        self.gcpservice.build()
        mock_auth.default.assert_called_with(scopes=["https://googleapis.com/auth/cloud-platform"])
        mock_discovery.build.assert_called_with(self.gcpservice.serviceName,
                                                self.gcpservice.version,
                                                credentials=mock.ANY)

    def test_configure_services(self):
        # Config needs to be list
        with self.assertRaises(GcpServiceQueryConfigError):
            configure_services("invalid argument")
        # Each entry in list need to be dict
        with self.assertRaises(GcpServiceQueryConfigError):
            configure_services(test_queries_config_incorrect_entry_type)
        # Each entry needs to have required keys
        with self.assertRaises(GcpServiceQueryConfigError):
            configure_services(test_queries_config_incorrect_entry_details)

        correct_result = configure_services(test_queries_config_correct)
        self.assertIsInstance(correct_result, dict)
        self.assertEqual(len(correct_result), 2)
        for key, value in correct_result.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, GcpServiceQuery)


if __name__ == '__main__':
    unittest.main()

test_queries_compute = [
    {
        "resource": "network",
        "gcp_call": "network",  # this for now point to serviceMap
        "field_exclude_filter": ["creationTimestamp"],
        "gcp_function_args": {
            "project": "<PROJECT_ID>"
        }
    },
    {
        "resource": "staticRoute",
        "gcp_call": "staticRoute",  # this for now point to serviceMap
        "field_exclude_filter": ["creationTimestamp"],
        "gcp_function_args": {
            "project": "<PROJECT_ID>"
        }
    },
    {
        "resource": "project",
        "gcp_call": "project",
    }
]

test_queries_project = [
    {
        "resource": "project",
        "gcp_call": "project",
        "gcp_function_args": {
            "project": "<PROJECT_ID>"
        }
    }
]

test_queries_config_correct = [
    {
        "serviceName": "compute",
        "version": "v1",
        "queries": test_queries_compute
    },
    {
        "serviceName": "project",
        "version": "v1",
        "queries": test_queries_project
    }
]

test_queries_config_incorrect_entry_type = [
    {
        "valid": "valid"
    },
    "invalid"
]

test_queries_config_incorrect_entry_details = [
    {
        "serviceName": "test",
        "version": "test",
        "queries": []
    },
    {
        "test": [
            {
                "requiredKey": "missing"
            }
        ]
    }
]
