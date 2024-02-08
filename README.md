# Portabooru

A docker application for danbooru syncing.

## Usage

### Using Docker

1. Write your username and API key to `inputs/.env`.
2. Write the tags you want to sync to `inputs/tags.txt`. You can put an asterisk (`*`) in front of a tag to only download the metadata.
3. Build the docker image with `docker build -t portabooru .`.
4. * (Option A) Retrieve the image with `docker save portabooru.tar portabooru`.
   * (Option B) Run the image with `docker run -v %userprofile%\Documents\GitHub\portabooru\inputs:/inputs -v %userprofile%\Documents\GitHub\portabooru\outputs:/outputs portabooru`.