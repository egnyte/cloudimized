"""
Azure query for subscriptions
"""
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient

from cloudimized.azurecore.azurequery import AzureQuery

SUBSCRIPTIONS_RESOURCE_NAME = "subscriptions"

@AzureQuery.register_class(SUBSCRIPTIONS_RESOURCE_NAME)
class SubscriptionsQuery(AzureQuery):
    """
    Azure query for virtual networks
    """
    def _AzureQuery__send_query(self, credential: DefaultAzureCredential, subscription_id):
        """
        Sends Azure query that lists all subscriptions.
        See: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/subscription/azure-mgmt-subscription/generated_samples/list_subscriptions.py
        :param credential: Azure credential object
        :param subscription_id: irrelevant for this implementation, needed due to inheritance
        :return: List of resources that were queried
        """
        client = SubscriptionClient(credential=credential)
        result = client.subscriptions.list()
        return result
