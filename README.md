# Pidroid [![CodeFactor](https://www.codefactor.io/repository/github/justanyones/pidroid/badge/master?s=0c22ba59631183971ce3cbdf92953418ea523d7c)](https://www.codefactor.io/repository/github/justanyones/pidroid/overview/master)

Pidroid is a custom discord bot for TheoTown written in Python using Rapptz's [discord.py](https://github.com/Rapptz/discord.py) wrapper.

## Planned features

Work-in-progress and planned features may be found on Pidroid's trello board [here](https://trello.com/b/1ZLnbi2A/pidroid).

## Setup

To begin, you'll need to install Python. Pidroid requires **Python 3.8** or above to work. You can check what version of Python you have installed by running this command:

```shell
python --version
```

After installing Python, we need to navigate to Pidroid's bot directory where we'll do the initial setup and run the bot.

```shell
cd bot
```

Pidroid requires a few Python Packages as dependencies. You can install them by running the following command:

```shell
pip install -r requirements.txt
```

After installing all required packages, we need to configure the bot. Please check [here](#configuration) on how to do so.
The bot uses a Mongo database. It accepts the login credentials as a [connection string](https://docs.mongodb.com/manual/reference/connection-string/#standard-connection-string-format). Please check [configuration manual](#configuration) on where to input it.

Lastly, all we have to do is run the bot. You can do so by running this command:

```shell
python main.py
```

### Configuration

Pidroid uses a `config.json` file at its `./bot` path (the same path where `main.py` is located) for its configuration.

```jsonc
{
  "embed color": 5928495,       // Default Discord Embed colour
  "prefixes": [],               // String array, used for prefixes. Prefixes are case sensitive.

  // Object which contains all secret bot authentication credentials
  "authentication": {
    "bot token": "",            // Bot token given by Discord

    // MySQL database
    "database": {
      "connection string": ""   // MongoDB connection string
    },

    "theotown api token": "",   // Token given by JustAnyone to access private TheoTown APIs

    // Used for the economy cog of the bot (OPTIONAL)
    "unbelievaboat": {
      "token": ""               // API token given by Unbelievaboat
    },

    // Used for GIF command (OPTIONAL)
    "tenor": {
      "token": ""               // API token given by TENOR
    },
  
    // Used for bitly command (OPTIONAL)
    "bitly": {
      "login": "",
      "api key": ""
    },

    // Used for Reddit command
    "reddit": {
      "client id": "",
      "client secret": "",
      "username": "",
      "password": ""
    },

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

Please note that Pidroid does not support the JSONC (JSON with comments) file format. It's used here for the sake of documentation and syntax highlighting.

## Versioning scheme

For the most part Pidroid uses a modified semantic versioning scheme.
|Version|Name                |Description                                               |
|-------|--------------------|----------------------------------------------------------|
| 1.0.0 |Major update        |Contains major incompatible changes with previous version.|
| 0.1.0 |Minor update        |Contains major new features or minor incompatibilies.     |
| 0.0.1 |Bugfix/patch update |Contains a hotfix or a bugfix.                            |
