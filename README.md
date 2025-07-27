# APPA live

## Installing the dependencies

Navigate to your preferred virtual environment, then run

```bash
pip install git+ssh://git@github.com/montefiore-sail/appa.git@v1.0 --no-deps
pip install -r requirements.txt
```

The first line is required because APPA wants older package versions for some things, notably `xarray`.

For generating png tiles, you must also run

```bash
sudo apt-get update && sudo apt install -y gdal-bin
```

Or equivalent if your package manager is not `apt`. The important requirement here is `gdal2tiles.py`.

## Configuring environment variables
Here are all the required environment variables to provide for the script to work

- _CDS_API_KEY_: Your CDS api key, to download ERA5 data ([more info](https://cds.climate.copernicus.eu/how-to-api))
- _S3_ACCESS_KEY_ID_: Your S3 bucket access key ID
- _S3_SECRET_ACCESS_KEY_: Your S3 bucket secret key
- _S3_ENDPOINT_: Your S3 bucket endpoint

## Usage

Run the whole pipeline with

```bash
python main.py -c path/to/forecast/config.yaml
```

You can also use `-h` to get a help message and `--temp-dir` to override the default temporary directory location. By default, it is set to the one provided by your OS.

## Running individual modules

Most modules can be run with `python -m module_name`. Refer to each module's "README.md" file for more information.