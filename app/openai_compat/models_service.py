"""Cached model catalog service for GET /v1/models (Week 2 Day 2)."""
from __future__ import annotations

from typing import Literal, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.openai_compat.cache import OpenAICompatCache
from app.openai_compat.catalog import build_models_payload, find_model_in_payload
from app.openai_compat.schemas import ModelObject, ModelsListResponse

CacheStatus = Literal["HIT", "MISS", "BYPASS"]


class ModelsService:
    def __init__(self, db: Session, cache: OpenAICompatCache | None = None):
        self.db = db
        self.cache = cache or OpenAICompatCache()

    def list_models(self, company_id: UUID) -> Tuple[ModelsListResponse, CacheStatus]:
        if not self.cache.enabled:
            payload = build_models_payload(self.db, company_id)
            return ModelsListResponse.model_validate(payload), "BYPASS"

        cached = self.cache.get_models_list(company_id)
        if cached is not None:
            return ModelsListResponse.model_validate(cached), "HIT"

        payload = build_models_payload(self.db, company_id)
        self.cache.set_models_list(company_id, payload)
        return ModelsListResponse.model_validate(payload), "MISS"

    def get_model(self, company_id: UUID, model_id: str) -> Tuple[ModelObject, CacheStatus]:
        if not self.cache.enabled:
            payload = build_models_payload(self.db, company_id)
            item = find_model_in_payload(payload, model_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "message": f"The model '{model_id}' does not exist",
                            "type": "invalid_request_error",
                            "code": "model_not_found",
                        }
                    },
                )
            return ModelObject.model_validate(item), "BYPASS"

        cached = self.cache.get_model(company_id, model_id)
        if cached is not None:
            return ModelObject.model_validate(cached), "HIT"

        # Prefer list cache to avoid rebuilding twice
        list_payload = self.cache.get_models_list(company_id)
        if list_payload is None:
            list_payload = build_models_payload(self.db, company_id)
            self.cache.set_models_list(company_id, list_payload)

        item = find_model_in_payload(list_payload, model_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "message": f"The model '{model_id}' does not exist",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            )
        self.cache.set_model(company_id, model_id, item)
        return ModelObject.model_validate(item), "MISS"
