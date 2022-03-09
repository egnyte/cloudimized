import unittest
import mock
import datetime as dt

import time_machine

from cloudimized.tfcore.query import TFQuery, TFQueryError, TFQueryConfigurationError, configure_tfquery
import cloudimized.tfcore.query as q
from cloudimized.tfcore.run import TFRun

class TFQueryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tf_query = TFQuery("https://terraform.test", test_sa_org_workspace_map, test_org_token_map)

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 40))
    def test_unknown_service_account(self):
        with self.assertRaises(TFQueryError):
            self.tf_query.get_runs("unknown_sa")

    #Query resolving workspace name to id fails
    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 40))
    @mock.patch("cloudimized.tfcore.query.TFC")
    def test_workspace_id_fail(self, mock_tfc):
        mock_tf_api = mock.MagicMock()
        mock_tf_api.workspaces.show.side_effect = Exception()
        mock_tfc.return_value = mock_tf_api
        with self.assertRaises(TFQueryError):
            self.tf_query.get_runs("sa-test-project1")
        mock_tf_api.workspaces.show.assert_called_with(workspace_name="test_workspace1")

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 40))
    @mock.patch("cloudimized.tfcore.query.TFC")
    def test_runs_list_fail(self, mock_tfc):
        mock_workspace_response = mock.MagicMock()
        mock_workspace_response.__getitem__.side_effect = test_workspace_response.__getitem__
        mock_tf_api = mock.MagicMock()
        mock_tf_api.workspaces.show.return_value = mock_workspace_response
        mock_tf_api.runs.list.side_effect = Exception()
        mock_tfc.return_value = mock_tf_api
        with self.assertRaises(TFQueryError):
            self.tf_query.get_runs("sa-test-project1")
        mock_tf_api.workspaces.show.assert_called_with(workspace_name="test_workspace1")
        mock_tf_api.runs.list.assert_called_with("id_test_workspace1", page_size=10, include=["created-by"])

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 40))
    @mock.patch("cloudimized.tfcore.query.parse_tf_runs")
    @mock.patch("cloudimized.tfcore.query.TFC")
    def test_runs_parse_fails(self, mock_tfc, mock_parse):
        mock_workspace_response = mock.MagicMock()
        mock_workspace_response.__getitem__.side_effect = test_workspace_response.__getitem__
        mock_tf_api = mock.MagicMock()
        mock_tf_api.workspaces.show.return_value = mock_workspace_response
        mock_tf_api.runs.list.return_value = test_runs_response
        mock_tf_api.get_org.return_value = "test_org1"
        mock_tfc.return_value = mock_tf_api
        mock_parse.side_effect = Exception()
        with self.assertRaises(TFQueryError):
            self.tf_query.get_runs("sa-test-project1")
        mock_tf_api.workspaces.show.assert_called_with(workspace_name="test_workspace1")
        mock_tf_api.runs.list.assert_called_with("id_test_workspace1", page_size=10, include=["created-by"])
        mock_parse.assert_called_with(test_runs_response, "test_org1", "test_workspace1")

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 40))
    @mock.patch("cloudimized.tfcore.query.parse_tf_runs")
    @mock.patch("cloudimized.tfcore.query.TFC")
    def test_runs_success(self, mock_tfc, mock_parse):
        mock_workspace_response = mock.MagicMock()
        mock_workspace_response.__getitem__.side_effect = test_workspace_response.__getitem__
        mock_tf_api = mock.MagicMock()
        mock_tf_api.workspaces.show.return_value = mock_workspace_response
        mock_tf_api.runs.list.return_value = test_runs_response
        mock_tf_api.get_org.return_value = "test_org2"
        mock_tfc.return_value = mock_tf_api
        mock_parse.return_value = test_get_runs_result
        result = self.tf_query.get_runs("sa-test-project2")

        calls_workspace_show = [
            mock.call(workspace_name="test_workspace2"),
            mock.call(workspace_name="test_workspace3")
        ]
        calls_runs_list = [
            mock.call("id_test_workspace1", page_size=10, include=["created-by"]),
            mock.call("id_test_workspace1", page_size=10, include=["created-by"])
        ]
        calls_parse = [
            mock.call(test_runs_response, "test_org2", "test_workspace2"),
            mock.call(test_runs_response, "test_org2", "test_workspace3")
        ]

        mock_tf_api.workspaces.show.assert_has_calls(calls_workspace_show, any_order=True)
        mock_tf_api.runs.list.assert_has_calls(calls_runs_list)
        mock_parse.assert_has_calls(calls_parse)

        self.assertIsInstance(result, list)
        #Only 2 elements in list
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].message, "test-message1")
        self.assertEqual(result[1].message, "test-message3")
        self.assertEqual(result[2].message, "test-message1")
        self.assertEqual(result[3].message, "test-message3")


    @mock.patch("cloudimized.tfcore.query.getenv")
    @mock.patch("cloudimized.tfcore.query.TFQuery", spec=TFQuery)
    @mock.patch("cloudimized.tfcore.query.json.load")
    @mock.patch("builtins.open")
    def test_configure_tfquery(self, mock_open, mock_json_load, mock_tfquery, mock_getenv):
        mock_json_load.return_value = token_file_correct_data
        # No terraform configuration
        self.assertIsNone(configure_tfquery(None))

        # Incorrect type
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config="incorrect type")

        # Missing keys
        ## url
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={})
        ## service account workspace map
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url"
            })
        ## token file
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {}
            })

        # Incorrect value
        ## url
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: 0, #incorrect type
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ## service workspace map
        ### type
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: "incorrect type",
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ### key in map
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {
                    1: {}
                },
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ### value in map
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {
                    "test": "incorrect_value"
                },
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ### missing required key arg in map
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {
                    "test_sa_1": {
                        "org": "test_org" # missing workspace
                    }
                },
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ### incorrect type of required args workspace
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {
                    "test_sa_1": {
                        "org": "test_org",
                        "workspace": 1
                    }
                },
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ### incorrect type of required args org
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {
                    "test_sa_1": {
                        "org": 1,
                        "workspace": "test_workspace"
                    }
                },
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test_file"
            })
        ## token file
        ### type
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: 0 #incorrect type
            })
        ### issue opening file
        mock_open.side_effect = Exception("open issue")
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: "test/file"
            })
        ### issue loading json file
        mock_open.side_effect = None
        mock_json_load.side_effect = Exception("load issue")
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: 'test/file'
            })
        ## issue with token file structure
        ### incorrect key
        mock_open.side_effect = None
        mock_json_load.side_effect = None
        mock_json_load.return_value = token_file_incorrect_key
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: 'test/file'
            })
        mock_json_load.return_value = token_file_incorrect_value
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {},
                q.TERRAFORM_WORKSPACE_TOKEN_FILE: 'test/file'
            })

        ### no token file in config and env var
        mock_open.side_effect = None
        mock_json_load.side_effect = None
        mock_json_load.return_value = token_file_incorrect_key
        with self.assertRaises(TFQueryConfigurationError):
            configure_tfquery(config={
                q.TERRAFORM_URL: "test_url",
                q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: {}
            })

        # Correct data
        mock_json_load.return_value = token_file_correct_data
        result = configure_tfquery(config={
            q.TERRAFORM_URL: "test_url",
            q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: test_sa_org_workspace_map,
            q.TERRAFORM_WORKSPACE_TOKEN_FILE: 'test/file'
        })
        self.assertIsInstance(result, TFQuery)
        mock_tfquery.assert_called_with("test_url", test_sa_org_workspace_map, token_file_correct_data)

        # Correct data with env var
        mock_json_load.return_value = token_file_correct_data
        mock_getenv.return_value = 'test/file'
        result = configure_tfquery(config={
            q.TERRAFORM_URL: "test_url",
            q.TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP: test_sa_org_workspace_map
        })
        self.assertIsInstance(result, TFQuery)
        mock_tfquery.assert_called_with("test_url", test_sa_org_workspace_map, token_file_correct_data)




if __name__ == '__main__':
    unittest.main()

test_sa_org_workspace_map = {
    "sa-test-project1": {
        "org": "test_org1",
        "workspace": ["test_workspace1"]
    },
    "sa-test-project2": {
        "org": "test_org2",
        "workspace": ["test_workspace2", "test_workspace3"]
    }
}

test_org_token_map = {
    "test_org1": "secret_token1",
    "test_org2": "secret_token2"
}

test_workspace_response = {
    "data": {
        "id": "id_test_workspace1"
    }
}

test_runs_response = {
    "data": "test"
}

token_file_incorrect_key = {
    1: "incorrect key"
}

token_file_incorrect_value = {
    "key": 1
}

token_file_correct_data = {
    "test_org_1": "test_token_1",
    "test_org_2": "test_token_2"
}

test_get_runs_result = [
    TFRun("test-message1",
          "test-id1",
          "applied",
          dt.datetime.strptime("1985-10-26T01:24:00", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
    TFRun("test-message3",
          "test-id3",
          "errored",
          dt.datetime.strptime("1985-10-26T01:29:00", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
    TFRun("test-message4",
          "test-id4",
          "applied",
          dt.datetime.strptime("1985-10-25T01:22:00", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace")
]
