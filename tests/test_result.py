import unittest
import mock
from core.result import QueryResult, QueryResultError, set_query_results_from_configuration
from gcpcore.gcpservicequery import GcpServiceQuery


class QueryResultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.queryresult = QueryResult()

    def test_add_resource_success(self):
        self.queryresult.add_resource("test-resource")
        self.assertIn("test-resource", self.queryresult.resources)
        self.assertIsInstance(self.queryresult.resources["test-resource"], dict)

    def test_add_resource_resource_already_there(self):
        self.queryresult.add_resource("test-resource")
        with self.assertRaises(QueryResultError) as cm:
            self.queryresult.add_resource("test-resource")
        self.assertEqual(f"Resource 'test-resource' is already added in results", str(cm.exception))

    def test_add_result(self):
        self.queryresult.add_result(resource_name="test_resource", project_id="test_projectID", result=test_result)
        resources = self.queryresult.resources
        self.assertIn("test_resource", resources)
        projects = resources["test_resource"]
        self.assertIn("test_projectID", projects)
        self.assertIs(test_result, projects["test_projectID"])

    def test_get_results_existing(self):
        self.queryresult.add_result(resource_name="test_resource", project_id="test_projectID", result=test_result)
        existing_result = self.queryresult.get_result(resource_name="test_resource", projectId="test_projectID")
        self.assertIs(test_result, existing_result)

    def test_get_results_no_resource(self):
        result = self.queryresult.get_result(resource_name="non-existing", projectId="test_project")
        self.assertIsNone(result)

    def test_get_results_no_project(self):
        self.queryresult.add_result(resource_name="test_resource", project_id="test_projectID", result=test_result)
        result = self.queryresult.get_result(resource_name="test_resource", projectId="non_existing")
        self.assertIsNone(result)

    def test_set_query_results_from_configuration_no_queris(self):
        mock_gcpservicequery = mock.MagicMock(spec=GcpServiceQuery)
        mock_gcpservicequery.queries = {}
        test_gcp_services = {
            "test_serviceName": mock_gcpservicequery
        }
        with self.assertRaises(QueryResultError) as cm:
            set_query_results_from_configuration(test_gcp_services)
        self.assertEqual("No queries configured for service 'test_serviceName'", str(cm.exception))

    def test_set_query_results_from_configuration_success(self):
        mock_gcpservicequery = mock.MagicMock(spec=GcpServiceQuery)
        mock_gcpservicequery.queries = {"test_resource": "query_configuration"}
        test_gcp_services = {
            "test_serviceName": mock_gcpservicequery
        }
        result = set_query_results_from_configuration(test_gcp_services)
        self.assertIsInstance(result, QueryResult)
        resources = result.resources
        self.assertIn("test_resource", result.resources)
        projects = resources["test_resource"]
        self.assertEqual(len(projects), 0)

    @mock.patch("core.result.isdir")
    def test_dump_results_not_directory(self, mock_isdir):
        mock_isdir.return_value = False
        with self.assertRaises(QueryResultError) as cm:
            self.queryresult.dump_results("test_directory")
        self.assertEqual("Issue dumping results to files. Directory 'test_directory' doesn't exist",
                         str(cm.exception))

    @mock.patch("core.result.Path")
    @mock.patch("core.result.isdir")
    def test_dump_results_issue_creating_subdirectory(self, mock_isdir, mock_path):
        mock_isdir.return_value = True
        mock_mkdir = mock.MagicMock()
        mock_mkdir.mkdir.side_effect = Exception("Issue creating test directory")
        mock_path.return_value = mock_mkdir
        self.queryresult.add_result(resource_name="test_resource", project_id="test_project", result=test_result)
        with self.assertRaises(QueryResultError) as cm:
            self.queryresult.dump_results("test_directory")
        self.assertEqual("Issue creating directory 'test_directory/test_resource'",
                         str(cm.exception))

    @mock.patch("builtins.open")
    @mock.patch("core.result.Path")
    @mock.patch("core.result.isdir")
    def test_dump_results_issue_creating_files(self, mock_isdir, mock_path, mock_open):
        mock_isdir.return_value = True
        mock_open.side_effect = Exception("issue opening file")
        self.queryresult.add_result(resource_name="test_resource", project_id="test_project", result=test_result)
        with self.assertRaises(QueryResultError) as cm:
            self.queryresult.dump_results("test_directory")
        self.assertEqual("Issue dumping results into file 'test_directory/test_resource/test_project.yaml",
                         str(cm.exception))

    @mock.patch("core.result.yaml.dump")
    @mock.patch("builtins.open")
    @mock.patch("core.result.Path")
    @mock.patch("core.result.isdir")
    def test_dump_results_issue_creating_files(self, mock_isdir, mock_path, mock_b_open, mock_dump):
        mock_isdir.return_value = True
        mock_temp = mock.MagicMock()
        mock_fh = mock.MagicMock()
        mock_fh.__enter__.return_value = mock_temp
        mock_b_open.return_value = mock_fh
        self.queryresult.add_result(resource_name="test_resource", project_id="test_project", result=test_result)
        self.queryresult.dump_results("test_directory")
        mock_b_open.assert_called_with("test_directory/test_resource/test_project.yaml", "w")
        mock_dump.assert_called_with(test_result, mock_temp, default_flow_style=False)

    @mock.patch("core.result.yaml.dump")
    @mock.patch("builtins.open")
    @mock.patch("core.result.Path")
    @mock.patch("core.result.isdir")
    def test_dump_results_empty_list_result(self, mock_isdir, mock_path, mock_b_open, mock_dump):
        mock_isdir.return_value = True
        mock_temp = mock.MagicMock()
        mock_fh = mock.MagicMock()
        mock_fh.__enter__.return_value = mock_temp
        mock_b_open.return_value = mock_fh
        self.queryresult.add_result(resource_name="test_resource", project_id="test_project", result=[])
        self.queryresult.dump_results("test_directory")
        mock_b_open.assert_not_called()
        mock_dump.assert_not_called()


if __name__ == '__main__':
    unittest.main()

test_result = [
    {"entry_name": "test_1"},
    {"entry_name": "test_2"}
]

test_gcp_services = {
    "test_serviceName": mock.MagicMock(spec=GcpServiceQuery)
}
