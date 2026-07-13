from abc import ABC, abstractmethod
from typing import List
from app.search.schemas import SearchResultItem

class BaseSearchProvider(ABC):
    """
    Abstract base class for all Search Providers.
    Ensures they expose a standard search signature.
    """

    @abstractmethod
    async def search(self, query: str, max_results: int) -> List[SearchResultItem]:
        """
        Executes a search query and returns a list of normalized SearchResultItem objects.
        """
        pass
