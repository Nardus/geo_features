# Handle landcover data files from the CDS

import os
import pickle
import rioxarray

from warnings import warn
from datetime import date
from zipfile import ZipFile

from . import schedule_cds_requests


def _check_years(years):
    """
    Check that the requested years are valid and available. Years which are valid, but not 
    available will be removed, with a warning.
    
    Parameters
    ----------
    years : list of int
        Years to check.
    
    Returns
    -------
    list of int
        Valid and available years.
    """
    # Completely invalid (an error)
    if not isinstance(years, list):
        raise TypeError("years should be a list.")

    if not all(isinstance(y, int) for y in years):
        raise TypeError("years should be a list of integers.")

    if len(years) != len(set(years)):
        raise ValueError("Requested years should be unique.")
        
    # Unavailable (raise warning)
    #  - Data released with a "1 year delay", but current year doesn't seem to count (e.g. 2019
    #    data was released in early 2021) 
    last_available_year = date.today().year - 2
    
    if any(y < 1992 for y in years):
        warn(f"Requested years before 1992 not yet available. "
             "These will be ignored.", 
             RuntimeWarning, stacklevel=3)
        
        years = [y for y in years if y >= 1992]
    
    if any(y > last_available_year for y in years):
        warn(f"Requested years beyond {last_available_year} not yet available. "
             "These will be ignored.", 
             RuntimeWarning, stacklevel=3)
        
        years = [y for y in years if y <= last_available_year]

    return years


def get_landcover_data(years, archive_folder, summary_fun=None):
    """
    Get landcover data from the CDS API.
    
    Parameters
    ----------
    years : list of int
        Years to get data for.
    archive_folder : str
        Path to a folder where the downloaded data will be stored.
    summary_fun : function
        Function to run on each downloaded file. See `schedule_cds_requests` for details.
        If no summarisation is required, set `summary_fun=None`.
    
    Returns
    -------
    list
        The output of `summary_fun` for each query. If `summary_fun` is None, a list of
        (output_file_name, query) tuples.
    """
    # Check if requested data are available
    years = sorted(years)
    years = _check_years(years)
    
    # Build queries
    queries = []

    for year in years:
        if year < 2016:
            version = "v2.0.7cds"
        else:
            # v2.1.1 contains 2016 onwards, but not earlier data
            version = "v2.1.1"

        query = {
            "variable": "all",
            "format": "zip",
            "year": year,
            "version": version
        }

        out_name = f"{archive_folder}/satellite-land-cover_{year}.zip"

        res = out_name, query
        queries.append(res)

    # Get data from CDS
    print(f"Scheduling {len(queries)} CDS queries for landcover data.")
    print("\nCheck https://cds.climate.copernicus.eu/cdsapp#!/yourrequests for progress\n")

    query_results = schedule_cds_requests(
        queries,
        summary_fun=summary_fun,
        dataset="satellite-land-cover"
    )
    
    return query_results


def unpack_landcover_file(file_name, clipping_bounds, out_folder):
    """
    Extract and preprocess landcover data from a compressed netCDF file.
    
    Three categories of files will be extracted to `out_folder` (where `<yyyy>` is the year
    represented by `file_name`):
    - `landcover_lccs_category_<yyyy>.tif`: Land cover class
    - `landcover_change_count_<yyyy>.tif`: Number of land cover changes
    - `landcover_lccs_legend_<yyyy>.pkl`: Legend for land cover classes
    
    Parameters
    ----------
    file_name : str
        Path to compressed netCDF file (.zip)
    clipping_bounds : rasterio.coords.BoundingBox
        Bounding box to clip extracter rasters to
    out_folder:
        Location for final output
        
    Returns
    -------
    None
    """
    # Extract file
    archive_folder = os.path.dirname(file_name)

    with ZipFile(file_name) as archive:
        members = archive.infolist()
        assert len(members) == 1, "Expected only one file in zip file"

        out_name = members[0].filename
        assert out_name.endswith(".nc"), "Expected netCDF file."
        assert out_name == os.path.basename(out_name), "Archive members must extract to current dir."

        archive.extract(members[0], archive_folder)

    netcdf = f"{archive_folder}/{out_name}"

    # Extract relevant variables as rasters
    # - CRS is Plate Carrée / WGS84 (EPSG:4326), see:
    #   - http://maps.elie.ucl.ac.be/CCI/viewer/download/ESACCI-LC-Ph2-PUGv2_2.0.pdf (page 32), and
    #   - https://datastore.copernicus-climate.eu/documents/satellite-land-cover/D5.3.1_PUGS_ICDR_LC_v2.1.x_PRODUCTS_v1.1.pdf
    dataset = rioxarray.open_rasterio(netcdf)
    dataset = dataset[0].rio.write_crs("EPSG:4326")

    # - Land cover class
    landcover = dataset.lccs_class
    
    # Also described in flags but needs to be set for rasterstats summaries later:
    landcover.rio.write_nodata(0, inplace=True)

    landcover = landcover.rio.clip_box(
        minx=clipping_bounds.left,
        miny=clipping_bounds.bottom,
        maxx=clipping_bounds.right,
        maxy=clipping_bounds.top,
    )

    flags = landcover.flag_values
    flags = flags.astype(landcover.dtype)
    meanings = landcover.flag_meanings.split()
    landcover_legend = {k: v for k, v in zip(flags, meanings)}

    # - Change count (normalised to rate of change)
    change_count = dataset.change_count

    query_time = change_count.time.values
    assert len(query_time) == 1, "File should represent a single year"
    query_year = query_time[0].year

    # Counts represent number of years with a change since 1992
    elapsed_time = query_year - 1992

    change_count = change_count.rio.clip_box(
        minx=clipping_bounds.left,
        miny=clipping_bounds.bottom,
        maxx=clipping_bounds.right,
        maxy=clipping_bounds.top,
    )

    change_count = change_count / elapsed_time
    
    # Arbitrary (no missing values expected):
    change_count.rio.write_nodata(100, inplace=True)

    # Output
    landcover.rio.to_raster(f"{out_folder}/landcover_lccs_category_{query_year}.tif")
    change_count.rio.to_raster(f"{out_folder}/landcover_change_count_{query_year}.tif")
    
    with open(f"{out_folder}/landcover_lccs_legend_{query_year}.pkl", "wb") as f:
        pickle.dump(landcover_legend, f)

    # Clean up
    dataset.close()
    os.remove(netcdf)
