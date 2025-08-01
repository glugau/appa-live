import xarray as xr

ds = xr.open_zarr('data/processed/2025-08-01T00:00:00Z.zarr')
print(ds)
ds.to_netcdf('out_test.nc')