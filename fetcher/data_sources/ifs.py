# The IFS model is maintained by ECMWF, and outputs, from a set of observations
# and recent forecasts, an estimate of the current system.
# More information: 
#   https://www.ecmwf.int/en/forecasts/documentation-and-support/changes-ecmwf-model
#   https://data.ecmwf.int/forecasts/
#   https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS
#   https://github.com/ecmwf/ecmwf-opendata - List of available params

from ecmwf.opendata import Client
import os
import xarray as xr
import cfgrib
import logging
from datetime import datetime, timezone

def download_latest(target: str) -> datetime:
    '''
    Download the latest relevant files given by the IFS model. No API key is
    required for this model.
        
    Parameters:
        target (str): The target output **folder**.
    Returns:
        datetime: The date and time of the downloaded data
    '''
    data_file = os.path.join(target, 'data.grib2')
    client = Client(model='ifs')
    result = client.retrieve(
        type='fc',
        step=0,
        param=[
                # Single level fields
                
                '10u',  # 10 metre U wind component
                '10v',  # 10 metre V wind component
                '2t',   # 2 metre temperature
                'msl',  # Mean sea level pressure
                #'ro',   # Runoff
                #'skt',  # Skin temperature
                #'sp',   # Surface pressure
                #'st',   # Soil Temperature - Not found?!
                #'stl1', # Soil temperature level 1 - Not found?!
                #'tcwv', # Total column vertically-integrated water vapour 	
                'tp',   # Total Precipitation
                #'ssr', # Doesn't work
                
                # Atmospheric fields on pressure levels
                
                #'d',   # Divergence
                'gh', 	# Geopotential height
                'q',	# Specific humidity
                #'r',	# Relative humidity
                't',	# Temperature 	K
                'u',	# U component of wind
                'v',	# V component of wind
                #'vo', 	# Vorticity (relative)
            ],
        target=data_file,
    )
        
    iso_format = result.datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
    os.rename(data_file, os.path.join(target, f'{iso_format}.grib2'))
    data_file = os.path.join(target, f'{iso_format}.grib2')
    
    logger = logging.getLogger(__name__)
    logger.info('Converting the obtained .grib2 file into NetCDF4')
    _grib_to_netcdf4(data_file)
    
    return result.datetime.replace(tzinfo=timezone.utc)

def _grib_to_netcdf4(grib_path: str) -> None:
    dss = cfgrib.open_datasets(grib_path, decode_timedelta=True)
    
    # Remove the 'heightAboveGround' coordinate that's messing up the merging
    # of all single-layer variables into a single file.
    for i in range(len(dss)):
        if 'heightAboveGround' in dss[i].coords:
            dss[i] = dss[i].drop_vars('heightAboveGround')
            
    pressures = []
    singles= []

    for ds in dss:
        if 'isobaricInhPa' in ds.coords:
            pressures.append(ds)
        else:
            singles.append(ds)

    pressures = xr.merge(pressures)
    singles = xr.merge(singles)

    if 'gh' in pressures.variables:
        pressures['gh'] = pressures['gh'] * 9.81
    
    pressures.to_netcdf(os.path.splitext(grib_path)[0] + '-pressure.nc')
    singles.to_netcdf(os.path.splitext(grib_path)[0] + '-single.nc')