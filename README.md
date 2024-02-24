# Portabooru

A docker application for danbooru syncing.

## Usage

### Using Docker

1. In `inputs/`, create a file called `.env` and put in your credentials as follows:
   ```
   NAME=<your username here>
   API_KEY=<your api key here>
   ```
3. In `inputs/`, create a file called `tags.txt` containing the list of tags you want to sync. You can put an asterisk (`*`) in front of a tag to only download the metadata. For example:
   ```
   furina_(genshin_impact)
   *arknights
   ```
5. Build the docker image with `docker build -t portabooru .`.
6. * **(Option A)** Retrieve the image with `docker save portabooru.tar portabooru`.
   * **(Option B)** Run the image with the following command:
     ```
     docker run -v <inputs folder here>:/inputs -v <outputs folder here>:/outputs portabooru
     ```
     The paths have to be absolute. Usual values are:
     * `%userprofile%\Documents\GitHub\portabooru\inputs` for the inputs folder
     * `%userprofile%\Documents\GitHub\portabooru\outputs` for the outputs folder
