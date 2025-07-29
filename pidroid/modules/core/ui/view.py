import logging

from discord import Interaction
from discord.ui import Container, Item, LayoutView
from typing import Self, override

logger = logging.getLogger("pidroid.ui.view")

class PidroidLayoutView(LayoutView):
    """
    A base class for Pidroid layout views.
    """

    @override
    async def on_error(self, interaction: Interaction, error: Exception, item: Item[Self]):
        logger.exception(
            "An error occurred in PidroidLayoutView: %s\nItem: %s",
            error,
            item,
            exc_info=error,
        )
        await interaction.response.send_message(
            "An error occurred while processing your request. Please try again later.",
            ephemeral=True,
        )


class ReadonlyContainerView(PidroidLayoutView):
    """
    A read-only view that contains a single container.
    This view is designed to be used when you want to display a container
    without allowing any interaction with its items.
    """

    def __init__(
        self,
        container: Container[Self],
    ):
        super().__init__(timeout=None)
        self.add_item(container)
