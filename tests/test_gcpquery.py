import logging
import unittest
import mock
from copy import deepcopy
from cloudimized.gcpcore.gcpquery import GcpQuery, GcpQueryError, GcpQueryArgumentError, configure_queries, logger


class GcpQueryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.query = GcpQuery(resource_name="test_name",
                              api_call=None,
                              gcp_log_resource_type=None,
                              result_items_field="items",
                              project="<PROJECT_ID>")
        self.test_config = test_queries_compute[:]
        self.query_response_multiple_items = deepcopy(query_response_multiple_items_org)
        #TODO deepcopy of all test data dict

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def testArguments(self):
        # Test argument conflict
        with self.assertRaises(GcpQueryArgumentError) as cm:
            GcpQuery(resource_name="test_name",
                     api_call=None,
                     gcp_log_resource_type=None,
                     result_items_field="items",
                     field_exclude_filter=["test"],
                     field_include_filter=["test"])
        self.assertEqual(f"Issue for resource_name test_name field_include_filter and "
                         f"field_exclude_filter are mutually exclusive", str(cm.exception))

        # Test lack of argument conflict
        GcpQuery(resource_name="test_name",
                 api_call=None,
                 gcp_log_resource_type=None,
                 result_items_field="items",
                 field_include_filter=["test"])
        GcpQuery(resource_name="test_name",
                 api_call=None,
                 gcp_log_resource_type=None,
                 result_items_field="items",
                 field_exclude_filter=["test"])

    def testExecute_no_service(self):
        mock_service = None
        with self.assertRaises(GcpQueryError) as cm:
            self.query.execute(service=mock_service, project_id="no-project")
        self.assertEqual(f"Service not set for '{self.query.resource_name}'", str(cm.exception))

    def testExecute_non_default_items_field(self):
        query = GcpQuery(resource_name="test_projects",
                         api_call="projects.list",
                         gcp_log_resource_type="N/A",
                         result_items_field="clusters")
        mock_service = mock.MagicMock()
        mock_service.projects().list().execute.return_value = {"clusters": ["test"]}
        result = query.execute(service=mock_service, project_id=None)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], "test")
        mock_service.projects().list.assert_called_with()

    def testExecute_missing_items_field(self):
        query = GcpQuery(resource_name="test_projects",
                         api_call="projects.list",
                         gcp_log_resource_type="N/A",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.projects().list().execute.return_value = {"not-items": ["test"]}
        result = query.execute(service=mock_service, project_id=None)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
        mock_service.projects().list.assert_called_with()

    def testExecute_no_kwargs(self):
        query = GcpQuery(resource_name="test_projects",
                         api_call="projects.list",
                         gcp_log_resource_type="N/A",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.projects().list().execute.return_value = {"items": ["test"]}
        result = query.execute(service=mock_service, project_id=None)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], "test")
        mock_service.projects().list.assert_called_with()

    def testExecute_single_kwarg(self):
        query = GcpQuery(resource_name="test_projects",
                         api_call="projects.locations.clusters.list",
                         gcp_log_resource_type="gke_cluster",
                         result_items_field="items",
                         parent=f"projects/<PROJECT_ID>/locations/-")
        mock_service = mock.MagicMock()
        mock_service.projects().locations().clusters().list().execute.return_value = {"items": ["test"]}
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], "test")
        mock_service.projects().locations().clusters().list.assert_called_with(parent="projects/test_project/locations/-")

    def testExecute_multiple_kwargs(self):
        query = GcpQuery(resource_name="test_projects",
                         api_call="globalAddresses.list",
                         gcp_log_resource_type="gce_tocheck",
                         result_items_field="items",
                         project="<PROJECT_ID>",
                         filter="purpose=VPC_PEERING")
        mock_service = mock.MagicMock()
        mock_service.globalAddresses().list().execute.return_value = {"items": ["test"]}
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], "test")
        mock_service.globalAddresses().list.assert_called_with(project="test_project",
                                                               filter="purpose=VPC_PEERING")

    def testExecute_aggregatedList(self):
        query = GcpQuery(resource_name="subnetworks",
                         api_call="subnetworks.aggregatedList",
                         gcp_log_resource_type="gce_subnetwork",
                         result_items_field="items",
                         project="<PROJECT_ID>")
        mock_service = mock.MagicMock()
        mock_service.subnetworks().aggregatedList().execute.return_value = test_aggregatedList_response
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test-subnetwork1")
        self.assertEqual(result[1]["name"], "test-subnetwork2")
        mock_service.subnetworks().aggregatedList.assert_called_with(project="test_project")

    def testExecute_aggregatedList_empty_reply(self):
        query = GcpQuery(resource_name="subnetworks",
                         api_call="subnetworks.aggregatedList",
                         gcp_log_resource_type="gce_subnetwork",
                         result_items_field="items",
                         project="<PROJECT_ID>")
        mock_service = mock.MagicMock()
        mock_service.subnetworks().aggregatedList().execute.return_value = test_aggregatedList_response_empty
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
        mock_service.subnetworks().aggregatedList.assert_called_with(project="test_project")

    def testExecute_aggreagtedList_paged(self):
        query = GcpQuery(resource_name="subnetworks",
                         api_call="subnetworks.aggregatedList",
                         gcp_log_resource_type="gce_subnetwork",
                         result_items_field="items",
                         project="<PROJECT_ID>")
        mock_service = mock.MagicMock()
        mock_service.subnetworks().aggregatedList().execute.side_effect = [test_aggregatedList_response_paged,
                                                                           test_aggregatedList_response]
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertIsInstance(result, list)
        self.assertEqual(6, len(result))
        self.assertEqual(result[0]["name"], "test-subnetwork1")
        self.assertEqual(result[1]["name"], "test-subnetwork2")
        self.assertEqual(result[2]["name"], "test-subnetwork3")
        self.assertEqual(result[3]["name"], "test-subnetwork4")
        self.assertEqual(result[4]["name"], "test-subnetwork5")
        self.assertEqual(result[5]["name"], "test-subnetwork6")
        mock_service.subnetworks().aggregatedList.assert_called_with(project="test_project", pageToken="test_token")

    def testExecute_unsorted_result_issue_sorting(self):
        query = GcpQuery(resource_name="firewalls",
                         api_call="firewalls.list",
                         gcp_log_resource_type="gce_firewall_rule",
                         result_items_field="items",
                         project="<PROJECT_ID>")
        mock_service = mock.MagicMock()
        mock_service.firewalls().list().execute.return_value = test_result_unsorted_with_name_unsortable
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertEqual(result[0]["name"], "zzzz")
        self.assertNotIn("name", result[1])
        self.assertEqual(result[2]["name"], "aaaa")
        mock_service.firewalls().list.assert_called_with(project="test_project")

    def testExecute_unsorted_result(self):
        query = GcpQuery(resource_name="firewalls",
                         api_call="firewalls.list",
                         gcp_log_resource_type="gce_firewall_rule",
                         result_items_field="items",
                         project="<PROJECT_ID>",
                         sort_fields=["name", {"testNestedField": "name"}])
        mock_service = mock.MagicMock()
        mock_service.firewalls().list().execute.return_value = test_result_unsorted_with_name
        result = query.execute(service=mock_service, project_id="test_project")
        self.assertEqual(result[0]["name"], "aaaa")
        self.assertEqual(result[1]["name"], "dddd")
        self.assertEqual(result[2]["name"], "zzzz")
        self.assertEqual(result[0]["testNestedField"][0]["name"], "aaaa")
        self.assertEqual(result[0]["testNestedField"][1]["name"], "bbbb")
        self.assertEqual(result[0]["testNestedField"][2]["name"], "zzzz")
        mock_service.firewalls().list.assert_called_with(project="test_project")

    def testExecute_no_items_in_response(self):
        logging.disable(logging.NOTSET)
        query = GcpQuery(resource_name="firewalls",
                         api_call="firewalls.list",
                         gcp_log_resource_type="gce_firewall_rule",
                         result_items_field="items",
                         project="<PROJECT_ID>")
        mock_service = mock.MagicMock()
        mock_service.firewalls().list().execute.return_value = {"no_items_key": "test"}
        # Workaround to verify that actual warning message was not logged
        # if only dummy is present, then other wasn't logged
        with self.assertLogs(logger, level="WARNING") as cm:
            result = query.execute(service=mock_service, project_id="test_project")
            logger.warning("dummy warning")
        self.assertEqual(["WARNING:cloudimized.gcpcore.gcpquery:dummy warning"], cm.output)
        # self.assertEqual(cm.output, [(f"WARNING:gcpnetscanner.gcpcore.gcpquery:"
        #                               f"Skipping result sorting for API call 'firewalls.list' for project "
        #                              f"'test_project'. Missing default sort key in result 'name'")])
        mock_service.firewalls().list.assert_called_with(project="test_project")

    # def testResultExcludeFilter(self):
    #     query = GcpQuery(resource_name="test_projects",
    #                      service=mock.MagicMock(),
    #                      field_exclude_filter=field_filter,
    #                      api_call="test.call",
    #                      gcp_log_resource_type="test_type",
    #                      result_items_field="items")
    #     mock_service.test().call().execute.return_value = query_response
    #     result = query.execute(service=mock_service, project_id=None)
    #     self.assertEqual(query_exclude_filter_result, result)

    def testResultExcludeFilterNew(self):
        query = GcpQuery(resource_name="test_projects",
                         field_exclude_filter=field_filter_new,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = query_response_k8s
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(query_response_k8s_exclude_filter_expected, result)

    def testResultIncludeFilter(self):
        query = GcpQuery(resource_name="test_projects",
                         field_include_filter=field_filter,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = query_response
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(query_include_filter_result, result)

    def testResultItemFilter(self):
        query = GcpQuery(resource_name="test_projects",
                         item_exclude_filter=item_filters_and_clause,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = self.query_response_multiple_items
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(expected_testResultItemFilter, result)

    def testResultItemFilterList(self):
        query = GcpQuery(resource_name="test_projects",
                         item_exclude_filter=item_filters_list_filtering,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = query_response_items_with_list
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(expected_result_after_filtering, result)

    def testResultItemFilterOrClause(self):
        query = GcpQuery(resource_name="test_projects",
                         item_exclude_filter=item_filters_or_clause,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = query_response_item_filter_or_clause
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(query_response_item_filter_or_clause_after_filtering, result)

    def testResultItemFilterAndOrNested(self):
        query = GcpQuery(resource_name="test_projects",
                         item_exclude_filter=item_filters_nested_and_or_clause,
                         api_call="test.call",
                         gcp_log_resource_type="test_type",
                         result_items_field="items")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = self.query_response_multiple_items
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(expected_testResultItemFilterAndOrNested, result)

    def testFieldAndItemFilter(self):
        query = GcpQuery(resource_name="test_projects",
                         result_items_field="items",
                         item_exclude_filter=item_filters_and_clause,
                         field_exclude_filter=field_filter,
                         api_call="test.call",
                         gcp_log_resource_type="test_type")
        mock_service = mock.MagicMock()
        mock_service.test().call().execute.return_value = self.query_response_multiple_items
        result = query.execute(service=mock_service, project_id=None)
        self.assertEqual(expected_testFieldAndItemFilter, result)

    @mock.patch("cloudimized.gcpcore.gcpquery.GcpQuery", spec=GcpQuery)
    def testConfigureQueries(self, mock_gcpquery):
        with self.assertRaises(GcpQueryArgumentError):
            configure_queries("incorrect type")

        # Actual configure_queries test
        result = configure_queries(test_queries_compute)
        calls = [
            mock.call(resource_name="network",
                      api_call="networks.list",
                      gcp_log_resource_type="gce_network",
                      result_items_field="items",
                      num_retries=3,
                      sort_fields=["name"],
                      field_exclude_filter=["creationTimestamp"],
                      project="<PROJECT_ID>"),
            mock.call(resource_name="staticRoute",
                      api_call="routes.list",
                      gcp_log_resource_type="gce_route",
                      result_items_field="items",
                      num_retries=3,
                      sort_fields=["name"],
                      field_exclude_filter=["creationTimestamp"],
                      project="<PROJECT_ID>"),
            mock.call(resource_name="project",
                      api_call="projects.list",
                      gcp_log_resource_type="N/A",
                      result_items_field="items",
                      num_retries=3,
                      sort_fields=["name", {"testNestedField": "name"}])
        ]
        mock_gcpquery.assert_has_calls(calls)
        self.assertIsInstance(result, dict)
        self.assertIn("network", result)
        self.assertIsInstance(result["network"], GcpQuery)
        self.assertIn("staticRoute", result)
        self.assertIsInstance(result["staticRoute"], GcpQuery)
        self.assertIn("project", result)
        self.assertIsInstance(result["project"], GcpQuery)

#TODO Improve test by checking errors
    def testConfigureQueries_missing_required_param(self):
        with self.assertRaises(GcpQueryArgumentError):
            configure_queries(test_queries_missing_arg)

    def testConfigureQueries_missing_gcp_log_resource_type_param(self):
        del self.test_config[0]["gcp_log_resource_type"]
        with self.assertRaises(GcpQueryArgumentError) as cm:
            configure_queries(self.test_config)
        self.assertEqual("Missing required key: 'gcp_log_resource_type' in query configuration "
                         "'{'resource': 'network', 'gcp_api_call': 'networks.list', "
                         "'field_exclude_filter': ['creationTimestamp'], "
                         "'gcp_function_args': {'project': '<PROJECT_ID>'}}'", str(cm.exception))

    def testConfigureQueries_incorrect_query_type(self):
        with self.assertRaises(GcpQueryArgumentError):
            configure_queries(test_queries_incorrect_type)


if __name__ == '__main__':
    unittest.main()

field_filter = ["creationTimestamp", "kind", "description"]

field_filter_new = [
    "status",
    {
        "nodePools": ["status"],
        "nodeConfig": ["testKey"]
    }
]

item_filters_and_clause = [{
    "name": '^k8s.*',
    "description": '^{"kubernetes.io/'
}]

item_filters_list_filtering = [{
    "test_list": ".*test1.*"
}]

item_filters_or_clause = [
    {"name": ".*default-route.*"},
    {"description": "k8s-node-route"}
]

item_filters_nested_and_or_clause = [
    {
        "name": '^k8s-fw.*',
        "description": '^{"kubernetes.io/'
    },
    {
        "test_nested_list": {"name": ".*name1"}
    },
    {
        "test_nested_dict": {"test_inner_field": ".*value2"}
    }
]

query_response = {"items": [
    {
        "autoCreateSubnetworks": False,
        "creationTimestamp": "2010-01-01T00:00:00.000-07:00",
        "id": "1111111",
        "kind": "compute#network",
        "name": "vpc-network",
        "peerings": [
            {
                "autoCreateRoutes": True,
                "exchangeSubnetRoutes": True,
                "exportCustomRoutes": False,
                "exportSubnetRoutesWithPublicIp": False,
                "importCustomRoutes": False,
                "importSubnetRoutesWithPublicIp": False,
                "name": "vpc-peered",
                "network": "https://www.googleapis.com/compute/v1/projects/vpc-peered",
                "state": "ACTIVE",
                "stateDetails": "[2010-01-01T00:00:00.000-07:00]: Connected."
            }
        ],
        "routingConfig": {
            "routingMode": "GLOBAL"
        },
        "selfLink": "https://www.googleapis.com/compute/v1/projects/project-111/global/networks/vpc-network",
        "subnetworks": [
            "https://www.googleapis.com/compute/v1/projects/project-111/regions/us-central1/subnetworks/vpc-subnet"
        ]
    }
]}

query_response_k8s = {"items": [
    {
        "addonsConfig": "test_addons1",
        "name": "test_name1",
        "status": "test_status1",
        "nodePools": [{
                "name": "test_name1",
                "status": "test_status1"
            },
            {
                "name": "test_name2",
                "status": "test_status2"
            }
        ]
    },
    {
        "addonsConfig": "test_addons2",
        "name": "test_name2",
        "status": "test_status2",
        "nodeConfig": {
            "testKey": "testField"
        },
        "nodePools": [{
            "name": "test_name3",
            "status": "test_status1"
            },
            {
                "name": "test_name4",
                "status": "test_status2"
            }
        ]
    }
]}

query_response_k8s_exclude_filter_expected = [{
    "addonsConfig": "test_addons1",
    "name": "test_name1",
    "nodePools": [{
        "name": "test_name1"
    },
        {
            "name": "test_name2"
        }
    ]
}, {
    "addonsConfig": "test_addons2",
    "name": "test_name2",
    "nodeConfig": {},
    "nodePools": [{
        "name": "test_name3"
    },
        {
            "name": "test_name4"
        }
    ]
}]

query_exclude_filter_result = [
    {
        "autoCreateSubnetworks": False,
        "id": "1111111",
        "name": "vpc-network",
        "peerings": [
            {
                "autoCreateRoutes": True,
                "exchangeSubnetRoutes": True,
                "exportCustomRoutes": False,
                "exportSubnetRoutesWithPublicIp": False,
                "importCustomRoutes": False,
                "importSubnetRoutesWithPublicIp": False,
                "name": "vpc-peered",
                "network": "https://www.googleapis.com/compute/v1/projects/vpc-peered",
                "state": "ACTIVE",
                "stateDetails": "[2010-01-01T00:00:00.000-07:00]: Connected."
            }
        ],
        "routingConfig": {
            "routingMode": "GLOBAL"
        },
        "selfLink": "https://www.googleapis.com/compute/v1/projects/project-111/global/networks/vpc-network",
        "subnetworks": [
            "https://www.googleapis.com/compute/v1/projects/project-111/regions/us-central1/subnetworks/vpc-subnet"
        ]
    }
]

query_include_filter_result = [
    {
        "creationTimestamp": "2010-01-01T00:00:00.000-07:00",
        "kind": "compute#network",
    }
]

query_response_multiple_items_org = {"items": [
    {
        "name": "k8s-1234adsf1234",
        "description": '{"kubernetes.io/cluster-id":"1234zxcv"}'
    },
    {
        "name": "k8s-fw-5678zxcv1234",
        "description": '{"kubernetes.io/cluster-id":"5678asdf"}'
    },
    {
        "name": "allow-ssh1",
        "description": "custom_rule",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name1"
            },
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh2",
        "description": "custom_rule",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name1"
            },
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh3",
        "description": "custom_rule",
        "test_nested_dict": {"test_inner_field": "test_value1"}
    },
    {
        "name": "allow-ssh4",
        "description": "custom_rule",
        "test_nested_dict": {"test_inner_field": "test_value2"}
    }
]}

query_response_item_filter_or_clause = {"items": [
    {
        "name": "default-route-1234",
        "description": "test1"
    },
    {
        "name": "test-custom-route2",
        "description": "test1"
    },
    {
        "name": "test-custom-route2",
        "description": "k8s-node-route"
    },
    {
        "name": "test-custom-route1",
        "description": "test1"
    }
]}

query_response_item_filter_or_clause_after_filtering = [
    {
        "name": "test-custom-route1",
        "description": "test1"
    },
    {
        "name": "test-custom-route2",
        "description": "test1"
    }
]

query_response_filtered_items = [
    {
        "name": "allow-ssh",
        "description": "custom_rule"
    }
]

query_response_filtered_items_fields = [
    {
        "name": "allow-ssh"
    }
]

expected_testResultItemFilter = [
    {
        'description': 'custom_rule',
        'name': 'allow-ssh1',
        'test_nested_list': [
            {
                'name': 'test_name1',
                'test_value': 'test2'
            },
            {
                'name': 'test_name2',
                'test_value': 'test2'
            },
            {
                'name': 'test_name3',
                'test_value': 'test3'
            }
        ]
    },
    {
        "name": "allow-ssh2",
        "description": "custom_rule",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name1"
            },
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                'name': 'test_name3',
                'test_value': 'test3'
            }
        ]
    },
    {
        "name": "allow-ssh3",
        "description": "custom_rule",
        "test_nested_dict": {"test_inner_field": "test_value1"}
    },
    {
        "name": "allow-ssh4",
        "description": "custom_rule",
        "test_nested_dict": {"test_inner_field": "test_value2"}
    }
]

