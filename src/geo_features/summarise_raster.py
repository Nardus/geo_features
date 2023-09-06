# Functions for summarising rasters to polygons

from warnings import warn
from pandas import DataFrame
from rasterstats import zonal_stats
from rasterio import open as rio_open


def _adapt_crs_to_raster(polygons, raster_file):
    """
    Adapt CRS of polygons to match that of a raster file.
    
    Parameters
    ----------
    polygons: A geopandas dataframe specifying location polygons.
    raster_file: Path to a raster file.
    
    Returns
    -------
    A geopandas dataframe.
    """
    # Ensure CRS matches
    with rio_open(raster_file) as f:
        raster_crs = f.crs
    
    if raster_crs is None:
        warn("Raster file does not specify a CRS - assuming WGS84", RuntimeWarning, stacklevel=3)
        raster_crs = "WGS84"
    
    return polygons.to_crs(raster_crs)


def summarise_raster(raster_file, polygons, column_name, summary_fun, 
                     all_touched=True, location_col="location"):
    """
    Summarise raster values within polygons.
    
    Parameters
    ----------
    raster_file: Path to a raster file.
    polygons: A geopandas dataframe specifying location polygons.
    column_name: A column name to use for counts in the output dataframe.
    summary_fun: A summary function to use (see rasterstats.utils.VALID_STATS).
    all_touched: Whether to include all pixels touched by a polygon, or only those whose centres
                 are within the polygon.
    location_col: The name of the column in `polygons` specifying location IDs.
    
    Returns
    -------
    A dataframe.
    """
    # Ensure CRS matches
    polygons = _adapt_crs_to_raster(polygons, raster_file)

    # Summarise to polygons
    vals = zonal_stats(
        vectors=polygons,
        raster=raster_file,
        stats=[summary_fun],
        all_touched=all_touched
    )

    vals = DataFrame(vals)
    vals.rename({summary_fun: column_name}, axis=1, inplace=True)

    # Add location names
    vals[location_col] = polygons[location_col]

    return vals[[location_col, column_name]]


def summarise_categorical_raster(raster_file, polygons, value_map=None, all_touched=True, 
                                 proportion=False, location_col="location"):
    """
    Summarise categorical raster values within polygons.
    
    Returned values can represent either the number of occurences of each category within each 
    polygon, or the proportion of each polygon covered by each category. Note that the latter
    accounts for nodata and "nan" values, meaning proportions may not sum to 1.
    
    Parameters
    ----------
    raster_file: Path to a raster file.
    polygons: A geopandas dataframe specifying location polygons.
    value_map: A dictionary mapping raster values to human-readable labels. If not specified, 
               values will be used as-is.
    all_touched: Whether to include all pixels touched by a polygon, or only those whose centres
                 are within the polygon.
    proportion: Whether to return counts or proportions.
    location_col: The name of the column in `polygons` specifying location IDs.
    
    Returns
    -------
    A dataframe.
    """
    polygons = _adapt_crs_to_raster(polygons, raster_file)
    
    # If calculating proportions, also need counts of filled and nodata pixels
    stats = None if not proportion else ["count", "nodata", "nan"]
    
    vals = zonal_stats(
        vectors=polygons,
        raster=raster_file,
        stats=stats,
        all_touched=all_touched,
        categorical=True,
        category_map=value_map
    )
    
    # zonal_stats only returns counts for categories that are present in each polygon
    vals = DataFrame(vals).fillna(0)
    
    # Calculate proportions if required
    if proportion:
        total_pixels = vals["count"] + vals["nodata"] + vals["nan"]
        vals = (
            vals
            .drop(["count", "nodata", "nan"], axis=1)
            .div(total_pixels, axis=0)
        )
    
    # Add location names
    vals.insert(0, location_col, polygons[location_col])

    return vals
