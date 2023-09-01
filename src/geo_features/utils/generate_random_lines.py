import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString

def generate_random_lines(polygons, n, random_seed=1, group_column="location"):
    """
    Generate lines connecting random points between polygons. 
    
    For each polygon, n random points are connected to n random points in all other polygons, 
    creating n linear paths between each pair of polygons.
    
    Parameters
    ----------
    polygons: A geopandas dataframe containing polygons.
    n: Number of random connections required between each pair of polygons.
    group_column: Name of a column in polygons to use for grouping.
    
    Returns
    -------
    A geopandas dataframe containing the sampled connections as LineString features.
    """
    # Sample random points within each location
    random_points = polygons.copy()
    random_points.geometry = polygons.sample_points(n, seed=random_seed)
    random_points = random_points.explode(index_parts=False)
    
    # Convert to lines
    lines = []
    
    for group1 in random_points[group_column].unique():
        group1_points = random_points.loc[random_points[group_column] == group1]
        
        for group2 in random_points[group_column].unique():
            if group1 == group2:
                continue
            
            geom = []
            group2_points = random_points.loc[random_points[group_column] == group2]
            
            for p1, p2 in zip(group1_points.geometry, group2_points.geometry):
                geom.append(LineString([p1, p2]))
            
            current = gpd.GeoDataFrame({
                "origin": [group1] * len(geom),
                "destination": [group2] * len(geom),
                "geometry": geom
            },
            crs=polygons.crs
            )
            
            lines.append(current)
    
    return gpd.GeoDataFrame(pd.concat(lines, ignore_index=True))
