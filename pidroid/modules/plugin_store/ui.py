import calendar
import discord

from discord import ui, utils

from pidroid.modules.plugin_store.types import CreatorEntryDict, PluginStoreStatisticsDict, PluginEntry
from pidroid.utils import clean_inline_translations

def distribute_fairly(entries: list[CreatorEntryDict], limit: int = 10) -> list[int]:
    """Distributes slots fairly among entries based on their plugin counts using the Largest Remainder Method."""
    if not entries:
        return []

    counts = [int(e['plugins']) for e in entries]
    total = sum(counts)
    
    # In the case of no plugins, return zero allocation for everyone
    if total == 0:
        return [0] * len(entries)

    # Initial allocation (Floor of the proportional share)
    allocated: list[int] = []
    remainders: list[float] = []
    for count in counts:
        raw_share = (count / total) * limit
        floor_val = int(raw_share)
        allocated.append(floor_val)
        remainders.append(raw_share - floor_val)

    # Distribute remaining slots
    leftover = limit - sum(allocated)
    # We sort the indices of the remainders list based on their values (descending)
    # This tells us which indices deserve the "leftover" slots first
    priority_indices = sorted(range(len(remainders)), key=lambda i: remainders[i], reverse=True)

    for i in range(leftover):
        index_to_increase = priority_indices[i]
        allocated[index_to_increase] += 1

    return allocated

class PluginEntryContainer(ui.Container["MonthlyPluginReportLayout"]):
    def __init__(self, index: int, entry: PluginEntry):
        super().__init__()
        title = f"### {index + 1}. {clean_inline_translations(entry['name'])}"
        text = ""
        text += "**Author:** " + utils.escape_markdown(entry['author_name']) + "\n"
        text += f"**Downloads:** {entry['downloads']:,}\n"
        rating_percentage = round(entry['rating_sum'] / entry['rating_count'] * 100)
        text += f"**Rating:** {rating_percentage}% by {entry['rating_count']:,} ratings\n"

        url = f"https://data.theotown.com/get_file.php?t=pf&name={entry['img']}"
        self.add_item(ui.Section(
            f"{title}\n{text}",
            accessory=ui.Thumbnail[MonthlyPluginReportLayout](url)
        ))

class MonthlyPluginReportLayout(ui.LayoutView):
    def __init__(self, data: PluginStoreStatisticsDict):
        super().__init__()

        plugin_count_last_month = data['plugin count last month']
        plugin_creators_last_month = data['plugin creators last month']
        plugin_creators_all_time = data['plugin creators all time']
        plugin_creators_all_time_by_downloads = data['plugin creators all time by downloads']
        plugins_all_time = data['plugins all time']

        year_of_data = int(data["year"])
        month_of_data = int(data["month"])
        month_name = calendar.month_name[month_of_data]

        # Display creators of last month
        text = f"## Plugin store statistics for {month_name}\n"
        text += f"In total {plugin_count_last_month} new plugins have been released in {month_name} of {year_of_data}. Major contributors were:\n"
        for i, entry in enumerate(plugin_creators_last_month):
            escaped_name = utils.escape_markdown(entry['author_name'])
            text += f"{i+1}. {escaped_name}\n {entry['plugins']:,} plugin(s) which reached {entry['downloads']:,} downloads!\n"
        self.add_item(ui.TextDisplay(text))

        # Show those plugins in a gallery, allocating slots fairly based on plugin count
        distribution = distribute_fairly(plugin_creators_last_month, limit=10)
        gallery_items: list[discord.MediaGalleryItem] = []
        for i, slot_count in enumerate(distribution):
            for j in range(slot_count):
                gallery_items.append(discord.MediaGalleryItem(
                    f"https://data.theotown.com/get_file.php?t=pf&name={plugin_creators_last_month[i]["plugin arr"][j]['img']}"
                ))
        if gallery_items:
            self.add_item(ui.MediaGallery(
                *gallery_items
            ))

        # Display most popular creators of all time and by downloads
        most_popular_creators = "## Most popular plugin creators of all time\n"
        for i, entry in enumerate(plugin_creators_all_time):
            if i >= 10:
                break
            most_popular_creators += f"{i+1}. {entry['author_name']}\n And their {entry['plugins']:,} plugin(s) reaching {entry['downloads']:,} downloads!\n"
        self.add_item(ui.TextDisplay(most_popular_creators))

        most_popular_creators_by_downloads = "## Most popular plugin creators of all time by downloads\n"
        for i, entry in enumerate(plugin_creators_all_time_by_downloads):
            if i >= 10:
                break
            most_popular_creators_by_downloads += f"{i+1}. {entry['author_name']}\n And their {entry['plugins']:,} plugin(s) reaching {entry['downloads']:,} downloads!\n"
        self.add_item(ui.TextDisplay(most_popular_creators_by_downloads + "## Most popular plugins of all time"))

        # Display top plugins of all time
        plugins_all_time = data['plugins all time']
        for i in range(9): # Only 9 results
            top_plugin = plugins_all_time[i]
            self.add_item(PluginEntryContainer(i, top_plugin))
