import asyncpraw # type: ignore
import random
import typing

from asyncpraw.models.reddit.submission import Submission # type: ignore
from asyncpraw.models.reddit.subreddit import Subreddit # type: ignore
from asyncprawcore import exceptions # type: ignore
from asyncprawcore.exceptions import ResponseException # type: ignore
from discord.channel import DMChannel, GroupChannel, PartialMessageable
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from typing import Optional, Union

from pidroid.client import Pidroid
from pidroid.models.categories import RandomCategory
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.parsers import truncate_string

BASE_REDDIT_URL = 'https://www.reddit.com'
UNMARKED_NSFW_SUBREDDITS = [
    'keqing', 'copypasta'
]

async def get_random_submission(subreddit: Subreddit, limit: int = 50) -> Submission:
    """Returns a random submission from hot subreddit submissions."""
    return random.choice([s async for s in subreddit.hot(limit=limit)]) # nosec

def assure_content_rating(ctx: Context, content: Union[Submission, Subreddit]) -> None:
    """This function assures that the content is safe for consumption in accordance to channel NSFW level."""
    assert not isinstance(ctx.channel, PartialMessageable)

    # Allow it by default in DMs and groups
    if isinstance(ctx.channel, (DMChannel, GroupChannel)):
        return

    # Allow it in channels with NSFW option turned on
    if ctx.channel.is_nsfw():
        return

    if isinstance(content, Subreddit):
        if content.over18 or content.display_name.lower() in UNMARKED_NSFW_SUBREDDITS:
            raise BadArgument('Specified subreddit is age-restricted. Please browse such subreddits in age-restricted channels!')

    if isinstance(content, Submission):
        if content.over_18:
            raise BadArgument('Found submission was age-restricted. Please try again or browse similiar content in age-restricted channels!')

def get_author_name(sub: Submission) -> str:
    """Returns the name of the author."""
    if sub.author is None:
        return "[deleted]"
    return sub.author.name

def get_submission_footer(sub: Submission) -> str:
    """Returns the string of the submission footer."""
    text = f"Submitted by {get_author_name(sub)}"
    gallery_size = len(get_submission_gallery(sub))
    if gallery_size > 1:
        text += f'\nGallery of {gallery_size} images.'
    return text

def is_submission_gallery(sub: Submission) -> bool:
    """Returns True if submission is a gallery."""
    return hasattr(sub, 'media_metadata')

def get_submission_gallery(sub: Submission) -> typing.List[str]:
    """Returns a list of submission gallery."""
    if not is_submission_gallery(sub):
        return []
    return [sub.media_metadata[i]['s']['u'] for i in sub.media_metadata.keys()]

class RedditCommands(commands.Cog): # type: ignore
    """This class implements a cog for reddit related commands and methods."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

        # Reddit login
        c = self.client.config
        self.reddit_instance = asyncpraw.Reddit(
            client_id=c['reddit_client_id'],
            client_secret=c['reddit_client_secret'],
            username=c['reddit_username'],
            password=c['reddit_password'],
            user_agent="Pidroid bot by u/RealJustAnyone"
        )

    def cog_unload(self):
        # Logout from reddit session
        if self.reddit_instance is not None:
            self.client.loop.create_task(self.reddit_instance.close())  # Just so I don't get asyncio unclosed loop errors

    @commands.command( # type: ignore
        brief='Fetches a random post from specified subreddit.',
        usage='<subreddit name>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def reddit(self, ctx: Context, subreddit_name: Optional[str] = None):
        async with ctx.typing():
            if subreddit_name is None:
                raise BadArgument('Please specify a subreddit from which you want to fetch a random post!')

            try:
                subreddit = await self.reddit_instance.subreddit(subreddit_name, fetch=True)
            except exceptions.Redirect:
                raise BadArgument("I am being redirected, are you certain that the specified subreddit exists?")
            except ResponseException as e:
                raise BadArgument(str(e))
            except Exception:
                raise BadArgument("I could not find the specified subreddit!")

            # Check subreddit for nsfw
            assure_content_rating(ctx, subreddit)

            submission = await get_random_submission(subreddit)
            # Check submission for nsfw
            assure_content_rating(ctx, submission)

            images: typing.List[str] = []
            is_gallery = is_submission_gallery(submission)

            subreddit_name = f'/{submission.subreddit_name_prefixed}/'
            subreddit_url = BASE_REDDIT_URL + subreddit.url
            post_url = BASE_REDDIT_URL + submission.permalink

            # Get images from gallery
            images.extend(get_submission_gallery(submission))

            # Handles preview files
            if hasattr(submission, 'preview'):
                images.append(submission.preview['images'][0]['source']['url'])

            text = submission.selftext
            if not hasattr(submission, 'preview'):
                if not is_gallery and post_url != submission.url:
                    text = submission.url + '\n' + submission.selftext

            embed = PidroidEmbed(
                title=truncate_string(submission.title, 256),
                description=truncate_string(text.replace('&#x200B;', '')),
                url=post_url
            )
            embed.set_author(name=subreddit_name, url=subreddit_url)
            if len(images) > 0:
                embed.set_image(url=images[0])
            embed.set_footer(text=get_submission_footer(submission))

            await ctx.reply(embed=embed)


async def setup(client: Pidroid) -> None:
    await client.add_cog(RedditCommands(client))
