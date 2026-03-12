"""
Embedding Service - Unified Embedding + Vector Storage Service
Compatible with llama-stack's /v1/embeddings and /v1/vector_io/* APIs

Combines:
- Text embedding generation (sentence-transformers)
- Vector storage and similarity search (ChromaDB)
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# Suppress ChromaDB telemetry errors (bug in ChromaDB's PostHog integration)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

# Global instances
embedding_model = None
chroma_client = None
collections: Dict[str, chromadb.Collection] = {}

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

# Embedding models
class EmbeddingRequest(BaseModel):
    input: List[str]
    model: str = "sentence-transformers/all-mpnet-base-v2"

class EmbeddingData(BaseModel):
    embedding: List[float]
    index: int

class EmbeddingResponse(BaseModel):
    data: List[EmbeddingData]
    model: str
    usage: dict = {"total_tokens": 0}

# Vector storage models
class VectorDocument(BaseModel):
    document_id: str
    content: str
    metadata: Dict[str, Any]

class InsertRequest(BaseModel):
    vector_store_id: str
    documents: List[VectorDocument]
    embeddings: List[List[float]]

class QueryRequest(BaseModel):
    vector_store_id: str
    query: List[float]
    k: int = 10

class QueryResult(BaseModel):
    document_id: str
    score: float
    content: str
    metadata: Dict[str, Any]

class QueryResponse(BaseModel):
    results: List[QueryResult]

# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    global embedding_model, chroma_client

    # Startup
    logger.info("Starting Embedding Service...")

    # Load embedding model
    logger.info("Loading embedding model: sentence-transformers/all-mpnet-base-v2")
    try:
        embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        raise

    # Initialize ChromaDB
    logger.info("Initializing ChromaDB client")
    try:
        chroma_client = chromadb.PersistentClient(
            path="/app/data/chroma",
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info("ChromaDB client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {e}")
        raise

    logger.info("Embedding Service startup complete")

    # Application is running - yield control to FastAPI
    yield

    # Shutdown
    logger.info("Shutting down Embedding Service...")

    # Cleanup ChromaDB
    if chroma_client is not None:
        try:
            # ChromaDB PersistentClient doesn't require explicit cleanup,
            # but we can clear our reference
            logger.info("Cleaning up ChromaDB client")
            chroma_client = None
        except Exception as e:
            logger.error(f"Error during ChromaDB cleanup: {e}")

    # Clear collections cache
    collections.clear()

    logger.info("Embedding Service shutdown complete")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="Embedding Service",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "embedding_model_loaded": embedding_model is not None,
        "chroma_initialized": chroma_client is not None,
        "model": "sentence-transformers/all-mpnet-base-v2",
        "collections": list(collections.keys())
    }

# ============================================================================
# EMBEDDING ENDPOINTS
# ============================================================================

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """
    Generate embeddings for input texts.
    Compatible with llama-stack's /v1/embeddings API.
    """
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")

    if not request.input or len(request.input) == 0:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    try:
        logger.info(f"Generating embeddings for {len(request.input)} texts")

        # Generate embeddings
        embeddings = embedding_model.encode(request.input, convert_to_numpy=True)

        # Format response to match llama-stack API
        data = [
            EmbeddingData(
                embedding=embedding.tolist(),
                index=idx
            )
            for idx, embedding in enumerate(embeddings)
        ]

        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage={"total_tokens": sum(len(text.split()) for text in request.input)}
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating embeddings: {str(e)}")

# ============================================================================
# VECTOR STORAGE ENDPOINTS
# ============================================================================

@app.post("/v1/vector_io/insert")
async def insert_vectors(request: InsertRequest):
    """
    Insert documents with their embeddings into a vector store.
    Compatible with llama-stack's /v1/vector_io/insert API.
    """
    if chroma_client is None:
        raise HTTPException(status_code=503, detail="ChromaDB not initialized")

    if len(request.documents) != len(request.embeddings):
        raise HTTPException(
            status_code=400,
            detail=f"Number of documents ({len(request.documents)}) must match number of embeddings ({len(request.embeddings)})"
        )

    try:
        logger.info(f"Inserting {len(request.documents)} documents into vector store: {request.vector_store_id}")

        # Get or create collection
        if request.vector_store_id not in collections:
            # Determine embedding dimension from first embedding
            dimension = len(request.embeddings[0]) if request.embeddings else 768

            logger.info(f"Creating new collection: {request.vector_store_id} (dimension: {dimension})")
            collections[request.vector_store_id] = chroma_client.get_or_create_collection(
                name=request.vector_store_id,
                metadata={"dimension": dimension}
            )

        collection = collections[request.vector_store_id]

        # Prepare data for ChromaDB
        ids = [doc.document_id for doc in request.documents]
        documents = [doc.content for doc in request.documents]
        metadatas = [doc.metadata for doc in request.documents]
        embeddings = request.embeddings

        # Insert into ChromaDB (upsert to handle updates)
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        logger.info(f"Successfully inserted {len(ids)} documents")
        return {"status": "success", "inserted": len(ids)}

    except Exception as e:
        logger.error(f"Error inserting vectors: {e}")
        raise HTTPException(status_code=500, detail=f"Error inserting vectors: {str(e)}")

@app.post("/v1/vector_io/query", response_model=QueryResponse)
async def query_vectors(request: QueryRequest):
    """
    Query vector store for similar documents.
    Compatible with llama-stack's /v1/vector_io/query API.
    """
    if chroma_client is None:
        raise HTTPException(status_code=503, detail="ChromaDB not initialized")

    if request.vector_store_id not in collections:
        raise HTTPException(
            status_code=404,
            detail=f"Vector store not found: {request.vector_store_id}"
        )

    try:
        logger.info(f"Querying vector store: {request.vector_store_id} (k={request.k})")

        collection = collections[request.vector_store_id]

        # Query ChromaDB
        results = collection.query(
            query_embeddings=[request.query],
            n_results=request.k,
            include=["documents", "metadatas", "distances"]
        )

        # Convert ChromaDB results to llama-stack format
        # ChromaDB returns distances (lower is better), we convert to scores (higher is better)
        query_results = []
        if results['ids'] and len(results['ids']) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                # Convert distance to similarity score (1 / (1 + distance))
                distance = results['distances'][0][i]
                score = 1.0 / (1.0 + distance)

                query_results.append(QueryResult(
                    document_id=doc_id,
                    score=score,
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i]
                ))

        logger.info(f"Query returned {len(query_results)} results")
        return QueryResponse(results=query_results)

    except Exception as e:
        logger.error(f"Error querying vectors: {e}")
        raise HTTPException(status_code=500, detail=f"Error querying vectors: {str(e)}")

@app.delete("/v1/vector_io/store/{vector_store_id}")
async def delete_vector_store(vector_store_id: str):
    """Delete a vector store"""
    if chroma_client is None:
        raise HTTPException(status_code=503, detail="ChromaDB not initialized")

    try:
        if vector_store_id in collections:
            chroma_client.delete_collection(name=vector_store_id)
            del collections[vector_store_id]
            logger.info(f"Deleted vector store: {vector_store_id}")
            return {"status": "success", "deleted": vector_store_id}
        else:
            raise HTTPException(status_code=404, detail=f"Vector store not found: {vector_store_id}")
    except Exception as e:
        logger.error(f"Error deleting vector store: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting vector store: {str(e)}")

@app.get("/v1/vector_io/stores")
async def list_vector_stores():
    """List all vector stores"""
    if chroma_client is None:
        raise HTTPException(status_code=503, detail="ChromaDB not initialized")

    try:
        all_collections = chroma_client.list_collections()
        return {
            "stores": [
                {
                    "id": col.name,
                    "count": col.count(),
                    "metadata": col.metadata
                }
                for col in all_collections
            ]
        }
    except Exception as e:
        logger.error(f"Error listing vector stores: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing vector stores: {str(e)}")

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

# TODO: see if this is needed, can we remove it? Is there a better way to do this than hardcoding?
@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "Embedding Service",
        "version": "1.0.0",
        "description": "Unified embedding generation and vector storage service",
        "model": "sentence-transformers/all-mpnet-base-v2",
        "vector_backend": "ChromaDB",
        "endpoints": {
            "health": "/health",
            "embeddings": "/v1/embeddings",
            "vector_insert": "/v1/vector_io/insert",
            "vector_query": "/v1/vector_io/query",
            "vector_list": "/v1/vector_io/stores",
            "vector_delete": "/v1/vector_io/store/{id}"
        }
    }
