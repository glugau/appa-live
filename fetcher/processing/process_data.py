import os
import xarray as xr
from datetime import datetime, timezone
import logging
from . import shift_longitude
from pathlib import Path
import re
import numpy as np

CTX_VARIABLES_PATH = Path(__file__).resolve().parent.parent / "ctx_variables.nc"

def process_data(era5_data_folder: str, 
                 ifs_data_folder: str,
                 toa_solar_radiation: xr.DataArray,
                 target_folder: str) -> None:
    '''
    Imports the latest data from IFS, the latest data from ERA5, and concatenates
    them so that the latest ERA5 sea surface temperature is given along with the
    rest. Makes everything into a zarr file ready to be sent for inference.
    '''
    logger = logging.getLogger(__name__)
    
    path_era5_p, path_era5_s = _get_latest_era5(era5_data_folder)
    path_ifs_p, path_ifs_s = _get_latest_ifs(ifs_data_folder)
    
    # Retrieve the date and time of the IFS data
    dt = latest_datetime(ifs_data_folder)
    dt_str = dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    dt_np = np.datetime64(dt.replace(tzinfo=None), 'ns')
    
    ds_ifs_p = shift_longitude.shift_longitude(
        xr.open_dataset(path_ifs_p, engine='netcdf4'), '0-360')
    ds_ifs_s = shift_longitude.shift_longitude(
        xr.open_dataset(path_ifs_s, engine='netcdf4'), '0-360')
    ds_era5_s = shift_longitude.shift_longitude(
        xr.open_dataset(
            path_era5_s,
            engine='netcdf4'),
        '0-360').squeeze("valid_time", drop=True)
    ds_ctx = shift_longitude.shift_longitude(
        xr.open_dataset(
            CTX_VARIABLES_PATH,
            engine='netcdf4'),
        '0-360').squeeze("valid_time", drop=True)

    logger.info('Loaded all required netCDF files for processing')
    
    logger.info('Shifting longitudes to a common range')
    
    logger.info('Merging ERA5 SST, IFS, TOA solar radiation, and context vars into a single dataset')
    ds = xr.merge([
        ds_ifs_s,
        ds_ifs_p,
        ds_ctx
    ])
    ds['sea_surface_temperature'] = ds_era5_s['sst']
    ds['toa_incident_solar_radiation'] = toa_solar_radiation

    logger.info('Adding TOA solar radiation to the dataset')
    
    logger.info('Cleaning up the data to match expected format')
    
    ds = ds.rename({
        # Rename to level
        'isobaricInhPa': 'level',
        
        # Variables from IFS
        'u10': '10m_u_component_of_wind',
        'v10': '10m_v_component_of_wind',
        't2m': '2m_temperature',
        'msl': 'mean_sea_level_pressure',
        'gh': 'geopotential',
        'q': 'specific_humidity',
        't': 'temperature',
        'u': 'u_component_of_wind',
        'v': 'v_component_of_wind',
        'tp': 'total_precipitation',
        # 'skt': 'sea_surface_temperature' TODO: Change if using skt
        # Warning: sea_surface_temperature is incl. by era5.
        # Must drop it prior to using the skt.
        
        # Context variables from ERA5
        'anor': 'angle_of_sub_gridscale_orography',
        'isor': 'anisotropy_of_sub_gridscale_orography',
        'lsm': 'land_sea_mask',
        'slor': 'slope_of_sub_gridscale_orography',
        'sdor': 'standard_deviation_of_orography',
        
        # Already properly named by solar_radiation.py
        'toa_incident_solar_radiation': 'toa_incident_solar_radiation',
    })
    
    # Change to float32 (from float64)
    ds = ds.assign_coords(
        longitude=ds.longitude.astype('float32'),
        latitude=ds.latitude.astype('float32')
    )
    
    # Assign the time variable to all variables
    for var in ds.data_vars:
        ds[var] = ds[var].expand_dims(time=[dt_np])
        ds[var] = ds[var].transpose('time', ...) # puts time first

    # Then drop unused coords
    ds = ds.drop_vars([
        'step',
        'valid_time',
        'meanSea',
        'surface',
        'number',
        'expver'
    ])
        
    target_path = os.path.join(target_folder, f'{dt_str}.zarr')
    
    ds.attrs = {}
    
    # Save to file
    logger.info(f'Saving to {target_path}')
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        
    ds.to_zarr(target_path, mode='w', zarr_version=2, consolidated=True)

def latest_datetime(ifs_data_folder : str) -> datetime:
    path_pressure = _get_latest_ifs(ifs_data_folder)[0]
    return datetime.strptime(
        re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", Path(path_pressure).name).group(), 
        "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)

def _get_latest_era5(data_folder: str) -> tuple[str, str]:
    '''
    Gets the latest ifs data file that has been downloaded.

    Returns:
        (pressure_path, single_path) (str, str): A tuple of paths to a pressure and
            single level file.
    '''
    pressure_files = [f for f in os.listdir(data_folder) if f.endswith("pressure.nc")]
    single_files = [f for f in os.listdir(data_folder) if f.endswith("single.nc")]
    
    pressure_file = os.path.join(data_folder, max(pressure_files))
    single_file = os.path.join(data_folder, max(single_files))
    
    return pressure_file, single_file

def _get_latest_ifs(data_folder: str) -> tuple[str, str]:
    '''
    Gets the latest ifs data file that has been downloaded.

    Returns:
        (pressure_path, single_path) (str, str): A tuple of paths to a pressure and
            single level file.
    '''
    pressure_files = [f for f in os.listdir(data_folder) if f.endswith("pressure.nc")]
    single_files = [f for f in os.listdir(data_folder) if f.endswith("single.nc")]
    
    pressure_file = os.path.join(data_folder, max(pressure_files))
    single_file = os.path.join(data_folder, max(single_files))
    
    return pressure_file, single_file

if __name__ == '__main__':
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    logging.basicConfig(level=logging.INFO)
    from custom_data.solar_radiation import xarray_integrated_toa_solar_radiation
    process_data('./data/era5',
                 './data/ifs',
                 xarray_integrated_toa_solar_radiation(
                     datetime.now(tz=timezone.utc), 1
                 ),
                 './data/processed')

    ds = xr.open_dataset('data/processed/2025-07-15T00:00:00Z.zarr')
    print(ds)
    ds.to_netcdf('data/processed/2025-07-15T00:00:00Z.nc')

    # ds = xr.open_dataset('data/processed/2025-07-15T00:00:00Z.zarr')
    # print(ds)

    
    #ds = xr.open_dataset('./data/processed/2025-07-14T11:38:45Z.nc')
    #print(ds)
    
    # ds = xr.open_dataset('ctx_variables.nc')
    # print(ds.info())