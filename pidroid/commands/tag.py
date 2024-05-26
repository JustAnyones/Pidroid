from __future__ import annotations

from discord import AllowedMentions, Attachment, File, Member, Message
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.utils import escape_markdown, format_dt
from io import BytesIO
from typing import TYPE_CHECKING, Optional, override

from pidroid.models.categories import TagCategory
from pidroid.models.event_types import EventName, EventType
from pidroid.models.tags import Tag
from pidroid.models.view import PaginatingView
from pidroid.utils.checks import has_moderator_guild_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import ListPageSource

ALLOWED_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class TagListPaginator(ListPageSource):
    def __init__(self, title: str, data: list[Tag]):
        super().__init__(data, per_page=20)
        self.embed = PidroidEmbed(title=title)

        amount = len(data)
        if amount == 1:
            self.embed.set_footer(text=f"{amount} tag")
        else:
            self.embed.set_footer(text=f"{amount} tags")

    @override
    async def format_page(self, menu: PaginatingView, data: list[Tag]):
        offset = menu._current_page * self.per_page + 1
        values = ""
        for i, item in enumerate(data):
            values += f"{i + offset}. {item.name}\n"
        self.embed.description = values.strip()
        return self.embed

class TagCommandCog(commands.Cog):
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    async def fetch_tag(self, ctx: Context[Pidroid], tag_name: str) -> Tag:
        """Fetches a tag by specified name using the context."""
        assert ctx.guild is not None
        tag = await self.client.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            raise BadArgument("I couldn't find any tags matching that name!")
        return tag

    async def find_tags(self, ctx: Context[Pidroid], tag_name: str) -> list[Tag]:
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


    @commands.hybrid_group(
        name="tag",
        brief='Returns a server tag by the specified name.',
        usage='[tag name]',
        category=TagCategory,
        invoke_without_command=True,
        fallback="get",
        examples=[
            ("Show a tag that contains the name files", 'tag files'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_command(self, ctx: Context, *, tag_name: str):
        if ctx.invoked_subcommand is None:
            tag_list = await self.find_tags(ctx, tag_name)
            assert tag_name is not None

            if len(tag_list) == 1:
                message_content = tag_list[0].content

            else:            
                found = False
                for tag in tag_list:
                    if tag.name.lower() == tag_name.lower():
                        message_content = tag.content
                        found = True
                        break

                if not found:
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


    @tag_command.command(
        name="list",
        brief="Returns a list of available server tags.",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_list_command(self, ctx: Context):
        assert ctx.guild is not None
        guild_tags = await self.client.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            raise BadArgument("This server has no defined tags!")

        source = TagListPaginator(f"{escape_markdown(ctx.guild.name)} server tag list", guild_tags)
        view = PaginatingView(self.client, ctx, source=source)
        await view.send()

    @tag_command.command(
        name="info",
        brief='Returns information about a specific server tag.',
        usage='<tag name>',
        category=TagCategory,
        examples=[
            ("Show tag information. Note how you have to use the full name.", 'tag info role explanations'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_info_command(self, ctx: Context, *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        authors = tag.get_authors()

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


    @tag_command.command(
        name="raw",
        brief='Returns raw tag content.',
        usage='<tag name>',
        category=TagCategory,
        examples=[
            ("Show raw tag content. Note how you have to use the full name.", 'tag raw role explanations'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @commands.guild_only()
    async def tag_raw_command(self, ctx: Context, *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        with BytesIO(tag.content.encode("utf-8")) as buffer:
            file = File(buffer, f"{tag.name[:40]}-content.txt")

        await ctx.reply(embed=SuccessEmbed(f"Raw content for the tag '{tag.name}'"), file=file)


    @tag_command.command(
        name="create",
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory,
        examples=[
            ("Create a tag called Role explanations", 'tag create "Role explanations" amazing role tag'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=10, per=60, type=commands.BucketType.user)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_create_command(self, ctx: Context, tag_name: str, *, content: Optional[str], file: Optional[Attachment] = None):
        assert ctx.guild

        stripped_name = tag_name.strip()

        if await self.client.api.fetch_guild_tag(ctx.guild.id, stripped_name) is not None:
            raise BadArgument("There's already a tag by the specified name!")

        attachment_url = await self.resolve_attachments(ctx.message) # The file from interactions are also obtained this way
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content or an attachment for the tag!")
        parsed_content = ((content or "") + "\n" + (attachment_url or "")).strip()

        tag = await Tag.create(
            self.client,
            guild_id=ctx.guild.id,
            name=stripped_name,
            content=parsed_content,
            author=ctx.author.id
        )

        await ctx.reply(embed=SuccessEmbed("Tag created successfully!"))
        self.client.log_event(
            EventType.tag_create, EventName.tag_create, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="edit",
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        category=TagCategory,
        examples=[
            ("Edit a tag called Role explanations", 'tag edit "Role explanations" amazingly edited tag'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_edit_command(self, ctx: Context, tag_name: str, *, content: Optional[str], file: Optional[Attachment] = None):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if not tag.is_author(ctx.author.id):
                raise BadArgument("You cannot edit a tag you don't own or co-author!")

        attachment_url = await self.resolve_attachments(ctx.message) # The file from interactions are also obtained this way
        if content is None and attachment_url is None:
            raise BadArgument("Please provide content or an attachment for the tag!")
        parsed_content = ((content or "") + "\n" + (attachment_url or "")).strip()

        await tag.edit(content=parsed_content)
        await ctx.reply(embed=SuccessEmbed("Tag edited successfully!"))
        self.client.log_event(
            EventType.tag_update, EventName.tag_edit, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="add-author",
        brief="Add a new tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory,
        examples=[
            ("Allow JustAnyone to edit role tag", 'tag add-author "Role explanations" JustAnyone'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_add_author_command(self, ctx: Context, tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot add a co-author to a tag you don't own!")

        if member.bot:
            raise BadArgument("You cannot add a bot as co-author, that'd be stupid!")

        await tag.add_co_author(member.id)
        await ctx.reply(embed=SuccessEmbed("Tag co-author added successfully!"))
        self.client.log_event(
            EventType.tag_update, EventName.tag_author_update, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="remove-author",
        brief="Remove a tag co-author.",
        usage="<tag name> <member>",
        category=TagCategory,
        examples=[
            ("Remove JustAnyone from authors", 'tag remove-author "Role explanations" JustAnyone'),
        ],
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_remove_author_command(self, ctx: Context[Pidroid], tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a co-author from a tag you don't own!")

        await tag.remove_co_author(member.id)
        await ctx.reply(embed=SuccessEmbed("Tag co-author removed successfully!"))
        self.client.log_event(
            EventType.tag_update, EventName.tag_author_update, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="claim",
        brief="Claim a server tag in the case the tag owner leaves.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_claim_command(self, ctx: Context[Pidroid], *, tag_name: str):
        assert ctx.guild
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

        await tag.edit(owner_id=ctx.author.id)
        await ctx.reply(embed=SuccessEmbed("Tag claimed successfully!"))
        self.client.log_event(
            EventType.tag_update, EventName.tag_claim, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="transfer",
        brief="Transfer a server tag to someone else.",
        usage="<tag name> <member>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_transfer_command(self, ctx: Context[Pidroid], tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot transfer a tag you don't own!")

        if ctx.author.id == member.id:
            raise BadArgument("You cannot transfer a tag to yourself!")

        if member.bot:
            raise BadArgument("You cannot transfer a tag to a bot, that'd be stupid!")

        await tag.edit(owner_id=member.id)
        await ctx.reply(embed=SuccessEmbed(f"Tag transfered to {escape_markdown(str(member))} successfully!"))
        self.client.log_event(
            EventType.tag_update, EventName.tag_transfer, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="remove",
        brief="Remove a server tag.",
        usage="<tag name>",
        category=TagCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_remove_command(self, ctx: Context[Pidroid], *, tag_name: str):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked!")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a tag you don't own!")

        await self.client.api.delete_tag(tag.row)
        await ctx.reply(embed=SuccessEmbed("Tag removed successfully!"))
        self.client.log_event(
            EventType.tag_delete, EventName.tag_delete, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


async def setup(client: Pidroid) -> None:
    await client.add_cog(TagCommandCog(client))
