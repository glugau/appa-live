# https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels
# https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels

import os
import requests
import cdsapi
import logging
from datetime import datetime
import zipfile

def download_latest(target: str) -> datetime:
    '''
    Download the latest relevant files given by the era5 model.
    In order for this function to work, a CDS API key must be provided as an
    environment variable called CDS_API_KEY (https://cds.climate.copernicus.eu).
        
    Parameters:
        target (str): The target output **folder**.
    Returns:
        datetime: The date and time of the downloaded data
    '''
    
    CDS_API_KEY = os.environ['CDS_API_KEY']
    
    # Save the API key (env var) to the ~/.cdsapirc file (as required by the spec)
    with open(os.path.expandvars("$HOME/.cdsapirc"), "w+") as f:
        f.write(f'url: https://cds.climate.copernicus.eu/api\nkey: {CDS_API_KEY}')
    
    dt = _latest_datetime()
    
    logger = logging.getLogger(__name__)
    logger.info(f'Found latest datetime: {dt}')
    logger.info(f'Downloading pressure levels for {dt}...')
    _download_pressure_levels(target, dt)
    logger.info(f'Downloading single levels for {dt}...')
    _download_single_levels(target, dt)
    return dt

def _download_pressure_levels(target: str, dt: datetime):
    '''
    Download the latest pressure levels. See
    [here](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels)
    for more info. The selected variables are the same as in the APPA paper.
    
    Will not work if called externally (requires the API key to first be stored).
    '''
    
    dataset = "reanalysis-era5-pressure-levels"
    request = {
        "product_type": ["reanalysis"],
        "variable": [
            "geopotential",
            "specific_humidity",
            "temperature",
            "u_component_of_wind",
            "v_component_of_wind"
        ],
        "year": [dt.year],
        "month": [dt.month],
        "day": [dt.day],
        "time": [dt.strftime("%H:%M:%S")],
        "pressure_level": [
            "50", "100", "150",
            "200", "250", "300",
            "400", "500", "600",
            "700", "850", "925",
            "1000"
        ],
        "data_format": "netcdf",
        "download_format": "zip"
    }

    path = os.path.join(target, f'{dt.strftime("%Y-%m-%dT%H:%M:%SZ")}-pressure.zip')

    client = cdsapi.Client()
    client.retrieve(dataset, request).download(target=path)
    
    filename_in_zip = 'data_stream-oper_stepType-instant.nc'
    
    with zipfile.ZipFile(path, 'r') as z:
        z.extract(filename_in_zip,
                  path=target)
    
    os.rename(os.path.join(target, filename_in_zip), os.path.splitext(path)[0] + '.nc')

def _download_single_levels(target: str, dt: datetime):
    '''
    Download the latest single levels. See
    [here](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels)
    for more info. The selected variables are the same as in the APPA paper.
    
    Will not work if called externally (requires the API key to first be stored).
    '''

    dataset = "reanalysis-era5-single-levels"
    request = {
        "product_type": ["reanalysis"],
        "variable": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "2m_temperature",
            "mean_sea_level_pressure",
            "sea_surface_temperature",
            "total_precipitation"
        ],
        "year": [dt.year],
        "month": [dt.month],
        "day": [dt.day],
        "time": [dt.strftime("%H:%M:%S")],
        "data_format": "netcdf",
        "download_format": "zip"
    }

    path = os.path.join(target, f'{dt.strftime("%Y-%m-%dT%H:%M:%SZ")}-single.zip')

    client = cdsapi.Client()
    client.retrieve(dataset, request).download(target=path)
    
    filename_in_zip = 'data_stream-oper_stepType-instant.nc'
    
    with zipfile.ZipFile(path, 'r') as z:
        z.extract(filename_in_zip,
                  path=target)
    
    os.rename(os.path.join(target, filename_in_zip), os.path.splitext(path)[0] + '.nc')


def _latest_datetime() -> datetime:
    '''
    Get the latest datetime available for the era5 hourly dataset.
    Returns:
        datetime(str): Latest date and time available (YYYY-mm-ddTHH-MMZ)
    '''
    r = requests.get("https://cds.climate.copernicus.eu/api/catalogue/v1/collections/reanalysis-era5-single-levels")
    json = r.json()
    latest_single = json['extent']['temporal']['interval'][0][1]
    latest_single_dt = datetime.fromisoformat(latest_single.replace('Z','+00:00'))
    
    r = requests.get("https://cds.climate.copernicus.eu/api/catalogue/v1/collections/reanalysis-era5-pressure-levels")
    json = r.json()
    latest_pressure = json['extent']['temporal']['interval'][0][1]
    latest_pressure_dt = datetime.fromisoformat(latest_pressure.replace('Z','+00:00'))
    
    # Just as an extra safety, we make sure we take the last datetime that is
    # available for both datasets (single levels and pressure levels). The datetimes
    # should normally be equal.
    return min(latest_pressure_dt, latest_single_dt)

if __name__ == '__main__':
    dt = _latest_datetime()
    print(dt)