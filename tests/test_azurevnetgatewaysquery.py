import logging
import unittest
import mock
from cloudimized.azurecore.azurequery import AzureQueryError
from cloudimized.azurecore.vnetgatewaysquery import VnetGatewaysQuery

class AzureVnetGatewaysQueryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = mock.patch("cloudimized.azurecore.vnetgatewaysquery.NetworkManagementClient")
        self.mock_client = self.patcher.start()

        logging.disable(logging.WARNING)
        self.query = VnetGatewaysQuery(
            resource_name="test_name"
        )
        mock_result_1 = mock.MagicMock()
        mock_result_2 = mock.MagicMock()
        mock_result_1.as_dict.return_value = result_resource_1
        mock_result_2.as_dict.return_value = result_resource_2
        self.mock_client.return_value.virtual_network_gateways.list.side_effect = [
            iter([mock_result_2]),
            iter([mock_result_1])
        ]

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)
        self.patcher.stop()

    def testArguments(self):
        #TODO
        pass

    def testExecute(self):
        result = self.query.execute(credentials="test_creds",
                                    subscription_id="test_subs_id",
                                    resource_groups=["test_rg_1", "test_rg_2"])

        self.mock_client.assert_called_with(credential="test_creds",
                                            subscription_id="test_subs_id")
        api_calls = [
            mock.call(resource_group_name="test_rg_1"),
            mock.call(resource_group_name="test_rg_2")
        ]
        self.mock_client.return_value.virtual_network_gateways.list.assert_has_calls(api_calls)

        self.assertIsInstance(result, list)
        self.assertListEqual(result, query_result_expected)

    def testExecute_query_fail(self):
        self.mock_client.return_value.virtual_networks.list_all.side_effect = Exception("test")
        with self.assertRaises(AzureQueryError):
            self.query.execute(credentials="test_creds",
                               subscription_id="test_subs_id",
                               resource_groups=None)

    def testExecute_serializing_fail(self):
        mock_raw_result = self.mock_client.return_value.virtual_networks.list_all.return_value
        mock_raw_result.__iter__.side_effect = Exception("test")
        with self.assertRaises(AzureQueryError):
            self.query.execute(credentials="test_creds",
                               subscription_id="test_subs_id",
                               resource_groups=None)
        self.mock_client.assert_called_with(credential="test_creds", subscription_id="test_subs_id")

if __name__ == '__main__':
    unittest.main()

result_resource_1 = {
    "name": "test1",
    "test_str_key": "test_str_value",
    "test_list_key": ["test_value1, test_value2"],
    "test_dict_key": {
        "test_inner_key": "test_inner_value",
        "test_inner_list": ["test_inner_value1", "test_inner_value2"]
    }
}

result_resource_2 = {
    "name": "test2",
    "test_str_key": "test_str_value",
    "test_list_key": ["test_value1, test_value2"],
    "test_dict_key": {
        "test_inner_key": "test_inner_value",
        "test_inner_list": ["test_inner_value1", "test_inner_value2"]
    }
}

query_result_expected = [
    result_resource_1,
    result_resource_2
]
