# appa-fetcher

A service that pulls data from online sources on which the APPA model is then conditioned for its public predictions.

## Usage

```bash
python main.py [-h] [-t TARGET_FOLDER] [--skip-processing] [--skip-download] [-c]
```

## API key requirements

| Data Source | API  key required | Key Environment variable |
|-------------|-------------------|--------------------------|
| ifs         | No                | /                        |
| era5        | Yes               | CDS_API_KEY              |

Note that `era5` also requires accepting the terms and conditions. On first try, an error message should guide you to do so.

## Arguments

- **-h, --help**
    Show an help message and exit.

- **-t, --target-folder** _TARGET_FOLDER_: Destination output folder for the NetCDF4 files. Files will be saved in a subfolder named after the data source. The name of the data files will be the timestamp of the time at which they were generated, in the format `YY-mm-ddTHH-MM-SSZ`. Default is `./data`.
- **--skip-processing**: If set, skip the processing step.
- **--skip-download**: If set, will skip the downloads and look straight for cached data files. Will throw an exception if none are found.
- **-c, --cleanup**: If set, will delete the `ifs_raw` and `era5_raw` folders inside _TARGET_FOLDER_, only keeping the `processed` files.
