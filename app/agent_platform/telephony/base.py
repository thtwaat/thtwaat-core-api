"""Abstract telephony provider — mirrors the LLM/voice provider pattern
(ABC + name-keyed registry, self-registration on import). A provider is
responsible for two, and only two, concerns: verifying that an inbound
webhook really came from it, and rendering its call-control markup (TwiML
for Twilio). Everything else — routing, agent resolution, conversation
persistence, calling the AI — lives in ``call_runtime.py`` and never
branches on provider name.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Mapping, Optional, Type


class TelephonyProvider(ABC):
    name: str = "base"

    @abstractmethod
    def verify_webhook(
        self,
        *,
        url: str,
        form_params: Mapping[str, str],
        signature_header: Optional[str],
    ) -> bool:
        """Return True only if this request is authentically from the provider.

        Must never raise — callers map any False to a uniform 401/403 so this
        can't become an oracle for *why* verification failed.
        """
        ...

    @abstractmethod
    def build_say_and_gather(
        self,
        *,
        text: str,
        gather_action_url: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
        fallback_text: Optional[str] = None,
    ) -> str:
        """Speak ``text`` then listen for the caller's next utterance, posting
        the recognized speech back to ``gather_action_url``."""
        ...

    @abstractmethod
    def build_say_and_hangup(self, *, text: str) -> str:
        """Speak ``text`` then end the call."""
        ...

    @abstractmethod
    def build_say_and_dial(self, *, text: str, phone_number: str) -> str:
        """Speak ``text`` then transfer the live call to ``phone_number``
        (human handoff)."""
        ...

    @abstractmethod
    def build_reject(self) -> str:
        """Reject the call outright (e.g. agent not found / capability disabled)."""
        ...


class TelephonyProviderRegistry:
    _providers: Dict[str, Type[TelephonyProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[TelephonyProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(cls, name: str) -> TelephonyProvider:
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(f"Telephony provider '{name}' is not registered.")
        return provider_class()
