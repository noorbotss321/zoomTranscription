import os
import chromadb
from chromadb.utils import embedding_functions
import groq
from typing import List, Dict
import json
from datetime import datetime
import queue
import threading
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client
groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Get or create collection
try:
    collection = chroma_client.get_collection(
        name="services_knowledge",
        embedding_function=embedding_function
    )
except:
    collection = chroma_client.create_collection(
        name="services_knowledge",
        embedding_function=embedding_function
    )

class RecommendationService:
    def __init__(self):
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
    
    def _process_queue(self):
        """Process items from the recommendation queue"""
        while self.is_running:
            try:
                # Get item from queue with timeout
                item = recommendation_queue.get(timeout=1)
                if item:
                    asyncio.run(self.process_transcription(item))
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing recommendation: {e}")
    
    async def process_transcription(self, item: Dict):
        """Process a transcription and generate recommendations"""
        try:
            meeting_id = item["meeting_id"]
            transcription = item["transcription"]
            timestamp = item["timestamp"]
            
            # Query the vector database
            results = collection.query(
                query_texts=[transcription],
                n_results=3
            )
            
            if not results['documents'] or not results['documents'][0]:
                return
            
            # Prepare context from retrieved documents
            context = "\n\n".join(results['documents'][0])
            
            # Get metadata for more detailed context
            metadatas = results['metadatas'][0]
            metadata_context = "\n\n".join([
                f"Service: {meta.get('name', 'N/A')}\nDescription: {meta.get('description', 'N/A')}"
                for meta in metadatas
            ])
            
            # Generate recommendations using Groq
            system_message = {
                "role": "system",
                "content": """You are a professional consultation assistant. Your role is to:
1. Analyze consultation transcripts and identify client needs
2. Provide brief, actionable service recommendations
3. Keep responses concise and to-the-point
4. Focus on immediate, practical solutions
5. Maintain a professional, consultative tone"""
            }
            
            user_message = {
                "role": "user",
                "content": f"""Consultation transcript:
{transcription}

Available services:
{metadata_context}

Provide brief, specific recommendations based on this consultation."""
            }
            
            chat_completion = groq_client.chat.completions.create(
                messages=[system_message, user_message],
                model="llama3-70b-8192",
                temperature=0.1
            )
            
            recommendation = chat_completion.choices[0].message.content
            
            # Store recommendation
            self._store_recommendation(meeting_id, recommendation, timestamp)
            
            # If auto-send is enabled, send to Zoom
            if item.get("auto_send_to_zoom", False):
                await self._send_to_zoom(meeting_id, recommendation)
                
        except Exception as e:
            print(f"Error in recommendation processing: {e}")
    
    def _store_recommendation(self, meeting_id: str, recommendation: str, timestamp: str):
        """Store recommendation in a file"""
        try:
            os.makedirs("recommendations", exist_ok=True)
            filename = f"recommendations/{meeting_id}.json"
            
            data = {
                "meeting_id": meeting_id,
                "recommendation": recommendation,
                "timestamp": timestamp
            }
            
            with open(filename, "w") as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Error storing recommendation: {e}")
    
    async def _send_to_zoom(self, meeting_id: str, recommendation: str):
        """Send recommendation to Zoom"""
        # TODO: Implement Zoom integration
        pass
    
    def stop(self):
        """Stop the recommendation service"""
        self.is_running = False
        if self.processing_thread.is_alive():
            self.processing_thread.join()

# Initialize recommendation service
recommendation_service = RecommendationService() 