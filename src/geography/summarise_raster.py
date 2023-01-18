# Functions for summarising rasters to polygons

from warnings import warn
from pandas import DataFrame
from rasterstats import zonal_stats
from rasterio import open as rio_open


def summarise_raster(raster_file, polygons, column_name, summary_fun):
    """
    Summarise raster values within polygons.
    
    Parameters
    ----------
    raster_file: Path to a raster file with terrain ruggedness index values in each cell.
    polygons: A geopandas dataframe specifying location polygons.
    column_name: A column name to use for counts in the output dataframe.
    summary_fun: A summary function to use (see rasterstats.utils.VALID_STATS).
    
    Returns
    -------
    A dataframe listing the total population in each polygon.
    """
    # Ensure CRS matches
    with rio_open(raster_file) as f:
        raster_crs = f.crs
    
    if raster_crs is None:
        warn("Raster file does not specify a CRS - assuming WGS84")
        raster_crs = "WGS84"
        
    polygons.to_crs(raster_crs, inplace=True)

    # Summarise to polygons
    vals = zonal_stats(
        vectors=polygons,
        raster=raster_file,
        stats=[summary_fun],
        all_touched=True,
        categorical=False
    )

    vals = DataFrame(vals)
    vals.rename({summary_fun: column_name}, axis=1, inplace=True)

    # Add locations and rename to match sequence annotations
    vals["location"] = polygons.location.apply(lambda x: f"location{x}")

    return vals[["location", column_name]]
