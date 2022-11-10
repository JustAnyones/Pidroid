from __future__ import annotations

import datetime

from discord.ext import commands # type: ignore
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.file import File
from discord.guild import Guild
from discord.user import User
from discord.member import Member
from discord.mentions import AllowedMentions
from discord.message import Message
from discord.utils import escape_markdown, format_dt
from io import BytesIO
from typing import TYPE_CHECKING, List, Optional

from pidroid.cogs.models.categories import TagCategory
from pidroid.cogs.utils.checks import has_moderator_permissions
from pidroid.cogs.utils.decorators import command_checks
from pidroid.cogs.utils.embeds import PidroidEmbed, SuccessEmbed

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = [
    "create", "edit", "remove", "claim", "transfer", "list", "info",
    "add-author", "add_author", "raw",
    "remove-author", "remove_author"
]
ALLOWED_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)

if TYPE_CHECKING:
    from pidroid.client import Pidroid
    from pidroid.cogs.utils.api import API, TagTable


class Tag:
    """This class represents a guild tag."""

    if TYPE_CHECKING:
        _id: int
        guild_id: int
        _name: str
        _content: str
        _author_ids: List[int]
        aliases: List[str]
        locked: bool
        date_created: datetime.datetime

    def __init__(self, api: API, data: TagTable = None) -> None:
        self.api = api
        self._author_ids = []
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

    @property
    def author_id(self) -> int:
        return self._author_ids[0]

    @author_id.setter
    def author_id(self, value: int) -> None:
        # If it was in list before hand, like a co-author
        if value in self.co_author_ids:
            self._author_ids.remove(value)

        if len(self._author_ids) == 0:
            return self._author_ids.append(value)
        self._author_ids[0] = value

    @property
    def co_author_ids(self) -> List[int]:
        return self._author_ids[1:]

    def add_co_author(self, author_id: int) -> None:
        if self.author_id == author_id:
            raise BadArgument("You cannot add yourself as a co-author!")
        if len(self._author_ids) > 4:
            raise BadArgument("A tag can only have up to 4 co-authors!")
        if author_id in self.co_author_ids:
            raise BadArgument("Specifed member is already a co-author!")
        self._author_ids.append(author_id)

    def remove_co_author(self, author_id: int) -> None:
        if author_id not in self.co_author_ids:
            raise BadArgument("Specified member is not a co-author!")
        self._author_ids.remove(author_id)

    def _deserialize(self, data: TagTable) -> None:
        self._id = data.id # type: ignore
        self.guild_id = data.guild_id # type: ignore
        self._name = data.name # type: ignore
        self._content = data.content # type: ignore
        self._author_ids = data.authors # type: ignore
        self.aliases = data.aliases # type: ignore
        self.locked = data.locked # type: ignore
        self.date_created = data.date_created # type: ignore

    async def create(self) -> None:
        """Creates a tag by inserting a document to the database."""
        self._id = await self.api.insert_tag(self.guild_id, self.name, self.content, self._author_ids)

    async def edit(self) -> None:
        """Edits a tag by updating the document in the database."""
        await self.api.update_tag(self._id, self.content, self._author_ids, self.aliases, self.locked)

    async def remove(self) -> None:
        """Removes a tag from the database."""
        if not self.api:
            raise BadArgument("API attribute is missing!")
        await self.api.delete_tag(self._id)


