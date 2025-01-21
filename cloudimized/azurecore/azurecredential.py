from cloudimized.gcpcore.gcpexternaltoken import get_idtoken
import logging
from os import getenv
import time
from typing import Any, Optional
from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import DefaultAzureCredential
from msal import ConfidentialClientApplication

AZURE_AUTHORITY = "https://login.microsoftonline.com"
AZURE_ACCESS_TOKEN_AUDIENCE = "api://AzureADTokenExchange"

ENV_AZURE_CLIENT_ID = "AZURE_CLIENT_ID"
ENV_AZURE_TENANT_ID = "AZURE_TENANT_ID"

logger = logging.getLogger(__name__)
####
# Create as potential wrapper - for compatibility with gcpservicequery logic
####

class WorkloadIdentityCredential(TokenCredential):
    """Custom credential class for Azure SDK"""
    def __init__(self, azure_client_id: str, azure_tenant_id: str, ext_token_id: str):
        # create a confidential client application
        self.app = ConfidentialClientApplication(
            azure_client_id,
            client_credential={
                'client_assertion': ext_token_id
            },
            authority=f"{AZURE_AUTHORITY}/{azure_tenant_id}"
        )

    def get_token(self, *scopes: str, claims: Optional[str] = None, tenant_id: Optional[str] = None, **kwargs: Any) -> AccessToken:
        token = self.app.acquire_token_for_client(list(scopes))
        if "error" in token:
            raise Exception(token["error_description"])
        expires_on = time.time() + token["expires_in"]
        return AccessToken(token["access_token"], int(expires_on))

def get_azure_credential() -> DefaultAzureCredential:
    """
    Returns Azure credential object
    :param azure_client_id: Azure application's client ID
    :param azure_tenant_id: Azure application's tenenat ID
    :param ext_token_id: external token ID when used with Federated Workload identity
    """
    logger.info(f"Generating Azure credential object")
    azure_client_id = getenv(ENV_AZURE_CLIENT_ID)
    azure_tenant_id = getenv(ENV_AZURE_TENANT_ID)
    if azure_client_id and azure_tenant_id:
        logger.info(f"Authenticating via Workload Identity Federation. Getting GCP ID token")
        ext_token_id = get_idtoken(AZURE_ACCESS_TOKEN_AUDIENCE)
        logger.info(f"GCP ID token retrived. Getting Azure access token")
        return WorkloadIdentityCredential(azure_client_id, azure_tenant_id, ext_token_id)
    else:
        logger.info(f"Logging to Azure using DefaultAzureCredential method")
        return DefaultAzureCredential()
