import numpy as np
from matplotlib import cm

def array_to_rgb_u8(data, cmap_name='viridis'):
    """
    Converts a 2D array to a (3, H, W) RGB image using the given colormap.

    Parameters:
    - data: 2D numpy array (lat, lon)
    - cmap_name: str, name of a matplotlib colormap

    Returns:
    - rgb: numpy array with shape (3, lat, lon), dtype=float32, range [0, 1]
    """
    norm = (data - np.min(data)) / (np.ptp(data) + 1e-8)  # normalize to [0, 1]
    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(norm)  # shape: (lat, lon, 4)
    rgb = np.moveaxis(rgba[..., :3], -1, 0)  # -> (3, lat, lon)
    rgb = (rgb * 255).astype(np.uint8)
    return rgb