from __future__ import annotations

from bson.objectid import ObjectId
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.mentions import AllowedMentions
from discord.utils import escape_markdown
from typing import TYPE_CHECKING, Optional

from cogs.models.categories import UtilityCategory
from cogs.utils.embeds import create_embed, error, success

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"

if TYPE_CHECKING:
    from client import Pidroid
    from cogs.utils.api import API


class Tag:
    """This class represents a guild tag."""

    if TYPE_CHECKING:
        _id: ObjectId
        guild_id: int
        name: str
        content: str
        author_id: int

    def __init__(self, api: API = None, data: dict = None) -> None:
        self.api = api
        if data:
            self._deserialize(data)

    def _serialize(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "name": self.name,
            "content": self.content,
            "author_id": self.author_id
        }

    def _deserialize(self, data) -> None:
        self._id = data["_id"]
        self.guild_id = data["guild_id"]
        self.name = data["name"]
        self.content = data["content"]
        self.author_id = data["author_id"]

    async def create(self) -> None:
        """Creates a tag by inserting a document to the database."""
        self._id = await self.api.create_tag(self._serialize())

    async def edit(self) -> None:
        """Edits a tag by updating the document in the database."""
        await self.api.edit_tag(self._id, self._serialize())

    async def remove(self) -> None:
        """Removes a tag from the database."""
        if not self.api:
            raise BadArgument("API attribute is missing")
        await self.api.remove_tag(self._id)


class TagCommands(commands.Cog):
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief="Returns a server tag by the specified name.",
        usage="[tag name]",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag(self, ctx: Context, *, tag_name: Optional[str]):
        if tag_name is None:
            return await ctx.reply(embed=error("Tag? no idea"))

        tag = await self.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            return await ctx.reply(embed=error("I couldn't find any tags by that name!"))

        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            return await message.reply(tag.content, allowed_mentions=AllowedMentions(replied_user=True))

        await ctx.reply(tag.content)

    @commands.command(
        brief="Returns a list of available server tags.",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tags(self, ctx: Context):
        guild_tags = await self.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            return await ctx.reply(embed=error("This server has no defined tags!"))

        embed = create_embed()
        embed.title = f"{escape_markdown(ctx.guild.name)}'s tags"
        embed.description = f'({len(guild_tags)}) **' + '**, **'.join([t.name for t in guild_tags]) + '**'
        await ctx.reply(embed=embed)

    @commands.command(
        name="create-tag",
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def create_tag(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = Tag(self.api)
        tag.guild_id = ctx.guild.id
        tag.author_id = ctx.author.id
        if tag_name is None:
            return await ctx.reply(embed=error("Please specify a tag name!"))

        if len(tag_name) > 30:
            return await ctx.reply(embed=error("Tag name is too long! Please keep it below 30 characters!"))

        if any(c in FORBIDDEN_CHARS for c in tag_name):
            return await ctx.reply(embed=error("Tag name contains forbidden characters!"))
        tag.name = tag_name

        if content is None:
            return await ctx.reply(embed=error("Please provide content for a tag!"))

        if len(content) > 2000:
            return await ctx.reply(embed=error("Tag content is too long! Please keep it below 2000 characters!"))
        tag.content = content

        if await self.api.fetch_guild_tag(tag.guild_id, tag.name) is not None:
            return await ctx.send(embed=error("There's already a tag by the specified name!"))

        await tag.create()
        await ctx.reply(embed=success("Tag created successfully!"))

    @commands.command(
        name="remove-tag",
        brief="Remove a server tag.",
        usage="<tag name>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def remove_tag(self, ctx: Context, *, tag_name: Optional[str]):
        if tag_name is None:
            return await ctx.reply(embed=error("Please specify a tag name!"))

        tag = await self.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            return await ctx.reply(embed=error("I couldn't find any tags by that name!"))

        await tag.remove()
        await ctx.reply(embed=success("Tag removed successfully!"))

    @commands.command(
        name="edit-tag",
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(manage_guild=True)
    @commands.guild_only()
    async def edit_tag(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        if tag_name is None:
            return await ctx.reply(embed=error("Please specify a tag name!"))

        tag = await self.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            return await ctx.reply(embed=error("I couldn't find any tags by that name!"))

        if content is None:
            return await ctx.reply(embed=error("Please provide content for a tag!"))

        if len(content) > 2000:
            return await ctx.reply(embed=error("Tag content is too long! Please keep it below 2000 characters!"))

        tag.content = content

        await tag.edit()
        await ctx.reply(embed=success("Tag edited successfully!"))

def setup(client: Pidroid) -> None:
    client.add_cog(TagCommands(client))