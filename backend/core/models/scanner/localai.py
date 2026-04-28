import httpx
from typing import List

from config.settings import settings
from core.models.descriptor import ModelDescriptor
from core.models.registry import get_model_registry
from log import logger


class LocalAIScanner:
    """
    LocalAI 模型扫描器（OpenAI-compatible）。
    """

    def __init__(self, base_url: str = settings.localai_base_url):
        self.base_url = base_url.rstrip("/")
        self.registry = get_model_registry()

    async def scan(self) -> List[ModelDescriptor]:
        logger.info(f"[LocalAIScanner] Scanning models from {self.base_url}")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                if response.status_code != 200:
                    logger.debug(f"[LocalAIScanner] Failed to fetch models: {response.status_code}")
                    return []
                data = response.json()
                models_data = data.get("data", [])
                out: List[ModelDescriptor] = []
                for item in models_data:
                    provider_model_id = str(item.get("id") or "").strip()
                    if not provider_model_id:
                        continue
                    descriptor = ModelDescriptor(
                        id=f"localai:{provider_model_id}",
                        name=provider_model_id,
                        provider="localai",
                        provider_model_id=provider_model_id,
                        runtime="openai",
                        base_url=self.base_url,
                        capabilities=["chat", "stream"],
                        description=f"LocalAI model: {provider_model_id}",
                        tags=["local", "localai", "openai-compatible"],
                    )
                    self.registry.upsert_model(descriptor)
                    out.append(descriptor)
                logger.info(f"[LocalAIScanner] Registered {len(out)} models")
                return out
        except Exception as e:
            logger.debug(f"[LocalAIScanner] LocalAI not reachable: {e}")
            return []
