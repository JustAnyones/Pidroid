import discord
import os

from discord.ext import commands
from discord.ext.commands.context import Context
from io import BytesIO
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from typing import Union, Tuple

from discord.ext.commands.errors import BadArgument

from cogs.models.categories import RandomCategory
from cogs.utils import http
from cogs.utils.embeds import error

COMIC_FONT_PATH = './resources/COMIC.TTF'

def draw_text_with_border(draw, x, y, text, font, text_colour='white', border_colour='black') -> None:
    """Draws text with borders."""
    # Borders
    draw.text((x - 1, y - 1), text, font=font, fill=border_colour)
    draw.text((x + 1, y - 1), text, font=font, fill=border_colour)
    draw.text((x - 1, y + 1), text, font=font, fill=border_colour)
    draw.text((x + 1, y + 1), text, font=font, fill=border_colour)
    # The actual text
    draw.text((x, y), text, font=font, fill=text_colour)


async def handle_attachment(ctx: Context) -> Union[Tuple[discord.Attachment, str], None]:
    """Returns None or discord.Attachment after assuring it is safe to use."""
    attachments = ctx.message.attachments
    if len(attachments) < 1:
        raise BadArgument('I could not find any attachments!')

    attachment = attachments[0]

    filename = attachment.filename
    extension = os.path.splitext(filename)[1]
    if extension.lower() not in ['.png', '.jpg', '.jpeg']:
        raise BadArgument('Unsupported file extension. Only image files of .png, .jpg and .jpeg extensions are supported!')

    if attachment.size >= 7000000:
        raise BadArgument('Your image is too big! Please upload images below 7 MBs')

    return attachment, extension


class ImageManipCommands(commands.Cog):
    """This class implements cog which contains commands for image manipulation."""

    def __init__(self, client):
        self.client = client

    @commands.command(
        brief='Bonks the specified member.',
        usage='<member>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    async def bonk(self, ctx: Context, member: discord.Member = None):
        if member is None:
            await ctx.reply(embed=error('Please specify a member which you want to bonk!'))
            self.bonk.reset_cooldown(ctx)
            return

        async with ctx.channel.typing():
            output_file = BytesIO()
            img = Image.open('./resources/bonk.jpg')
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(COMIC_FONT_PATH, 14)
            # Target
            draw_text_with_border(draw, 165, 140, member.display_name, font)
            # Issuer of command
            draw_text_with_border(draw, 7, 43, ctx.author.display_name, font)

            img.save(output_file, format='png')
            img.close()
            output_file.seek(0)
            await ctx.reply(content=member.mention, file=discord.File(output_file, filename='image.png'))
        output_file.close()

    @commands.command(
        brief='Updates meme uploaded as attachment to comply within the German copyright regulations.',
        usage='[bool whether to retain ratio]',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    async def memefy(self, ctx: Context, retain_aspect: bool = False):
        async with ctx.channel.typing():
            attachment, extension = await handle_attachment(ctx)

            output_file = BytesIO()
            async with await http.get(self.client, attachment.url) as r:
                payload = await r.read()
            input_file = BytesIO(payload)
            img = Image.open(input_file)
            sizes = (128, 128)
            if retain_aspect:
                orig_w, orig_h = img.size
                sizes = (128, round(orig_w * 128 / orig_h))
            img = img.resize(sizes, Image.ANTIALIAS)
            img.save(output_file, format='png')
            img.close()
            input_file.close()
            output_file.seek(0)
            await ctx.reply(
                content='Meme has been updated to comply within German regulations.',
                file=discord.File(output_file, filename=f'image{extension}')
            )
        output_file.close()

    @commands.command(
        brief='Upscales image to 4k resolution.',
        usage='<quality(1-10)>',
        aliases=['jpeg'],
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    async def hank(self, ctx: Context, quality: int = 1):
        async with ctx.channel.typing():
            attachment, _ = await handle_attachment(ctx)

            if quality < 1:
                await ctx.reply(embed=error('Quality must be a positive number!'))
                return

            if quality > 10:
                await ctx.reply(embed=error('Quality must be 10 or less!'))
                return

            async with await http.get(self.client, attachment.url) as r:
                payload = await r.read()
            input_file = BytesIO(payload)

            img = Image.open(input_file)
            img = img.convert("RGB")
            b = BytesIO()
            img.save(b, format='JPEG', quality=quality)
            img.close()
            input_file.close()
            b.seek(0)
            await ctx.reply(content='Do I look like I know what a JPEG is?', file=discord.File(b, filename='compression.jpg'))
        b.close()


def setup(client):
    client.add_cog(ImageManipCommands(client))
