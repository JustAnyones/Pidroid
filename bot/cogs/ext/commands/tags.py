from __future__ import annotations

from bson.int64 import Int64
from bson.objectid import ObjectId
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.member import Member
from discord.mentions import AllowedMentions
from discord.message import Message
from discord.utils import escape_markdown, format_dt
from typing import TYPE_CHECKING, List, Optional

from cogs.models.categories import UtilityCategory
from cogs.utils.checks import has_moderator_permissions
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, error, success

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = ["create", "edit", "remove", "claim", "transfer", "list", "info"]
ALLOWED_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)

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
        if len(value) < 3:
            raise BadArgument("Tag name is too short! Please keep it above 2 characters!")
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

    async def find_tags(self, ctx: Context, tag_name: Optional[str]) -> List[Tag]:
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")

        if len(tag_name) < 3:
            raise BadArgument("Query term is too short! Please keep it above 2 characters!")

        tag_list = await self.api.search_guild_tags(ctx.guild.id, tag_name)
        if len(tag_list) == 0:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag_list

    async def resolve_tag(self, ctx: Context, tag_name: Optional[str]) -> Optional[Tag]:
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")

        tag = await self.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag

    async def resolve_attachments(self, message: Message) -> Optional[str]:
        if len(message.attachments) == 0:
            return None

        if len(message.attachments) > 1:
            raise BadArgument("Tags can only support a single attachment!")

        attachment = message.attachments[0]
        return attachment.url

    @commands.group(
        brief='Returns a server tag by the specified name.',
        usage='[tag name]',
        category=UtilityCategory,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag(self, ctx: Context, *, tag_name: Optional[str]):
        if ctx.invoked_subcommand is None:
            tag_list = await self.find_tags(ctx, tag_name)

            if len(tag_list) == 1:
                message_content = tag_list[0].content
            elif tag_list[0].name.lower() == tag_name.lower():
                message_content = tag_list[0].content
            else:
                tag_name_list = [t.name for t in tag_list[:10]]
                tag_list_str = ', '.join(tag_name_list)
                message_content = f"I found multiple tags matching your query: {tag_list_str}\n..."

            if ctx.message.reference:
                message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                return await message.reply(
                    message_content,
                    allowed_mentions=ALLOWED_MENTIONS.merge(AllowedMentions(replied_user=True))
                )
            return await ctx.reply(message_content, allowed_mentions=ALLOWED_MENTIONS)

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

        embed = PidroidEmbed()
        embed.title = f"{escape_markdown(ctx.guild.name)} server tags"
        embed.description = f'({len(guild_tags)}) **' + '**, **'.join([t.name for t in guild_tags]) + '**'
        await ctx.reply(embed=embed)

    @tag.command(
        brief='Returns information about the server tag.',
        usage='<tag name>',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def info(self, ctx: Context, *, tag_name: str = None):
        tag = await self.resolve_tag(ctx, tag_name)

        user = await self.client.get_or_fetch_user(tag.author_id)

        embed = PidroidEmbed(title=tag.name, description=tag.content)
        if user:
            embed.add_field(name="Tag owner", value=user.mention)
        embed.add_field(name="Date created", value=format_dt(tag._id.generation_time))
        await ctx.reply(embed=embed)

    @tag.command(
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=10, per=60 * 60, type=commands.BucketType.user)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def create(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = Tag(self.api)
        tag.guild_id = ctx.guild.id
        tag.author_id = ctx.author.id
        if tag_name is None:
            return await ctx.reply(embed=error("Please specify a tag name!"))
        tag.name = tag_name

        attachment_url = await self.resolve_attachments(ctx.message)
        if content is None and attachment_url is None:
            return await ctx.reply(embed=error("Please provide content for the tag!"))
        tag.content = (content or "" + "\n" + attachment_url or "").strip()

        if await self.api.fetch_guild_tag(tag.guild_id, tag.name) is not None:
            return await ctx.reply(embed=error("There's already a tag by the specified name!"))

        await tag.create()
        await ctx.reply(embed=success("Tag created successfully!"))

    @tag.command(
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def edit(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot edit a tag you don't own!")

        attachment_url = await self.resolve_attachments(ctx.message)
        if content is None and attachment_url is None:
            return await ctx.reply(embed=error("Please provide content for a tag!"))
        tag.content = (content or "" + "\n" + attachment_url or "").strip()

        await tag.edit()
        await ctx.reply(embed=success("Tag edited successfully!"))

    @tag.command(
        brief="Claim a server tag in the case the tag owner leaves.",
        usage="<tag name>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def claim(self, ctx: Context, *, tag_name: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if ctx.author.id == tag.author_id:
            raise BadArgument("You are the tag owner, there is no need to claim it!")

        if not has_moderator_permissions(ctx, manage_messages=True):
            member = await self.client.get_or_fetch_member(ctx.guild, ctx.author.id)
            if member is not None:
                raise BadArgument("Tag owner is still in the server!")

        tag.author_id = ctx.author.id

        await tag.edit()
        await ctx.reply(embed=success("Tag claimed successfully!"))

    @tag.command(
        brief="Transfer a server tag to someone else.",
        usage="<tag name> <member>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def transfer(self, ctx: Context, tag_name: Optional[str], *, member: Optional[Member]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot transfer a tag you don't own!")

        if member is None:
            raise BadArgument("Please specify a member to whom you want to transfer the tag!")

        if ctx.author.id == member.id:
            raise BadArgument("You cannot transfer a tag to yourself!")

        tag.author_id = member.id

        await tag.edit()
        await ctx.reply(embed=success(f"Tag transfered to {escape_markdown(str(member))} successfully!"))

    @tag.command(
        brief="Remove a server tag.",
        usage="<tag name>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def remove(self, ctx: Context, *, tag_name: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a tag you don't own!")

        await tag.remove()
        await ctx.reply(embed=success("Tag removed successfully!"))

async def setup(client: Pidroid) -> None:
    await client.add_cog(TagCommands(client))
