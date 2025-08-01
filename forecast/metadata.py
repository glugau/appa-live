# This file handles the unit attachments to the output zarr file, as well as
# conversions if they are required for better visualization.

import xarray as xr

UNIT_MAPPINGS = {
    '10m_u_component_of_wind': 'm/s',
    '10m_v_component_of_wind': 'm/s',
    'v_component_of_wind': 'm/s',
    'u_component_of_wind': 'm/s',
    'total_precipitation': 'mm/h',
    'mean_sea_level_pressure': 'Pa',
    'sea_surface_temperature': 'K',
    'temperature': 'K',
    '2m_temperature': 'K',
    'geopotential': 'm^2 s^-2',
    'specific_humidity': 'kg kg^-1',
}

LONG_NAME_MAPPINS = {
    '10m_u_component_of_wind': '10 meter U wind component',
    '10m_v_component_of_wind': '10 meter V wind component',
    'v_component_of_wind': 'V wind component',
    'u_component_of_wind': 'U wind component',
    'total_precipitation': 'Total precipitation',
    'mean_sea_level_pressure': 'Mean sea level pressure',
    'sea_surface_temperature': 'Sea surface temperature',
    'temperature': 'Temperature',
    '2m_temperature': '2 meter temperature',
    'geopotential': 'Geopotential',
    'specific_humidity': 'Specific humidity'
}


def convert_units(ds: xr.Dataset) -> xr.Dataset:
    """Converts predicted units into desired output units

    Args:
        ds (xr.Dataset): Input dataset (modified in-place)

    Returns:
        xr.Dataset: Converted dataset
    """
    
    # Convert total precipitation from the predicted m/hr to mm/hr
    if 'total_precipitation' in ds:
        ds['total_precipitation'] = ds['total_precipitation'] * 1000
        
    return ds

def attach_metadata(ds: xr.Dataset) -> xr.Dataset:
    """Attach units and long names to the dataset metadata

    Args:
        ds (xr.Dataset): The dataset to which attach the units (modified
            in-place)

    Returns:
        xr.Dataset: The modified dataset
    """
    for var, unit in UNIT_MAPPINGS.items():
        if var in ds and unit is not None:
            ds[var].attrs['units'] = unit

    for var, ln in LONG_NAME_MAPPINS.items():
        if var in ds and ln is not None:
            ds[var].attrs['long_name'] = ln

    return ds