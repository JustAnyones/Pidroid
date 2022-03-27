import asyncpraw
import random
import typing

from asyncpraw.models.reddit.submission import Submission
from asyncpraw.models.reddit.subreddit import Subreddit
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument

from client import Pidroid
from cogs.models.categories import RandomCategory
from cogs.utils.embeds import PidroidEmbed, error
from cogs.utils.parsers import truncate_string

BASE_REDDIT_URL = 'https://www.reddit.com'
UNMARKED_NSFW_SUBREDDITS = [
    'keqing'
]

async def get_random_submission(subreddit: Subreddit, limit: int = 50) -> Submission:
    """Returns a random submission from hot subreddit submissions."""
    return random.choice([s async for s in subreddit.hot(limit=limit)]) # nosec

def assure_content_rating(ctx: Context, content: typing.Union[Submission, Subreddit]) -> None:
    """This function assures that the content is safe for consumption in accordance to channel NSFW level."""
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

def get_submission_gallery(sub: Submission) -> list:
    """Returns a list of submission gallery."""
    if not is_submission_gallery(sub):
        return []
    return [sub.media_metadata[i]['s']['u'] for i in sub.media_metadata.keys()]

class RedditCommands(commands.Cog):
    """This class implements a cog for reddit related commands and methods."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

        # Reddit login
        c = self.client.config['authentication']['reddit']
        self.reddit_instance = asyncpraw.Reddit(
            client_id=c['client id'],
            client_secret=c['client secret'],
            username=c['username'],
            password=c['password'],
            user_agent="Pidroid bot by u/RealJustAnyone"
        )

    def cog_unload(self) -> None:
        # Logout from reddit session
        if self.reddit_instance is not None:
            self.client.loop.create_task(self.reddit_instance.close())  # Just so I don't get asyncio unclosed loop errors

    @commands.command(
        brief='Fetches a random post from specified subreddit.',
        usage='<subreddit name>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def reddit(self, ctx: Context, subreddit_name: str = None):
        async with ctx.typing():
            if subreddit_name is None:
                await ctx.reply(embed=error('Please specify a subreddit from which you want to fetch a random post!'))
                return

            try:
                subreddit = await self.reddit_instance.subreddit(subreddit_name, fetch=True)
            except Exception:
                await ctx.reply(embed=error("I could not find the specified subreddit!"))
                return

            # Check subreddit for nsfw
            assure_content_rating(ctx, subreddit)

            submission = await get_random_submission(subreddit)
            # Check submission for nsfw
            assure_content_rating(ctx, submission)

            images = []
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
