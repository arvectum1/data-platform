from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .acquisition import (
    AcquisitionEngine,
    AcquisitionRequest,
    AcquisitionResult,
    RenderMode,
)
from .engine import (
    AutoDiscoveryProvider,
    CandidateProvider,
    ExtractionEngine,
    ExtractionResult,
    FieldSpec,
)


@dataclass(frozen=True, slots=True)
class URLExtractionResult:
    """End-to-end result retaining both acquisition and extraction evidence."""

    acquisition: AcquisitionResult
    extraction: ExtractionResult

    @property
    def asset(self):
        return self.extraction.asset

    @property
    def requires_confirmation(self) -> bool:
        return self.extraction.requires_confirmation

    @property
    def unresolved_required_fields(self) -> tuple[str, ...]:
        return self.extraction.unresolved_required_fields

    @property
    def ready(self) -> bool:
        """True only when downstream use needs neither review nor required-field repair."""

        return not self.requires_confirmation and not self.unresolved_required_fields

    def values(self, *, include_unconfirmed: bool = False) -> dict[str, Any]:
        return self.extraction.values(include_unconfirmed=include_unconfirmed)


class URLExtractionPipeline:
    """One governed URL -> RawAsset -> candidates -> decisions execution path."""

    def __init__(
        self,
        *,
        acquisition: AcquisitionEngine | None = None,
        extraction: ExtractionEngine | None = None,
        providers: Sequence[CandidateProvider] | None = None,
    ) -> None:
        if extraction is not None and providers is not None:
            raise ValueError("Pass either extraction or providers, not both")
        self.acquisition = acquisition or AcquisitionEngine()
        self.extraction = extraction or ExtractionEngine(
            tuple(providers) if providers is not None else (AutoDiscoveryProvider(),)
        )

    def extract(
        self,
        request: AcquisitionRequest,
        fields: Sequence[FieldSpec],
    ) -> URLExtractionResult:
        acquired = self.acquisition.acquire(request)
        extracted = self.extraction.extract(acquired.asset, fields)
        return URLExtractionResult(acquisition=acquired, extraction=extracted)

    def extract_url(
        self,
        url: str,
        fields: Sequence[FieldSpec],
        *,
        asset_id: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float = 20.0,
        max_bytes: int = 5_000_000,
        render_mode: RenderMode = RenderMode.AUTO,
    ) -> URLExtractionResult:
        return self.extract(
            AcquisitionRequest(
                url=url,
                asset_id=asset_id,
                headers={} if headers is None else dict(headers),
                timeout_s=timeout_s,
                max_bytes=max_bytes,
                render_mode=render_mode,
            ),
            fields,
        )

    def confirm(
        self,
        result: URLExtractionResult,
        selections: Mapping[str, str | None],
    ) -> URLExtractionResult:
        confirmed = self.extraction.confirm(result.extraction, selections)
        return URLExtractionResult(
            acquisition=result.acquisition,
            extraction=confirmed,
        )
