"""
RAG (Retrieval-Augmented Generation) System for Receipt Database
Provides semantic search, context retrieval, and LLM-powered question answering
"""

import psycopg2
import numpy as np
import json
import requests
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import logging
from pgvector.psycopg2 import register_vector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================
# CONFIG
# =====================================================

DB_CONFIG = {
    "dbname": "receipt_db",
    "user": "postgres",
    "password": "user",
    "host": "localhost",
    "port": "5432"
}

OLLAMA_URL = "http://localhost:11434/api/generate"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "gemma3"

# =====================================================
# DATABASE INITIALIZATION
# =====================================================

class RAGDatabase:
    """Handle all database operations for RAG system"""
    
    def __init__(self, db_config: Dict = None):
        self.db_config = db_config or DB_CONFIG
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            register_vector(self.conn)
            logger.info("Connected to PostgreSQL database")
            return self.conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def initialize_embeddings_table(self):
        """Create embeddings table if not exists"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE EXTENSION IF NOT EXISTS vector;
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS receipt_embeddings (
                        id SERIAL PRIMARY KEY,
                        receipt_id VARCHAR(255) UNIQUE NOT NULL,
                        embedding vector(384),
                        content TEXT NOT NULL,
                        embedding_type VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (receipt_id) REFERENCES receipts(receipt_id) ON DELETE CASCADE
                    );
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_receipt_embeddings 
                    ON receipt_embeddings USING ivfflat (embedding vector_cosine_ops);
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS qa_history (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        context_receipts TEXT[],
                        model_used VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                self.conn.commit()
                logger.info("Embeddings tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing embeddings table: {e}")
            self.conn.rollback()
            raise
    
    def store_embedding(self, receipt_id: str, embedding: List[float], 
                       content: str, embedding_type: str = "receipt_summary"):
        """Store embedding in database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO receipt_embeddings (receipt_id, embedding, content, embedding_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (receipt_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        content = EXCLUDED.content,
                        created_at = CURRENT_TIMESTAMP;
                """, (receipt_id, embedding, content, embedding_type))
                
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            self.conn.rollback()
            raise
    
    def search_similar_receipts(self, query_embedding: List[float], 
                               limit: int = 5) -> List[Dict]:
        """Search for similar receipts using vector similarity"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        r.receipt_id,
                        r.vendor_name,
                        r.date,
                        r.total_amount,
                        re.content,
                        1 - (re.embedding <=> %s::vector) as similarity_score
                    FROM receipt_embeddings re
                    JOIN receipts r ON re.receipt_id = r.receipt_id
                    ORDER BY re.embedding <=> %s::vector
                    LIMIT %s;
                """, (query_embedding, query_embedding, limit))
                
                columns = ['receipt_id', 'vendor_name', 'date', 'total_amount', 
                          'content', 'similarity_score']
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
                return results
        except Exception as e:
            logger.error(f"Error searching similar receipts: {e}")
            return []
    
    def get_receipt_details(self, receipt_id: str) -> Dict:
        """Get complete receipt details with items"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM receipts WHERE receipt_id = %s;
                """, (receipt_id,))
                
                receipt_data = cur.fetchone()
                if not receipt_data:
                    return None
                
                cur.execute("""
                    SELECT name, quantity, price FROM items WHERE receipt_id = %s;
                """, (receipt_id,))
                
                items = cur.fetchall()
                
                receipt_cols = ['receipt_id', 'vendor_name', 'vendor_address', 
                              'vendor_phone', 'vendor_gst', 'date', 'time', 
                              'currency', 'subtotal_amount', 'tax_amount', 
                              'discount_amount', 'total_amount', 'payment_method', 
                              'card_last4', 'transaction_id', 'confidence_score', 'source']
                
                receipt_dict = dict(zip(receipt_cols, receipt_data))
                receipt_dict['items'] = [
                    {'name': item[0], 'quantity': item[1], 'price': item[2]}
                    for item in items
                ]
                
                return receipt_dict
        except Exception as e:
            logger.error(f"Error retrieving receipt details: {e}")
            return None
    
    def save_qa_history(self, question: str, answer: str, 
                       context_receipts: List[str], model_used: str):
        """Save Q&A interaction to history"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO qa_history (question, answer, context_receipts, model_used)
                    VALUES (%s, %s, %s, %s);
                """, (question, answer, context_receipts, model_used))
                
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving QA history: {e}")
            self.conn.rollback()

# =====================================================
# EMBEDDING GENERATION
# =====================================================

class EmbeddingGenerator:
    """Generate embeddings using Ollama"""
    
    def __init__(self, model: str = EMBEDDING_MODEL, url: str = OLLAMA_URL):
        self.model = model
        self.url = url.replace("/api/generate", "")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using Ollama"""
        try:
            response = requests.post(
                f"{self.url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['embeddings'][0] if data.get('embeddings') else None
            else:
                logger.error(f"Embedding API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def batch_generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings

# =====================================================
# CONTEXT RETRIEVER
# =====================================================

class ContextRetriever:
    """Retrieve relevant context from database for queries"""
    
    def __init__(self, db: RAGDatabase, embeddings: EmbeddingGenerator):
        self.db = db
        self.embeddings = embeddings
    
    def retrieve_context(self, query: str, top_k: int = 5) -> Tuple[List[Dict], List[str]]:
        """
        Retrieve relevant receipts based on query
        Returns: (retrieved_receipts, receipt_ids)
        """
        try:
            # Generate embedding for query
            query_embedding = self.embeddings.generate_embedding(query)
            
            if not query_embedding:
                logger.warning(f"Failed to generate embedding for query: {query}")
                return [], []
            
            # Search similar receipts
            similar_receipts = self.db.search_similar_receipts(query_embedding, top_k)
            
            # Enrich with full details
            enriched_receipts = []
            receipt_ids = []
            
            for receipt in similar_receipts:
                receipt_id = receipt['receipt_id']
                receipt_ids.append(receipt_id)
                
                full_details = self.db.get_receipt_details(receipt_id)
                if full_details:
                    enriched_receipts.append({
                        **receipt,
                        **full_details
                    })
            
            return enriched_receipts, receipt_ids
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return [], []
    
    def format_context(self, receipts: List[Dict]) -> str:
        """Format retrieved receipts into readable context"""
        if not receipts:
            return "No relevant receipts found."
        
        context_text = "## Retrieved Receipt Information:\n\n"
        
        for i, receipt in enumerate(receipts, 1):
            context_text += f"### Receipt {i}\n"
            context_text += f"- Vendor: {receipt.get('vendor_name', 'N/A')}\n"
            context_text += f"- Date: {receipt.get('date', 'N/A')}\n"
            context_text += f"- Amount: {receipt.get('total_amount', 'N/A')} {receipt.get('currency', 'USD')}\n"
            
            if receipt.get('items'):
                context_text += "- Items:\n"
                for item in receipt['items']:
                    context_text += f"  - {item['name']}: {item['quantity']} x {item['price']}\n"
            
            context_text += "\n"
        
        return context_text

# =====================================================
# RAG PIPELINE
# =====================================================

class RAGPipeline:
    """Complete RAG pipeline for Q&A system"""
    
    def __init__(self, db_config: Dict = None):
        self.db = RAGDatabase(db_config)
        self.db.connect()
        self.embeddings = EmbeddingGenerator()
        self.retriever = ContextRetriever(self.db, self.embeddings)
    
    def initialize(self):
        """Initialize RAG system"""
        self.db.initialize_embeddings_table()
        logger.info("RAG system initialized successfully")
    
    def index_receipts(self):
        """Generate and store embeddings for all receipts"""
        try:
            logger.info("Starting receipt indexing...")
            
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT r.receipt_id, r.vendor_name, r.date, r.total_amount,
                           string_agg(i.name || ' (qty: ' || i.quantity || ')', ', ') as items
                    FROM receipts r
                    LEFT JOIN items i ON r.receipt_id = i.receipt_id
                    GROUP BY r.receipt_id, r.vendor_name, r.date, r.total_amount;
                """)
                
                receipts = cur.fetchall()
                total = len(receipts)
                
                for idx, (receipt_id, vendor, date, amount, items) in enumerate(receipts, 1):
                    # Create summary text
                    summary = f"Receipt from {vendor} on {date} for amount {amount}. Items: {items}"
                    
                    # Generate embedding
                    embedding = self.embeddings.generate_embedding(summary)
                    
                    if embedding:
                        self.db.store_embedding(receipt_id, embedding, summary)
                        logger.info(f"Indexed receipt {idx}/{total}: {receipt_id}")
                    else:
                        logger.warning(f"Failed to index receipt: {receipt_id}")
            
            logger.info(f"Indexing completed: {total} receipts processed")
        except Exception as e:
            logger.error(f"Error indexing receipts: {e}")
    
    def answer_question(self, question: str) -> Dict:
        """
        Answer user question using RAG approach
        Returns: {'question': str, 'answer': str, 'context': List[Dict], 'metadata': Dict}
        """
        try:
            logger.info(f"Processing question: {question}")
            
            # Step 1: Retrieve relevant context
            retrieved_receipts, receipt_ids = self.retriever.retrieve_context(question, top_k=5)
            formatted_context = self.retriever.format_context(retrieved_receipts)
            
            # Step 2: Build prompt
            system_prompt = """You are a helpful assistant answering questions about receipt data.
Based on the provided receipt information, answer the user's question accurately and concisely.
If the information is not available in the receipts, say so clearly."""
            
            user_prompt = f"""User Question: {question}

{formatted_context}

Please answer the question based on the provided receipt information."""
            
            # Step 3: Generate answer using LLM
            answer = self._generate_answer_with_llm(user_prompt)
            
            # Step 4: Save to history
            self.db.save_qa_history(question, answer, receipt_ids, LLM_MODEL)
            
            return {
                'question': question,
                'answer': answer,
                'context': retrieved_receipts,
                'context_count': len(retrieved_receipts),
                'model': LLM_MODEL,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                'question': question,
                'answer': f"Error processing question: {str(e)}",
                'context': [],
                'error': str(e)
            }
    
    def _generate_answer_with_llm(self, prompt: str) -> str:
        """Generate answer using Ollama LLM"""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                logger.error(f"LLM API error: {response.status_code}")
                return "Unable to generate answer at this time."
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return f"Error generating answer: {str(e)}"
    
    def search_receipts(self, query: str, limit: int = 10) -> Dict:
        """Search receipts by query"""
        retrieved_receipts, receipt_ids = self.retriever.retrieve_context(query, top_k=limit)
        return {
            'query': query,
            'results': retrieved_receipts,
            'count': len(retrieved_receipts),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_statistics(self) -> Dict:
        """Get RAG system statistics"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM receipt_embeddings;")
                indexed_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM receipts;")
                total_receipts = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM qa_history;")
                qa_count = cur.fetchone()[0]
                
                return {
                    'indexed_receipts': indexed_count,
                    'total_receipts': total_receipts,
                    'qa_interactions': qa_count,
                    'indexing_coverage': f"{(indexed_count/total_receipts*100):.1f}%" if total_receipts > 0 else "0%"
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()

# =====================================================
# EXAMPLE USAGE
# =====================================================

if __name__ == "__main__":
    # Initialize RAG system
    rag = RAGPipeline(DB_CONFIG)
    rag.initialize()
    
    try:
        # Index all receipts
        print("Indexing receipts...")
        rag.index_receipts()
        
        # Show statistics
        stats = rag.get_statistics()
        print(f"\nRAG Statistics: {json.dumps(stats, indent=2)}")
        
        # Example questions
        questions = [
            "What is the total amount spent at restaurants?",
            "Show me all receipts from January 2026",
            "Which vendor had the highest transaction?",
            "List all transactions above 1000",
            "What items were purchased most frequently?"
        ]
        
        # Answer questions
        print("\n" + "="*60)
        print("ANSWERING QUESTIONS")
        print("="*60)
        
        for question in questions[:2]:  # Answer first 2 questions
            print(f"\nQ: {question}")
            result = rag.answer_question(question)
            print(f"A: {result['answer']}")
            print(f"Context receipts: {result['context_count']}")
    
    finally:
        rag.cleanup()
