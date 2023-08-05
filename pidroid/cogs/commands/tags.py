from __future__ import annotations

import datetime

from discord.ext import commands # type: ignore
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.file import File
from discord.message import Attachment
from discord.user import User
from discord.member import Member
from discord.mentions import AllowedMentions
from discord.message import Message
from discord.utils import escape_markdown, format_dt
from io import BytesIO
from typing import TYPE_CHECKING, List, Optional

from pidroid.models.categories import TagCategory
from pidroid.models.view import PaginatingView
from pidroid.utils.checks import has_moderator_guild_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import ListPageSource

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = [
    "create", "edit", "remove", "claim", "transfer", "list", "info",
    "add-author", "add_author", "raw",
    "remove-author", "remove_author"
]
ALLOWED_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)

if TYPE_CHECKING:
    from pidroid.client import Pidroid
    from pidroid.utils.api import TagTable

class TagListPaginator(ListPageSource):
    def __init__(self, title: str, data: List[Tag]):
        super().__init__(data, per_page=20)
        self.embed = PidroidEmbed(title=title)

        amount = len(data)
        if amount == 1:
            self.embed.set_footer(text=f"{amount} tag")
        else:
            self.embed.set_footer(text=f"{amount} tags")

    async def format_page(self, menu: PaginatingView, data: List[Tag]):
        offset = menu._current_page * self.per_page + 1
        values = ""
        for i, item in enumerate(data):
            values += f"{i + offset}. {item.name}\n"
        self.embed.description = values.strip()
        return self.embed

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
        _date_created: datetime.datetime

    def __init__(self, client: Pidroid, data: Optional[TagTable] = None) -> None:
        self._client = client
        self._api = client.api
        self._author_ids = []
        if data:
            self._deserialize(data)

    @property
    def name(self) -> str:
        """Returns the name of the tag."""
        return self._name

    @name.setter
    def name(self, value: str):
        """Sets the name of the tag.
        
        Will raise BadArgument if the name is deemed invalid."""
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
        """Returns the content of the tag."""
        return self._content

    @content.setter
    def content(self, value: str):
        """Sets the content of the tag.
        
        Will raise BadArgument if the content string is too long."""
        if len(value) > 2000:
            raise BadArgument("Tag content is too long! Please keep it below 2000 characters!")
        self._content = value

    @property
    def author_id(self) -> int:
        """Returns the user ID of the tag author."""
        return self._author_ids[0]

    @author_id.setter
    def author_id(self, value: int) -> None:
        """Sets the tag author to the specified user ID."""
        # If it was in list before hand, like a co-author
        if value in self.co_author_ids:
            self._author_ids.remove(value)

        if len(self._author_ids) == 0:
            return self._author_ids.append(value)
        self._author_ids[0] = value

    @property
    def co_author_ids(self) -> List[int]:
        """Returns a list of tag's co-authors' user IDs."""
        return self._author_ids[1:]

    def add_co_author(self, author_id: int) -> None:
        """Adds the specified author to tag co-authors.
        
        Will raise BadArgument if author ID is not valid."""
        if self.author_id == author_id:
            raise BadArgument("You cannot add yourself as a co-author!")
        if len(self._author_ids) > 4:
            raise BadArgument("A tag can only have up to 4 co-authors!")
        if author_id in self.co_author_ids:
            raise BadArgument("Specifed member is already a co-author!")
        self._author_ids.append(author_id)

    def remove_co_author(self, author_id: int) -> None:
        """Removes the specified author ID from co-authors.
        
        Will raise BadArgument if specified member is not a co-author."""
        if author_id not in self.co_author_ids:
            raise BadArgument("Specified member is not a co-author!")
        self._author_ids.remove(author_id)

    def is_author(self, user_id: int) -> bool:
        """Returns true if specified user is an author."""
        return user_id in self._author_ids

    async def fetch_authors(self) -> List[Optional[User]]:
        """Returns a list of optional user objects which represent the tag authors."""
        return [await self._client.get_or_fetch_user(auth_id) for auth_id in self._author_ids]

    def _deserialize(self, data: TagTable) -> None:
        self._id = data.id # type: ignore
        self.guild_id = data.guild_id # type: ignore
        self._name = data.name # type: ignore
        self._content = data.content # type: ignore
        self._author_ids = data.authors # type: ignore
        self.aliases = data.aliases # type: ignore
        self.locked = data.locked # type: ignore
        self._date_created = data.date_created # type: ignore

    async def create(self) -> None:
        """Creates a tag by inserting an entry to the database."""
        self._id = await self._api.insert_tag(self.guild_id, self.name, self.content, self._author_ids)

    async def edit(self) -> None:
        """Edits the tag by updating the entry in the database."""
        await self._api.update_tag(self._id, self.content, self._author_ids, self.aliases, self.locked)

    async def remove(self) -> None:
        """Removes the tag entry from the database."""
        if not self._api:
            raise BadArgument("API attribute is missing!")
        await self._api.delete_tag(self._id)


