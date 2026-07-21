import json
from typing import List, Dict, Any, Optional
from src.database.chat_db import AsyncSessionLocal
from src.services.memory_service import memory_service
from src.services.brain import MemoryPruningLLM
from src import config
from src.utils.logger import logger
from langchain_core.messages import SystemMessage, HumanMessage

class MemoryExtractor:
    def __init__(self):
        # We can use GPT-4o or GPT-4o-mini for extraction
        self.llm = MemoryPruningLLM(
            model_name="openai/gpt-4o-mini",
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.1
        )
        
        self.extraction_prompt = """You are an advanced Memory Extraction AI.
Analyze the following conversation turn between a User and an AI Assistant.
Extract any long-term knowledge that should be persisted across sessions.

Output strict JSON only, with the following structure:
{
    "semantic_memories": [
        {
            "fact_key": "user_preference_or_fact_label",
            "fact_value": "detailed description of the fact",
            "confidence": 0.9
        }
    ],
    "episodic_memories": [
        {
            "task_summary": "what the user asked and what the AI did",
            "outcome": "SUCCESS or FAIL",
            "key_steps": "JSON string of actions taken",
            "tags": "JSON string of tags"
        }
    ],
    "procedural_memories": [
        {
            "skill_name": "name_of_workflow",
            "procedure": "step by step JSON instructions of how to do it"
        }
    ]
}
If there is nothing useful to remember, return empty arrays.
"""

    async def extract_and_store(self, user_id: str, domain: str, conversation_history: str):
        """
        Runs post-conversation to extract memories and store them.
        """
        try:
            messages = [
                SystemMessage(content=self.extraction_prompt),
                HumanMessage(content=f"Conversation:\n{conversation_history}")
            ]
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON safely
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            data = json.loads(content.strip())
            
            async with AsyncSessionLocal() as db:
                # Store Semantic
                for sm in data.get("semantic_memories", []):
                    await memory_service.add_semantic_memory(
                        db=db,
                    user_id=user_id,
                    domain=domain,
                    fact_key=sm["fact_key"],
                    fact_value=sm["fact_value"],
                    confidence=sm.get("confidence", 1.0)
                )
                
            # Store Episodic
            for em in data.get("episodic_memories", []):
                await memory_service.add_episodic_memory(
                    db=db,
                    user_id=user_id,
                    domain=domain,
                    task_summary=em["task_summary"],
                    outcome=em["outcome"],
                    key_steps=em["key_steps"],
                    tags=em["tags"]
                )
                
            # Store Procedural
            for pm in data.get("procedural_memories", []):
                await memory_service.add_procedural_memory(
                    db=db,
                    user_id=user_id,
                    skill_name=pm["skill_name"],
                    domain=domain,
                    procedure=pm["procedure"]
                )
                
            logger.info(f"Memory extraction complete for user {user_id}")
            
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")

memory_extractor = MemoryExtractor()
