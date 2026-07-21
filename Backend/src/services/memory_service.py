from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.database.chat_db import MemorySemantic, MemoryEpisodic, MemoryProcedural
from src.services.embedding_service import embedding_service
from src.utils.logger import logger
from datetime import datetime, timezone

class MemoryService:
    async def add_semantic_memory(self, db: AsyncSession, user_id: str, domain: str, fact_key: str, fact_value: str, confidence: float = 1.0) -> MemorySemantic:
        # Check for duplicates using string match first (for fast deduplication)
        stmt = select(MemorySemantic).where(
            MemorySemantic.user_id == user_id,
            MemorySemantic.domain == domain,
            MemorySemantic.fact_key == fact_key
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update confidence and timestamp
            existing.confidence_score = min(existing.confidence_score + 0.1, 1.0)
            existing.last_validated = datetime.now(timezone.utc)
            existing.access_count += 1
            if existing.fact_value != fact_value:
                existing.fact_value = fact_value
                # Re-generate embedding since value changed
                existing.embedding = await embedding_service.get_embedding(f"{fact_key}: {fact_value}")
            await db.commit()
            return existing

        # Create new memory
        embedding = await embedding_service.get_embedding(f"{fact_key}: {fact_value}")
        new_memory = MemorySemantic(
            user_id=user_id,
            domain=domain,
            fact_key=fact_key,
            fact_value=fact_value,
            confidence_score=confidence,
            embedding=embedding
        )
        db.add(new_memory)
        await db.commit()
        await db.refresh(new_memory)
        return new_memory

    async def add_episodic_memory(self, db: AsyncSession, user_id: str, domain: str, task_summary: str, outcome: str, key_steps: str, tags: str) -> MemoryEpisodic:
        embedding = await embedding_service.get_embedding(task_summary)
        new_memory = MemoryEpisodic(
            user_id=user_id,
            domain=domain,
            task_summary=task_summary,
            outcome=outcome,
            key_steps=key_steps,
            tags=tags,
            embedding=embedding
        )
        db.add(new_memory)
        await db.commit()
        await db.refresh(new_memory)
        return new_memory

    async def add_procedural_memory(self, db: AsyncSession, user_id: Optional[str], skill_name: str, domain: Optional[str], procedure: str) -> MemoryProcedural:
        stmt = select(MemoryProcedural).where(
            MemoryProcedural.user_id == user_id,
            MemoryProcedural.skill_name == skill_name
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.procedure = procedure
            existing.confidence_score = min(existing.confidence_score + 0.1, 1.0)
            existing.last_used = datetime.now(timezone.utc)
            existing.embedding = await embedding_service.get_embedding(f"{skill_name}: {procedure}")
            await db.commit()
            return existing

        embedding = await embedding_service.get_embedding(f"{skill_name}: {procedure}")
        new_memory = MemoryProcedural(
            user_id=user_id,
            skill_name=skill_name,
            domain=domain,
            procedure=procedure,
            embedding=embedding
        )
        db.add(new_memory)
        await db.commit()
        await db.refresh(new_memory)
        return new_memory

    async def retrieve_semantic_memories(self, db: AsyncSession, user_id: str, query: str, top_k: int = 5) -> List[MemorySemantic]:
        query_embedding = await embedding_service.get_embedding(query)
        # Using pgvector cosine distance operator <=>
        stmt = select(MemorySemantic).where(
            MemorySemantic.user_id == user_id
        ).order_by(
            MemorySemantic.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        
        result = await db.execute(stmt)
        memories = result.scalars().all()
        
        # Update access count
        for mem in memories:
            mem.access_count += 1
            mem.last_validated = datetime.now(timezone.utc)
        await db.commit()
        
        return list(memories)

    async def retrieve_episodic_memories(self, db: AsyncSession, user_id: str, query: str, top_k: int = 5) -> List[MemoryEpisodic]:
        query_embedding = await embedding_service.get_embedding(query)
        stmt = select(MemoryEpisodic).where(
            MemoryEpisodic.user_id == user_id
        ).order_by(
            MemoryEpisodic.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        
        result = await db.execute(stmt)
        memories = result.scalars().all()
        
        for mem in memories:
            mem.access_count += 1
            mem.last_accessed = datetime.now(timezone.utc)
        await db.commit()
        
        return list(memories)

memory_service = MemoryService()
