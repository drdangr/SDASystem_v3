# SDASystem v0.1 - Quick Start

## 🚀 5-Minute Setup

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd SDASystem_v3

# Run the quick start script
./run.sh           # Linux/Mac
# or
run.bat            # Windows
```

The script will:
1. Create virtual environment
2. Install dependencies
3. Generate mock data
4. Start the server

### Access

- **UI**: http://localhost:8000/ui
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## 📊 What You'll See

The UI shows:

### Left Panel - Stories
- 5 story clusters (AI Regulation, Ukraine Conflict, Climate Summit, etc.)
- Metrics: Relevance, Freshness, Cohesion
- Click to view details

### Center Panel - Story Details
- Story summary and key points
- Related news items (13 total)
- Top actors involved
- Domains and categories

### Right Panel - Details
- Click on news → See full article
- Click on actor → See mentions and aliases
- Interactive navigation

### Bottom Panel - Timeline
- **Blue events** = Facts
- **Orange events** = Opinions
- Chronological event flow

## 🎯 Sample Stories

1. **AI Regulation** - EU/US AI safety frameworks, OpenAI response
2. **Ukraine Conflict** - NATO aid, Russia criticism, UN peace calls
3. **Climate Summit** - Global leaders, EU carbon neutrality pledge
4. **Tech Investment** - Microsoft-OpenAI partnership, Google response
5. **US Elections** - Campaign activities, tech companies and security

## 📚 Documentation

- `README.md` - Full concept (Russian)
- `INSTALLATION.md` - Detailed setup guide
- `CLAUDE.md` - AI assistant development guide
- API Docs - http://localhost:8000/docs

## 🔧 Manual Initialization

If you prefer manual setup:

```bash
# 1. Create venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate

# 2. Install deps
pip install -r requirements.txt

# 3. Generate data
python -m backend.utils.mock_data_generator

# 4. Start server
python main.py

# 5. Initialize (in another terminal)
python scripts/init_system.py
```

## 🎨 System Features

### Implemented ✅
- Two-layer graph (News + Actors)
- Story clustering by semantic similarity
- Timeline event extraction (Facts/Opinions)
- Actor extraction and relationships
- 4-panel interactive UI
- REST API with full documentation

### Mock Implementation (for prototype) 📝
- Embeddings (keyword-based)
- NER (pattern matching + gazetteer)
- Event extraction (regex patterns)

### Future 🚧
- Real embeddings (sentence-transformers)
- spaCy NER
- Database persistence
- Graph visualization (Cytoscape.js)

## 🐛 Troubleshooting

**Port 8000 in use?**
→ Edit `main.py`, change port to 8080

**Module not found?**
→ Activate venv: `source venv/bin/activate`

**Empty stories?**
→ Run: `python scripts/init_system.py`

**Connection error?**
→ Ensure server is running: `python main.py`

## 📞 Support

- Check `INSTALLATION.md` for detailed guide
- View API at http://localhost:8000/docs
- Read code comments for implementation details

---

**Version**: 0.1.0 (Prototype)
**Status**: Working proof of concept
**Tech**: Python + FastAPI + NetworkX + Vanilla JS
