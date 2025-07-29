import numpy as np
from matplotlib import cm

def array_to_rgb_u8(data, data_min, data_max, cmap_name='viridis'):
    """Converts a 2D array to a (3, H, W) RGB image using the given colormap.

    Args:
        data (_type_): The 2d data
        data_min (float): Minimum data value to represent.
        data_max (float): Maximum data value to represent.
        cmap_name (str, optional): Name of the colormap. Defaults to 'viridis'.

    Returns:
        _type_: _description_
    """
    norm = np.clip((data - data_min) / (data_max - data_min + 1e-8), 0, 1)
    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(norm)  # shape: (lat, lon, 4)
    rgb = np.moveaxis(rgba[..., :3], -1, 0)  # -> (3, lat, lon)
    rgb = (rgb * 255).astype(np.uint8)
    return rgb