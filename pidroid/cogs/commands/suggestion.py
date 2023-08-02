import os
import random

from contextlib import suppress
from datetime import timedelta
from discord.channel import TextChannel
from discord.ext import commands # type: ignore
from discord.errors import HTTPException
from discord.ext.commands import BadArgument, MissingRequiredArgument # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.member import Member
from typing import Dict, List

from pidroid.client import Pidroid
from pidroid.cogs.handlers.error_handler import notify
from pidroid.models.categories import UtilityCategory 
from pidroid.models.persistent_views import PersistentSuggestionDeletionView
from pidroid.utils import truncate_string
from pidroid.utils.checks import check_bot_channel_permissions, is_guild_theotown
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import timedelta_to_datetime

ALLOWED_SUGGESTION_ATTACHMENT_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif']

SUGGESTION_REACTIONS: Dict[str, str] = {
    "✅": "I like this idea",
    "❌": "I hate this idea",
}

THEOTOWN_SUGGESTION_REACTIONS = {
    "✅": "I like this idea",
    "❌": "I hate this idea",
    "❗": "Already possible",
    "❕": "Already possible with plugin(s)"
}

BOT_COMMANDS_CHANNEL_ID = 367299681635794954
REFUSE_COMMAND_RESPONSES = [
    'I do not recommend using my commands here. Perhaps there\'s a better channel for that?',
    'It wouldn\'t be wise to run your command here, therefore, I won\'t.',
    'You may not run your command here.',
    'Sorry, I cannot do that here.'
]


class SuggestionCommand(commands.Cog): # type: ignore
    """This class implements a cog for the suggestion command."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command( # type: ignore
        name="suggest",
        brief='Send a suggestion to the server suggestions channel.',
        usage='<suggestion>',
        examples=[
            ("Suggest a luxurious building", 'suggest A luxury pickle-themed building'),
        ],
        category=UtilityCategory
    )
    @commands.guild_only()
    @commands.cooldown(rate=1, per=60 * 5, type=commands.BucketType.user) # type: ignore
    async def suggest_command(self, ctx: Context, *, suggestion: str):
        assert isinstance(ctx.me, Member)
        assert ctx.guild

        config = await self.client.fetch_guild_configuration(ctx.guild.id)
        if not config.suggestion_system_active:
            raise BadArgument("Suggestion system is not active in this server!")

        # Check if we're in TheoTown guild
        is_theotown_guild = is_guild_theotown(ctx.guild)
        reactions = SUGGESTION_REACTIONS
        if is_theotown_guild:
            # Check if they are sending it outside the bot commands channel
            if ctx.channel.id != BOT_COMMANDS_CHANNEL_ID:
                raise BadArgument(random.choice(REFUSE_COMMAND_RESPONSES)) # nosec

            reactions = THEOTOWN_SUGGESTION_REACTIONS

        # Construct the reaction legend
        reaction_legend = ""
        keys = list(reactions.keys())
        for key in keys[:-1]:
            reaction_legend += f"{key} {reactions[key]}; "
        reaction_legend += f"{keys[-1]} {reactions[keys[-1]]}."

        if config.suggestions_channel_id is None:
            raise BadArgument("This server does not have a suggestion channel set.")

        # Get the channel and ensure bot has the permission to send messages there
        channel = self.client.get_channel(config.suggestions_channel_id)
        if channel is None:
            raise BadArgument("Could not find the suggestion channel for this server.")

        assert isinstance(channel, TextChannel)
        check_bot_channel_permissions(
            ctx.me, channel,
            send_messages=True,
            attach_files=True,
            add_reactions=True,
            create_public_threads=True
        )

        async with ctx.typing():
            if len(suggestion) < 10:
                raise BadArgument("Your suggestion is too short! Include at least 10 characters.")

            # If suggestion text is above discord embed description limit
            if len(suggestion) > 2048:
                raise BadArgument("The suggestion is too long! Keep it within 2048 character limit.")

            embed = PidroidEmbed(description=suggestion)
            embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)

            # Deal with attachments
            file = None
            attachments = ctx.message.attachments
            if attachments:
                if len(attachments) > 1:
                    raise BadArgument("Only one picture can be submitted for a suggestion!")

                attachment = attachments[0]
                if attachment.size >= ctx.filesize_limit:
                    raise BadArgument("Your image is too big to be uploaded!")

                filename = attachment.filename
                extension = os.path.splitext(filename)[1]
                if extension.lower() not in ALLOWED_SUGGESTION_ATTACHMENT_EXTENSIONS:
                    raise BadArgument("Could not submit a suggestion: unsupported file extension. Only image files are supported!")

                file = await attachment.to_file()
                embed.set_image(url=f'attachment://{filename}')

            # Add the reaction legend to the footer
            embed.set_footer(text=reaction_legend)

            # Send the suggestion message
            if file:
                message = await channel.send(embed=embed, file=file)
            else:
                message = await channel.send(embed=embed)

            # Add reactions to the sent message
            for key in reactions:
                await message.add_reaction(key)

            # If we're in TheoTown guild, update the footer and send the suggestion to a database
            if is_theotown_guild:
                suggestion_attachments: List[str] = []
                if message.embeds[0].image.url is not None:
                    suggestion_attachments.append(message.embeds[0].image.url)
                s_id = await self.client.api.insert_suggestion(ctx.author.id, message.id, suggestion, suggestion_attachments)
                embed.set_footer(text=f"{embed.footer.text}\n#{s_id}")
                await message.edit(embed=embed, view=PersistentSuggestionDeletionView())

            if config.suggestion_threads_enabled:
                await self.client.create_expiring_thread(
                    message, f"{truncate_string(str(ctx.author), 40)}'s suggestion discussion",
                    timedelta_to_datetime(timedelta(days=30)),
                    channel.default_auto_archive_duration
                )

            # Let the suggestion author know that the suggestion was sent
            with suppress(HTTPException):
                await ctx.reply(f'Your suggestion has been submitted to {channel.mention} channel successfully!')

    @suggest_command.error
    async def on_suggest_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "suggestion":
                return await notify(ctx, "Please specify your suggestion.")
        setattr(error, 'unhandled', True)

async def setup(client: Pidroid) -> None:
    await client.add_cog(SuggestionCommand(client))
