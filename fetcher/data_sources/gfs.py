# The GFS model is maintained by NOAA and produces data 4 times per day.
# This script downloads the .f000 file and not .anl file. The f000 is the first
# "forecast" while the anl file is the "ground truth" file. The reason for using
# f000 is that this file contains more commonly used variables such as temperature
# at 2 metres, wind U-V at 10m etc.
# More information:
#   https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast
#   https://registry.opendata.aws/noaa-gfs-bdp-pds/
#   https://www.nco.ncep.noaa.gov/pmb/products/gfs/

# THIS FILE IS NOT SUPPOSED TO BE USED AND PROBABLY DOES NOT WORK

import re
import requests
import logging
import os

def download_latest(target: str) -> str:
    '''
    Download the latest relevant files given by the GFS model. No API key is
    required for this model.
        
    Parameters:
        target (str): The target output **folder**.
    Returns:
        datetime (str): The date and time of the downloaded data, in ISO
            8601 format (YYYY-mm-ddTHH-MMZ).
    '''

    # https://www.nco.ncep.noaa.gov/pmb/products/gfs/gfs.t00z.pgrb2.0p25.f000.shtml
    # PARAMS = [
    #     'TMP',      # Temperature
    #     'UGRD',     # U-Component of wind
    #     'VGRD',     # V-Component of wind
    #     'HGT',      # Geopotential height
    #     'SPFH',     # Specific humidity
    #     'PRMSL',    # Pressure Reduced to mean sea level
    #     'PRATE',    # Precipitation Rate [kg/m^2/s] - can't find total because only in next forecast files (needs accumulation)
    #     # 'APCP' 	# ONLY IN f003+ - Total Precipitation [kg/m^2] 
    #     # 'DSWRF',	# ONLY IN f003+ - Downward Short-Wave Radiation Flux [W/m^2]
        
    # ]
    
    base = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/'
    logger = logging.getLogger(__name__)
    
    # Get the latest date
    r = requests.get(base)
    latest_date = max(re.findall(r"gfs\.(\d{8})", r.text))
    
    # Get the latest available hour
    hours_url = f"{base}gfs.{latest_date}/"
    r = requests.get(hours_url)
    hours = re.findall(r'href="(\d{2})/"', r.text)  # just "00", "06", "12", "18"
    hour = max(hours)
    
    datetime = (f'{latest_date[0:4]}-{latest_date[4:6]}-{latest_date[6:8]}'
                f'T{hour}:00:00Z')
    
    logger.info(f'Found latest GFS data on datetime {datetime}')
    
    fname = f"gfs.t{hour}z.pgrb2.0p25.f000"
    file_url = f"{hours_url}{hour}/atmos/{fname}"
    
    # # Download only relevant lines
    # idx_text = requests.get(f'{file_url}.idx').text
    # idx_lines = idx_text.splitlines()
    
    # # Extract byte ranges
    # ranges = []
    # for i, line in enumerate(idx_lines):
    #     if any(var in line for var in PARAMS):
    #         start = int(line.split(":")[1])
    #         # End is next line start -1, or end of file
    #         end = int(idx_lines[i+1].split(":")[1]) - 1 if i+1 < len(idx_lines) else None
    #         ranges.append((start, end))
            
    # # Download ranges and save
    # with open(os.path.join(target, f'{datetime}.grib2'), "wb") as f_out:
    #     for start, end in ranges:
    #         headers = {"Range": f"bytes={start}-{end}" if end else f"bytes={start}-"}
    #         r = requests.get(file_url, headers=headers)
    #         f_out.write(r.content)
    
    # return datetime
    
    r = requests.head(file_url)
    size_bytes = int(r.headers["Content-Length"])
    size_mb = size_bytes / (1024 * 1024)

    logger.info(f'Downloading {fname} ({size_mb:.2f} MB)')
    
    destination_file = os.path.join(target, f'{datetime}.grib2')

    with open(destination_file, 'wb') as f:
        f.write(requests.get(file_url).content)
      
    # TODO: NetCDF conversion  
    # ds = xr.open_dataset(destination_file, engine='cfgrib')
    # ds.to_netcdf(os.path.splitext(destination_file)[0] + '.nc')
        
    return datetime

# def _grib_to_netcdf4(grib_path: str) -> None:
#     dss = cfgrib.open_datasets(grib_path, decode_timedelta=True)

if __name__ == '__main__':
    download_latest('')