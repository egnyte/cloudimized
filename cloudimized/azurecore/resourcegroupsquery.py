"""
Azure query for resource groups
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from cloudimized.azurecore.azurequery import AzureQuery
from typing import Dict, List

RESOURCE_GROUPS_RESOURCE_NAME = "resourceGroups"

@AzureQuery.register_class(RESOURCE_GROUPS_RESOURCE_NAME)
class ResourceGropusQuery(AzureQuery):
    """
    Azure query for virtual networks
    """
    def _AzureQuery__send_query(self,
                                credential: DefaultAzureCredential,
                                subscription_id,
                                resource_groups) -> List[Dict]:
        """
        Sends Azure query that lists Resource Groups.
        :param credential: Azure credential object
        :param subscription_id: Azure subscription id
        :param resource_groups: irrelevant for this implementation, needed due to inheritance
        :return: List of resources that were queried
        """
        client = ResourceManagementClient(credential=credential,subscription_id=subscription_id)
        result = client.resource_groups.list()
        return result