expected_testFieldAndItemFilter = [
    {
        "name": "allow-ssh1",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name1"
            },
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh2",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name1"
            },
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh3",
        "test_nested_dict": {"test_inner_field": "test_value1"}
    },
    {
        "name": "allow-ssh4",
        "test_nested_dict": {"test_inner_field": "test_value2"}
    }
]

expected_testResultItemFilterAndOrNested = [
    {
        "name": "allow-ssh1",
        "description": "custom_rule",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh2",
        "description": "custom_rule",
        "test_nested_list": [
            {
                "test_value": "test2",
                "name": "test_name2"
            },
            {
                "test_value": "test3",
                "name": "test_name3"
            }
        ]
    },
    {
        "name": "allow-ssh3",
        "description": "custom_rule",
        "test_nested_dict": {"test_inner_field": "test_value1"}
    },
    {
        "name": "k8s-1234adsf1234",
        "description": '{"kubernetes.io/cluster-id":"1234zxcv"}'
    }
]

test_queries_compute = [
    {
        "resource": "network",
        "gcp_api_call": "networks.list",
        "gcp_log_resource_type": "gce_network",
        "field_exclude_filter": ["creationTimestamp"],
        "gcp_function_args": {
            "project": "<PROJECT_ID>"
        }
    },
    {
        "resource": "staticRoute",
        "gcp_api_call": "routes.list",
        "gcp_log_resource_type": "gce_route",
        "field_exclude_filter": ["creationTimestamp"],
        "gcp_function_args": {
            "project": "<PROJECT_ID>"
        },
    },
    {
        "resource": "project",
        "gcp_api_call": "projects.list",
        "gcp_log_resource_type": "N/A",
        "sortFields": ["name", {"testNestedField": "name"}],
    }
]

