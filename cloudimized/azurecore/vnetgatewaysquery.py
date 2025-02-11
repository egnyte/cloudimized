"""
Azure query for virtual networks
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from cloudimized.azurecore.azurequery import AzureQuery
from typing import Dict, List

@AzureQuery.register_class("vnetGateways")
class VnetGatewaysQuery(AzureQuery):
    """
    Azure query for virtual network gateways
    """
    def _AzureQuery__send_query(self,
                                credential: DefaultAzureCredential,
                                subscription_id: str,
                                resource_groups: List[str]) -> List[Dict]:
        """
        Sends Azure query that lists Virtual Networks in subscription in project.
        See: https://learn.microsoft.com/en-us/cli/azure/network/vnet-gateway?view=azure-cli-latest#az-network-vnet-gateway-list
        :param credential:  Azure credential object
        :param subscription_id: Azure subscription ID to query
        :param resource_groups: list of Resource Group names to query
        :return: List of resources that were queried
        """
        client = NetworkManagementClient(credential=credential, subscription_id=subscription_id)
        result = []
        for rg in resource_groups:
            result.extend(client.virtual_network_gateways.list(resource_group_name=rg))
        return result
