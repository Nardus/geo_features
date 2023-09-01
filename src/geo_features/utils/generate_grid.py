import numpy as np
import geopandas as gpd
from shapely.geometry import box

def generate_grid(data, cell_size, value_name="value", fill_value=None):
    """
    Create a grid of polygons covering all features in a GeoDataFrame.
    
    Based on https://james-brennan.github.io/posts/fast_gridding_geopandas/
    
    Parameters
    ----------
    data: A geopandas dataframe containing features to be covered by the grid.
    cell_size: The size of each grid cell, in the same units as the CRS of data.
    value_name: The name of the column to use for the value of each grid cell.
    fill_value: The initial value to use for each grid cell.
    
    Returns
    -------
    A geopandas dataframe containing the grid polygons.
    """
    xmin, ymin, xmax, ymax = data.total_bounds
    grid_cells = []

    for x0 in np.arange(xmin, xmax+cell_size, cell_size):
        for y0 in np.arange(ymin, ymax+cell_size, cell_size):
            x1 = x0 - cell_size
            y1 = y0 + cell_size

            grid_cells.append(box(x0, y0, x1, y1))
    
    empty_data = {value_name: [fill_value] * len(grid_cells)}
    
    return gpd.GeoDataFrame(empty_data, geometry=grid_cells, crs=data.crs)
