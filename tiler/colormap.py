import numpy as np
from matplotlib import colormaps as cm
import xarray as xr
import logging
from concurrent.futures import ThreadPoolExecutor

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

def _1d_arr_to_rgb_u8(data, data_min, data_max, cmap_name='viridis'):
    """Used by `get_legends`, converts a 1D array of data into a list of dicts,
    with `r`, `g`, and `b` keys.

    Args:
        data (_type_): _description_
        data_min (_type_): _description_
        data_max (_type_): _description_
        cmap_name (str, optional): _description_. Defaults to 'viridis'.

    Returns:
        list[dict]: List of {`r`, `g`, `b`} dictionaries for each value.
    """
    norm = np.clip((data - data_min) / (data_max - data_min + 1e-8), 0, 1)
    cmap = cm.get_cmap(cmap_name)
    rgb = cmap(norm)[..., :3]  # Drop alpha
    rgb_u8 = (rgb * 255).astype(np.uint8)
    rgb_list = [{'r': int(r), 'g': int(g), 'b': int(b)} for r, g, b in rgb_u8.reshape(-1, 3)]
    return rgb_list

def get_legends(
    dataset: xr.Dataset,
    qmin: float,
    qmax:float,
    cmap_mappings: dict[str, str], 
    cmap_default: str,
    n_values: int = 100,
):
    """Get a dictionary, where each key corresponds to a data variable in `dataset`,
    and for each key contains a `colors` field and a `values` field, with the same
    length. A given color's index in the `colors` field corresponds to the value
    with the same index in `values`. For pressure level variables, the key for
    the variable contains child dictionaries, where the key is given by the
    pressure level. Colors are given as dictionaries of `{r, g, b}` values.
    This function is multithreaded by default.

    Args:
        dataset (xr.Dataset): Dataset containing the variables
        qmin (float): Minimum rendered quantile
        qmax (float): Maximum rendered quantile
        cmap_mappings (dict[str, str]): (variable, colormap) mappings
        cmap_default (str): Default colormap, if none is provided for the given
            variable
            
    Returns:
        dict: Dictionary, as described in the summary
    """
    logger = logging.getLogger(__name__)
    output = {}
    
    def process_variable(variable):
        logger.info('Computing colormap legend(s) for ' + variable)
        this_output = {}
        cmap = cmap_mappings.get(variable, cmap_default)
        is_level = 'level' in dataset[variable].dims
        if is_level:
            for ilevel in range(len(list(dataset['level'].to_numpy()))):
                level_val = int(dataset['level'].values[ilevel])
                this_output[level_val] = {}
                dqmin = float(dataset[variable].sel(level=level_val).quantile(qmin, dim=['time', 'latitude', 'longitude']))
                dqmax = float(dataset[variable].sel(level=level_val).quantile(qmax, dim=['time', 'latitude', 'longitude']))
                values = np.linspace(dqmin, dqmax, n_values)
                colors = _1d_arr_to_rgb_u8(values, dqmin, dqmax, cmap)
                this_output[level_val]['values'] = values.astype(float).tolist()
                this_output[level_val]['colors'] = colors
        else:
            dqmin = float(dataset[variable].quantile(qmin, dim=['time', 'latitude', 'longitude']))
            dqmax = float(dataset[variable].quantile(qmax, dim=['time', 'latitude', 'longitude']))
            values = np.linspace(dqmin, dqmax, n_values)
            colors = _1d_arr_to_rgb_u8(values, dqmin, dqmax, cmap)
            this_output['values'] = values.astype(float).tolist()
            this_output['colors'] = colors
        logger.info('DONE computing colormap legend(s) for ' + variable)
        return variable, this_output
        
    output = {}
    with ThreadPoolExecutor() as executor:
        results = executor.map(process_variable, dataset.data_vars)
        for variable, result in results:
            output[variable] = result
    
    return output
