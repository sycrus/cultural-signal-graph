"""Extraction stage — STUBBED for the thin slice (issue #2).

Returns the fixed fixture in `fixtures.EXTRACTED`; no model calls. The
signature `(corpus) -> Extraction` is the JSON seam that issue #3's cheap-model
extraction will implement for real. The only check here is a cheap integrity
guard: every signal's source must exist in the corpus, so the corpus -> signal
provenance link can't silently drift.
"""

from .fixtures import EXTRACTED
from .models import Extraction, SourceDoc


def extract(corpus: list[SourceDoc]) -> Extraction:
    corpus_uris = {source.uri for source in corpus}
    for signal in EXTRACTED.signals:
        if signal.source_uri not in corpus_uris:
            raise ValueError(
                f"extraction fixture signal {signal.id} references unknown source "
                f"{signal.source_uri}"
            )
    return EXTRACTED
