import xarray as xr

def shift_longitude(dataset: xr.Dataset, range:str ='-180-180') -> xr.Dataset:
    '''
    For each field in a given dataset, shift each longitude value to go in the
    desired `range`.
    
    Parameters:
        dataset (xr.Dataset): the dataset to be modified
        range (`-180-180` or `0-360`): The desired final range of the longitude
            values
    '''
    lon = dataset.coords['longitude']
    if range == '0-360':
        new_lon = lon % 360
    elif range == '-180-180':
        new_lon = (lon + 180) % 360 - 180
    else:
        raise ValueError("Invalid range. Use '-180-180' or '0-360'.")
    
    dataset.coords['longitude'] = new_lon
    dataset = dataset.sortby(dataset.longitude)
    return dataset

if __name__ == '__main__':
    import xarray as xr
    ds = xr.load_dataset('./data/era5/2025-07-08T00:00:00Z-single.nc')
    print("Lon range:", ds.longitude.min().values, "to", ds.longitude.max().values)
    ds = shift_longitude(ds, '-180-180')
    print("Shifted lon range:", ds.longitude.min().values, "to", ds.longitude.max().values)