class TagCommands(commands.Cog): # type: ignore
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        self.client = client

    async def fetch_tag_author_users(self, tag: Tag) -> List[Optional[User]]:
        return [await self.client.get_or_fetch_user(auth_id) for auth_id in tag._author_ids]

    async def fetch_tag_author_members(self, guild: Guild, tag: Tag) -> List[Optional[Member]]:
        return [await self.client.get_or_fetch_member(guild, auth_id) for auth_id in tag._author_ids]

    async def find_tags(self, ctx: Context, tag_name: Optional[str]) -> List[Tag]:
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")

        if len(tag_name) < 3:
            raise BadArgument("Query term is too short! Please keep it above 2 characters!")

        tag_list = await self.client.api.search_guild_tags(ctx.guild.id, tag_name)
        if len(tag_list) == 0:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag_list

    async def resolve_tag(self, ctx: Context, tag_name: Optional[str]) -> Tag:
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")

        tag = await self.client.api.fetch_guild_tag(ctx.guild.id, tag_name)
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

    @commands.group( # type: ignore
        brief='Returns a server tag by the specified name.',
        usage='[tag name]',
        category=TagCategory,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def tag(self, ctx: Context, *, tag_name: Optional[str]):
        if ctx.invoked_subcommand is None:
            tag_list = await self.find_tags(ctx, tag_name)
            assert tag_name is not None

            if len(tag_list) == 1:
                message_content = tag_list[0].content
            elif tag_list[0].name.lower() == tag_name.lower():
                message_content = tag_list[0].content
            else:
                tag_name_list = [t.name for t in tag_list[:10]]
                tag_list_str = '``, ``'.join(tag_name_list)
                message_content = f"I found multiple tags matching your query: ``{tag_list_str}``"

            if ctx.message.reference:
                message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                return await message.reply(
                    message_content,
                    allowed_mentions=ALLOWED_MENTIONS.merge(AllowedMentions(replied_user=True))
                )
            return await ctx.reply(message_content, allowed_mentions=ALLOWED_MENTIONS)

    @tag.command(
        brief="Returns a list of available server tags.",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def list(self, ctx: Context):
        assert ctx.guild is not None
        guild_tags = await self.client.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            raise BadArgument("This server has no defined tags!")

        embed = PidroidEmbed()
        embed.title = f"{escape_markdown(ctx.guild.name)} server tags"
        embed.description = f'({len(guild_tags)}) **' + '**, **'.join([t.name for t in guild_tags]) + '**'
        await ctx.reply(embed=embed)

    @tag.command(
        brief='Returns information about a server tag.',
        usage='<tag name>',
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def info(self, ctx: Context, *, tag_name: str = None):
        tag = await self.resolve_tag(ctx, tag_name)

        authors = await self.fetch_tag_author_users(tag)

        embed = PidroidEmbed(title=tag.name, description=tag.content)
        if authors[0]:
            embed.add_field(name="Tag owner", value=authors[0].mention)
        if len(authors[1:]) > 0:
            author_value = ""
            for i, user in enumerate(authors[1:]):
                if user is None:
                    author_value += f'{tag.co_author_ids[i]} '
                else:
                    author_value += f'{user.mention} '
            embed.add_field(name="Co-authors", value=author_value.strip())
        embed.add_field(name="Date created", value=format_dt(tag.date_created))
        await ctx.reply(embed=embed)

    @tag.command(
        brief='Returns raw tag content.',
        usage='<tag name>',
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def raw(self, ctx: Context, *, tag_name: str = None):
        tag = await self.resolve_tag(ctx, tag_name)

        with BytesIO(tag.content.encode("utf-8")) as buffer:
            file = File(buffer, f"{tag.name[:40]}-content.txt")

        await ctx.reply(f"Raw content for the tag '{tag.name}'", file=file)

    @tag.command(
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.cooldown(rate=10, per=60 * 60, type=commands.BucketType.user) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def create(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        assert ctx.guild is not None
        tag = Tag(self.client.api)
        tag.guild_id = ctx.guild.id
        tag.author_id = ctx.author.id
        if tag_name is None:
            raise BadArgument("Please specify a tag name!")
        tag.name = tag_name

        attachment_url = await self.resolve_attachments(ctx.message)
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content for the tag!")
        tag.content = ((content or "") + "\n" + (attachment_url or "")).strip()

        if await self.client.api.fetch_guild_tag(tag.guild_id, tag.name) is not None:
            raise BadArgument("There's already a tag by the specified name!")

        await tag.create()
        await ctx.reply(embed=SuccessEmbed("Tag created successfully!"))

    @tag.command(
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def edit(self, ctx: Context, tag_name: Optional[str], *, content: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id not in tag._author_ids:
                raise BadArgument("You cannot edit a tag you don't own or co-author!")

        attachment_url = await self.resolve_attachments(ctx.message)
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content for a tag!")
        tag.content = ((content or "") + "\n" + (attachment_url or "")).strip()

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag edited successfully!"))

    @tag.command(
        name="add-author",
        brief="Add a new tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def add_author(self, ctx: Context, tag_name: Optional[str], member: Optional[Member]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot add a co-author to a tag you don't own!")

        if member is None:
            raise BadArgument("Please specify the member you want to add a co-author!")

        if member.bot:
            raise BadArgument("You cannot add a bot as co-author, that'd be stupid!")

        tag.add_co_author(member.id)

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag co-author added successfully!"))

    @tag.command(
        name="remove-author",
        brief="Remove a tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def remove_author(self, ctx: Context, tag_name: Optional[str], member: Optional[Member]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a co-author from a tag you don't own!")

        if member is None:
            raise BadArgument("Please specify the member you want to remove from co-authors!")

        tag.remove_co_author(member.id)

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag co-author removed successfully!"))

    @tag.command(
        brief="Claim a server tag in the case the tag owner leaves.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def claim(self, ctx: Context, *, tag_name: Optional[str]):
        assert ctx.guild is not None
        tag = await self.resolve_tag(ctx, tag_name)

        if ctx.author.id == tag.author_id:
            raise BadArgument("You are the tag owner, there is no need to claim it!")

        if not has_moderator_permissions(ctx, manage_messages=True):
            authors = await self.fetch_tag_author_members(ctx.guild, tag)
            if authors[0] is not None:
                raise BadArgument("Tag owner is still in the server!")

            if ctx.author.id not in tag.co_author_ids and any(member for member in authors[1:] if member is not None):
                raise BadArgument("There are still tag co-authors in the server! They can claim the tag too!")

        tag.author_id = ctx.author.id

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag claimed successfully!"))

    @tag.command(
        brief="Transfer a server tag to someone else.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def transfer(self, ctx: Context, tag_name: Optional[str], member: Optional[Member]):
        tag = await self.resolve_tag(ctx, tag_name)

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot transfer a tag you don't own!")

        if member is None:
            raise BadArgument("Please specify a member to whom you want to transfer the tag!")

        if ctx.author.id == member.id:
            raise BadArgument("You cannot transfer a tag to yourself!")

        if member.bot:
            raise BadArgument("You cannot transfer a tag to a bot, that'd be stupid!")

        tag.author_id = member.id

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed(f"Tag transfered to {escape_markdown(str(member))} successfully!"))

    @tag.command(
        brief="Remove a server tag.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def remove(self, ctx: Context, *, tag_name: Optional[str]):
        tag = await self.resolve_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a tag you don't own!")

        await tag.remove()
        await ctx.reply(embed=SuccessEmbed("Tag removed successfully!"))

async def setup(client: Pidroid) -> None:
    await client.add_cog(TagCommands(client))
