import os
import json
import httpx
import math
from typing import List, Dict, Any, Tuple
from src.utils.logger import logger

class ToolSelector:
    def __init__(self, model_name: str = os.getenv("TOOL_SELECTION_MODEL")):
        self.model_name = model_name
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.embedding_model = "text-embedding-3-small"
        # Cache embeddings to avoid redundant network requests
        self._embedding_cache: Dict[str, List[float]] = {}

    async def _get_embedding(self, text: str) -> List[float]:
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found. Skipping semantic embeddings.")
            raise ValueError("No API Key")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"input": text, "model": self.embedding_model}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    embedding = data["data"][0]["embedding"]
                    self._embedding_cache[text] = embedding
                    return embedding
                else:
                    logger.warning(f"Embeddings API error: {resp.status_code} - {resp.text}")
                    raise ValueError(f"HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Failed to generate embedding via OpenRouter: {e}")
            raise

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def _fallback_similarity(self, query: str, text: str) -> float:
        # Simple Jaccard similarity fallback if embedding fails
        q_words = set(query.lower().split())
        t_words = set(text.lower().split())
        if not q_words:
            return 0.0
        return len(q_words.intersection(t_words)) / len(q_words)

    def _clean_json_string(self, s: str) -> str:
        s = s.strip()
        first_idx = s.find('{')
        if first_idx == -1:
            return s
        
        brace_count = 0
        in_string = False
        escape_char = False
        
        for i in range(first_idx, len(s)):
            char = s[i]
            if escape_char:
                escape_char = False
                continue
            if char == '\\':
                escape_char = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return s[first_idx:i+1]
        
        # Fallback to last index match if count balancing logic fails
        last_idx = s.rfind('}')
        if last_idx > first_idx:
            return s[first_idx:last_idx+1]
        return s

    async def select_tools(self, query: str, tools: List[Any]) -> List[Any]:
        if not tools:
            return []

        # 1. Generate representations
        tool_representations = []
        for tool in tools:
            args_list = list(tool.args.keys()) if hasattr(tool, "args") and tool.args else []
            rep = {
                "name": tool.name,
                "description": tool.description or "",
                "required_inputs": args_list,
                "capabilities": [tool.description or ""],
                "examples": []
            }
            tool_representations.append((tool, rep))

        # 2. Candidate Selection (Semantic Search or Full List if list is small)
        if len(tools) <= 25:
            candidate_json = [rep for tool, rep in tool_representations]
        else:
            candidates = []
            try:
                query_embedding = await self._get_embedding(query)
                for tool, rep in tool_representations:
                    tool_text = f"{rep['name']} {rep['description']}"
                    tool_embedding = await self._get_embedding(tool_text)
                    sim = self._cosine_similarity(query_embedding, tool_embedding)
                    candidates.append((sim, tool, rep))
            except Exception:
                logger.warning("Using keyword fallback for tool selection due to embedding failure.")
                for tool, rep in tool_representations:
                    tool_text = f"{rep['name']} {rep['description']}"
                    sim = self._fallback_similarity(query, tool_text)
                    candidates.append((sim, tool, rep))

            # Sort candidates and keep top 5
            candidates.sort(key=lambda x: x[0], reverse=True)
            top_candidates = candidates[:5]
            candidate_json = [item[2] for item in top_candidates]

        # 3. LLM verification with the exact system prompt
        system_prompt = (
            "You are an expert Tool Selection Agent.\n\n"
            "Your job is to choose the most appropriate tool for the user's request.\n\n"
            "Your responsibilities:\n"
            "- Understand the user's true intent rather than relying on keywords.\n"
            "- Compare the request with each candidate tool's capabilities.\n"
            "- Select the tool that best satisfies the user's intent.\n"
            "- Ignore tools that have similar words but do not solve the user's problem.\n"
            "- Consider synonyms, paraphrases, and implicit intent.\n"
            "- If multiple tools are required, return them in execution order.\n"
            "- If none of the retrieved tools are suitable, return \"NO_TOOL\".\n\n"
            "For every tool consider:\n"
            "- Primary capability\n"
            "- Supported use cases\n"
            "- Required inputs\n"
            "- Limitations\n"
            "- Best-fit scenarios\n\n"
            "Selection Rules:\n"
            "1. Prioritize semantic intent over keyword matching.\n"
            "2. Prefer the most specific tool over a generic one.\n"
            "3. Do not select a tool if required inputs are unavailable unless clarification is needed.\n"
            "4. If confidence is below 0.70, ask for clarification instead of guessing.\n"
            "5. Never invent a tool that is not in the candidate list.\n\n"
            "Input Format:\n\n"
            "User Request:\n"
            "{user_query}\n\n"
            "Candidate Tools:\n"
            "{candidate_tools}\n\n"
            "Output Format:\n"
            "{{\n"
            "  \"selected_tool\": \"<tool_name | NO_TOOL>\",\n"
            "  \"confidence\": 0.0,\n"
            "  \"reason\": \"<short explanation>\",\n"
            "  \"missing_inputs\": [],\n"
            "  \"execution_order\": [\n"
            "    \"<tool1>\",\n"
            "    \"<tool2>\"\n"
            "  ]\n"
            "}}\n\n"
            "Only output valid JSON."
        ).format(user_query=query, candidate_tools=json.dumps(candidate_json, indent=2))

        selected_tool_names = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": "You are a precise JSON assistant."},
                            {"role": "user", "content": system_prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }
                )
                if resp.status_code == 200:
                    result = resp.json()
                    raw_content = result["choices"][0]["message"]["content"]
                    logger.info(f"ToolSelector raw output: {raw_content}")
                    cleaned_content = self._clean_json_string(raw_content)
                    selection = json.loads(cleaned_content)
                    
                    confidence = selection.get("confidence", 0.0)
                    selected_tool = selection.get("selected_tool", "NO_TOOL")
                    exec_order = selection.get("execution_order", [])

                    if confidence >= 0.70:
                        if exec_order:
                            selected_tool_names = [name for name in exec_order if name != "NO_TOOL"]
                        elif selected_tool and selected_tool != "NO_TOOL":
                            selected_tool_names = [selected_tool]
                    else:
                        logger.info(f"Confidence score {confidence} is below 0.70. Defaulting to NO_TOOL.")
                else:
                    logger.error(f"LLM tool selector API failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Error during LLM tool selection validation: {e}")

        # 4. Filter original tools list based on selected names
        if not selected_tool_names:
            logger.info("No tools selected by the Tool Selection Agent.")
            return []

        selected_tools = [t for t in tools if t.name in selected_tool_names]
        logger.info(f"Tool Selection System active. Selected tools: {[t.name for t in selected_tools]}")
        return selected_tools
