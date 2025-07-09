# TESTAIOWNIK 🤖📚

AI-powered learning assistant that automatically generates test questions from educational materials using LangGraph and Azure OpenAI.

## 🎯 Project Overview

**Problem:** Students are overwhelmed by massive amounts of study materials and lack efficient ways to create personalized test questions for exam preparation.

**Solution:** An intelligent system that processes educational documents (PDF/PPTX/TXT) and generates customized test questions with user feedback loops for continuous improvement.

## 🚧 Progress overview

**Sprint 1/4 - Infrastructure & Basic Agent** ✅ Completed

- ✅ Azure infrastructure setup with Bicep templates
- ✅ Basic LangGraph agent with document analysis workflow
- ✅ Azure OpenAI GPT-4 integrationa
- ✅ Topic extraction with user feedback loops
- ✅ MockRetriever for document processing
- ✅ Vector store integration 


**Sprint 2/4 - RAG System & Full Agent** ✅ Completed

- ✅ Complete LangGraph agent workflow (Topic Selection + Quiz)
- ✅ Azure OpenAI GPT-4 integration with structured output
- ✅ Qdrant vector store integration for RAG
- ✅ Document processing (PDF/PPTX/TXT/DOCX)
- ✅ Comprehensive test suite


**Sprint 3**: FastAPI backend + Streamlit frontend ✅ Completed

**Sprint 4**: Testing & production polish & Publishing on Azure ✅ Completed

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
   cd src/testaiownik
   uv sync
   ```

2. **Environment setup**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your Azure credentials:
   # AZURE_OPENAI_ENDPOINT=your-endpoint
   # AZURE_OPENAI_API_KEY=your-api-key
   # CHAT_MODEL_NAME=your-deployment-name
   # CHAT_MODEL_VERSION=your-api-version
   ```



3. **Run locally-  docker (recommended)**
   Be in root directory

   ```bash
   docker compose build
   docker compose up -d
   ```

   Streamlit should be open on localhost:8501 now :)

   



3*. **Run locally - no docker**

   Qdrant: 


   Linux
   ```bash
   docker pull qdrant/qdrant

   docker run -p 6333:6333 -p 6334:6334 \
    -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
    qdrant/qdrant
   ```
   Windows
   
   ```Powershell
   docker pull qdrant/qdrant
   docker run -p 6333:6333 -p 6334:6334 `
     -v "${PWD}/qdrant_storage:/qdrant/storage:z" `
     qdrant/qdrant
   ```



   Backend:

   ```bash
   cd src/Testaiownik
   uv run -m Backend.run
   ```

   Frontend:

   ```bash
   cd src/Testaiownik/Frontend
   streamlit run main.py
   ```

   Make sure Qdrant is running!






   

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


### Code Quality

```bash
# Format code
uv run black src/

# Lint code
uv run ruff check src/

# Type checking
uv run mypy src/
```

### Testing

```bash
# Run tests 
uv run pytest tests/

```


## 🏗️ Architecture

**Current Stack:**
- **Agent Orchestration**: LangGraph
- **LLM**: Azure OpenAI GPT-4
- **Document Processing**: Azure Embedding Model
- **Vector Store**: Qdrant
- 

**Architecture:**
```
               +------------------------------+
               | PostgreSQL (serialization)   |
               +------------------------------+
                          |
                          |
                          v
+----------------+     +----------------+     +----------------+
|   Streamlit    | <-- |  FastAPI API   | --> |     Qdrant     |
|   Frontend     |     |    Backend     |     |  (Vector DB)   |
+----------------+     +----------------+     +----------------+
                          |
                          v
              +-----------------------------+
              |     RAG & Quiz Agent        |
              +-----------------------------+

                
           
```

## 🧪 Roadmap

### Sprint 1 - Basic Agent (Week 1)

- ✅ **Document Processing**: MockRetriever with sample educational content
- ✅ **LangGraph Agent**: Complete workflow with interrupts and state management
- ✅ **Azure Integration**: GPT-4 calls with structured output
- ✅ **User Feedback**: Interactive CLI for topic refinement
- ✅ **Logging**: Comprehensive logging setup
- ✅ **Infrastructure**: Deployable Azure resources

### Sprint 2 - Full Agent (Week 2)
- ✅ Question generation from topics
- ✅ Complex questionaire (quiz) generation



### Sprint 3 - Web Interface (Week 3)
-✅ FastAPI backend with endpoints
-✅ Streamlit frontend for document upload
-✅ Progress tracking with PostgreSQL
-✅ User session management

### Sprint 4 - Production Ready (Week 4)
-✅ Comprehensive testing
-✅ Performance optimization
-✅ Production deployment on Azure


### Development Setup

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Install dependencies: `uv sync --group dev`
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push branch: `git push origin feature/amazing-feature`
8. Open Pull Request

## 📚 Documentation

- **Agents Architecture**: Check `src/Testaiownik/Agent/` for current Agents implementation

- 
## 🔧 Troubleshooting

**Common Issues:**

1. **Azure Connection Failed**
   ```bash
   # Check .env file has correct credentials
   # Verify Azure OpenAI deployment is active
   ```

## 📄 License

Machalski & Mleczak  Corp

## 🙋‍♂️ Support

For questions about the current implementation, check the code comments or create an issue.

---

**Built with:** LangGraph • Azure OpenAI • Python • UV • Streamlit • Azure Container Apps • FastApi 
