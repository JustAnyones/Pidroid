import logging

from asyncio import Queue, sleep
from discord import AllowedMentions, Embed, TextChannel
from typing import override

logger = logging.getLogger('pidroid.models.queue')

def split_text_into_chunks(text: str, max_chunk_length: int = 2000):
    """Splits text into nice chunks."""
    if len(text) <= max_chunk_length:
        return [text]

    chunks: list[str] = []
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

    def __init__(self, channel: TextChannel, *, delay: float = -1) -> None:
        self._queue: Queue[Embed | str] = Queue(maxsize=0)
        self._channel = channel
        self._delay = delay
        if delay <= 0:
            self._delay = 5

    async def queue(self, item: Embed | str) -> None:
        """Adds the specified embed to the queue."""
        await self._queue.put(item)
    
    async def handle_queue(self):
        """Handles the queue items."""
        raise NotImplementedError

class MessageQueue(AbstractMessageQueue):
    """This defines an generic message queue in a specific channel."""

    def __init__(self, channel: TextChannel, *, delay: float = -1) -> None:
        super().__init__(channel, delay=delay)

    @override
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
    
    async def _combine_if_possible(self, value: str) -> str:
        """Tries to combine multiple queue elements into a single message."""
        if not self._queue.empty():

            # WARN: usually, this is a very bad idea in multi consumer flows, but
            # since there's only a single consumer for our messages queues,
            # this doesn't matter in this specific case
            next_value: str = self._queue._queue[0]
            #print("Peeking:", next_value)

            combined = value + "\n" + next_value
            if len(combined) <= 2000:
                #print("Combining", len(value), "->", len(combined))
                await self._queue.get()
                return await self._combine_if_possible(combined)
        #print("Leaving combining loop")
        return value

    @override
    async def handle_queue(self):
        try:
            item = await self._queue.get()
            assert isinstance(item, str)
            #print("Grabbed:", item)
            content = await self._combine_if_possible(item)
            _ = await self._channel.send(
                content=content,
                allowed_mentions=AllowedMentions(
                    everyone=False, replied_user=False,
                    users=False, roles=False
                )
            )
            await sleep(self._delay)
        except Exception as e:
            logger.exception(e)

class EmbedMessageQueue(AbstractMessageQueue):

    def __init__(self, channel: TextChannel, *, delay: float = -1) -> None:
        super().__init__(channel, delay=delay)

    @override
    async def handle_queue(self):
        try:
            queue_size = self._queue.qsize()

            # Discord allows max 10 embeds per message
            stop_index = queue_size if queue_size <= 10 else 10

            items: list[Embed] = []
            for _ in range(stop_index):
                item = await self._queue.get()
                assert isinstance(item, Embed)
                items.append(item)

            # If we have items, send em
            if items:
                _ = await self._channel.send(embeds=items)

            # Don't run this too often
            await sleep(self._delay)
        except Exception as e:
            logger.exception(e)
