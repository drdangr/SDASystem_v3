# SDASystem v0.1 - Installation & Quick Start Guide

## Overview

Story Driven Analytical System (SDASystem) is a prototype for analyzing news and forming story clusters based on a two-layer graph structure:
- **Layer 1: News Graph** - semantic clustering of news items
- **Layer 2: Actors Graph** - entities (people, companies, countries) and their relationships

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- PostgreSQL 12 or higher (with pgvector extension)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### PostgreSQL Setup

SDASystem v3 requires PostgreSQL with pgvector extension for vector similarity search.

**Quick setup:**

1. Install PostgreSQL (see [docs/database_setup.md](docs/database_setup.md) for detailed instructions)
2. Install pgvector extension
3. Create database:
   ```bash
   psql -U postgres
   CREATE DATABASE sdas_db;
   CREATE EXTENSION vector;
   ```
4. Apply schema:
   ```bash
   psql -U postgres -d sdas_db -f backend/db/schema.sql
   ```
5. Set environment variables (create `.env` file):
   ```env
   POSTGRES_DB=sdas_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=yourpassword
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```

For detailed database setup instructions, see [docs/database_setup.md](docs/database_setup.md).

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd SDASystem_v3
```

### 2. Create virtual environment

```bash
python -m venv venv

# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### Step 1: Generate Mock Data

Generate test data (news, actors, relationships):

```bash
python -m backend.utils.mock_data_generator
```

This creates `data/mock_data.json` with:
- ~19 actors (politicians, companies, countries)
- ~17 news items across 5 story clusters
- Multiple domains (Politics, Technology, Economics, etc.)

### Step 2: Start the API Server

```bash
python main.py
```

The server will start on `http://localhost:8000`

You should see:
```
============================================================
SDASystem v0.1 - Story Driven Analytical System
============================================================
Starting server...
API Documentation: http://localhost:8000/docs
UI Interface: http://localhost:8000/ui
============================================================
```

### Step 3: Initialize the System

In a new terminal (keep the server running):

```bash
# Activate venv first
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run initialization script
python scripts/init_system.py
```

This will:
- Load actors and news into the system
- Generate embeddings for semantic similarity
- Compute news relationships
- Cluster news into stories
- Extract timeline events

### Step 4: Access the UI

Open your browser and navigate to:

**UI Interface:** http://localhost:8000/ui

**API Documentation:** http://localhost:8000/docs

## System Architecture

### Backend Components

```
backend/
├── models/
│   └── entities.py          # Data models (News, Actor, Story, Event)
├── services/
│   ├── graph_manager.py     # Two-layer graph management
│   ├── clustering_service.py # Story clustering (HDBSCAN/kNN)
│   ├── ner_service.py       # Named Entity Recognition
│   ├── event_extraction_service.py  # Timeline events
│   └── embedding_service.py # Text embeddings
├── api/
│   └── routes.py            # FastAPI endpoints
└── utils/
    └── mock_data_generator.py  # Test data generator
```

### Frontend Components

```
frontend/
├── static/
│   ├── css/
│   │   └── styles.css       # UI styling
│   └── js/
│       └── app.js           # Frontend logic
└── templates/
    └── index.html           # Main UI template
```

### UI Layout

The interface consists of 4 panels:

1. **Left Panel (Sidebar)** - Stories list with metrics
2. **Main Panel (Center)** - Story details, actors, news
3. **Right Panel (Detail)** - News/Actor detail view
4. **Bottom Panel (Timeline)** - Timeline events (facts & opinions)

## API Endpoints

### Stories
- `GET /api/stories` - List all stories
- `GET /api/stories/{story_id}` - Get story details
- `POST /api/stories/{story_id}/merge` - Merge stories
- `POST /api/stories/{story_id}/split` - Split story

### News
- `GET /api/news` - List news (with filters)
- `GET /api/news/{news_id}` - Get news details
- `GET /api/news/{news_id}/related` - Get related news

### Actors
- `GET /api/actors` - List actors
- `GET /api/actors/{actor_id}` - Get actor details
- `GET /api/actors/{actor_id}/mentions` - Get actor mentions
- `GET /api/actors/{actor_id}/relations` - Get actor relationships

### Events
- `GET /api/events` - List timeline events
- `GET /api/stories/{story_id}/events` - Get story timeline

### Graph
- `GET /api/graph/news` - Get news graph (for visualization)
- `GET /api/graph/actors` - Get actors graph

### System
- `GET /api/health` - Health check
- `GET /api/stats` - System statistics
- `POST /api/initialize` - Initialize with data

## Testing the System

### 1. Browse Stories

The main UI shows clustered stories sorted by relevance. Click on any story to view:
- Story summary and key points
- Related news items
- Top actors involved
- Timeline of events

### 2. Explore Actors

Click on any actor chip to see:
- Actor details and aliases
- Recent mentions in news
- Relationships with other actors

### 3. View Timeline

The timeline shows events extracted from news:
- **Blue events** = Facts (verified information)
- **Orange events** = Opinions (statements, claims)

### 4. API Testing

Access interactive API documentation at:
http://localhost:8000/docs

Try these endpoints:
- `GET /api/stories` - View all stories
- `GET /api/stats` - See system statistics
- `GET /api/graph/news` - Get graph data

## Configuration

### Embedding Service

By default, the system uses mock embeddings for fast prototyping.

To use real embeddings (requires model download):

```python
# In backend/api/routes.py, change:
embedding_service = EmbeddingService(use_mock=False)
```

### Clustering Parameters

Adjust clustering in `backend/services/clustering_service.py`:

```python
# In cluster_news_to_stories():
min_cluster_size=2,  # Minimum news items per story
eps=0.3,             # DBSCAN epsilon (similarity threshold)
```

### Similarity Threshold

Adjust in `backend/api/routes.py`:

```python
# In initialize_system():
graph_manager.compute_news_similarities(threshold=0.4)  # 0.0 to 1.0
```

## Troubleshooting

### Port Already in Use

If port 8000 is busy, change in `main.py`:

```python
uvicorn.run("main:app", host="0.0.0.0", port=8080, ...)
```

### Module Import Errors

Make sure you're in the project root and venv is activated:

```bash
cd SDASystem_v3
source venv/bin/activate  # or venv\Scripts\activate
python main.py
```

### Empty Stories List

Run the initialization script:

```bash
python scripts/init_system.py
```

### API Connection Error in UI

Check that:
1. API server is running (`python main.py`)
2. No CORS errors in browser console
3. API is accessible at http://localhost:8000/api/health

## Development

### Adding New Mock Data

Edit `backend/utils/mock_data_generator.py` and add new story clusters:

```python
def _generate_my_story(self):
    """Generate news cluster about my topic"""
    domain = ["MyDomain", "Subdomain"]

    self._create_news(
        title="My News Title",
        summary="Summary text",
        full_text="Full content...",
        actors=["Actor1", "Actor2"],
        domains=domain,
        days_ago=0
    )
```

### Running Tests

```bash
pytest tests/
```

## Next Steps

1. Explore the UI and browse generated stories
2. Check API documentation at /docs
3. Modify mock data generator to create custom test scenarios
4. Experiment with clustering parameters
5. Add custom actors and news through the API

## Support

For issues and questions:
- Check the README.md for concept overview
- View API docs at /docs
- Review code comments in source files

---

**Version:** 0.1.0 (Prototype)
**License:** MIT
**Author:** SDASystem Team
