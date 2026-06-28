from __future__ import annotations

from nifresearch.models import Fact, Profile, SourceResult, SourceStatus, Subject


def build_profile(subject: Subject, results: list[SourceResult]) -> Profile:
    best: dict[tuple, Fact] = {}
    contributors: dict[tuple, set[str]] = {}
    order: list[tuple] = []

    for result in results:
        if result.status != SourceStatus.OK:
            continue
        for fact in result.facts:
            key = (fact.type, fact.value)
            contributors.setdefault(key, set()).add(fact.source_id)
            if key not in best:
                best[key] = fact.model_copy(deep=True)
                order.append(key)
            elif fact.confidence > best[key].confidence:
                kept_detail = best[key].detail
                best[key] = fact.model_copy(deep=True)
                best[key].detail = {**kept_detail, **best[key].detail}

    facts: list[Fact] = []
    for key in order:
        fact = best[key]
        fact.detail["also_from"] = sorted(contributors[key])
        facts.append(fact)

    return Profile(subject=subject, facts=facts, results=results)
