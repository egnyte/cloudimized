"""
Azure query for virtual networks
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient

from cloudimized.azurecore.azurequery import AzureQuery


@AzureQuery.register_class("virtualNetworks")
class VirtualNetworksQuery(AzureQuery):
    """
    Azure query for virtual networks
    """
    def _AzureQuery__send_query(self, credential: DefaultAzureCredential, subscription_id: str):
        """
        Sends Azure query that lists Virtual Networks in subscription in project.
        See: https://learn.microsoft.com/en-us/rest/api/virtualnetwork/virtual-networks/list-all?view=rest-virtualnetwork-2024-05-01&tabs=HTTP
        :param subscription_id: Azure subscription ID to query
        :return: List of resources that were queried
        """
        client = NetworkManagementClient(credential=credential, subscription_id=subscription_id)
        result = client.virtual_networks.list_all()
        return result
