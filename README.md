# APPA live

## Installing the dependencies

Navigate to your preferred virtual environment **using python 3.12** (later/earlier versions will fail due to dependency versions), then run

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

For uploading the tiles to an S3 bucket, this script makes use of the `aws` CLI, which has programs that are a lot more efficient at uploading many small files than what could be achieved with `boto3`. Install it with

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

Finally, to optimize storage, this code uses `pmtiles` which stores tiles as a single file that then is served with HTTP range requests instead of many small files. You can install it from [GitHub](https://github.com/protomaps/go-pmtiles/releases/latest), or run this script if on a Linux x86-64 system with the apt package manager.

```bash
curl -s https://api.github.com/repos/protomaps/go-pmtiles/releases/latest \
| grep "browser_download_url.*Linux_x86_64.tar.gz" \
| cut -d '"' -f 4 \
| xargs curl -L -o go-pmtiles.tar.gz \
&& mkdir -p /tmp/go-pmtiles-install \
&& tar -xzf go-pmtiles.tar.gz -C /tmp/go-pmtiles-install \
&& sudo mv /tmp/go-pmtiles-install/pmtiles /usr/local/bin/ \
&& rm -rf /tmp/go-pmtiles-install go-pmtiles.tar.gz  
```

## Configuring environment variables

Here are all the required environment variables to provide for the script to work

- **CDS_API_KEY**: Your CDS api key, to download ERA5 data ([more info](https://cds.climate.copernicus.eu/how-to-api))
- **S3_ACCESS_KEY_ID**: Your S3 bucket access key ID
- **S3_SECRET_ACCESS_KEY**: Your S3 bucket secret key
- **S3_ENDPOINT**: Your S3 bucket endpoint
- **S3_BUCKET_NAME**: The name of your S3 bucket

## Usage

Run the whole pipeline with

```bash
python main.py -c path/to/forecast/config.yaml
```

You can also use `-h` to get a help message and `--temp-dir` to override the default temporary directory location. By default, it is set to the one provided by your OS.

## Running individual modules

Most modules can be run with `python -m module_name`. Refer to each module's "README.md" file for more information.
