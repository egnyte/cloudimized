from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import id_token
import logging

logger = logging.getLogger(__name__)


def get_idtoken(audience: str):
    """
    Use the Google Application Credentials to get ID token

    Args:
        audience: The url or target audience to obtain the ID token for
    """

    logger.info(f"Requesting GCP ID token from metatdata server for audience: {audience}")
    credentials, _ = default()
    logger.info(f"Fetching ID token for account: {credentials.service_account_email}")
    id_token_creds = id_token.fetch_id_token(Request(), audience)
    return id_token_creds
