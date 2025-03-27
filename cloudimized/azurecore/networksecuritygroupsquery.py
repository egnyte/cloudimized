"""
Azure query for Network Security Group
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from cloudimized.azurecore.azurequery import AzureQuery
from typing import Dict, List


@AzureQuery.register_class("networkSecurityGroups")
class NetworkSecurityGroupQuery(AzureQuery):
    """
    Azure query for Network Security Groups
    """
    def _AzureQuery__send_query(self,
                                credential: DefaultAzureCredential,
                                subscription_id: str,
                                resource_groups) -> List[Dict]:
        """
        Sends Azure query that lists Network Security Groups in subscription in project.
        See: https://learn.microsoft.com/en-us/rest/api/virtualnetwork/network-security-groups/list-all?view=rest-virtualnetwork-2024-05-01&tabs=HTTP
        :param credential:  Azure credential object
        :param subscription_id: Azure subscription ID to query
        :param resource_groups: irrelevant for this implementation, needed due to inheritance
        :return: List of resources that were queried
        """
        client = NetworkManagementClient(credential=credential, subscription_id=subscription_id)
        result = client.network_security_groups.list_all()
        return result
