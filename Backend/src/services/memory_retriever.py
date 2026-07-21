import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.memory_service import memory_service
from src.utils.logger import logger

class MemoryRetriever:
    async def retrieve_context(self, db: AsyncSession, user_id: str, query: str, domain: str = "general") -> str:
        """
        Retrieves top memories and formats them into a context string.
        """
        try:
            # 1. Retrieve Semantic Memories
            semantic_memories = await memory_service.retrieve_semantic_memories(
                db=db, user_id=user_id, query=query, top_k=3
            )
            
            # 2. Retrieve Episodic Memories
            episodic_memories = await memory_service.retrieve_episodic_memories(
                db=db, user_id=user_id, query=query, top_k=2
            )
            
            # 3. Build Context String
            context_parts = []
            
            if semantic_memories:
                context_parts.append("### User Facts & Preferences ###")
                for sm in semantic_memories:
                    # Apply simple scoring: Confidence + (Access Count * 0.01)
                    score = sm.confidence_score + (sm.access_count * 0.01)
                    context_parts.append(f"- {sm.fact_key}: {sm.fact_value} (Relevance Score: {score:.2f})")
                    
            if episodic_memories:
                context_parts.append("\n### Previous Experiences (Episodes) ###")
                for em in episodic_memories:
                    score = em.confidence_score + (em.access_count * 0.01)
                    context_parts.append(f"- Task: {em.task_summary}\n  Outcome: {em.outcome}\n  Steps: {em.key_steps} (Relevance Score: {score:.2f})")

            if not context_parts:
                return ""
                
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to retrieve memory context: {e}")
            return ""

memory_retriever = MemoryRetriever()
