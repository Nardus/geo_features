# Request data from the Copernicus Climate Data Store, running multiple requests in parallel while
# respecting usage limits

import os
import ray

from warnings import warn
from cdsapi import Client


@ray.remote
def requester(out_name, query, dataset, cds_client=Client()):
    """
    Run a CDS api request.
    
    Note: if the requested output file already exists, it will be returned as is (with a warning).
    
    Parameters
    ----------
    out_name : str
        Name of the output file.
    query : dict
        Query to submit to CDS.
    dataset : str
        Name of an ERA5 dataset to query.
    cds_client : cdsapi.Client
        CDS client to use.
        
    Returns
    -------
    (str, dict)
        The path to the output file, and the original query.
    """
    if not os.path.exists(out_name):
        # Don't re-download if the file already exists
        cds_client.retrieve(dataset, query, out_name)
    else:
        warn(f"{out_name} exists. Summarising existing file", 
             RuntimeWarning, stacklevel=3)

    return out_name, query


def schedule_cds_requests(queries, summary_fun=None, dataset="reanalysis-era5-land", 
                          max_concurrent_requests=10):
    """
    Schedule a fixed number of CDS requests in parallel, with `summary_fun` 
    scheduled as soon as a result is done.
    
    Note, each API request blocks the thread it is on (since it needs resources to handle the
    download once it's ready), so start a ray cluster with `num_cpus` > `max_concurrent_requests` 
    to allow `summary_fun` to run while requests are pending.
    
    If no summarisation is required, set `summary_fun=None`.
    
    Parameters
    ----------
    queries : list of dicts
        List of queries to submit to CDS.
    summary_fun : function
        Function to call once a request is done. This function should: 
            (a) Be a ray remote actor (i.e, decorated with `@ray.remote`), and
            (b) Take two arguments: the path to the output file and the submitted query 
                (in that order).
    dataset : str
        Name of an ERA5 dataset to query (default: "reanalysis-era5-land").
    max_concurrent_requests : int
        Maximum number of requests to submit at once (default: 10).
        
    Returns
    -------
    list:
        The output of `summary_fun` for each query. If `summary_fun` is None, a list of
        (output_file_name, query) tuples.
    """
    cds_client = Client()

    requesters = []

    # schedule first max_concurrent_requests tasks (other available CPU threads reserved for processing)
    n_initial_tasks = min(len(queries), max_concurrent_requests)

    for i in range(n_initial_tasks):
        ref = requester.remote(
            out_name=queries[i][0],
            query=queries[i][1],
            dataset=dataset,
            cds_client=cds_client
        )
        requesters.append(ref)

    task_index = i

    # Continue processing as soon as a request is done
    summarizers = []
    done = False

    while not done:
        ready_refs, remaining_refs = ray.wait(requesters, num_returns=1)

        for ref in ready_refs:
            # Schedule a new API request to replace the one that just finished
            if task_index < (len(queries)-1):
                task_index += 1
                new_ref = requester.remote(
                    out_name=queries[task_index][0],
                    query=queries[task_index][1],
                    dataset=dataset,
                    cds_client=cds_client
                )
                remaining_refs.append(new_ref)

            # Schedule a processing task
            if summary_fun is not None:
                cur_result = ray.get(ref)
                final_ref = summary_fun.remote(cur_result[0], cur_result[1])  # (out_name, query)
                summarizers.append(final_ref)
            else:
                # No further processing needed - allow the ray.get call below to directly retrieve the requester's
                # results instead
                summarizers.append(ref)

        if len(remaining_refs) != 0:
            requesters = remaining_refs
            print(f"{len(summarizers)} of {len(queries)} queries retrieved", end="\r")
        else:
            done = True

    return ray.get(summarizers)