test_aggregatedList_response = {"items":{
    "regions/asia-south1": {
        "warning": {
            "code": "NO_RESULTS_ON_PAGE",
            "data": [
                {
                    "key": "scope",
                    "value": "regions/asia-south1"
                }
            ],
            "message": "There are no results for scope 'regions/asia-south1' on this page."
        }
    },
    "regions/asia-south2": {
        "subnetworks": [
            {
                "name": "test-subnetwork1"
            },
            {
                "name": "test-subnetwork2"
            }
        ]
    }
}}

test_aggregatedList_response_paged = {"items":{
    "regions/europe-north1": {
        "warning": {
            "code": "NO_RESULTS_ON_PAGE",
            "data": [
                {
                    "key": "scope",
                    "value": "regions/asia-south1"
                }
            ],
            "message": "There are no results for scope 'regions/asia-south1' on this page."
        }
    },
    "regions/europe-north2": {
        "subnetworks": [
            {
                "name": "test-subnetwork3"
            },
            {
                "name": "test-subnetwork4"
            }
        ]
    },
    "regions/asia-south2": {
        "subnetworks": [
            {
                "name": "test-subnetwork5"
            },
            {
                "name": "test-subnetwork6"
            }
        ]
    },
},
"nextPageToken": "test_token"
}

