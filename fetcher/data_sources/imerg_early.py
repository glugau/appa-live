# IMERG Early Run data, from NASA, is used to get precipitation accumulation
# over an hour for a given date/time with >4hr delays. This data has a 0.1
# degree resolution and is downsampled to 0.25 degrees in order to appropriately
# function with the model's expectations.
#
# Note that this data source REQUIRES an account at
# https://urs.earthdata.nasa.gov/
#
# - Info about the model and other available sources:
#   https://gpm.nasa.gov/data/directory
# - The exact dataset used:
#   https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHE_07/summary?keywords=%22IMERG%20Early%22
# - Earthaccess API to download the data easily - Didn't end up being used,
#   because it introduces additional delay (about 3-5 hours?!):
#   https://earthaccess.readthedocs.io/en/latest/

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import matplotlib.pyplot as plt
import xarray as xr
import numpy as np
import requests
import tempfile
import logging
import dotenv
import os

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

def get_total_precipitation(dt: datetime, output_dir: os.PathLike) -> Path:
    output_dir = Path(output_dir)
    start_dt = dt - timedelta(minutes=30)
    out_path = output_dir / (dt.isoformat() + '.nc')
    
    with tempfile.TemporaryDirectory() as tempdir:
        nc4 = _get_nc4_at_starthour(start_dt, tempdir)
        ds = xr.open_dataset(nc4)
        ds = reformat_to_era5(ds)
        ds.to_netcdf(out_path)

    return out_path

def _get_nc4_at_starthour(start_dt: datetime, output_dir: os.PathLike):
    update_netrc_credentials()
    
    year = start_dt.year
    day_of_year = start_dt.timetuple().tm_yday

    date_str = f"{year}{day_of_year:03d}"

    start_hour = start_dt.hour
    start_minute = start_dt.minute

    end_dt = start_dt + timedelta(minutes=29, seconds=59)

    start_time_str = start_dt.strftime("%H%M%S")
    end_time_str = end_dt.strftime("%H%M%S")
    
    minutes_since_midnight = start_dt.hour * 60 + start_dt.minute

    # Build the filename
    filename = f"3B-HHR-E.MS.MRG.3IMERG.{start_dt.strftime('%Y%m%d')}-S{start_time_str}-E{end_time_str}.{minutes_since_midnight:04d}.V07B.HDF5.dap.nc4"

    # Base URL with year and day_of_year folders
    url = f"https://gpm1.gesdisc.eosdis.nasa.gov/opendap/hyrax/GPM_L3/GPM_3IMERGHHE.07/{year}/{day_of_year:03d}/{filename}"
    
    url += "?dap4.ce=/lat[0:1:1799];/lon[0:1:3599];/precipitation[0:1:0][0:1:3599][0:1:1799]"

    username = os.environ["EARTHDATA_USERNAME"]
    password = os.environ["EARTHDATA_PASSWORD"]

    session = requests.Session()
    session.auth = (username, password)
    session.headers.update({"User-Agent": "python-requests"})

    logger.info(f'Downloading IMERG Early data from {url}')
    r = session.get(url)
    r.raise_for_status()
    
    out_filename = start_dt.isoformat() + '.nc4'
    out_path = os.path.join(output_dir, out_filename)
    
    with open(out_path, "wb") as f:
        f.write(r.content)
    
    return out_path

def reformat_to_era5(ds: xr.Dataset):
    N_LON = 1440
    N_LAT = 721
    
    ds = ds.rename({"lat": "latitude", "lon": "longitude"})
    
    new_lats = np.linspace(90, -90, N_LAT, endpoint=True)
    new_lons = np.linspace(-180, 180, N_LON, endpoint=False)

    ds['precipitation'] = ds['precipitation'] * 0.001 # mm/hr to m/hr
    
    ds = ds.transpose("time", "latitude", "longitude")

    return ds.interp(latitude=new_lats, longitude=new_lons)

def add_together(a: xr.Dataset, b: xr.Dataset):
    pass

from pathlib import Path

def update_netrc_credentials():
    username = os.getenv("EARTHDATA_USERNAME")
    password = os.getenv("EARTHDATA_PASSWORD")
    if not username or not password:
        raise RuntimeError("EARTHDATA_USERNAME or EARTHDATA_PASSWORD missing")

    netrc_path = Path.home() / ".netrc"
    lines = []
    if netrc_path.exists():
        with netrc_path.open("r") as f:
            lines = f.readlines()

    new_lines = []

    # Find and remove existing urs.earthdata.nasa.gov block
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("machine urs.earthdata.nasa.gov"):
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")):
                i += 1
        else:
            new_lines.append(line)
            i += 1

    # Append new credentials block at end
    new_lines.append(f"machine urs.earthdata.nasa.gov\n")
    new_lines.append(f" login {username}\n")
    new_lines.append(f" password {password}\n")

    netrc_path.write_text("".join(new_lines))
    os.chmod(netrc_path, 0o600)
    
if __name__ == '__main__':
    update_netrc_credentials()