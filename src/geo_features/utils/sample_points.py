# Sample points while respecting exclusion zones

from warnings import warn

def sample_points(polygon_df, n_points, exclusion_zones=None, buffer=0, max_retries=100, seed=None):
    """
    Sample random points within each polygon, respecting any exclusion zones.
    
    Note that this is a brute-force approach, so it is only useful if the exclusion zone
    dataframe is so large/complex that calculating its unary_union and simply subtracting that
    from the polygon dataframe is too slow. It is intended for cases where exclusion zones make 
    up only a small fraction of the total area being sampled, in which case only a small number 
    of random points need to be replaced.
    
    Parameters
    ----------
    polygon_df: A geopandas dataframe containing polygons.
    n_points: Number of points to sample within each polygon.
    exclusion_zones: A geopandas dataframe containing polygons defining areas which should not
                     contain any sampled points (optional).
    buffer: Size of a buffer around exclusion zones where no points should be sampled (optional).
    max_retries: Maximum number of times to try to achieve the desired number of points within
                 each polygon. If this number is exceeded, the function returns the points that
                 were sampled so far, and prints a warning. Not used when exclusion_zones is None.
    seed: Random seed to use.
    
    Returns
    -------
    A geopandas dataframe containing the sampled points.
    """
    # Sample an initial set of points
    points = (
        polygon_df
        .assign(geometry=polygon_df.sample_points(n_points, seed=seed))
        .explode(index_parts=False)
        .reset_index()
        .rename(columns={"index": "polygon_id"})
    )
    
    if exclusion_zones is None:
        return points
    
    # Validate inputs
    assert max_retries > 0, "max_retries must be > 0."
    exclusion_zones = exclusion_zones.to_crs(polygon_df.crs)
    
    # Remove any extraneous columns from exclusion_zones so joins below don't add columns
    exclusion_zones.drop(columns=exclusion_zones.columns.difference(["geometry"]), inplace=True)
    
    # Replace points that fall within exclusion zones
    # - Using a buffer around the points rather than the exclusion zones themselves,
    #   under the assumption that there are far fewer points than exclusion zones.
    buffered_points = points.assign(geometry=points.buffer(buffer))
    invalid_points = buffered_points.sjoin(exclusion_zones)
    tries = 0
    
    while len(invalid_points) > 0 and tries < max_retries:
        # Find number of points to replace in each polygon
        n_replacements = invalid_points["polygon_id"].value_counts()
        
        # Sample new points
        invalid_polygons = polygon_df.loc[n_replacements.index]
        
        new_points = (
            invalid_polygons
            .assign(geometry=invalid_polygons.sample_points(n_replacements, seed=seed))
            .explode(index_parts=False)
            .reset_index()
            .rename(columns={"index": "polygon_id"})
        )
        
        # Replace invalid points
        points = (
            points
            .drop(index=invalid_points.index)
            .append(new_points)
            .reset_index(drop=True)
        )
        
        # Check again
        buffered_points = points.assign(geometry=points.buffer(buffer))
        invalid_points = buffered_points.sjoin(exclusion_zones)
        tries += 1
        
        if len(invalid_points) == 0:
            break
    
    # Check if max_retries was exceeded
    if len(invalid_points) != 0:
        n_polygons = len(invalid_points["polygon_id"].unique())
        mean_missing_points = invalid_points["polygon_id"].value_counts().mean()
        warn(
            f"Could not find valid points for {n_polygons} polygons after {max_retries} tries. "
            f"Average number of missing points per polygon: {mean_missing_points}."
        )
    
    return points.drop(columns=["polygon_id"])
