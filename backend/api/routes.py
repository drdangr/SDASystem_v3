"""
FastAPI routes for SDASystem API
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime

from backend.models.entities import (
    News, Actor, Story, Event, ActorRelation, NewsRelation
)
from backend.services.graph_manager import GraphManager
from backend.services.clustering_service import ClusteringService
from backend.services.ner_service import NERService
from backend.services.ner_spacy_service import HybridNERService
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.services.event_extraction_service import EventExtractionService
from backend.services.embedding_service import EmbeddingService
from backend.services.llm_service import LLMService
from backend.services.llm_registry import ServiceRegistry
from backend.api import graph_routes

from pydantic import BaseModel
from pydantic import Field

# Initialize services
graph_manager = GraphManager()
embedding_service = EmbeddingService(use_mock=True)
ner_service = NERService()
event_service = EventExtractionService()
clustering_service = ClusteringService(graph_manager)

# Load data on startup
import json
import os
from dotenv import load_dotenv
load_dotenv()
# LLM registry (auto reload by mtime)
llm_registry = ServiceRegistry(
    config_path=os.getenv("LLM_SERVICES_CONFIG", "config/llm_services.json"),
    auto_reload=True
)
# Базовый LLM для акторов
default_llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"))
# Сервис извлечения акторов (инициализируется после загрузки данных)
actors_extraction_service: Optional[ActorsExtractionService] = None

def load_data():
    """Load mock data from JSON files"""
    data_dir = "data"
    
    # Load actors
    if os.path.exists(f"{data_dir}/actors.json"):
        with open(f"{data_dir}/actors.json", 'r') as f:
            actors_data = json.load(f)
            for item in actors_data:
                actor = Actor(**item)
                graph_manager.add_actor(actor)
            print(f"Loaded {len(actors_data)} actors")

    # Load news
    if os.path.exists(f"{data_dir}/news.json"):
        with open(f"{data_dir}/news.json", 'r') as f:
            news_data = json.load(f)
            for item in news_data:
                # Convert date string back to datetime
                if 'published_at' in item and item['published_at']:
                    item['published_at'] = datetime.fromisoformat(item['published_at'])
                news = News(**item)
                # Generate embedding if missing
                if not news.embedding:
                    # encode returns numpy array (n, dim), take first item and convert to list
                    news.embedding = embedding_service.encode(news.full_text or news.summary)[0].tolist()
                graph_manager.add_news(news)
            print(f"Loaded {len(news_data)} news items")

    # Load stories
    if os.path.exists(f"{data_dir}/stories.json"):
        with open(f"{data_dir}/stories.json", 'r') as f:
            stories_data = json.load(f)
            for item in stories_data:
                # Convert dates
                if 'first_seen' in item and item['first_seen']:
                    item['first_seen'] = datetime.fromisoformat(item['first_seen'])
                if 'last_activity' in item and item['last_activity']:
                    item['last_activity'] = datetime.fromisoformat(item['last_activity'])
                # Mock/stub fill for missing generated fields
                if not item.get('summary'):
                    item['summary'] = f"Auto summary for {item.get('title', 'Story')}"
                if not item.get('bullets'):
                    item['bullets'] = [f"Key point for {item.get('title', 'story')}"]
                if not item.get('domains'):
                    item['domains'] = []
                if not item.get('top_actors'):
                    item['top_actors'] = []
                story = Story(**item)
                graph_manager.add_story(story)
            print(f"Loaded {len(stories_data)} stories")
            
    # Compute similarities
    print("Computing news similarities...")
    graph_manager.compute_news_similarities(threshold=0.6)

    # Extract timeline events from news
    print("Extracting timeline events from news...")
    total_events = 0
    for news in graph_manager.news.values():
        events = event_service.extract_events_from_news(news)
        for event in events:
            # Ensure story linkage is set from news
            if not event.story_id:
                event.story_id = news.story_id
            graph_manager.add_event(event)
            total_events += 1
    print(f"Extracted {total_events} events")

    # Ensure each story has at least one event (synthetic fallback)
    from backend.models.entities import Event, EventType
    for story in graph_manager.stories.values():
        if len(story.event_ids) == 0:
            synthetic = Event(
                id=f"event_synth_{story.id}",
                news_id=story.core_news_ids[0] if story.core_news_ids else story.news_ids[0] if story.news_ids else f"news_{story.id}",
                story_id=story.id,
                event_type=EventType.FACT,
                title=f"{story.title} (synthetic event)",
                description=story.summary[:200] if story.summary else story.title,
                event_date=story.last_activity or story.updated_at or datetime.utcnow(),
                actors=story.top_actors,
                source_trust=0.5,
                confidence=0.5
            )
            graph_manager.add_event(synthetic)

# Execute loading
try:
    load_data()
    # Создать сервис извлечения акторов после загрузки данных
    # Используем автоматическое определение языка, если SPACY_MODEL не указан явно
    spacy_model_env = os.getenv("SPACY_MODEL")
    # Если SPACY_MODEL не установлен или равен дефолтному - используем автоопределение
    spacy_model = None if (not spacy_model_env or spacy_model_env == "en_core_web_sm") else spacy_model_env
    
    actors_extraction_service = ActorsExtractionService(
        graph_manager,
        default_llm_service,
        data_dir="data",
        use_spacy=True,
        spacy_model=spacy_model,  # None = автоматическое определение языка
    )
    # Автоинициализация, если акторов нет
    if len(graph_manager.actors) == 0:
        try:
            actors_extraction_service.start_initialization(low_conf_threshold=0.75)
        except Exception as auto_init_error:
            print(f"Auto initialization failed: {auto_init_error}")
except Exception as e:
    print(f"Error loading data: {e}")


app = FastAPI(
    title="SDASystem API",
    description="Story Driven Analytical System API",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include graph router
app.include_router(graph_routes.router)

class LLMRequest(BaseModel):
    task: Literal["summary", "bullets", "domains", "events"]
    title: Optional[str] = ""
    text: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    profile_id: Optional[str] = Field(None, description="LLM profile id (overrides defaults)")
    service_id: Optional[str] = Field(None, description="Optional service to route call through registry")

class LLMActorsRequest(BaseModel):
    news_id: str = Field(..., description="News ID to enrich")
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    profile_id: Optional[str] = Field(None, description="LLM profile id for actors enrichment")


class LLMServiceUpdateRequest(BaseModel):
    profile_id: Optional[str] = Field(None, description="New default profile id")
    params: Optional[Dict[str, Any]] = Field(None, description="Override params for the service")


class LLMInvokeRequest(BaseModel):
    profile_id: Optional[str] = None
    payload: Dict[str, Any]

# --- LLM ---

@app.get("/api/llm/services")
async def llm_services():
    """
    List registered LLM services and profiles (for UI).
    """
    services = llm_registry.list_services()
    profiles = llm_registry.list_profiles()
    return {
        "services": [
            {
                "id": s.id,
                "label": s.label,
                "description": s.description,
                "default_profile_id": s.default_profile_id,
                "params": s.params,
            }
            for s in services
        ],
        "profiles": [p.__dict__ for p in profiles],
    }


@app.put("/api/llm/services/{service_id}")
async def llm_service_update(service_id: str, req: LLMServiceUpdateRequest):
    """
    Update service default profile/params (persisted to JSON).
    """
    try:
        updated = llm_registry.update_service(
            service_id=service_id,
            profile_id=req.profile_id,
            params=req.params,
        )
        return {
            "id": updated.id,
            "label": updated.label,
            "description": updated.description,
            "default_profile_id": updated.default_profile_id,
            "params": updated.params,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/llm/services/{service_id}/invoke")
async def llm_service_invoke(service_id: str, req: LLMInvokeRequest):
    """
    Dev-only: invoke a registered service with given payload.
    """
    try:
        service_cfg = llm_registry.get_service(service_id)
        if not service_cfg:
            raise HTTPException(status_code=404, detail="Service not found")
        profile_id = req.profile_id or service_cfg.default_profile_id
        llm = llm_registry.build_llm(profile_id, use_mock=True)
        service = llm_registry.instantiate_service(service_id)
        result = service.run(llm, req.payload)
        return {"service_id": service_id, "profile_id": profile_id, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/generate")
async def llm_generate(payload: LLMRequest):
    """
    Generate content via Gemini (with cache), or mock if no key.
    Uses registry profiles; backward-compatible with direct params.
    """
    # resolve profile (if provided) else fallback to first profile or env defaults
    profile_id = payload.profile_id
    llm = None
    if profile_id:
        llm = llm_registry.build_llm(profile_id, use_mock=os.getenv("LLM_FORCE_MOCK") == "1")
    else:
        profiles = llm_registry.list_profiles()
        if profiles:
            llm = llm_registry.build_llm(
                profiles[0].id,
                use_mock=(os.getenv("LLM_FORCE_MOCK") == "1" or not os.getenv("GEMINI_API_KEY"))
            )

    if not llm:
        # fallback to direct construction
        llm = LLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_name=payload.model,
            temperature=payload.temperature,
            top_p=payload.top_p,
            top_k=payload.top_k,
            max_tokens=payload.max_tokens
        )

    # allow overrides
    if payload.model:
        llm.model_name = payload.model
    if payload.temperature is not None:
        llm.params["temperature"] = payload.temperature
    if payload.top_p is not None:
        llm.params["top_p"] = payload.top_p
    if payload.top_k is not None:
        llm.params["top_k"] = payload.top_k
    if payload.max_tokens is not None:
        llm.params["max_output_tokens"] = payload.max_tokens

    if payload.task == "summary":
        result = llm.summarize(payload.title or "", payload.text)
        return {"result": result}
    if payload.task == "bullets":
        result = llm.make_bullets(payload.title or "", payload.text)
        return {"result": result}
    if payload.task == "domains":
        result = llm.extract_domains(payload.text)
        return {"result": result}
    if payload.task == "events":
        result = llm.extract_events(payload.text)
        return {"result": result}

    raise HTTPException(status_code=400, detail="Unsupported task")


@app.post("/api/news/{news_id}/actors/refresh")
async def refresh_news_actors(news_id: str, payload: LLMActorsRequest):
    """
    Enrich news with actors via Hybrid NER (spaCy + LLM) or LLM only.
    Uses hybrid approach by default if available, falls back to LLM only.
    """
    news = graph_manager.news.get(news_id)
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    # Build LLM from registry profile if provided
    llm = None
    profile_id = payload.profile_id
    if profile_id:
        llm = llm_registry.build_llm(profile_id, use_mock=os.getenv("LLM_FORCE_MOCK") == "1")
    if not llm:
        llm = LLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_name=payload.model,
            temperature=payload.temperature,
            top_p=payload.top_p,
            top_k=payload.top_k,
            max_tokens=payload.max_tokens,
        )

    text = f"{news.title}\n{news.summary or ''}\n{news.full_text or ''}"
    
    # Использовать гибридный подход если доступен spaCy, иначе только LLM
    use_hybrid = os.getenv("USE_HYBRID_NER", "true").lower() == "true"
    method_used = "llm_only"
    
    try:
        if use_hybrid:
            try:
                # Создать гибридный сервис
                hybrid_service = HybridNERService(llm, use_spacy=True)
                # Загрузить акторов в gazetteer
                actors_list = list(graph_manager.actors.values())
                if actors_list:
                    hybrid_service.load_gazetteer(actors_list)
                
                # Извлечь акторов гибридным методом
                actors = hybrid_service.extract_actors(text, use_llm=True)
                method_used = "hybrid_spacy_llm"
            except Exception as hybrid_error:
                # Fallback на LLM если гибридный не работает
                print(f"[Hybrid NER fallback] {hybrid_error}, using LLM only")
                actors = llm.extract_actors(text)
                method_used = "llm_only_fallback"
        else:
            # Только LLM
            actors = llm.extract_actors(text)
            method_used = "llm_only"
        
        raw = getattr(llm, "last_raw", None)
    except Exception as e:
        import traceback
        detail = f"{e}\n{traceback.format_exc()}"
        print(f"[Actors extraction error] news_id={news_id} method={method_used} detail={detail}")
        raise HTTPException(status_code=500, detail=detail)

    # Update graph: add/merge actors and mentions
    updated_ids = []
    for actor_data in actors:
        name = actor_data.get("name")
        if not name:
            continue
        actor_id = graph_manager.ensure_actor(name=name, actor_type=actor_data.get("type"), confidence=actor_data.get("confidence"))
        graph_manager.add_mention(news_id=news.id, actor_id=actor_id, confidence=actor_data.get("confidence", 0.5))
        updated_ids.append(actor_id)

    # Keep only actor_* ids, replace old entries
    unique_ids = list({aid for aid in updated_ids if isinstance(aid, str) and aid.startswith("actor_")})
    news.mentioned_actors = unique_ids
    graph_manager.news[news.id].mentioned_actors = unique_ids
    # update story top actors
    if news.story_id:
        graph_manager.update_story_top_actors(news.story_id)

    return {"actors": actors, "actor_ids": unique_ids, "raw": raw, "method": method_used}


# --- Health Check ---

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "SDASystem API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    stats = graph_manager.get_graph_stats()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "stats": stats
    }


# --- Stories ---

@app.get("/api/stories", response_model=List[Story])
async def get_stories(
    active_only: bool = Query(True, description="Return only active stories"),
    sort_by: str = Query("relevance", description="Sort by: relevance, freshness, size"),
    limit: int = Query(100, description="Maximum number of results")
):
    """Get all stories"""
    stories = list(graph_manager.stories.values())

    # Filter active
    if active_only:
        stories = [s for s in stories if s.is_active]

    # Sort
    if sort_by == "relevance":
        stories.sort(key=lambda s: s.relevance, reverse=True)
    elif sort_by == "freshness":
        stories.sort(key=lambda s: s.freshness, reverse=True)
    elif sort_by == "size":
        stories.sort(key=lambda s: s.size, reverse=True)
    elif sort_by == "date":
        stories.sort(key=lambda s: s.last_activity, reverse=True)

    return stories[:limit]


@app.get("/api/stories/{story_id}", response_model=Story)
async def get_story(story_id: str):
    """Get specific story by ID"""
    if story_id not in graph_manager.stories:
        raise HTTPException(status_code=404, detail="Story not found")

    return graph_manager.stories[story_id]


@app.post("/api/stories/{story_id}/merge")
async def merge_stories(story_id: str, other_story_ids: List[str]):
    """Merge multiple stories into one"""
    all_ids = [story_id] + other_story_ids

    merged = clustering_service.merge_stories(all_ids)
    if not merged:
        raise HTTPException(status_code=400, detail="Failed to merge stories")

    return merged


@app.post("/api/stories/{story_id}/split")
async def split_story(story_id: str, news_groups: List[List[str]]):
    """Split a story into multiple stories"""
    new_stories = clustering_service.split_story(story_id, news_groups)

    if not new_stories:
        raise HTTPException(status_code=400, detail="Failed to split story")

    return new_stories


# --- News ---

@app.get("/api/news", response_model=List[News])
async def get_news(
    story_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = Query(100, description="Maximum number of results")
):
    """Get news items with optional filters"""
    news_items = list(graph_manager.news.values())

    # Apply filters
    if story_id:
        news_items = [n for n in news_items if n.story_id == story_id]

    if actor_id:
        news_items = [n for n in news_items if actor_id in n.mentioned_actors]

    if domain:
        news_items = [n for n in news_items if domain in n.domains]

    # Sort by publication date
    news_items.sort(key=lambda n: n.published_at, reverse=True)

    return news_items[:limit]


@app.get("/api/news/{news_id}", response_model=News)
async def get_news_item(news_id: str):
    """Get specific news item by ID"""
    if news_id not in graph_manager.news:
        raise HTTPException(status_code=404, detail="News not found")

    return graph_manager.news[news_id]


@app.get("/api/news/{news_id}/related")
async def get_related_news(news_id: str, limit: int = 10):
    """Get related news items"""
    if news_id not in graph_manager.news:
        raise HTTPException(status_code=404, detail="News not found")

    # Get neighbors in graph
    related_ids = graph_manager.get_node_neighbors(news_id, depth=1)

    # Get news objects with similarity scores
    related = []
    for rid in related_ids[:limit]:
        if graph_manager.news_graph.has_edge(news_id, rid):
            edge_data = graph_manager.news_graph[news_id][rid]
            similarity = edge_data.get('similarity', 0.0)

            related.append({
                "news_id": rid,
                "news": graph_manager.news[rid],
                "similarity": similarity
            })

    # Sort by similarity
    related.sort(key=lambda x: x['similarity'], reverse=True)

    return related


# --- Actors ---

@app.get("/api/actors", response_model=List[Actor])
async def get_actors(
    actor_type: Optional[str] = None,
    limit: int = Query(100, description="Maximum number of results")
):
    """Get all actors"""
    actors = list(graph_manager.actors.values())

    if actor_type:
        actors = [a for a in actors if a.actor_type == actor_type]

    return actors[:limit]


@app.get("/api/actors/{actor_id}", response_model=Actor)
async def get_actor(actor_id: str):
    """Get specific actor by ID"""
    if actor_id not in graph_manager.actors:
        raise HTTPException(status_code=404, detail="Actor not found")

    return graph_manager.actors[actor_id]


@app.get("/api/actors/{actor_id}/mentions")
async def get_actor_mentions(actor_id: str, limit: int = 50):
    """Get news mentioning this actor"""
    if actor_id not in graph_manager.actors:
        raise HTTPException(status_code=404, detail="Actor not found")

    news_ids = graph_manager.get_actor_news(actor_id)

    # Get news objects
    news_items = [graph_manager.news[nid] for nid in news_ids if nid in graph_manager.news]

    # Sort by date
    news_items.sort(key=lambda n: n.published_at, reverse=True)

    return news_items[:limit]


@app.get("/api/actors/{actor_id}/relations")
async def get_actor_relations(actor_id: str):
    """Get relationships for an actor"""
    if actor_id not in graph_manager.actors:
        raise HTTPException(status_code=404, detail="Actor not found")

    relations = []

    # Outgoing relations
    if actor_id in graph_manager.actors_graph:
        for target_id in graph_manager.actors_graph.successors(actor_id):
            edge_data = graph_manager.actors_graph[actor_id][target_id]
            relations.append({
                "source": actor_id,
                "target": target_id,
                "relation_type": edge_data.get('relation_type'),
                "weight": edge_data.get('weight', 1.0)
            })

    # Incoming relations
    if actor_id in graph_manager.actors_graph:
        for source_id in graph_manager.actors_graph.predecessors(actor_id):
            edge_data = graph_manager.actors_graph[source_id][actor_id]
            relations.append({
                "source": source_id,
                "target": actor_id,
                "relation_type": edge_data.get('relation_type'),
                "weight": edge_data.get('weight', 1.0)
            })

    return relations


# --- Events ---

@app.get("/api/events", response_model=List[Event])
async def get_events(
    story_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(100, description="Maximum number of results")
):
    """Get timeline events"""
    events = list(graph_manager.events.values())

    # Apply filters
    if story_id:
        events = [e for e in events if e.story_id == story_id]

    if event_type:
        events = [e for e in events if e.event_type == event_type]

    # Sort by event date
    events.sort(key=lambda e: e.event_date, reverse=True)

    return events[:limit]


@app.get("/api/stories/{story_id}/events", response_model=List[Event])
async def get_story_events(story_id: str):
    """Get all events for a story (timeline)"""
    if story_id not in graph_manager.stories:
        raise HTTPException(status_code=404, detail="Story not found")

    events = graph_manager.get_story_events(story_id)
    return events


# --- Graph ---

@app.get("/api/graph/news")
async def get_news_graph(story_id: Optional[str] = None):
    """Get news graph for visualization"""
    if story_id:
        # Get subgraph for specific story
        if story_id not in graph_manager.stories:
            raise HTTPException(status_code=404, detail="Story not found")

        subgraph = graph_manager.get_story_subgraph(story_id)
        nodes = [
            {
                "id": node,
                "type": "news",
                "title": graph_manager.news[node].title if node in graph_manager.news else node,
                "story_id": story_id,
                "domains": graph_manager.news[node].domains if node in graph_manager.news else []
            }
            for node in subgraph.nodes()
        ]
        links = [
            {
                "source": u,
                "target": v,
                "weight": data.get('weight', 1.0),
                "type": "similarity"
            }
            for u, v, data in subgraph.edges(data=True)
        ]
        stories = [{
            "id": story_id,
            "title": graph_manager.stories[story_id].title,
            "news_ids": graph_manager.stories[story_id].news_ids,
            "size": graph_manager.stories[story_id].size
        }] if story_id in graph_manager.stories else []
    else:
        # Get full graph
        nodes = [
            {
                "id": node,
                "type": "news",
                "title": graph_manager.news[node].title if node in graph_manager.news else node,
                "story_id": graph_manager.news_graph.nodes[node].get('story_id'),
                "domains": graph_manager.news_graph.nodes[node].get('domains', []),
                "is_pinned": graph_manager.news_graph.nodes[node].get('is_pinned', False)
            }
            for node in graph_manager.news_graph.nodes()
        ]
        links = [
            {
                "source": u,
                "target": v,
                "weight": data.get('weight', 1.0),
                "type": "similarity"
            }
            for u, v, data in graph_manager.news_graph.edges(data=True)
        ]
        
        # Add stories data
        stories = [
            {
                "id": story_id,
                "title": story_data.title,
                "news_ids": story_data.news_ids,
                "domain": story_data.primary_domain or (story_data.domains[0] if story_data.domains else None),
                "size": story_data.size,
                "relevance": story_data.relevance,
                "cohesion": story_data.cohesion
            }
            for story_id, story_data in graph_manager.stories.items()
        ]

    return {"nodes": nodes, "links": links, "stories": stories}


@app.get("/api/graph/actors")
async def get_actors_graph():
    """Get actors graph for visualization"""
    nodes = [
        {
            "id": node,
            "label": graph_manager.actors[node].canonical_name if node in graph_manager.actors else node,
            "type": graph_manager.actors_graph.nodes[node].get('actor_type') if node in graph_manager.actors_graph.nodes else None
        }
        for node in graph_manager.actors_graph.nodes()
    ]

    edges = [
        {
            "source": u,
            "target": v,
            "relation_type": data.get('relation_type'),
            "weight": data.get('weight', 1.0)
        }
        for u, v, data in graph_manager.actors_graph.edges(data=True)
    ]

    # Get mentions (news <-> actor)
    mentions = []
    for u, v, data in graph_manager.mentions_graph.edges(data=True):
        # Mentions graph uses prefixed IDs e.g. "news_123", "actor_456"
        # We need to extract the raw IDs stored in edge data
        if 'news_id' in data and 'actor_id' in data:
            mentions.append({
                "news_id": data['news_id'],
                "actor_id": data['actor_id']
            })

    return {"nodes": nodes, "edges": edges, "mentions": mentions}


# --- Data Management ---

@app.post("/api/initialize")
async def initialize_system(data: Dict):
    """Initialize system with data (actors and news)"""
    try:
        # Load actors
        if "actors" in data:
            for actor_data in data["actors"]:
                actor = Actor(**actor_data)
                graph_manager.add_actor(actor)

            # Load into NER gazetteer
            ner_service.load_gazetteer(list(graph_manager.actors.values()))

        # Load news
        if "news" in data:
            for news_data in data["news"]:
                news = News(**news_data)

                # Generate embedding if not present
                if not news.embedding:
                    text_to_embed = f"{news.title}. {news.summary}"
                    embedding = embedding_service.encode(text_to_embed)[0]
                    news.embedding = embedding.tolist()

                graph_manager.add_news(news)

        # Compute similarities
        graph_manager.compute_news_similarities(threshold=0.6)

        # Boost by shared actors
        graph_manager.boost_similarity_by_shared_actors(boost_factor=0.15)

        # Load stories if provided, otherwise cluster
        stories = []
        if "stories" in data and data["stories"]:
            for story_data in data["stories"]:
                story = Story(**story_data)
                graph_manager.add_story(story)
                stories.append(story)
        else:
            # Cluster into stories
            stories = clustering_service.cluster_news_to_stories(min_cluster_size=2)

        # Extract events
        for news in graph_manager.news.values():
            events = event_service.extract_events_from_news(news)
            for event in events:
                graph_manager.add_event(event)

        return {
            "success": True,
            "stats": graph_manager.get_graph_stats(),
            "stories_created": len(stories)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/init/status")
async def get_init_status():
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    return actors_extraction_service.get_status()


@app.post("/api/system/init/reset")
async def reset_initialization():
    """Сбросить состояние процесса инициализации (для случаев когда процесс завис)"""
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    from backend.services.actors_extraction_service import InitProgress
    actors_extraction_service.progress = InitProgress()
    return {"message": "Initialization state reset", "status": actors_extraction_service.get_status()}


@app.post("/api/system/init/start")
async def start_initialization(background_tasks: fastapi.BackgroundTasks, low_conf_threshold: float = 0.75):
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    
    if actors_extraction_service.progress.running:
         return {"message": "Already running", "status": actors_extraction_service.get_status()}

    background_tasks.add_task(actors_extraction_service.start_initialization, low_conf_threshold=low_conf_threshold)
    
    # Не устанавливаем running здесь - start_initialization сам устанавливает правильное состояние
    # Небольшая задержка, чтобы background task успел установить состояние
    import asyncio
    await asyncio.sleep(0.1)
    
    return actors_extraction_service.get_status()


# --- Actors extraction triggers ---

@app.post("/api/actors/extract/all")
async def extract_all_actors(background_tasks: fastapi.BackgroundTasks, low_conf_threshold: float = 0.75):
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    
    if actors_extraction_service.progress.running:
         return {"message": "Already running", "status": actors_extraction_service.get_status()}

    actors_extraction_service.clear_all(clear_cache=True)
    
    background_tasks.add_task(actors_extraction_service.extract_all, low_conf_threshold=low_conf_threshold)
    
    actors_extraction_service.progress.running = True
    actors_extraction_service.progress.message = "Starting full extraction..."

    return actors_extraction_service.get_status()


@app.post("/api/actors/extract/story/{story_id}")
async def extract_story_actors(story_id: str, low_conf_threshold: float = 0.75):
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    if story_id not in graph_manager.stories:
        raise HTTPException(status_code=404, detail="Story not found")
    try:
        result = actors_extraction_service.extract_for_story(story_id, low_conf_threshold=low_conf_threshold)
        status = actors_extraction_service.get_status()
        return {"story_id": story_id, "updated": len(result), "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/actors/extract/news/{news_id}")
async def extract_news_actors(news_id: str, low_conf_threshold: float = 0.75):
    if not actors_extraction_service:
        raise HTTPException(status_code=500, detail="ActorsExtractionService not initialized")
    if news_id not in graph_manager.news:
        raise HTTPException(status_code=404, detail="News not found")
    try:
        news = graph_manager.news[news_id]
        _, ids = actors_extraction_service.extract_for_news(news, low_conf_threshold=low_conf_threshold)
        actors_extraction_service.load_gazetteer()
        actors_extraction_service._save_actors()
        actors_extraction_service._save_news()
        status = actors_extraction_service.get_status()
        return {"news_id": news_id, "actors": ids, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    return graph_manager.get_graph_stats()
