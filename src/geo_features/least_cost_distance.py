# Functions for calculating least cost distances between hexagons

from rasterio.transform import rowcol
from skimage.graph import MCP_Geometric
from h3 import h3_get_resolution, k_ring, h3_to_children, h3_to_geo
from numpy import zeros as np_zeros

from .edge_feature import CachedEdgeFeature


class LeastCostDistance(CachedEdgeFeature):
    """
    A class for calculating least cost distances. 
        
    Resolution controls how this is done: if resolution matches that of the H3 hexagon 
    identifiers passed to `get()`, distances will be from between the centres of 
    hexagons. If resolution is finer, the mimimum of all costs between centres of child 
    hexagons occuring within the two parents is returned instead.
    
    Methods
    -------
    get(from_node, to_node)
        Retreive a distance, calculating it if needed.
    save(filename):
        Save a record of previously-calculated values to disk in numpy's ".npy" format.
    restore(filename)
        Restore a previously-saved set of values from disk.
    """
    
    def __init__(self, node_names, cost_raster, raster_transform, resolution, k_distance=1):
        """      
        Parameters
        ----------
        node_names: List of names used to index stored features.
        cost_raster: An ndarray to use as the cost surface.
        raster_transform: `rasterio` coefficients mapping pixel coordinates to the coordinate 
                           reference system in `cost_raster`.
        resolution: H3 resolution for calculations.
        k_distance: Number of neighbours for which distances will be required (can be used to 
                    reduce redundant calculations; default: 1).
        """
        base_resolution = h3_get_resolution(node_names[0])

        if resolution < base_resolution:
            m = f"Resolution must be at least as fine as that of from_hex (i.e., >= {base_resolution})."
            raise ValueError(m)
            
        if k_distance < 1:
            raise ValueError("k_distance must be >= 1.")

        super().__init__(node_names)
        
        self.mcp = MCP_Geometric(cost_raster, fully_connected=True)
        
        self.raster_transform = raster_transform
        self.resolution = resolution
        self.base_resolution = base_resolution
        self.k_distance = k_distance
        

    def get_costs_from_geo(self, start_points, end_points):
        """
        Get the least cost path between a set of possible start and end points.
        
        Parameters
        ----------
        start_points: An iterable of starting coordinates, with each coordinate a (lat, lon) tuple.
        end_points: An iterable of end coordinates.
        
        Returns
        -------
        A numpy array of costs, corresponding to each end point (and using the nearest/cheapest 
        start point).
        """
        xy_from = (rowcol(self.raster_transform,
                   c[1], c[0]) for c in start_points)
        xy_to = [rowcol(self.raster_transform, c[1], c[0]) for c in end_points]

        cumulative_cost, _ = self.mcp.find_costs(xy_from, xy_to)

        # Unpack [(x1, y1), (x2, y2), ...] into (x_inds, y_inds)
        end_inds = tuple(zip(*xy_to))
        
        # Since costs are cumulative, only need to keep values for the end points
        end_costs = cumulative_cost[end_inds]

        return end_costs

    def get_costs_from_h3(self, from_hex, to_hex):
        """
        Get the least cost path between two H3 hexagons. 
        
        Parameters
        ----------
        from_hex: An H3 hexagon identifier.
        to_hex: An H3 hexagon identifier.
        
        Returns
        -------
        float
        """
        # Get costs
        if self.resolution == self.base_resolution:
            # If resolution matches, get least cost between centres of hexagons
            from_center = h3_to_geo(from_hex)
            to_center = h3_to_geo(to_hex)
            
            min_cost = self.get_costs_from_geo([from_center], [to_center])
            
            assert min_cost.shape == (1,)
            return min_cost[0]

        else:
            # Get hexagons inside the specified hexagons, then costs between the centres of these:
            from_children = h3_to_children(from_hex, res=self.resolution)
            from_centres = [h3_to_geo(c) for c in from_children]

            to_children = h3_to_children(to_hex, res=self.resolution)
            to_centres = [h3_to_geo(c) for c in to_children]

            # Costs
            # - Getting costs to all end points at once more efficient, since they will be 
            #   encountered while searching outward from a given start point anyway (all end
            #   points are close together)
            costs = self.get_costs_from_geo(from_centres, to_centres)

            # Get the minimum cost across all end points
            return costs.min()

    def calculate(self, from_node, to_node):
        """
        Calculate least cost distance.
        
        Parameters
        ----------
        from_node: An origin node identifier present in `node_names`.
        to_node: A destination node identifier present in `node_names`.
        
        Returns
        -------
        float
        """
        return self.get_costs_from_h3(from_node, to_node)
