from typing import TypedDict

class PluginEntry(TypedDict):
    id: int
    author_id: int
    rating_sum: int
    rating_count: int
    downloads: int
    name: str
    description: str
    price: int
    img: str
    author_name: str

CreatorEntryDict = TypedDict('CreatorEntryDict', {
    'author_id': int,
    'plugins': int,
    'downloads': int,
    'rating_sum': int,
    'rating_count': int,
    'author_name': str,
    'plugin arr': list[PluginEntry],
})

class TopCreatorEntry(TypedDict):
    author_id: int
    plugins: int
    downloads: int
    rating_sum: int
    rating_count: int
    author_name: str

PluginStoreStatisticsDict = TypedDict('PluginStoreStatisticsDict', {
    'year': str,
    'month': str,
    'plugin count last month': int,
    'plugin creators last month': list[CreatorEntryDict],
    'plugin creators all time by downloads': list[TopCreatorEntry],
    'plugin creators all time': list[TopCreatorEntry],
    'plugins all time': list[PluginEntry],
})
