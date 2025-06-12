# TESTAIOWNIK 🤖📚

AI-powered learning assistant that automatically generates test questions from educational materials using LangGraph and Azure OpenAI.

## 🎯 Project Overview

**Problem:** Students are overwhelmed by massive amounts of study materials and lack efficient ways to create personalized test questions for exam preparation.

**Solution:** An intelligent system that processes educational documents (PDF/PPTX/TXT) and generates customized test questions with user feedback loops for continuous improvement.

## 🚧 Current Status

**Sprint 1/4 - Infrastructure & Basic Agent** ✅ In Progress

- ✅ Azure infrastructure setup with Bicep templates
- ✅ Basic LangGraph agent with document analysis workflow
- ✅ Azure OpenAI GPT-4 integration
- ✅ Topic extraction with user feedback loops
- ✅ MockRetriever for document processing
- 🔄 Vector store integration (planned)

**Next Sprints:**
- **Sprint 2**: RAG system with vector store, Full Agent functionalities 
- **Sprint 3**: FastAPI backend + Streamlit frontend  
- **Sprint 4**: Testing & production polish

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (Developed on 3.11.12)
- **[uv](https://docs.astral.sh/uv/)** - Fast Python project manager
- **Azure subscription** with OpenAI access
- **PowerShell** (for infrastructure deployment)

### Installation

1. **Clone and install dependencies**
   ```bash
   git clone <repository-url>
   cd testaiownik
   uv sync
   ```

2. **Environment setup**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your Azure credentials:
   # AZURE_OPENAI_ENDPOINT=your-endpoint
   # AZURE_OPENAI_API_KEY=your-api-key
   # CHAT_MODEL_NAME_DEV=your-deployment-name
   # CHAT_MODEL_VERSION_DEV=your-api-version
   ```

3. **Test the current main (for tests)**
   ```bash
   uv run python src/Testaiownik/main.py
   ```

### Infrastructure Deployment (Optional)

Deploy and Clean up Azure resources using Bicep:

```powershell
cd IaaC
./deploy.ps1 -Environment dev
./cleanup.ps1 -Environment dev
```

**Resources created:**
- Azure OpenAI Hub & Project
- PostgreSQL Flexible Server
- Storage Account
- Application Insights
- Container App Environment

## 📁 Project Structure

```
testaiownik/
├── src/Testaiownik/
│   ├── Agent/              # LangGraph agent implementation
│   │   ├── graph.py        # Agent workflow definition
│   │   ├── nodes.py        # Individual workflow nodes
│   │   ├── models.py       # Pydantic models
│   │   ├── state.py        # Agent state management
│   │   └── runner.py       # CLI runner for testing
│   ├── RAG/                # Document retrieval system
│   │   └── Retrieval/      # Retriever implementations
│   ├── AzureModels/        # Azure OpenAI integration
│   ├── config/             # Configuration management
│   └── utils/              # Shared utilities (logging)
├── IaaC/                   # Infrastructure as Code
│   ├── main.bicep          # Main Bicep template
│   ├── modules/            # Bicep modules
│   ├── parameters/         # Environment parameters
│   └── deploy.ps1          # Deployment script
├── tests/                  # Test files
└── pyproject.toml          # UV project configuration
└── main.py                 # Main file to run the current state of the project
```

## 🛠️ Development Workflow

### Using UV (Recommended)

```bash
# Install dependencies
uv sync

# Install dev dependencies
uv sync --group dev

# Add new dependency
uv add package-name

# Add dev dependency
uv add --group dev package-name

# Run Python scripts
uv run python src/Testaiownik/main.py

# Create virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### Code Quality

```bash
# Format code
uv run black src/

# Lint code
uv run ruff check src/

# Type checking (if added)
uv run mypy src/
```

### Testing

```bash
# Run tests (when implemented)
uv run pytest tests/

# Run specific test
uv run python tests/main.py
```

## 🔄 Current Agent Workflow

The LangGraph agent currently implements this workflow:

1. **Document Analysis** - Process chunks of educational material
2. **Topic Extraction** - Extract relevant topics using GPT-4
3. **User Feedback** - Present topics to user for approval/modification
4. **Topic Refinement** - Adjust topics based on user input
5. **Confirmation** - Finalize approved topics

**Example interaction:**
```
Found topics:
0: Algorytmy sortowania i ich złożoność
1: Struktury danych liniowe i nieliniowe
2: Analiza złożoności obliczeniowej

Provide feedback on given topics please.
Your feedback: > Remove topic 1, add more about graph algorithms
```

## 🏗️ Architecture

**Current Stack:**
- **Agent Orchestration**: LangGraph
- **LLM**: Azure OpenAI GPT-4
- **Document Processing**: MockRetriever (temporary)
- **Logging**: Custom logger with Azure Application Insights
- **Infrastructure**: Azure (Bicep templates)

**Planned Architecture:**
```
Documents → Vector Store → RAG Agent → FastAPI → Streamlit
                ↓
            Azure OpenAI GPT-4
                ↓
            PostgreSQL (progress tracking)
```

## 🧪 What's Working Now

- ✅ **Document Processing**: MockRetriever with sample educational content
- ✅ **LangGraph Agent**: Complete workflow with interrupts and state management
- ✅ **Azure Integration**: GPT-4 calls with structured output
- ✅ **User Feedback**: Interactive CLI for topic refinement
- ✅ **Logging**: Comprehensive logging setup
- ✅ **Infrastructure**: Deployable Azure resources

## 📋 Roadmap

### Sprint 2 - Full Agent (Week 2)
- [ ] Question generation from topics
- [ ] Complex questionaire (quiz) generation

### Sprint 3 - Web Interface (Week 3)
- [ ] FastAPI backend with endpoints
- [ ] Streamlit frontend for document upload
- [ ] Progress tracking with PostgreSQL
- [ ] User session management

### Sprint 4 - Production Ready (Week 4)
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] User feedback system
- [ ] Production deployment

## 🤝 Contributing

This is an active development project in Sprint 1. Key areas needing attention:

1. **Vector Store Selection** - Need to replace Azure AI Search
2. **RAG Implementation** - Complete the RAGRetriever class
3. **Question Generation** - Add question/answer generation nodes
4. **Testing** - Expand test coverage

### Development Setup

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Install dependencies: `uv sync --group dev`
4. Make changes and test: `uv run python src/Testaiownik/main.py`
5. Format code: `uv run black src/`
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push branch: `git push origin feature/amazing-feature`
8. Open Pull Request

## 📚 Documentation

- **Agent Architecture**: Check `src/Testaiownik/Agent/` for current implementation
- **Infrastructure**: Review `IaaC/` for Azure deployment details



## 🔧 Troubleshooting

**Common Issues:**

1. **Azure Connection Failed**
   ```bash
   # Check .env file has correct credentials
   # Verify Azure OpenAI deployment is active
   ```


3. **Infrastructure Deployment**
   ```powershell
   # Check you're logged into Azure
   Connect-AzAccount
   # Verify subscription access
   Get-AzSubscription
   ```

## 📄 License

Machalski & Mleczak Corp

## 🙋‍♂️ Support

For questions about the current implementation, check the code comments or create an issue.

---

**Built with:** LangGraph • Azure OpenAI • Python • UV • Bicep
