# Find representative points for polygons when an altitude threshold is in place

from rasterio import transform
from geopandas import points_from_xy
from numpy import argmax, isinf

def find_representative_points(gdf, altitude_raster, altitude_transform,
                               projection_crs, raster_crs="WGS84", increment=1):
    """
    Find representative points, guaranteed to lie within each polygon and below any altitude
    thresholds.
    
    Parameters
    ----------
    gdf: A geopandas dataframe containing polygons.
    altitude_raster: A raster, with thresholded locations indicated using either infinite or
                     negative values.
    altitude_transform: The `rasterio` transform for `altitude_raster`.
    projection_crs: Projected CRS to use when finding representative points.
    raster_crs: The CRS used by `altitude_raster`.
    increment: Number of raster cells to shift invalid points by in each attempt. Cells in  
               all directions will be considered (but not diagonally), with the highest
               valid point returned.
    
    Returns
    -------
    A geopandas dataframe with representative points for each polygon.
    """
    # Simplify representation of thresholded areas
    altitude_raster[isinf(altitude_raster)] = -1
    
    # Get representative points - since altitude may be thresholded outside polygons, these
    # *have* to be inside the polygons (so can't use centroids)
    rep_points = gdf.to_crs(projection_crs)
    rep_points["point"] = rep_points.representative_point()

    rep_points = (
        rep_points
        .drop("geometry", axis=1)
        .set_geometry("point")
        .to_crs(raster_crs)
    )

    # Convert to raster indices
    rep_x = rep_points.geometry.x
    rep_y = rep_points.geometry.y
    rep_inds = [transform.rowcol(altitude_transform, x, y)
                for x, y in zip(rep_x, rep_y)]

    # Shift each point until it's in a valid part of the map (i.e. not in a thresholded region)
    raster_vals = [altitude_raster[r, c] for r, c in rep_inds]

    attempts = 0
    current_shift = increment

    while min(raster_vals) < 0 and attempts < 100000:
        attempts += 1

        for i in range(len(rep_inds)):
            if raster_vals[i] < 0:
                # Try shifting in all directions
                ind = rep_inds[i]
                left_val = altitude_raster[ind[0], ind[1] - current_shift]
                right_val = altitude_raster[ind[0], ind[1] + current_shift]
                top_val = altitude_raster[ind[0] - current_shift, ind[1]]
                bottom_val = altitude_raster[ind[0] + current_shift, ind[1]]

                neighbour_vals = [left_val, right_val, top_val, bottom_val]

                if max(neighbour_vals) > 0:
                    # Find direction with highest valid value
                    max_ind = argmax(neighbour_vals)

                    if max_ind == 0:
                        new_ind = (ind[0], ind[1] - current_shift)
                    elif max_ind == 1:
                        new_ind = (ind[0], ind[1] + current_shift)
                    elif max_ind == 2:
                        new_ind = (ind[0] - current_shift, ind[1])
                    else:
                        new_ind = (ind[0] + current_shift, ind[1])

                    # Update inds and raster_vals
                    rep_inds[i] = new_ind
                    raster_vals[i] = neighbour_vals[max_ind]

        # Increase current_shift for next round
        current_shift += increment

    if min(raster_vals) < 0:
        raise RuntimeError("Some points remain in thresholded areas after 100000 tries.")

    # Convert indices back to coordinates
    # - Note: this shifts even valid points slightly, to center of a raster cell
    rep_coords = [transform.xy(altitude_transform, r, c)
                  for r, c in rep_inds]
    rep_coords = tuple(zip(*rep_coords))  # unpack to (x_coords, y_coords)
    rep_points["geometry"] = points_from_xy(*rep_coords, crs=raster_crs)

    rep_points = (
        rep_points
        .drop("point", axis=1)
        .set_geometry("geometry")
        .to_crs(gdf.crs)
    )

    return rep_points
