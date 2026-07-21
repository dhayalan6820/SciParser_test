import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from src.database.chat_db import MemorySemantic, MemoryEpisodic, MemoryProcedural, AsyncSessionLocal
from src.utils.logger import logger

class MemoryConsolidationWorker:
    async def decay_confidence(self, db: AsyncSession):
        """
        Decay confidence score for memories that haven't been accessed recently.
        If a memory drops below 0.1, it can be archived or deleted.
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Decay Semantic
        stmt = update(MemorySemantic).where(
            MemorySemantic.last_validated < threshold_date
        ).values(
            confidence_score=MemorySemantic.confidence_score - 0.05
        )
        await db.execute(stmt)

        # Decay Episodic
        stmt2 = update(MemoryEpisodic).where(
            MemoryEpisodic.last_accessed < threshold_date
        ).values(
            confidence_score=MemoryEpisodic.confidence_score - 0.05
        )
        await db.execute(stmt2)

        await db.commit()
        logger.info("Memory decay applied successfully.")

    async def purge_obsolete_memories(self, db: AsyncSession):
        """
        Delete memories with confidence score < 0.1
        """
        stmt1 = delete(MemorySemantic).where(MemorySemantic.confidence_score < 0.1)
        stmt2 = delete(MemoryEpisodic).where(MemoryEpisodic.confidence_score < 0.1)
        
        await db.execute(stmt1)
        await db.execute(stmt2)
        await db.commit()
        logger.info("Obsolete memories purged.")

    async def run_consolidation_job(self):
        try:
            async with AsyncSessionLocal() as db:
                await self.decay_confidence(db)
                await self.purge_obsolete_memories(db)
        except Exception as e:
            logger.error(f"Memory consolidation job failed: {e}")

memory_worker = MemoryConsolidationWorker()
