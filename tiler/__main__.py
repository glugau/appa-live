import xarray as xr
import logging

from tiler import dataset_to_tiles

logging.basicConfig(level=logging.INFO)
ds = xr.open_zarr('/home/jovyan/shared/ggluckmann/appa-forecasts/2025-07-24T06Z_PT48H.zarr')  
dataset_to_tiles(ds, 'output', zoom_max=2)