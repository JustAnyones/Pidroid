from __future__ import annotations

from bson.int64 import Int64
from bson.objectid import ObjectId
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.mentions import AllowedMentions
from discord.utils import escape_markdown, format_dt
from typing import TYPE_CHECKING, List, Optional

from cogs.models.categories import UtilityCategory
from cogs.utils.embeds import create_embed, error, success

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = ["create", "edit", "remove", "list", "info"]

if TYPE_CHECKING:
    from client import Pidroid
    from cogs.utils.api import API


class Tag:
    """This class represents a guild tag."""

    if TYPE_CHECKING:
        _id: ObjectId
        guild_id: int
        _name: str
        _content: str
        author_id: int
        aliases: List[str]
        locked: bool

    def __init__(self, api: API = None, data: dict = None) -> None:
        self.api = api
        self.aliases = []
        self.locked = False
        if data:
            self._deserialize(data)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if len(value) > 30:
            raise BadArgument("Tag name is too long! Please keep it below 30 characters!")
        if any(w in RESERVED_WORDS for w in value.split(" ")):
            raise BadArgument("Tag name cannot contain reserved words!")
        if any(c in FORBIDDEN_CHARS for c in value):
            raise BadArgument("Tag name cannot contain forbidden characters!")
        self._name = value

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str):
        if len(value) > 2000:
            raise BadArgument("Tag content is too long! Please keep it below 2000 characters!")
        self._content = value

    def _serialize(self) -> dict:
        return {
            "guild_id": Int64(self.guild_id),
            "name": self.name,
            "content": self.content,
            "author_id": Int64(self.author_id),
            "aliases": self.aliases,
            "locked": self.locked
        }

    def _deserialize(self, data: dict) -> None:
        self._id = data["_id"]
        self.guild_id = data["guild_id"]
        self.name = data["name"]
        self.content = data["content"]
        self.author_id = data["author_id"]
        self.aliases = data.get("aliases", [])
        self.locked = data.get("locked", False)

    async def create(self) -> None:
        """Creates a tag by inserting a document to the database."""
        self._id = await self.api.create_tag(self._serialize())

    async def edit(self) -> None:
        """Edits a tag by updating the document in the database."""
        await self.api.edit_tag(self._id, self._serialize())

    async def remove(self) -> None:
        """Removes a tag from the database."""
        if not self.api:
            raise BadArgument("API attribute is missing!")
        await self.api.remove_tag(self._id)


class TagCommands(commands.Cog):
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    async def resolve_tag(self, ctx: Context, tag_name: Optional[str]) -> Optional[Tag]:
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")

        tag = await self.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            raise BadArgument("I couldn't find any tags by that name!")
        return tag

    @commands.group(
        brief='Returns a server tag by the specified name.',
        usage='[tag name]',
        category=UtilityCategory,
        invoke_without_command=True
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.guild_only()
    async def tag(self, ctx: Context, *, tag_name: Optional[str]):
        if ctx.invoked_subcommand is None:
            tag = await self.resolve_tag(ctx, tag_name)

            if ctx.message.reference:
                message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                return await message.reply(tag.content, allowed_mentions=AllowedMentions(replied_user=True))
            return await ctx.reply(tag.content)

    @tag.command(
        brief="Returns a list of available server tags.",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def list(self, ctx: Context):
        guild_tags = await self.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            raise BadArgument("This server has no defined tags!")

        embed = create_embed()
        embed.title = f"{escape_markdown(ctx.guild.name)}'s tags"
        embed.description = f'({len(guild_tags)}) **' + '**, **'.join([t.name for t in guild_tags]) + '**'
        await ctx.reply(embed=embed)

    @tag.command(
        brief='Returns information about the server tag.',
        usage='<tag name>',
        category=UtilityCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.guild_only()
    async def info(self, ctx: Context, *, tag_name: str = None):
        tag = await self.resolve_tag(ctx, tag_name)

        user = await self.client.resolve_user(tag.author_id)

        embed = create_embed(title=tag.name, description=tag.content)
        if user:
            embed.add_field(name="Tag owner", value=user.mention)
        embed.add_field(name="Date created", value=format_dt(tag._id.generation_time))
        await ctx.reply(embed=embed)

    @tag.command(
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def create(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = Tag(self.api)
        tag.guild_id = ctx.guild.id
        tag.author_id = ctx.author.id
        if tag_name is None:
            return await ctx.reply(embed=error("Please specify a tag name!"))
        tag.name = tag_name

        if content is None:
            return await ctx.reply(embed=error("Please provide content for the tag!"))
        tag.content = content

        if await self.api.fetch_guild_tag(tag.guild_id, tag.name) is not None:
            return await ctx.reply(embed=error("There's already a tag by the specified name!"))

        await tag.create()
        await ctx.reply(embed=success("Tag created successfully!"))

    @tag.command(
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def edit(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if content is None:
            return await ctx.reply(embed=error("Please provide content for a tag!"))
        tag.content = content

        await tag.edit()
        await ctx.reply(embed=success("Tag edited successfully!"))

    @tag.command(
        brief="Remove a server tag.",
        usage="<tag name>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def remove(self, ctx: Context, *, tag_name: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)
        await tag.remove()
        await ctx.reply(embed=success("Tag removed successfully!"))

def setup(client: Pidroid) -> None:
    client.add_cog(TagCommands(client))
