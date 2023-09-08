# Functions for calculating geodetic distances between hexagons

import h3
import numpy as np
from pyproj import CRS

from .edge_feature import CachedEdgeFeature


class CoordinateGeodeticDistance(object):
    """
    A class for calculating geodetic distances between shapely point objects or 
    geographic coordinates.
    
    Note that this class does not cache results for later use.
    
    Methods
    -------
    get_distance_from_geo(origin, destination)
        Calculate the geodetic distance between two coordinate tuples.
    get_distance_from_shapely(origin, destination)
        Calculate the geodetic distance between two shapely point objects.
    """

    def __init__(self, crs="WGS84"):
        """
        Parameters
        ----------
        crs: A pyproj-compatible coordinate reference system specification (default=WGS84).
        """
        crs = CRS.from_user_input(crs)
        self.geod = crs.get_geod()

    def get_distance_from_geo(self, origin, destination):
        """
        Calculate the geodetic distance between two coordinate tuples.
        
        Parameters
        ----------
        origin: A (lat, lon) tuple used as the origin.
        destination: A (lat, lon) tuple used as the destination.
        
        Returns
        -------
        float
        """
        _, __, distance = self.geod.inv(
            lons1=origin[1],
            lats1=origin[0],
            lons2=destination[1],
            lats2=destination[0]
        )

        return distance
    
    def get_distance_from_shapely(self, origin, destination, use_centroids=True):
        """
        Calculate the geodetic distance between two shapely objects. If the objects are
        not points, the distance is calculated between either their centroids (if use_centroids
        is True) or between representative points guaranteed to fall within the object (if
        use_centroids if False).
        
        Parameters
        ----------
        origin: A shapely object used as the origin.
        destination: A shapely object used as the destination.
        use_centroids: A boolean indicating whether to use the centroids of any non-point objects
                       (True) or reprentative points instead (False).
        
        Returns
        -------
        float
        """
        # For point objects, these actions do nothing:
        if use_centroids:
            origin = origin.centroid
            destination = destination.centroid
        else:
            origin = origin.representative_point()
            destination = destination.representative_point()
        
        dist = self.get_distance_from_geo(
            origin=(origin.y, origin.x),
            destination=(destination.y, destination.x)
        )
        
        return dist
        
    def get_pairwise_distances(self, objects, use_centroids=True):
        """
        Calculate the geodetic distance between all pairs of objects in a set.
        
        Parameters
        ----------
        objects: An iterable of objects. These can be either (lat, lon) tuples or shapely objects,
                 but not a mixture of both.
        use_centroids: A boolean indicating whether to use the centroids of any non-point objects
                       (True) or reprentative points instead (False).
        
        Returns
        -------
        A square numpy array of distances, with the same order as the input.
        """
        dists = np.zeros((len(objects), len(objects)))
        
        for i in range(len(objects)):
            for j in range(i+1, len(objects)):
                origin = objects[i]
                destination = objects[j]
                
                if isinstance(origin, tuple) and isinstance(destination, tuple):
                    dists[i, j] = self.get_distance_from_geo(origin, destination)
                else:
                    dists[i, j] = self.get_distance_from_shapely(origin, destination)
        
        # Fill in the lower triangle
        dists = dists + dists.T
        
        return dists


class GeodeticDistance(CachedEdgeFeature):
    """
    A class for calculating geodetic distances between H3 hexagons.
    
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
