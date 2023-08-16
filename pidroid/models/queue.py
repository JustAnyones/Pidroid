import logging

from asyncio import Queue, sleep
from discord import Embed, TextChannel
from typing import Any, Union

logger = logging.getLogger('Pidroid')

def split_text_into_chunks(text: str, max_chunk_length: int = 2000):
    """Splits text into nice chunks."""
    if len(text) <= max_chunk_length:
        return [text]

    chunks = []
    while len(text) > max_chunk_length:
        chunk = text[:max_chunk_length]
        last_newline = chunk.rfind('\n')
        if last_newline != -1:
            chunks.append(chunk[:last_newline+1])
            text = text[last_newline+1:]
        else:
            last_space = chunk.rfind(' ')
            if last_space != -1:
                chunks.append(chunk[:last_space+1])
                text = text[last_space+1:]
            else:
                # If there are no spaces, split at max_length
                chunks.append(chunk)
                text = text[max_chunk_length:]

    # Append any remaining part of the text
    if text:
        chunks.append(text)

    return chunks


class AbstractMessageQueue:
    """This is an abstract message queue."""

    def __init__(self, channel: TextChannel) -> None:
        self._queue: Queue[Union[Embed, str]] = Queue(maxsize=0)
        self._channel = channel

    async def queue(self, item: Any) -> None:
        """Adds the specified embed to the queue."""
        await self._queue.put(item)
    
    async def handle_queue(self):
        """Handles the queue items."""
        raise NotImplementedError

class MessageQueue(AbstractMessageQueue):
    """This defines an generic message queue in a specific channel."""

    def __init__(self, channel: TextChannel) -> None:
        super().__init__(channel)

    async def queue(self, item: str) -> None:
        stripped = item.strip()
        if stripped == '':
            return

        # If it is longer than 2000, split it at 2000
        # and preferably, near a newline
        if len(stripped) > 2000:
            chunks = split_text_into_chunks(stripped, 2000)

            for chunk in chunks:
                await super().queue(chunk.strip())
            return
        return await super().queue(item)
    
    async def handle_queue(self):
        try:
            if self._queue.qsize() > 0:
                item = await self._queue.get()
                await self._channel.send(content=item)
            await sleep(0.75)
        except Exception as e:
            logger.exception(e)

class EmbedMessageQueue(AbstractMessageQueue):

    def __init__(self, channel: TextChannel) -> None:
        super().__init__(channel)

    async def handle_queue(self):
        try:
            queue_size = self._queue.qsize()

            # Discord allows max 10 embeds per message
            stop_index = queue_size if queue_size <= 10 else 10

            items = []
            for _ in range(stop_index):
                item = await self._queue.get()
                items.append(item)

            # If we have items, send em
            if items:
                await self._channel.send(embeds=items)

            # Don't run this too often
            await sleep(0.75)
        except Exception as e:
            logger.exception(e)
