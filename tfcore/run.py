import logging

from typing import List, Dict
from itertools import filterfalse
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

RUN_CHANGE_STATUS = ['applied', 'errored']


class TFRun:
    """
    Represents terraform run related to change
    """

    def __init__(self, message: str, run_id: str, status: str, apply_time: datetime, org: str, workspace: str):
        """
        :param message: Terraform Run Message
        :param run_id: Terraform Run ID
        :param status: Terraform Run Status
        :param apply_time: Terraform Run apply time
        :param org: Terraform Organization name
        :param workspace: Terraform Workspace name
        """
        self.message = message
        self.run_id = run_id
        self.status = status
        self.apply_time = apply_time
        self.org = org
        self.workspace = workspace

    def __repr__(self):
        return f"Msg: '{self.message}', RunID: '{self.run_id}', Status:'{self.status}', Applied: '{self.apply_time}'"


def parse_tf_runs(runs_response: Dict, org: str, workspace: str) -> List[TFRun]:
    """
    Converts TF API runs response into TFRun objects
    :param runs_response: TF API response from runs list
    :param org: TF org's name related to runs
    :param workspace: TF workspace's name related to runs
    :returns list of parsed terraform runs
    """
    if "data" not in runs_response:
        raise TFRunError(f"No 'data' in TF run response")
    tf_runs = []
    for run_response in runs_response["data"]:
        status = run_response.get("attributes", {}).get("status", None)
        # Unknown response structure
        if status is None:
            logger.warning(f"No status field for TF run\n{run_response}")
            continue
        # Process only runs that might have changed configuration
        if status in ["applied", "errored"]:
            status_timestamps = run_response.get("attributes", {}).get("status-timestamps", {})
            apply_time_str = status_timestamps.get("applying-at", None)
            if apply_time_str is None and status == "errored":
                apply_time_str = status_timestamps.get("errored-at", None)
            if apply_time_str is None:
                logger.warning(f"No status-timestamps field for TF run\n{run_response}")
                continue
            try:
                apply_time = datetime.strptime(apply_time_str.split("+")[0], "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                logger.warning(f"Issue parsing run timestamp\n{type(e)} {e}")
            run_id = run_response.get("id", None)
            message = run_response.get("attributes", {}).get("message", None)
            tf_runs.append(TFRun(message, run_id, status, apply_time, org, workspace))
    return tf_runs


def filter_non_change_runs(tf_runs: List[TFRun], change_time: datetime, time_delta: int = 5) -> List[TFRun]:
    """
    Filters non-change and non-relevant Terraform Runs
    :param tf_runs: list of Terraform Runs
    :param change_time: reference timestamp of change made
    :param time_delta: time window size in minutes for relevant changes
    :return: relevant, change related Terraform Runs
    """
    relevant_runs = tf_runs[:]
    # Get only change related runs
    relevant_runs[:] = filterfalse(__filter_runs_status, relevant_runs)
    # Get runs that fall into specified time window
    relevant_runs[:] = filterfalse(lambda run: __filter_runs_time(run, change_time, time_delta), relevant_runs)
    return relevant_runs


def __filter_runs_status(run: TFRun) -> bool:
    """
    Filter non-change runs
    :param run: Terraform Run object
    """
    if run.status is None:
        return True
    if run.status in RUN_CHANGE_STATUS:
        return False
    else:
        return True


def __filter_runs_time(run: TFRun, change_time: datetime, time_delta: int) -> bool:
    """
    Filter runs that are outside of specified time window
    :param run: TFRun object
    :param change_time: Reference time of when change was made
    :param time_delta: Size of time window in minutes
    """
    if run.apply_time is None:
        return True
    # Time difference between reference point and apply time
    time_diff = abs(change_time - run.apply_time)
    # Filter out runs that our outside of window
    if time_diff < timedelta(minutes=time_delta):
        return False
    else:
        return True


class TFRunError(Exception):
    pass
