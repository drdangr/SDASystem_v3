# CLAUDE.md - AI Assistant Guide for SDASystem

## Project Overview

**SDASystem v3** (Story Driven Analytical System) is a prototype analytical tool that clusters news into stories using a two-layer graph structure.

### Core Concept

The system builds a **two-layer graph**:
1. **News Layer** - News items connected by semantic similarity
2. **Actors Layer** - Entities (people, companies, countries) with typed relationships

News are clustered into **Stories** based on:
- Semantic similarity (embeddings + cosine distance)
- Shared actors (boost factor)
- Graph connectivity (connected components)

Timeline **Events** are extracted from news and categorized as:
- **Facts** (blue) - Verified events from trusted sources
- **Opinions** (orange) - Statements, claims, criticisms

## Repository Structure

```
SDASystem_v3/
├── backend/                 # Backend Python code
│   ├── models/
│   │   └── entities.py     # Pydantic models (News, Actor, Story, Event)
│   ├── services/
│   │   ├── graph_manager.py          # Graph operations (NetworkX)
│   │   ├── clustering_service.py     # Story clustering
│   │   ├── ner_service.py            # Actor extraction (simplified NER)
│   │   ├── event_extraction_service.py  # Timeline events
│   │   └── embedding_service.py      # Text embeddings (mock for prototype)
│   ├── api/
│   │   └── routes.py       # FastAPI REST endpoints
│   └── utils/
│       └── mock_data_generator.py    # Test data generator
├── frontend/               # Frontend UI
│   ├── static/
│   │   ├── css/styles.css  # Dark theme UI styling
│   │   └── js/app.js       # Vanilla JS frontend
│   └── templates/
│       └── index.html      # 4-panel layout
├── scripts/
│   └── init_system.py      # System initialization script
├── data/                   # Data storage (gitignored except mock files)
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── README.md              # Concept document (in Russian)
├── INSTALLATION.md        # Setup and usage guide
└── CLAUDE.md              # This file
```

## Technology Stack

### Backend
- **FastAPI** - REST API framework
- **NetworkX** - Graph operations
- **scikit-learn** - Clustering (DBSCAN)
- **Pydantic** - Data validation
- **sentence-transformers** - Text embeddings (optional, uses mock by default)

### Frontend
- **Vanilla JavaScript** - No frameworks (keeps it simple)
- **HTML5/CSS3** - 4-panel responsive layout
- **Dark theme** - Space/cosmos aesthetic

### Data
- **JSON files** - Prototype storage (can be replaced with DB)
- **In-memory graphs** - NetworkX graphs

## Key Design Patterns

### 1. Service Layer Architecture

Services are stateless and injected into API routes:

```python
# In routes.py
graph_manager = GraphManager()
clustering_service = ClusteringService(graph_manager)
ner_service = NERService()
```

### 2. Two-Layer Graph

```python
# News graph (undirected, weighted by similarity)
graph_manager.news_graph

# Actors graph (directed, typed relationships)
graph_manager.actors_graph

# Cross-layer (bipartite mentions graph)
graph_manager.mentions_graph
```

### 3. Mock Data for Prototyping

The system uses simplified implementations for ML features:
- **Embeddings**: Mock vectors based on keyword features
- **NER**: Pattern matching + gazetteer
- **Event extraction**: Regex patterns

This allows fast prototyping without downloading models.

## Development Workflows

### Adding New News/Actors

1. **Via Mock Generator**: Edit `backend/utils/mock_data_generator.py`
   - Add actors in `_generate_actors()`
   - Create story cluster methods like `_generate_ai_regulation_story()`
   - Run `python -m backend.utils.mock_data_generator`

2. **Via API**: POST to `/api/initialize` with JSON data

### Modifying Clustering Logic

Edit `backend/services/clustering_service.py`:
- `cluster_news_to_stories()` - Main clustering method
- `_cluster_by_graph_components()` - Graph-based approach
- `_cluster_by_embeddings()` - DBSCAN approach

Key parameters:
- `min_cluster_size` - Minimum news per story
- `eps` - DBSCAN epsilon (similarity threshold)
- `threshold` - Edge creation threshold in graph

### Changing UI Layout

Files to modify:
- `frontend/static/css/styles.css` - Layout grid and styling
- `frontend/templates/index.html` - HTML structure
- `frontend/static/js/app.js` - UI logic and API calls

The layout uses CSS Grid with 4 areas:
```css
grid-template-areas:
    "header header header"
    "sidebar main detail"
    "timeline timeline timeline";
```

## Common Tasks for AI Assistants

### Task: Add New Actor Type

1. Update enum in `backend/models/entities.py`:
```python
class ActorType(str, Enum):
    # ... existing types
    NEW_TYPE = "new_type"
```

2. Update NER inference in `backend/services/ner_service.py`:
```python
def _infer_actor_type(self, entity: str, context: str) -> ActorType:
    # Add detection logic
    if "keyword" in entity_lower:
        return ActorType.NEW_TYPE
```

### Task: Add New API Endpoint

Add to `backend/api/routes.py`:
```python
@app.get("/api/my-endpoint")
async def my_endpoint():
    # Implementation
    return {"result": "data"}
```

### Task: Modify Story Metrics

Edit `backend/services/clustering_service.py`:
```python
def _calculate_story_metrics(self, story: Story) -> None:
    # Modify relevance, cohesion, freshness calculations
    story.relevance = ...  # Your formula
```

### Task: Add New UI Panel

1. Update CSS grid in `styles.css`
2. Add HTML section in `index.html`
3. Add JavaScript rendering in `app.js`

## Testing

### Manual Testing

1. Start server: `python main.py`
2. Generate data: `python scripts/init_system.py`
3. Open UI: http://localhost:8000/ui
4. Use API docs: http://localhost:8000/docs

