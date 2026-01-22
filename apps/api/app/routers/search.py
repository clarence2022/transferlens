"""
Search Router
=============

Provides unified search across players and clubs.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import SearchResponse
from app.services import search_entities

router = APIRouter(tags=["Search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db)
) -> SearchResponse:
    """
    Search for players and clubs by name.
    
    Results are ranked by relevance using fuzzy matching.
    Returns a mixed list of players and clubs.
    
    **Examples:**
    - `/search?q=Haaland` - Find players named Haaland
    - `/search?q=Manchester` - Find clubs with Manchester in name
    - `/search?q=Bellingham&limit=5` - Get top 5 matches
    """
    results = await search_entities(db, q, limit)
    
    return SearchResponse(
        query=q,
        results=results,
        total=len(results)
    )