class TagCommands(commands.Cog): # type: ignore
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        self.client = client

    async def fetch_tag(self, ctx: Context, tag_name: str) -> Tag:
        """Fetches a tag by specified name using the context."""
        assert ctx.guild is not None
        tag = await self.client.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag

    async def find_tags(self, ctx: Context, tag_name: str) -> List[Tag]:
        """Returns a list of tags matching the specified tag name using the context."""
        if len(tag_name) < 3:
            raise BadArgument("Query term is too short! Please keep it above 2 characters!")

        assert ctx.guild is not None
        tag_list = await self.client.api.search_guild_tags(ctx.guild.id, tag_name)
        if len(tag_list) == 0:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag_list

    async def resolve_attachments(self, message: Message) -> Optional[str]:
        """Returns attachment URL from the message. None if there are no attachments.
        
        Will raise BadArgument if more than one attachment is provided."""
        if len(message.attachments) == 0:
            return None

        if len(message.attachments) > 1:
            raise BadArgument("Tags can only support a single attachment!")

        attachment = message.attachments[0]
        return attachment.url


    @commands.hybrid_group( # type: ignore
        name="tag",
        brief='Returns a server tag by the specified name.',
        usage='[tag name]',
        category=TagCategory,
        invoke_without_command=True,
        fallback="get"
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def tag_command(self, ctx: Context, *, tag_name: str):
        if ctx.invoked_subcommand is None:
            tag_list = await self.find_tags(ctx, tag_name)
            assert tag_name is not None

            if len(tag_list) == 1:
                message_content = tag_list[0].content
            elif tag_list[0].name.lower() == tag_name.lower():
                message_content = tag_list[0].content
            else:
                source = TagListPaginator(f"Tags matching your query", tag_list)
                view = PaginatingView(self.client, ctx, source=source)
                return await view.send()
            if ctx.message.reference and ctx.message.reference.message_id:
                message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                return await message.reply(
                    message_content,
                    allowed_mentions=ALLOWED_MENTIONS.merge(AllowedMentions(replied_user=True))
                )
            return await ctx.reply(message_content, allowed_mentions=ALLOWED_MENTIONS)


    @tag_command.command( # type: ignore
        name="list",
        brief="Returns a list of available server tags.",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def tag_list_command(self, ctx: Context):
        assert ctx.guild is not None
        guild_tags = await self.client.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            raise BadArgument("This server has no defined tags!")

        source = TagListPaginator(f"{escape_markdown(ctx.guild.name)} server tag list", guild_tags)
        view = PaginatingView(self.client, ctx, source=source)
        await view.send()

    @tag_command.command( # type: ignore
        name="info",
        brief='Returns information about a server tag.',
        usage='<tag name>',
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def tag_info_command(self, ctx: Context, *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        authors = await tag.fetch_authors()

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
        embed.add_field(name="Date created", value=format_dt(tag._date_created))
        await ctx.reply(embed=embed)


    @tag_command.command( # type: ignore
        name="raw",
        brief='Returns raw tag content.',
        usage='<tag name>',
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def tag_raw_command(self, ctx: Context, *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        with BytesIO(tag.content.encode("utf-8")) as buffer:
            file = File(buffer, f"{tag.name[:40]}-content.txt")

        await ctx.reply(embed=SuccessEmbed(f"Raw content for the tag '{tag.name}"), file=file)


    @tag_command.command( # type: ignore
        name="create",
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.cooldown(rate=10, per=60, type=commands.BucketType.user) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_create_command(self, ctx: Context, tag_name: str, *, content: Optional[str], file: Optional[Attachment] = None):
        assert ctx.guild is not None
        tag = Tag(self.client)
        tag.guild_id = ctx.guild.id
        tag.author_id = ctx.author.id
        tag.name = tag_name

        if await self.client.api.fetch_guild_tag(tag.guild_id, tag.name) is not None:
            raise BadArgument("There's already a tag by the specified name!")

        attachment_url = await self.resolve_attachments(ctx.message) # The file from interactions are also obtained this way
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content or an attachment for the tag!")
        tag.content = ((content or "") + "\n" + (attachment_url or "")).strip()

        await tag.create()
        await ctx.reply(embed=SuccessEmbed("Tag created successfully!"))


    @tag_command.command( # type: ignore
        name="edit",
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_edit_command(self, ctx: Context, tag_name: str, *, content: Optional[str], file: Optional[Attachment] = None):
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if not tag.is_author(ctx.author.id):
                raise BadArgument("You cannot edit a tag you don't own or co-author!")

        attachment_url = await self.resolve_attachments(ctx.message) # The file from interactions are also obtained this way
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content or an attachment for the tag!")
        tag.content = ((content or "") + "\n" + (attachment_url or "")).strip()

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag edited successfully!"))


    @tag_command.command(
        name="add-author",
        brief="Add a new tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_add_author_command(self, ctx: Context, tag_name: str, member: Member):
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot add a co-author to a tag you don't own!")

        if member.bot:
            raise BadArgument("You cannot add a bot as co-author, that'd be stupid!")

        tag.add_co_author(member.id)

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag co-author added successfully!"))


    @tag_command.command(
        name="remove-author",
        brief="Remove a tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_remove_author_command(self, ctx: Context, tag_name: str, member: Member):
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a co-author from a tag you don't own!")

        tag.remove_co_author(member.id)

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag co-author removed successfully!"))


    @tag_command.command(
        name="claim",
        brief="Claim a server tag in the case the tag owner leaves.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_claim_command(self, ctx: Context, *, tag_name: str):
        assert ctx.guild is not None
        tag = await self.fetch_tag(ctx, tag_name)

        if ctx.author.id == tag.author_id:
            raise BadArgument("You are the tag owner, there is no need to claim it!")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            # First, check if owner is still in the server
            if await self.client.get_or_fetch_member(ctx.guild, tag.author_id) is not None:
                raise BadArgument("Tag owner is still in the server!")

            # First check if we can elevate user from co-author to owner
            if ctx.author.id not in tag.co_author_ids:

                # if we can't, we have to check every author and if at least a single one is in the server, raise exception
                for co_author_id in tag.co_author_ids:
                    if await self.client.get_or_fetch_member(ctx.guild, co_author_id):
                        raise BadArgument("There are still tag co-authors in the server! They can claim the tag too!")

        tag.author_id = ctx.author.id

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed("Tag claimed successfully!"))


    @tag_command.command(
        name="transfer",
        brief="Transfer a server tag to someone else.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_transfer_command(self, ctx: Context, tag_name: str, member: Member):
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot transfer a tag you don't own!")

        if ctx.author.id == member.id:
            raise BadArgument("You cannot transfer a tag to yourself!")

        if member.bot:
            raise BadArgument("You cannot transfer a tag to a bot, that'd be stupid!")

        tag.author_id = member.id

        await tag.edit()
        await ctx.reply(embed=SuccessEmbed(f"Tag transfered to {escape_markdown(str(member))} successfully!"))


    @tag_command.command(
        name="remove",
        brief="Remove a server tag.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.can_modify_tags()
    @commands.guild_only() # type: ignore
    async def tag_remove_command(self, ctx: Context, *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a tag you don't own!")

        await tag.remove()
        await ctx.reply(embed=SuccessEmbed("Tag removed successfully!"))


async def setup(client: Pidroid) -> None:
    await client.add_cog(TagCommands(client))
