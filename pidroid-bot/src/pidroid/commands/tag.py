from __future__ import annotations

import re
import logging

from discord import AllowedMentions, Attachment, File, Member
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.utils import escape_markdown, format_dt
from io import BytesIO
from typing import TYPE_CHECKING, override

from pidroid.models.categories import TagCategory
from pidroid.models.event_types import EventName, EventType
from pidroid.models.tags import Tag
from pidroid.models.view import PaginatingView
from pidroid.utils.checks import has_moderator_guild_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import ListPageSource

ALLOWED_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)

NUMERATION_ESCAPE_REGEX = re.compile(r"(\d+)\.") # designed to escape it anywhere in the text

if TYPE_CHECKING:
    from pidroid.client import Pidroid

logger = logging.getLogger("pidroid.commands.tag")

class TagListPaginator(ListPageSource):
    def __init__(self, title: str, data: list[Tag]):
        super().__init__(data, per_page=20)
        self.embed: PidroidEmbed = PidroidEmbed(title=title)

        amount = len(data)
        if amount == 1:
            _ = self.embed.set_footer(text=f"{amount} tag")
        else:
            _ = self.embed.set_footer(text=f"{amount} tags")

    @override
    async def format_page(self, menu: PaginatingView, page: list[Tag]):
        offset = menu.current_page * self.per_page + 1
        values = ""
        for i, item in enumerate(page):
            values += f"{i + offset}. {NUMERATION_ESCAPE_REGEX.sub(r"\1\.", item.name)}\n"
        self.embed.description = values.strip()
        return self.embed


async def _resolve_attachments(ctx: Context[Pidroid], maybe_file: Attachment | None) -> list[Attachment]:
    """
    Returns list of useable tag attachments from the context.
    If command was invoked via slash command, it will upload the provided attachment first. If it cannot, it will raise BadArgument.
    """
    message = ctx.message

    if ctx.interaction and maybe_file is not None:
        _ = await ctx.interaction.response.defer()
        file_bytes = await maybe_file.read()
        try:
            msg = await ctx.reply(
                "Attachments received via slash commands are ephemeral and will expire. Therefore, I have reuploaded it for it to be usable in tags.",
                file=File(BytesIO(file_bytes), filename=maybe_file.filename)
            )
            return msg.attachments
        except Exception as e:
            logger.exception("Failed to reupload attachment received via slash command")
            raise BadArgument(
                "Attachments received via slash commands are ephemeral and will expire. Please provide a link to the file instead."
            ) from e
    
    return message.attachments