test_aggregatedList_response_empty = {"items":{
    "regions/asia-south1": {
        "warning": {
            "code": "NO_RESULTS_ON_PAGE",
            "data": [
                {
                    "key": "scope",
                    "value": "regions/asia-south1"
                }
            ],
            "message": "There are no results for scope 'regions/asia-south1' on this page."
        }
    }
}}

test_result_unsorted_with_name = {"items": [
    {
        "name": "zzzz",
    },
    {
        "name": "dddd",
    },
    {
        "name": "aaaa",
        "testNestedField": [
            {"name": "zzzz"},
            {"name": "aaaa"},
            {"name": "bbbb"},
        ]
    }
]}

test_result_unsorted_with_name_unsortable = {"items": [
    {
        "name": "zzzz",
    },
    {
        "issue": "missing_name",
    },
    {
        "name": "aaaa",
    }
]}

test_queries_missing_arg = [
    {
        "resource": "network",
    }
]
test_queries_incorrect_type = [
    "incorrect type"
]

query_response_items_with_list = {"items": [
    {
        "name": "value1",
        "test_list": [
            "a_test1_value",
            "b_test2_value"
        ]
    },
    {
        "name": "value2",
        "test_list": [
            "a_test1_value"
        ]
    },
    {
        "name": "value3"
    }
]}

expected_result_after_filtering = [
    {
        "name": "value1",
        "test_list": [
            "b_test2_value"
        ]
    },
    {
        "name": "value2",
        "test_list": [
        ]
    },
    {
        "name": "value3"
    }
]
