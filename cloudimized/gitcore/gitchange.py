import logging

from collections import OrderedDict

logger = logging.getLogger(__name__)

#TODO: Change this to absract Change class, make GcpChange inherit from it and move it to gcpcore instead
# This will allow to easier expand into other Cloud providers
class GitChange:
    """
    Represents configuration change in resources
    """

    def __init__(self, provider: str, resource_type: str, project: str, is_old_structure: str=False):
        """
        :param provider: name of provider [azure, gcp]
        :param resource_type: GCP/Azure resource type
        :param project: GCP/Azure project name
        :param is_old_structure: used for transition when Azure support was added
        """
        self.provider = provider
        self.resource_type = resource_type
        self.project = project
        self.is_old_structure = is_old_structure
        self.message = None
        self.diff = None
        self.manual = False
        self.commit = None
        self.changers = None
        # List of GCP change logs related to this resource
        self.gcp_change_log = []
        # List of Terraform Runs related to this resource
        self.terraform_run_log = []

    def get_filename(self) -> str:
        """
        Provides file where configuration is stored
        """
        if self.is_old_structure:
            return f"{self.resource_type}/{self.project}.yaml"
        else:
            return f"{self.provider}/{self.resource_type}/{self.project}.yaml"

    def get_commit_message(self) -> str:
        """
        Returns Git commit message for this change
        """
        basic_msg = f"{self.resource_type.title()} updated in {self.provider.upper()}: {self.project} by"
        # Get only unique changer_identities with predicatable order (for passing tests mainly)
        unique_changer_identity = OrderedDict.fromkeys([change.changer for change in self.gcp_change_log])
        # No changers identified
        if not unique_changer_identity:
            message = f"{basic_msg} UNKNOWN"
        else:
            # TODO: Add addtional info to commit message from gcpchangelog i.e. methodname
            message = f"{basic_msg} {list(unique_changer_identity.keys())}"
            # Prepend information from Terraform if available
            # TODO: Add terraform logic
            if self.terraform_run_log:
                pass
            else:
                pass
        return message

    def __eq__(self, other):
        return self.provider == other.provider and \
            self.resource_type == other.resource_type and \
            self.project == other.project
