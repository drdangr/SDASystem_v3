"""
Graph API endpoints for visualization
Adapts existing API data for graph visualization
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from backend.api import routes

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/news")
async def get_news_graph() -> Dict[str, Any]:
    """
    Get news graph data for visualization
    
    Transforms existing API data into graph-friendly format
    
    Returns:
        nodes: News items with metadata
        links: Similarity edges between news
        stories: Story cluster information
    """
    try:
        graph_manager = routes.graph_manager
        
        # Get all news nodes
        nodes = []
        for news_id, news_data in graph_manager.news.items():
            node = {
                "id": news_id,
                "type": "news",
                "title": news_data.title,
                "story_id": news_data.story_id,
                "published_at": news_data.published_at.isoformat() if news_data.published_at else None,
                "domains": news_data.domains,
                "is_pinned": news_data.is_pinned,
                "source": news_data.source
            }
            nodes.append(node)
        
        # Get edges (news similarities) - transform to "links"
        links = []
        for source, target, data in graph_manager.news_graph.edges(data=True):
            link = {
                "source": source,
                "target": target,
                "weight": data.get("weight", 1.0),
                "type": "similarity"
            }
            links.append(link)
        
        # Get stories (cluster centers)
        stories = []
        for story_id, story_data in graph_manager.stories.items():
            story = {
                "id": story_id,
                "title": story_data.title,
                "news_ids": story_data.news_ids,
                "domain": story_data.primary_domain or (story_data.domains[0] if story_data.domains else None),
                "size": story_data.size,
                "relevance": story_data.relevance,
                "cohesion": story_data.cohesion,
                "top_actors": story_data.top_actors
            }
            stories.append(story)
        
        return {
            "nodes": nodes,
            "links": links,  # Changed from "edges" to "links"
            "stories": stories
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get graph data: {str(e)}")


@router.get("/actors")
async def get_actors_graph() -> Dict[str, Any]:
    """
    Get actors graph data for visualization
    
    Returns:
        nodes: Actor nodes with metadata
        links: Relations between actors
        mentions: Cross-layer connections (news ↔ actors)
    """
    try:
        graph_manager = routes.graph_manager
        
        # Get actor nodes
        nodes = []
        for actor_id, actor_data in graph_manager.actors.items():
            node = {
                "id": actor_id,
                "type": "actor",
                "name": actor_data.canonical_name,
                "actor_type": actor_data.actor_type,
                "mentions_count": graph_manager.get_actor_mentions_count(actor_id)
            }
            nodes.append(node)
        
        # Get actor relations
        links = []
        for source, target, data in graph_manager.actors_graph.edges(data=True):
            link = {
                "source": source,
                "target": target,
                "type": data.get("relation_type", "unknown"),
                "weight": data.get("weight", 1.0)
            }
            links.append(link)
        
        # Get cross-layer mentions (news ↔ actors)
        mentions = []
        for source, target, data in graph_manager.mentions_graph.edges(data=True):
            mention = {
                "news_id": data.get("news_id"),
                "actor_id": data.get("actor_id")
            }
            mentions.append(mention)
        
        return {
            "nodes": nodes,
            "links": links,
            "mentions": mentions
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get actors graph: {str(e)}")


@router.get("/stats")
async def get_graph_stats() -> Dict[str, Any]:
    """
    Get overall graph statistics
    """
    try:
        graph_manager = routes.graph_manager
        stats = graph_manager.get_graph_stats()
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph stats: {str(e)}")