### Adding Test Data

Create custom scenarios in `mock_data_generator.py`:
```python
def _generate_my_test_scenario(self):
    self._create_news(
        title="Test News",
        summary="Test summary",
        full_text="Full text...",
        actors=["Actor1"],
        domains=["TestDomain"],
        days_ago=0
    )
```

## Important Conventions

### Code Style
- **Python**: PEP 8, type hints where helpful
- **JavaScript**: camelCase for functions, PascalCase for classes
- **CSS**: kebab-case for classes

### Naming
- **IDs**: `{type}_{uuid}` (e.g., `story_a1b2c3d4`)
- **Files**: snake_case for Python, camelCase for JS
- **API routes**: `/api/{resource}/{id}/{action}`

### Error Handling
- API returns HTTP status codes (404, 400, 500)
- Frontend shows user-friendly messages
- Backend logs errors for debugging

### Data Flow
```
User Action → Frontend (app.js)
           → API Request
           → FastAPI Route (routes.py)
           → Service Layer (services/)
           → Graph Manager (graph_manager.py)
           → Response
           → Frontend Render
```

## Performance Considerations

### Current Limitations (Prototype)
- In-memory storage (data lost on restart)
- No pagination on large datasets
- Mock embeddings (not semantically accurate)
- Simple NER (pattern-based, not ML)

### Future Optimizations
- Use real sentence-transformers for embeddings
- Implement database (PostgreSQL + pgvector)
- Add caching (Redis)
- Use spaCy for proper NER
- Implement graph database (Neo4j) for complex queries

## Debugging Tips

### Backend Issues

Check logs in terminal where `python main.py` runs.

Common issues:
- **Import errors**: Ensure venv is activated
- **Port in use**: Change port in `main.py`
- **Empty data**: Run `python scripts/init_system.py`

### Frontend Issues

Open browser DevTools (F12):
- **Console**: Check for JavaScript errors
- **Network**: Verify API requests
- **Elements**: Inspect DOM structure

### Graph Issues

Use NetworkX debugging:
```python
# In graph_manager.py or clustering_service.py
print(f"Graph nodes: {len(self.graph.nodes())}")
print(f"Graph edges: {len(self.graph.edges())}")
print(f"Components: {nx.number_connected_components(self.graph)}")
```

## Integration Points

### Adding Real NER

Replace in `ner_service.py`:
```python
import spacy
nlp = spacy.load("en_core_web_sm")

def extract_actors_from_text(self, text: str):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ["PERSON", "ORG", "GPE"]:
            # Process entity
```

### Adding Real Embeddings

Replace in `embedding_service.py`:
```python
from sentence_transformers import SentenceTransformer

def __init__(self):
    self.model = SentenceTransformer('all-MiniLM-L6-v2')
    self.use_mock = False
```

### Adding Database

Create new `database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Setup SQLAlchemy
# Convert Pydantic models to SQLAlchemy models
# Update services to use DB instead of in-memory dicts
```

## When Modifying This System

### DO:
- ✅ Keep services stateless and testable
- ✅ Update both backend and frontend when changing data models
- ✅ Maintain the two-layer graph structure
- ✅ Add comments for complex algorithms
- ✅ Test with mock data before using real data

### DON'T:
- ❌ Mix UI logic with API logic
- ❌ Store state in service classes (use graph_manager)
- ❌ Modify core graph structure without understanding impact
- ❌ Remove existing API endpoints (breaks frontend)
- ❌ Change entity IDs format (breaks relationships)

## Questions to Ask When Extending

1. **Adding Features**: Does it fit the two-layer graph model?
2. **Changing APIs**: Will it break the frontend?
3. **Modifying Clustering**: How will it affect existing stories?
4. **Adding Data**: Can mock_data_generator create test cases?
5. **Performance**: Will it scale to 1000+ news items?

## Useful Commands

```bash
# Start development server (auto-reload)
python main.py

# Generate mock data only
python -m backend.utils.mock_data_generator

# Initialize system with data
python scripts/init_system.py

# Install new dependency
pip install <package>
pip freeze > requirements.txt

# Check graph statistics
curl http://localhost:8000/api/stats

# Get all stories
curl http://localhost:8000/api/stories

# Health check
curl http://localhost:8000/api/health
```

## Architecture Diagrams

### Data Flow
```
Mock Data → JSON → API Initialize → Services → Graph Manager
                                        ↓
                                   Clustering
                                        ↓
                                    Stories
                                        ↓
                                   UI Display
```

### Graph Structure
```
News Layer:          [N1] -- 0.8 -- [N2]
                       |              |
                      0.6           0.7
                       |              |
                     [N3] -- 0.9 -- [N4]

Actor Layer:        [A1] --member_of--> [A2]
                      |
                  criticized
                      ↓
                    [A3]

Cross-Layer:        [N1] --mentions--> [A1]
                    [N2] --mentions--> [A1, A3]
```

## Future Roadmap (for AI context)

### Phase 1 (Current - Prototype)
- ✅ Basic two-layer graph
- ✅ Mock data and embeddings
- ✅ Simple clustering
- ✅ 4-panel UI

### Phase 2 (Next Steps)
- Real embeddings (sentence-transformers)
- spaCy NER
- Database persistence
- Graph visualization (Cytoscape.js)

### Phase 3 (Advanced)
- Real-time news ingestion
- Advanced clustering (HDBSCAN)
- Actor relationship learning
- Editorial workflow tools

---

**Last Updated**: 2025-11-20
**Version**: 0.1.0
**Status**: Prototype - Working proof of concept

For questions or clarifications, refer to:
- `README.md` - Concept and requirements (Russian)
- `INSTALLATION.md` - Setup and usage
- Source code comments
