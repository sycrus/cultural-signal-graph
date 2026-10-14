"""The recorded fixture exploration on the seed corpus (PRD-futures.md, Testing).

Goal "the direction of AI wearables", 5 orders over 10 years from 2026. One recorded
model output per order, in the generator's output format, anchored to the seed
signals (`fixtures.EXTRACTED`). It exercises the baseline branch, a discontinuity per
order, and convergence (projections with several parents). Fixture mode replays
these instead of calling a model; tests parse them like real output.
"""

from __future__ import annotations

import json

FIXTURE_GOAL = "the direction of AI wearables"
FIXTURE_START_YEAR = 2026
FIXTURE_HORIZON = 10
FIXTURE_ORDERS = 5


def _p(id, statement, frm, window, baseline=False, discontinuity=False):
    return {
        "id": id,
        "statement": statement,
        "from": frm,
        "window": window,
        "baseline": baseline,
        "discontinuity": discontinuity,
    }


_ORDERS = [
    [
        _p("o1-glasses-default",
           "Smart glasses become the default AI-assistant form factor in China, led by Alibaba's Quark line",
           ["sig-release-note", "sig-search-spike"], [2026, 2028], baseline=True),
        _p("o1-backlash",
           "AI glasses meet a 'solution looking for a problem' backlash; adoption stalls outside early adopters",
           ["sig-viral-fad"], [2027, 2028]),
        _p("o1-privacy-rules",
           "Always-on cameras in public spaces trigger the first privacy-regulation proposals for AI glasses",
           ["sig-release-note"], [2027, 2028], discontinuity=True),
    ],
    [
        _p("o2-offline-models",
           "On-device models make glasses useful offline; daily dependence on the phone declines",
           ["o1-glasses-default"], [2028, 2030], baseline=True),
        _p("o2-headset-merge",
           "Gaming headsets and everyday glasses converge into one AI audio-visual wearable",
           ["o1-glasses-default", "sig-gaming-chatter"], [2029, 2030]),
        _p("o2-audio-only",
           "Camera-free, audio-only AI wearables win in markets with strict privacy rules",
           ["o1-privacy-rules", "o1-backlash"], [2028, 2030]),
        _p("o2-footage-leak",
           "A large leak of smart-glasses footage halts sales in the EU for a year",
           ["o1-privacy-rules"], [2029, 2029], discontinuity=True),
    ],
    [
        _p("o3-phone-replacement",
           "Glasses replace phones as the primary device for under-30s in urban Asia",
           ["o2-offline-models"], [2030, 2032], baseline=True),
        _p("o3-recording-norms",
           "Visible recording indicators become mandatory; ambient-AI etiquette norms settle",
           ["o2-audio-only", "o2-footage-leak"], [2030, 2031], discontinuity=True),
        _p("o3-glasses-first-games",
           "Wearable AI becomes a gaming platform; publishers ship glasses-first games",
           ["o2-headset-merge"], [2031, 2032]),
    ],
    [
        _p("o4-wearables-overtake",
           "Wearable sales overtake smartphone sales in China",
           ["o3-phone-replacement"], [2032, 2034], baseline=True),
        _p("o4-subsidized-monitors",
           "Insurers and employers subsidize AI glasses as health and safety monitors",
           ["o3-recording-norms", "o3-phone-replacement"], [2033, 2034]),
        _p("o4-unaugmented-status",
           "'Unaugmented' spaces and devices become a status signal and a counter-movement",
           ["o3-recording-norms"], [2032, 2034], discontinuity=True),
    ],
    [
        _p("o5-ambient-computing",
           "Interfaces dissolve into ambient, voice-first computing; the screen becomes optional",
           ["o4-wearables-overtake"], [2034, 2036], baseline=True),
        _p("o5-two-tier-society",
           "A divide between augmented and unaugmented citizens shapes policy debates",
           ["o4-subsidized-monitors", "o4-unaugmented-status"], [2035, 2036], discontinuity=True),
    ],
]

# One recorded raw model output per order (index 0 = order 1).
RECORDED_ORDER_OUTPUTS: list[str] = [json.dumps({"projections": ps}, indent=2) for ps in _ORDERS]

# Fixture mode's stand-in consequences for a regenerated or forked branch (no model).
FIXTURE_BRANCH_LINES = [
    "Buyers and regulators adjust to the new direction within two years",
    "A new set of players fills the gap the change leaves behind",
    "Everyday habits settle around the new arrangement",
    "The shift spreads to adjacent categories and markets",
    "What was contested becomes the unremarkable norm",
]
