# Base class for calculating edge features (i.e., describing a connection between two
# locations, such as distance)

import abc

from numpy import full as np_full
from numpy import save as np_save
from numpy import load as np_load
from numpy import nan, isnan

class CachedEdgeFeature(abc.ABC):
    """
    Base class for objects which calculate edge features as needed, but return 
    previously-calculated values if available.
        
    Values can be retreived by specifying the origin and destination node names. The 
    stored values can also be saved for later use using the save and restore methods.
    """
    def __init__(self, node_names):
        """
        Parameters
        ----------
        node_names: List of names used to index stored features.
        """
        n_nodes = len(node_names)
        self.node_names = node_names
        self.stored_values = np_full((n_nodes, n_nodes), nan)
    
    def get(self, from_node, to_node):
        """
        Retreive an edge feature, calculating it if needed.
        
        Parameters
        ----------
        from_node: An origin node identifier present in `node_names`.
        to_node: A destination node identifier present in `node_names`.
        
        Returns
        -------
        float
        """
        from_ind = self.node_names.index(from_node)
        to_ind = self.node_names.index(to_node)
        val = self.stored_values[from_ind, to_ind]
        
        if isnan(val):
            val = self.calculate(from_node, to_node)
        
        return val
    
    def set(self, from_node, to_node, value):
        """
        Save a calculated value in the internal data store.
        
        Parameters
        ----------
        from_node: An origin node identifier present in `node_names`.
        to_node: A destination node identifier present in `node_names`.
        value: The value to store.
        
        Returns
        -------
        None
        """
        from_ind = self.node_names.index(from_node)
        to_ind = self.node_names.index(to_node)
        self.stored_values[from_ind, to_ind] = value
    
    def save(self, filename):
        """
        Save the stored values to disk in numpy's ".npy" format.
        
        Parameters
        ----------
        filename: Location to save to.
        
        Returns
        -------
        None
        """
        np_save(filename, self.stored_values)
        
    def restore(self, filename):
        """
        Restore a previously-saved set of values from disk. This 
        operation occurs in place.
        
        Parameters
        ----------
        filename: Location to read from.
        
        Returns
        -------
        None
        """
        self.stored_values = np_load(filename)
    
    @abc.abstractmethod
    def calculate(self, from_node, to_node):
        """
        Derived classes must implement a method which calculates 
        features and saves any obtained values in self.stored_values.
        """
        pass
