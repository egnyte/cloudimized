"""
Azure query for AKS clusters
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient
from cloudimized.azurecore.azurequery import AzureQuery
from typing import Dict, List


@AzureQuery.register_class("aksClusters")
class AksClustersQuery(AzureQuery):
    """
    Azure query for AKS clusters
    """
    def _AzureQuery__send_query(self,
                                credential: DefaultAzureCredential,
                                subscription_id: str,
                                resource_groups) -> List[Dict]:
        """
        Sends Azure query that lists AKS clusters in subscription in project.
        See: https://learn.microsoft.com/en-us/rest/api/compute/container-services/list?view=rest-compute-2020-09-30&tabs=HTTP
        :param credential:  Azure credential object
        :param subscription_id: Azure subscription ID to query
        :param resource_groups: irrelevant for this implementation, needed due to inheritance
        :return: List of resources that were queried
        """
        client = ContainerServiceClient(credential=credential, subscription_id=subscription_id)
        result = client.managed_clusters.list()
        return result
