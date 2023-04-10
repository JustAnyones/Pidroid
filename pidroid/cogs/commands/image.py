import discord
import os

from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from io import BytesIO
from PIL import Image # type: ignore
from PIL import ImageFont
from PIL import ImageDraw
from typing import Tuple

from pidroid.client import Pidroid
from pidroid.models.categories import RandomCategory
from pidroid.utils import http
from pidroid.utils.embeds import ErrorEmbed
from pidroid.utils.file import Resource

COMIC_FONT_PATH = Resource("COMIC.TTF")

def draw_text_with_border(draw, x, y, text, font, text_colour='white', border_colour='black') -> None:
    """Draws text with borders."""
    # Borders
    draw.text((x - 1, y - 1), text, font=font, fill=border_colour)
    draw.text((x + 1, y - 1), text, font=font, fill=border_colour)
    draw.text((x - 1, y + 1), text, font=font, fill=border_colour)
    draw.text((x + 1, y + 1), text, font=font, fill=border_colour)
    # The actual text
    draw.text((x, y), text, font=font, fill=text_colour)


async def handle_attachment(ctx: Context) -> Tuple[discord.Attachment, str]:
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


class ImageManipCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for image manipulation."""

    def __init__(self, client):
        self.client = client

    @commands.command( # type: ignore
        brief='Bonks the specified member.',
        usage='<member>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.user) # type: ignore
    async def bonk(self, ctx: Context, member: discord.Member):
        async with ctx.channel.typing():
            output_file = BytesIO()
            img = Image.open(Resource('bonk.jpg'))
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

    @commands.command( # type: ignore
        brief='Updates meme uploaded as attachment to comply within the German copyright regulations.',
        usage='[bool whether to retain ratio]',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.user) # type: ignore
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

    @commands.command( # type: ignore
        brief='Upscales image to 4k resolution.',
        usage='<quality(1-10)>',
        aliases=['jpeg'],
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.user) # type: ignore
    async def hank(self, ctx: Context, quality: int = 1):
        async with ctx.channel.typing():
            attachment, _ = await handle_attachment(ctx)

            if quality < 1:
                await ctx.reply(embed=ErrorEmbed('Quality must be a positive number!'))
                return

            if quality > 10:
                await ctx.reply(embed=ErrorEmbed('Quality must be 10 or less!'))
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


async def setup(client: Pidroid):
    await client.add_cog(ImageManipCommands(client))
