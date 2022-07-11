# Pidroid

Pidroid is a custom discord bot for TheoTown written in Python using Rapptz's [discord.py](https://github.com/Rapptz/discord.py) wrapper.

## Production use

To use Pidroid in production, first we need to build a [docker](https://www.docker.com) image with this command:

```shell
docker build . --tag pidroid-bot
```

After building the docker image, now we just need to run it in a docker container with the following command:

```shell
docker-compose up -d
```

## Development setup

To begin, you'll need to install Python. Pidroid requires **Python 3.8** or above to work. You can check what version of Python you have installed by running this command:

```shell
python --version
```

After installing Python, we need to create a virtual environment where we'll install the project dependencies.

```shell
python -m venv venv
```

And activate the said virtual environment like so.

Linux:
```shell
source venv/bin/activate
```

Windows:
```shell
venv\Scripts\activate
```

Pidroid requires a few Python Packages as dependencies. You can install them by running the following command:

```shell
pip install -r requirements.txt
```

After installing all required packages, we need to configure the bot. Please check [here](#configuration) on how to do so.
The bot uses a MongoDB and a Postgres database. It accepts the login credentials as a [DSN](https://docs.mongodb.com/manual/reference/connection-string/#standard-connection-string-format). Please check [configuration manual](#configuration) on where to input it.

Lastly, all we have to do is run the bot. You can do so by running this command:

```shell
python pidroid/main.py -e config.env
```

The -e argument specifies which file to use for the environment variables.

### Configuration

Pidroid used to use a `config.json` file at its `./bot` path for its configuration.

Pidroid 5, however, switches to using environment variables as defined in the `config.env` file in the project root.
This is done to be compatible with Docker containers.

```ini
# Comma separated list of prefixes Pidroid will use by default
PREFIXES=
# Discord bot token
TOKEN=
# Mongo DSN string
MONGO_DSN=
# Postgres DSN string
POSTGRES_DSN=
# Github token for making issues on TT repo, optional
GITHUB_TOKEN=
# TheoTown API key to interact with backend TheoTown API
TT_API_KEY=
# DeepL API key used for translations
DEEPL_API_KEY=
# Unbelievaboat API key for economy integration in TT server
UNBELIEVABOAT_API_KEY=
# Tenor API key for gifs
TENOR_API_KEY=
# Bitly credentials for bitly command
BITLY_LOGIN=
BITLY_API_KEY=
# Reddit related credentials for reddit command
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=
```

Config options that are yet to be reimplemented
```jsonc
{
    // Used for RCON command (OPTIONAL)
    "minecraft rcon": {

      "server name": {          // Minecraft server name for indexing and accessing
        "address": "",          // Minecraft server IP address, to specify a port, localhost:5156
        "password": "",         // RCON protocol password
        "managers": []          // Snowflake array of allowed server managers, who can use the command
      }

    }
  }
}
```

Obtain docker IP to access services on host device from within a dockerised container.
```shell
ip addr show | grep "\binet\b.*\bdocker0\b" | awk '{print $2}' | cut -d '/' -f 1
```

## Versioning scheme

For the most part Pidroid uses a modified semantic versioning scheme.
|Version|Name                |Description                                               |
|-------|--------------------|----------------------------------------------------------|
| 1.0.0 |Major update        |Contains major incompatible changes with previous version.|
| 0.1.0 |Minor update        |Contains major new features or minor incompatibilies.     |
| 0.0.1 |Bugfix/patch update |Contains a hotfix or a bugfix.                            |
