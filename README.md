# Pidroid

Pidroid is a custom discord bot for TheoTown written in Python using Rapptz's [discord.py](https://github.com/Rapptz/discord.py) wrapper.

## Production use

To use Pidroid in production, first we need to build a [docker](https://www.docker.com) image with this command:

```shell
docker build . --tag pidroid-bot
```

After building the docker image, we need to make sure we have a the configuration environment file set up. You can read how to do so [here](#configuration).

Pidroid uses a Postgres database to store its information. You can read about setting it up [here](#database).

After making sure our configuration and database is set up, we just need to run the bot in a docker container with the following command:

```shell
docker-compose up -d
```

## Development setup

To begin, you'll need to install Python. Pidroid requires **Python 3.8** or above to work. You can check what version of Python you have installed by running this command:

```shell
python --version
```

After installing Python, you need to create a virtual environment where you'll install the project dependencies.

```shell
python -m venv venv
```

You then activate the said virtual environment like so:

On Linux:
```shell
source venv/bin/activate
```

On Windows:
```shell
venv\Scripts\activate
```

Pidroid requires a few Python Packages as dependencies. You can install them by running the following command:

```shell
pip install -r requirements.txt
```

After installing all the required packages, we need to configure the bot itself. Please check out the [configuration manual](#configuration) on how to do so.
The bot uses a Postgres database. It accepts the login credentials as a [DSN](#database) string. Please check [configuration manual](#configuration) on where to input it.

After setting up the database, you will need to do the database table creation and migrations using alembic:

```shell
alembic upgrade head
```

Lastly, all you have to do is run the bot. You can do so by running this command:

```shell
python pidroid/main.py -e config.env
```

The -e argument specifies which file to use for the environment variables.

## Database

You will need a PostgreSQL 9.5 database or higher. You will need to type the following in the psql tool:

```sql
CREATE ROLE pidroid WITH LOGIN PASSWORD 'your_database_password';
CREATE DATABASE pidroid OWNER pidroid;
CREATE EXTENSION pg_trgm;
```

After creating your database, you'll need your DSN string.

```
postgresql+asyncpg://pidroid:your_database_password@127.0.0.1
```

postgresql+asyncpg is required to specify sqlalchemy to use asyncpg driver.
You will only need to change the password field and the IP.

## Configuration

Pidroid used to use a `config.json` file at its `./bot` path for its configuration.

Pidroid 5, however, switches to using environment variables as defined in the `config.env` file in the project root.
This is done to be compatible with Docker containers.

```ini
# Comma separated list of prefixes Pidroid will use by default
PREFIXES=
# Discord bot token
TOKEN=
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
# Reddit related credentials for reddit command
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=
```

Please note that if your credentials contain a dollar sign, you need to add another dollar sign to make it a literal.

### Useful commands for setup

If you want to access a service on host device through a docker container, you'll need to obtain docker IP.
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


## For development

### Converters

The following is an example of how a command may fall back to using the message
author for the member argument, if it could not be resolved.

```py
@commands.command()
async def command(self, ctx: Context, member: Member = None):
    member = member or ctx.author
    ...
```

Linters and static analysis tools might suggest you to update typehinting to something like
```py
@commands.command()
async def command(self, ctx: Context, member: Optional[Member] = None):
    member = member or ctx.author
    ...
```
However, Optional has a special meaning in discord.py for special discord types such as
Member, User, etc. It suppresses conversion errors which is not always preferable and can lead
to myriad of unexpected issues.

Henceforth, it is preferable to use Annotated type like so

```py
@commands.command()
async def command(self, ctx: Context, member: Annotated[Optional[Member], Member] = None):
    member = member or ctx.author
    ...
```

The first argument of Annotated is for the linters, the second argument is used by discord.py

### Decorators

discord.py evaluates all decorators in an ascending order.

For clarity sake, all commands that are supposed to be executed inside guilds, require a guild_only check decorator.

The same applies for custom Pidroid decorators that check for specific channel or guild,
they require that you also use in-built guild_only check.

### Fancy command argument error handling

Sometimes you might want to provide a custom error message for your command.
Usually, it's in the case of a user not providing the required argument.

In the old days, you would make that argument optional with the default value as None.
And then you would just handle that value with an if statement.
However, that can sometimes lead to unexpected behaviour.

Moreover, with the new hybrid commands, making certain arguments optional is bad
user experience.

Henceforth, the following is an example of a new way of handling missing argument errors nicely:

```py
    @commands.command()
    async def role_info(self, ctx: Context, role: Role): # Role is a required argument here
        embed = Embed(description=role.mention, timestamp=role.created_at, colour=role.colour)
        if role.icon:
            embed.set_thumbnail(url=role.icon.with_size(4096).url) # type: ignore
        embed.add_field(name="Name", value=role.name)
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Colour", value=str(role.colour))
        embed.add_field(name="Is mentionable", value=role.mentionable)
        embed.set_footer(text="Role created")
        await ctx.reply(embed=embed)

    # We define a new async method to handle role_info command errors
    @role_info.error
    async def on_role_info_command_error(self, ctx: Context, error): # These arguments are required
        # We check if our error is of MissingRequiredArgument
        if isinstance(error, MissingRequiredArgument):
            # With that, we check what argument it is for
            if error.param.name == "role":
                # And we return a custom error message
                return await notify(ctx, "Please specify the role to view the information for")

        # This is a special call to notify the generic error handler
        # that the error was not handled and it should be done on
        # its side.
        # This must be at the end of the method.
        setattr(error, 'unhandled', True)
```

## Features in the works
- Level reward subsystem
- Support for slash commands
- Reaction role selection subsystem
- Refactoring of the help system to make it more lenient and less janky
