# Functions for calculating geodetic distances between hexagons

import h3
from pyproj import CRS

from .edge_feature import CachedEdgeFeature


class GeodeticDistance(CachedEdgeFeature):
    """
    A class for calculating geodetic distances.
    
    Methods
    -------
    get(from_node, to_node)
        Retreive a distance, calculating it if needed.
    save(filename):
        Save a record of previously-calculated values to disk in numpy's ".npy" format.
    restore(filename)
        Restore a previously-saved set of values from disk.
    """

    def __init__(self, node_names, crs="WGS84"):
        """
        Parameters
        ----------
        node_names: List of names used to index stored features.
        crs: A pyproj-compatible coordinate reference system specification (default=WGS84).
        """
        super().__init__(node_names)
        
        crs = CRS.from_user_input(crs)
        self.geod = crs.get_geod()
    
    def calculate(self, from_node, to_node):
        """
        Calculate the geodetic distance between the centres of two H3 hexagons.
        
        Parameters
        ----------
        from_node: An origin node identifier present in `node_names`.
        to_node: A destination node identifier present in `node_names`.
        
        Returns
        -------
        float
        """
        from_coords = h3.h3_to_geo(from_node)
        to_coords = h3.h3_to_geo(to_node)
        
        _, __, distance = self.geod.inv(
            lons1=from_coords[1], 
            lats1=from_coords[0],
            lons2=to_coords[1], 
            lats2=to_coords[0]
        )
        
        return distance
