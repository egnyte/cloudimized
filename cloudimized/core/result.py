import logging
import yaml
import csv
from typing import List, Dict
from pathlib import Path
from os.path import isdir
from flatdict import FlatterDict

from cloudimized.azurecore.azurequery import AzureQuery
from cloudimized.gcpcore.gcpservicequery import GcpServiceQuery

logger = logging.getLogger(__name__)

PROJECT_ID_KEY = "projectId" #GCP
SUBSCRIPTION_ID_KEY = "subscriptionId" #Azure
AZURE_KEY = "azure"
GCP_KEY = "gcp"

TARGET_ID_KEY = {
    AZURE_KEY: SUBSCRIPTION_ID_KEY,
    GCP_KEY: PROJECT_ID_KEY
}

class QueryResult:
    """
    Class representing monitored resource
    """

    def __init__(self):
        self.resources = {
            AZURE_KEY: {},
            GCP_KEY: {},
                          }

    def add_resource(self, resource_name: str, provider: str) -> None:
        """
        Adds new resource to results
        :param resource_name: name that matches resource_name in query object
        :param provider: type of Cloud provider: azure/gcp
        :raises QueryResultError
        """
        if resource_name in self.resources[provider]:
            raise QueryResultError(f"Resource '{resource_name}' is already added in results for provider {provider}")
        self.resources[provider][resource_name] = {}

    def add_result(self, resource_name: str, provider: str, target_id: str, result: List[Dict]) -> None:
        """
        Adds results for specific resource in given projectId
        :param resource_name: resource's result name
        :param provider: type of Cloud provider: azure/gcp
        :param target_id: projectId(GCP)/subscriptionId(Azure) from which result comes
        :param result: result from executing gcp query
        """
        if resource_name not in self.resources[provider]:
            self.add_resource(resource_name, provider)
        self.resources[provider][resource_name][target_id] = result

    def get_result(self, resource_name: str, provider: str, target_id: str) -> List[Dict]:
        """
        Get results for specific resoure in given project_id
        :param resource_name: resource's result name
        :param provider: type of Cloud provider: azure/gcp
        :param target_id: projectId(GCP)/subscriptionId(Azure) from which result comes
        :return: results from query
        """
        return self.resources.get(provider, {}).get(resource_name, {}).get(target_id, None)

    def dump_results(self, directory: str) -> None:
        """
        Save results to files
        :param directory: root directory to which dump all resources
        :raises QueryResultError
        """
        if not isdir(directory):
            raise QueryResultError(f"Issue dumping results to files. Directory '{directory}' doesn't exist")
        for provider, resources in self.resources.items():
            for resource_name, targets_id in resources.items():
                try:
                    logger.info(f"Creating directory '{directory}/{provider}/{resource_name}'")
                    Path(f"{directory}/{provider}/{resource_name}").mkdir(parents=True,exist_ok=True)
                except Exception as e:
                    raise QueryResultError(f"Issue creating directory '{directory}/{provider}/{resource_name}'") from e
                for target_id, result in targets_id.items():
                    # Don't dump files for projects with empty list
                    if not result:
                        continue
                    logger.info(f"Dumping results in {directory}/{provider}/{resource_name}/{target_id}.yaml")
                    try:
                        with open(f"{directory}/{provider}/{resource_name}/{target_id}.yaml", "w") as fh:
                            yaml.dump(result, fh, default_flow_style=False)
                    except Exception as e:
                        raise QueryResultError(f"Issue dumping results into file "
                                               f"'{directory}/{provider}/{resource_name}/{target_id}.yaml")

    def dump_results_csv(self, directory: str) -> None:
        """
        Save results in CSV files
        :param directory: directory to which dump CSV files
        :raises QueryResultError
        """
        logger.info(f"Dumping results in CSV files")
        if not isdir(directory):
            raise QueryResultError(f"Issue dumping results to files. Directory '{directory}' doesn't exist")
        fieldnames_map = {
            AZURE_KEY: {},
            GCP_KEY: {}
        }
        # Get fieldnames
        for provider in [AZURE_KEY, GCP_KEY]:
            for resource_name, targets_id in self.resources[provider].items():
                logger.info(f"Discovering fieldnames for provider: {provider}, resource: {resource_name}")
                fieldnames_map[provider][resource_name] = set()
                for target_id, result in targets_id.items():
                    for entry in result:
                        try:
                            flatentry = FlatterDict(entry)
                            fieldnames_map[provider][resource_name].update(flatentry.keys())
                        except Exception as e:
                            logger.warning(f"Unable to get fieldnames for {provider} for resource {resource_name} from entry {entry}")
                            continue
            for resource_name, targets_id in self.resources[provider].items():
                target_id_key = TARGET_ID_KEY[provider]
                fieldnames = [target_id_key] + sorted(list(fieldnames_map[provider][resource_name]))
                filename = f"{directory}/{provider}/{resource_name}.csv"
                logger.info(f"Dumping results in {filename}")
                try:
                    with open(filename, "w", newline="") as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames)
                        writer.writeheader()
                        for target_id, result in targets_id.items():
                            if not result:
                                continue
                            for entry in result:
                                entry[target_id_key] = target_id
                                flatentry = FlatterDict(entry)
                                writer.writerow(dict(flatentry))
                except Exception as e:
                    raise QueryResultError(f"Issue writing results to file {filename}") from e


def set_query_results_from_configuration(gcp_services: Dict[str, GcpServiceQuery],
                                         azure_queries: Dict[str, AzureQuery]) -> QueryResult:
    """
    Creates and configures QueryResults object based on configuration file
    :param gcp_services: service queries configuration stored in GcpOxidized
    :return: mapping of resource type and project with result
    """
    result = QueryResult()
    if gcp_services:
        for serviceName, service in gcp_services.items():
            if not service.queries:
                raise QueryResultError(f"No queries configured for service '{serviceName}'")
            for resource_name in service.queries:
                result.add_resource(resource_name=resource_name, provider=GCP_KEY)
    if azure_queries:
        for resource_name, query in azure_queries.items():
            result.add_resource(resource_name=resource_name, provider=AZURE_KEY)
    return result


class QueryResultError(Exception):
    pass