class TagCommandCog(commands.Cog):
    """This class implements a cog for dealing with guild tag related commands.."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client: Pidroid = client

    async def fetch_tag(self, ctx: Context[Pidroid], tag_name: str) -> Tag:
        """Fetches a tag by specified name using the context."""
        assert ctx.guild is not None
        tag = await self.client.api.fetch_guild_tag(ctx.guild.id, tag_name)
        if tag is None:
            raise BadArgument(f"Could not find any tags matching '{tag_name}'.")
        return tag

    async def find_tags(self, ctx: Context[Pidroid], tag_name: str) -> list[Tag]:
        """Returns a list of tags matching the specified tag name using the context."""
        if len(tag_name) < 3:
            raise BadArgument("Query term is too short. Please keep it above 2 characters.")

        assert ctx.guild is not None
        tag_list = await self.client.api.search_guild_tags(ctx.guild.id, tag_name)
        if len(tag_list) == 0:
            raise BadArgument(f"Could not find any tags matching '{tag_name}'.")
        return tag_list

    @commands.hybrid_group(
        name="tag",
        brief="Returns a server tag by the specified name.",
        usage="[tag name]",
        fallback="get",
        extras={
            "category": TagCategory,
            "examples": [("Show a tag that contains the name files", "tag files")],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_command(self, ctx: Context[Pidroid], *, tag_name: str):
        if ctx.invoked_subcommand is None:
            tag_list = await self.find_tags(ctx, tag_name)
            assert tag_name is not None

            # If there's only a single tag, return it right away
            message_content = ""
            if len(tag_list) == 1:
                message_content = tag_list[0].content
            # Otherwise, check for exact match first
            else:            
                found = False
                for tag in tag_list:
                    if tag.name.lower() == tag_name.lower():
                        message_content = tag.content
                        found = True
                        break
                if not found:
                    source = TagListPaginator("Tags matching your query", tag_list)
                    view = PaginatingView(self.client, ctx, source=source)
                    return await view.send()
                
            assert message_content != "", "Message content should have been found at this point"

            if ctx.message.reference and ctx.message.reference.message_id:
                message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                await ctx.message.delete(delay=0) # delete invoking message to reduce clutter
                return await message.reply(
                    message_content,
                    allowed_mentions=ALLOWED_MENTIONS.merge(AllowedMentions(replied_user=True))
                )
            return await ctx.reply(message_content, allowed_mentions=ALLOWED_MENTIONS)


    @tag_command.command(
        name="list",
        brief="Returns a list of available server tags.",
        extras={
            "category": TagCategory,
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_list_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        guild_tags = await self.client.api.fetch_guild_tags(ctx.guild.id)
        if len(guild_tags) == 0:
            raise BadArgument("This server has not defined any tags.")

        source = TagListPaginator(f"{escape_markdown(ctx.guild.name)} server tag list", guild_tags)
        view = PaginatingView(self.client, ctx, source=source)
        await view.send()

    @tag_command.command(
        name="info",
        brief="Returns information about a specific server tag.",
        usage="<tag name>",
        extras={
            "category": TagCategory,
            "examples": [("Show tag information. Note how you have to use the full name.", "tag info role explanations")],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def tag_info_command(self, ctx: Context[Pidroid], *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        authors = tag.get_authors()

        embed = PidroidEmbed(title=tag.name, description=tag.content)
        if authors[0]:
            _ = embed.add_field(name="Tag owner", value=authors[0].mention)
        if len(authors[1:]) > 0:
            author_value = ""
            for i, user in enumerate(authors[1:]):
                if user is None:
                    author_value += f'{tag.co_author_ids[i]} '
                else:
                    author_value += f'{user.mention} '
            _ = embed.add_field(name="Co-authors", value=author_value.strip())
        _ = embed.add_field(name="Date created", value=format_dt(tag.date_created))
        _ = await ctx.reply(embed=embed)


    @tag_command.command(
        name="raw",
        brief="Returns raw tag content.",
        usage="<tag name>",
        extras={
            "category": TagCategory,
            "examples": [("Show raw tag content. Note how you have to use the full name.", 'tag raw role explanations')],
        }
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @commands.guild_only()
    async def tag_raw_command(self, ctx: Context[Pidroid], *, tag_name: str):
        tag = await self.fetch_tag(ctx, tag_name)

        with BytesIO(tag.content.encode("utf-8")) as buffer:
            file = File(buffer, f"{tag.name[:40]}-content.txt")

        return await ctx.reply(embed=SuccessEmbed(f"Raw content for the tag '{tag.name}'"), file=file)


    @tag_command.command(
        name="create",
        brief="Create a server tag.",
        usage="<tag name> <tag content>",
        extras={
            "category": TagCategory,
            "examples": [
                ("Create a tag called Role explanations", 'tag create "Role explanations" amazing role tag'),
            ],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=10, per=60, type=commands.BucketType.user)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_create_command(self, ctx: Context[Pidroid], tag_name: str, *, content: str | None, file: Attachment | None = None):
        assert ctx.guild

        stripped_name = tag_name.strip()

        if await self.client.api.fetch_guild_tag(ctx.guild.id, stripped_name) is not None:
            raise BadArgument(f"There's already a tag named '{stripped_name}'.")
        
        attachments = await _resolve_attachments(ctx, file)
        if content is None and len(attachments) == 0:
            raise BadArgument("Please provide content or an attachments for the tag.")
        attachment_urls = ''.join(attachment.url + '\n' for attachment in attachments)
        parsed_content = ((content or "") + "\n" + attachment_urls).strip()

        tag = await Tag.create(
            self.client,
            guild_id=ctx.guild.id,
            name=stripped_name,
            content=parsed_content,
            author=ctx.author.id
        )

        await ctx.reply(embed=SuccessEmbed("Tag created successfully."))
        self.client.log_event(
            EventType.tag_create, EventName.tag_create, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="edit",
        brief="Edit a server tag.",
        usage="<tag name> <tag content>",
        extras={
            "category": TagCategory,
            "examples": [("Edit a tag called Role explanations", 'tag edit "Role explanations" amazingly edited tag')],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_edit_command(self, ctx: Context[Pidroid], tag_name: str, *, content: str | None, file: Attachment | None = None):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked.")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if not tag.is_author(ctx.author.id):
                raise BadArgument("You cannot edit a tag you don't own or co-author.")

        attachments = await _resolve_attachments(ctx, file)
        if content is None and len(attachments) == 0:
            raise BadArgument("Please provide content or an attachments for the tag.")
        attachment_urls = ''.join(attachment.url + '\n' for attachment in attachments)
        parsed_content = ((content or "") + "\n" + attachment_urls).strip()

        await tag.edit(content=parsed_content)
        await ctx.reply(embed=SuccessEmbed("Tag modified successfully."))
        self.client.log_event(
            EventType.tag_update, EventName.tag_edit, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="add-author",
        brief="Add a new tag co-author.",
        usage="<tag name> <member>",
        extras={
            "category": TagCategory,
            "examples": [("Allow JustAnyone to edit role tag", 'tag add-author "Role explanations" JustAnyone')],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_add_author_command(self, ctx: Context[Pidroid], tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot add a co-author to a tag you don't own.")

        if member.bot:
            raise BadArgument("You cannot add a bot as a tag co-author.")

        await tag.add_co_author(member.id)
        await ctx.reply(embed=SuccessEmbed("Tag co-author added successfully."))
        self.client.log_event(
            EventType.tag_update, EventName.tag_author_update, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="remove-author",
        brief="Remove a tag co-author.",
        usage="<tag name> <member>",
        extras={
            "category": TagCategory,
            "examples": [("Remove JustAnyone from authors", 'tag remove-author "Role explanations" JustAnyone')],
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_remove_author_command(self, ctx: Context[Pidroid], tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a co-author from a tag you don't own.")

        await tag.remove_co_author(member.id)
        await ctx.reply(embed=SuccessEmbed("Tag co-author removed successfully."))
        self.client.log_event(
            EventType.tag_update, EventName.tag_author_update, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="claim",
        brief="Claim a server tag in the case the tag owner leaves.",
        usage="<tag name>",
        extras={
            "category": TagCategory,
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_claim_command(self, ctx: Context[Pidroid], *, tag_name: str):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if ctx.author.id == tag.author_id:
            raise BadArgument("You are the tag owner, there is no need to claim it.")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            # First, check if owner is still in the server
            if await self.client.get_or_fetch_member(ctx.guild, tag.author_id) is not None:
                raise BadArgument("Tag owner is still in the server.")

            # First check if we can elevate user from co-author to owner
            if ctx.author.id not in tag.co_author_ids:

                # if we can't, we have to check every author and if at least a single one is in the server, raise exception
                for co_author_id in tag.co_author_ids:
                    if await self.client.get_or_fetch_member(ctx.guild, co_author_id):
                        raise BadArgument("There are still tag co-authors in the server. They can claim the tag too.")

        await tag.edit(owner_id=ctx.author.id)
        await ctx.reply(embed=SuccessEmbed("Tag claimed successfully."))
        self.client.log_event(
            EventType.tag_update, EventName.tag_claim, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="transfer",
        brief="Transfer a server tag to someone else.",
        usage="<tag name> <member>",
        extras={
            "category": TagCategory,
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_transfer_command(self, ctx: Context[Pidroid], tag_name: str, member: Member):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot transfer a tag you don't own.")

        if ctx.author.id == member.id:
            raise BadArgument("You cannot transfer a tag to yourself.")

        if member.bot:
            raise BadArgument("You cannot transfer a tag to a bot.")

        await tag.edit(owner_id=member.id)
        await ctx.reply(embed=SuccessEmbed(f"Tag transfered to {escape_markdown(str(member))} successfully."))
        self.client.log_event(
            EventType.tag_update, EventName.tag_transfer, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


    @tag_command.command(
        name="remove",
        brief="Remove a server tag.",
        usage="<tag name>",
        extras={
            "category": TagCategory,
        }
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.can_modify_tags()
    @commands.guild_only()
    async def tag_remove_command(self, ctx: Context[Pidroid], *, tag_name: str):
        assert ctx.guild
        tag = await self.fetch_tag(ctx, tag_name)

        if tag.locked:
            raise BadArgument("Tag cannot be modified as it is locked.")

        if not has_moderator_guild_permissions(ctx, manage_messages=True):
            if ctx.author.id != tag.author_id:
                raise BadArgument("You cannot remove a tag you don't own.")

        await self.client.api.delete_tag(tag.row)
        await ctx.reply(embed=SuccessEmbed("Tag removed successfully."))
        self.client.log_event(
            EventType.tag_delete, EventName.tag_delete, ctx.guild.id, tag.row, ctx.author.id,
            extra=tag.to_dict()
        )


async def setup(client: Pidroid) -> None:
    await client.add_cog(TagCommandCog(client))
