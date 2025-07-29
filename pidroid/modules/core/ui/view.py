from discord.ui import Container, LayoutView
from typing import Self

class ReadonlyContainerView(LayoutView):
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
