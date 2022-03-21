import logging
import yaml
import csv
from typing import List, Dict
from pathlib import Path
from os.path import isdir
from flatdict import FlatterDict

from cloudimized.gcpcore.gcpservicequery import GcpServiceQuery

logger = logging.getLogger(__name__)

PROJECTID_KEY = "projectId"

class QueryResult:
    """
    Class representing monitored resource
    """

    def __init__(self):
        self.resources = {}

    def add_resource(self, resource_name: str) -> None:
        """
        Adds new resource to results
        :param resource_name: name that matches resource_name in query object
        :raises QueryResultError
        """
        if resource_name in self.resources:
            raise QueryResultError(f"Resource '{resource_name}' is already added in results")
        self.resources[resource_name] = {}

    def add_result(self, resource_name: str, project_id: str, result: List[Dict]) -> None:
        """
        Adds results for specific resource in given projectId
        :param resource_name: resource's result name
        :param project_id: projectId from which result comes
        :param result: result from executing gcp query
        """
        if resource_name not in self.resources:
            self.add_resource(resource_name)
        self.resources[resource_name][project_id] = result

    def get_result(self, resource_name: str, projectId: str) -> List[Dict]:
        """
        Get results for specific resoure in given project_id
        :param resource_name: resource's result name
        :param projectId: project_id from which result comes
        :return: results from query
        """
        return self.resources.get(resource_name, {}).get(projectId, None)

    def dump_results(self, directory: str) -> None:
        """
        Save results to files
        :param directory: root directory to which dump all resources
        :raises QueryResultError
        """
        if not isdir(directory):
            raise QueryResultError(f"Issue dumping results to files. Directory '{directory}' doesn't exist")
        for resource_name, projects in self.resources.items():
            try:
                logger.info(f"Creating directory '{directory}/{resource_name}'")
                Path(f"{directory}/{resource_name}").mkdir(exist_ok=True)
            except Exception as e:
                raise QueryResultError(f"Issue creating directory '{directory}/{resource_name}'") from e
            for project_id, result in projects.items():
                # Don't dump files for projects with empty list
                if not result:
                    continue
                logger.info(f"Dumping results in {directory}/{resource_name}/{project_id}.yaml")
                try:
                    with open(f"{directory}/{resource_name}/{project_id}.yaml", "w") as fh:
                        yaml.dump(result, fh, default_flow_style=False)
                except Exception as e:
                    raise QueryResultError(f"Issue dumping results into file "
                                           f"'{directory}/{resource_name}/{project_id}.yaml")

    def dump_results_csv(self, directory: str) -> None:
        """
        Save results in CSV files
        :param directory: directory to which dump CSV files
        :raises QueryResultError
        """
        logger.info(f"Dumping results in CSV files")
        if not isdir(directory):
            raise QueryResultError(f"Issue dumping results to files. Directory '{directory}' doesn't exist")
        fieldnames_map = {}
        # Get fieldnames
        for resource_name, projects in self.resources.items():
            logger.info(f"Discovering fieldnames for resource: {resource_name}")
            fieldnames_map[resource_name] = set()
            for project_id, result in projects.items():
                for entry in result:
                    try:
                        flatentry = FlatterDict(entry)
                        fieldnames_map[resource_name].update(flatentry.keys())
                    except Exception as e:
                        logger.warning(f"Unable to get fieldnames for resource {resource_name} from entry {entry}")
                        continue
        for resource_name, projects in self.resources.items():
            fieldnames = [PROJECTID_KEY] + sorted(list(fieldnames_map[resource_name]))
            filename = f"{directory}/{resource_name}.csv"
            logger.info(f"Dumping results in {filename}")
            try:
                with open(filename, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames)
                    writer.writeheader()
                    for project_id, result in projects.items():
                        if not result:
                            continue
                        for entry in result:
                            entry[PROJECTID_KEY] = project_id
                            flatentry = FlatterDict(entry)
                            writer.writerow(dict(flatentry))
            except Exception as e:
                raise QueryResultError(f"Issue writing results to file {filename}") from e


def set_query_results_from_configuration(gcp_services: Dict[str, GcpServiceQuery]) -> QueryResult:
    """
    Creates and configures QueryResults object based on configuration file
    :param gcp_services: service queries configuration stored in GcpOxidized
    :return: mapping of resource type and project with result
    """
    result = QueryResult()
    for serviceName, service in gcp_services.items():
        if not service.queries:
            raise QueryResultError(f"No queries configured for service '{serviceName}'")
        for resource_name in service.queries:
            result.add_resource(resource_name)
    return result


class QueryResultError(Exception):
    pass
