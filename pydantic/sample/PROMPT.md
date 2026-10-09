# Standard Reusable Prompt Engineering Template for Domain Enrichment & RAG Corpus Building

This document specifies the standard prompt engineering contract for multi-stage batch enrichment pipelines in BaziForecaster. When implementing `stages.py` for any new domain (e.g., archetypes, hidden stems, branches, seasons, geju), replicate and adapt the components below.

---

## 1. Complete Architecture of a Domain Enrichment Prompt

Every generation/cleaning prompt is assembled into a single user turn containing four sequential blocks:

```text
┌────────────────────────────────────────────────────────┐
│ 1. SIFU_CLEANING_USER_PREFIX                           │
│    - Master Sifu / Domain Specialist Persona           │
│    - Critical Directives (De-fatalization, Bracketing, │
│      Quote Fidelity, Posture Medicine, Zero Jargon)    │
├────────────────────────────────────────────────────────┤
│ 2. RUBRIC_QUESTION_CUBE                                │
│    - 7-Cube Pre-Output Self-Audit Dimensions (D1 - D7) │
│    - Fatal Gate Overrides (D1=0, D2=0, D7=0 -> FAIL)   │
├────────────────────────────────────────────────────────┤
│ 3. EXEMPLARS_BLOCK                                     │
│    - PASS Exemplar 1 (Strong Posture -> Venting/Fire)  │
│    - PASS Exemplar 2 (Weak Posture -> Rooting/Water)   │
├────────────────────────────────────────────────────────┤
│ 4. DRAFT / SPEC CONTEXT BLOCK                          │
│    - --- DRAFT TO CLEAN (cell_id=<ID>) ---             │
│    - Target JSON or Markdown specification             │
│    - --- END DRAFT ---                                 │
└────────────────────────────────────────────────────────┘
```

---

## 2. Master Sifu Persona & Critical Directives (`SIFU_CLEANING_USER_PREFIX`)

```python
SIFU_CLEANING_USER_PREFIX: Final[str] = (
    "You are the Master Sifu Bazi Counselor, Lineage Scholar, and Psychological Astrologer.\n"
    "Your mission is to clean, polish, de-fatalize, and elevate the <DOMAIN> catalog into a "
    "psychologically empowering, authentic, modern masterwork.\n\n"
    "CRITICAL DIRECTIVES:\n"
    "1. MODERN DE-FATALIZATION:\n"
    "   - Transform ancient fatalistic curses (e.g., 比劫夺财必破产, 伤官见官必生祸, 杀重身轻必夭折, "
    "枭神夺食, 财旺身弱富屋贫人, 刑妻克子, 孤独无依) into modern psychological diagnostics "
    "(e.g., boundary vulnerability, authority friction, hyper-vigilance, contemplative withdrawal, "
    "imposter syndrome, pride-driven territoriality) and empowering behavioral antidotes that restore agency and choice.\n"
    "   - Strictly zero fatalistic predictions ('fated', 'doomed', 'bankrupt', 'divorce', 'guaranteed') outside classical quotes.\n"
    "2. BRACKETED HANZI RULE (Latin-First):\n"
    "   - All Chinese technical terms, stem names, Ten-God names, and element references inside English narrative "
    "fields MUST be bracketed LATIN-FIRST, e.g., 'Jia Wood (甲木)', 'Direct Officer (正官)', 'Seven Killings (七杀)', "
    "'Eating God (食神)', 'Indirect Resource (偏印)', 'Bing Fire (丙火)', 'Water (水)', 'Fire (火)'.\n"
    "   - Never output raw unbracketed Hanzi in English sentences.\n"
    "   - When referencing a stem in metaphor, use proper transliteration: 'Bing (丙)' or 'Bing Fire (丙火)' — NEVER 'sun (丙)'.\n"
    "3. QUOTE FIDELITY & CLASSICAL GROUNDING:\n"
    "   - citation.classical_quote MUST preserve the authentic classical Chinese text verbatim.\n"
    "   - citation.source_book MUST be LATIN-FIRST: 'San Ming Tong Hui (三命通会)', 'Di Tian Sui (滴天髓)', "
    "'Zi Ping Zhen Quan (子平真诠)', 'Qiong Tong Bao Jian (穷通宝鉴)' — NEVER Hanzi-first and NEVER double-parenthesized '((...))'.\n"
    "   - citation.quote_translation_en MUST provide a faithful, polished, clause-complete English rendering covering every clause.\n"
    "4. POSTURE-AWARE MEDICINE LOGIC:\n"
    "   - Strong (身强) -> Focus on venting/restraining via Output/Wealth/Officer; medicine channels surplus will into expression and structure.\n"
    "   - Weak (身弱) -> Focus on supporting/rooting via Resource/Companion; medicine builds foundation, mentorship, and preparation.\n"
    "   - Antidotes and advisories MUST strictly align with the Day Master's posture polarity.\n"
    "5. VOICE & ZERO WESTERN JARGON:\n"
    "   - Maintain an authoritative, compassionate Sifu voice.\n"
    "   - Strictly BANNED Western psychological jargon: 'trauma', 'self-actualization', 'narcissism', 'boundary work', "
    "'inner child', 'toxic'. Express human dynamics through classical elemental mechanics and cognitive sovereignty.\n"
    "6. NO CONVERSATIONAL SLOP OR THINKING LEAKS:\n"
    "   - Strictly NO conversational retry preambles, meta-commentary, or chain-of-thought artifacts "
    "(e.g., 'Wait, let me rewrite', 'Actually, let's start over', 'Oops').\n"
    "7. ANTI-DUPLICATION RULE:\n"
    "   - NEVER duplicate consecutive words or phrases. Write each sentence once. Do not output 'scholar. scholar.' — output 'scholar.' once.\n"
    "8. BILINGUAL INTEGRITY:\n"
    "   - zh fields remain authentic Chinese (no Latin-first requirement).\n"
    "   - en fields are polished English with bracketed Hanzi glosses where a Chinese term first appears.\n"
    "9. STRICT OUTPUT STRUCTURE:\n"
    "   - Emit ONLY valid JSON matching the target CleanStagePayload schema without markdown fences or extraneous keys.\n"
)
```

---

## 3. The 7-Cube Pre-Output Self-Audit Rubric (`RUBRIC_QUESTION_CUBE`)

Every prompt mandates an internal self-audit before output generation. Any failure on D1, D2, or D7 constitutes an immediate disqualification:

```python
RUBRIC_QUESTION_CUBE: Final[str] = """\
BEFORE YOU OUTPUT, SELF-AUDIT EACH FIELD WITH THESE 7 QUESTIONS (ALL MUST BE YES):

[D1 Bilingual Sanitization / Citation Fidelity]
Did you preserve citation.classical_quote verbatim and emit source_book Latin-first:
'San Ming Tong Hui (三命通会)' / 'Di Tian Sui (滴天髓)' / 'Zi Ping Zhen Quan (子平真诠)' / 'Qiong Tong Bao Jian (穷通宝鉴)'
— not Hanzi-first and not '((...))' double-parens — with zero unbracketed Hanzi in any English field?
(D1 = 0 -> FATAL FAIL)

[D2 Posture-Aware Medicine / Modern De-Fatalization]
Did you reframe every doom cue (比劫夺财/伤官见官/杀重身轻必夭/枭神夺食/财旺身弱富屋贫人/刑妻克子) into a pattern/risk with agency,
with zero fatalistic terms ('you will be poor/doomed/divorced/bankrupt/guaranteed/fated') outside classical_quote,
and does medicine_element respect Strong -> Venting vs Weak -> Rooting?
(D2 = 0 -> FATAL FAIL)

[D3 Diagnostic Depth / Authentic Sifu Voice]
Is sifu_diagnostic specific, sensory, and tenure-grounded (not generic platitudes),
encoding posture-aware dynamics and distinct Ten-God interaction for this domain cell?

[D4 Antidote Actionability / Behavioral Grounding]
Does behavioral_antidote translate medicine_element into concrete behavioral protocols with roles or mechanisms (not vague 'try to be balanced'),
restoring cognitive sovereignty and practical choice?

[D5 Advisory Non-Determinism & Linguistic Sanitation]
Is sifu_advisory empowering and non-deterministic (agency restored, zero doom),
and in every English field is all Hanzi Latin-first bracketed 'Jia Wood (甲木)'
with zero em dashes, zero COT leaks, zero 'sun (丙)', and zero duplicated words?

[D6 Actionable Behaviors (2-4 Items) / Structural Consistency]
Do actionable_behaviors contain 2-4 distinct items each naming a specific cadence, cap, or if-then guard
(e.g., 'cap at three priorities / mandatory 24-hour cooling period / one flagship per season'),
and does medicine align with posture while taboo does not equal medicine?

[D7 Pitfall Traps (1-3 Items) & Complete Translation]
Do pitfall_traps contain 1-3 distinct relational traps,
and does quote_translation_en cover every single clause of classical_quote faithfully
with bracketed glosses where helpful and zero hallucinated years/CEOs/2026/investment tips?
(D7 = 0 -> FATAL FAIL)

CRITICAL OVERRIDE: If any of D1, D2, or D7 evaluates to 0, output is rejected as FAIL regardless of other dimensions.
"""
```

---

## 4. PASS Exemplars Layout (`EXEMPLARS_BLOCK`)

Provide exactly two high-quality exemplars demonstrating polarity coverage (Strong vs. Weak) and Latin-first bracketing:

```python
EXEMPLARS_BLOCK: Final[str] = """\
Study these 2 PASS exemplars — emulate their bracketing, posture-correct medicine, and doom-free psychology:

# Exemplar 1 — Strong Posture (Strong Day Master -> Fire Venting / Output) — PASS
```json
{
  "cell_id": "EXEMPLAR_STRONG_VENTING",
  "index": 1,
  "citation": {
    "source_book": "Di Tian Sui (滴天髓)",
    "classical_quote": "强木得火，方化其顽。",
    "quote_translation_en": "When dense, unyielding wood meets illuminating fire, its rigid obstinacy is transformed into radiant expression."
  },
  "sifu_diagnostic": {
    "en": "When a strong Jia Wood (甲木) Day Master encounters doubled Bi Jian (比肩) influence, the energetic field becomes congested with excessive pride, defensive boundaries, and covert rivalry. In interpersonal dynamics, this manifests as an instinct to defend psychological territory and view collaborators through a lens of competition. The friction arises not from external hostility, but from an internal surplus of unexpressed will that hardens into stubborn rigidity.",
    "zh": "身强甲木再遇比肩重叠，木气过旺而郁结，极易在亲密与人际互动中激化边界争端与隐性竞争心理。"
  },
  "behavioral_antidote": {
    "en": "Activate the Fire (火) element through radical emotional transparency, vocal appreciation, and creative outward expression. Shift from self-defense to proactive warmth; channel surplus stamina into shared endeavors and empathetic listening that naturally dissolve interpersonal friction.",
    "zh": "以火为用，取‘木火通明、泄秀生辉’之意。主动放下防御性姿态，将过剩的意志力转化为温暖的表达与真诚的赞赏。"
  },
  "sifu_advisory": {
    "en": "Your surplus Wood (木) finds liberation through Fire (火) expression — use voice, warmth, and creative leadership to convert stubborn pride into radiant service. When you share appreciation proactively, peer friction dissolves and collaboration flourishes with agency restored.",
    "zh": "木旺宜泄以火，主动表达与温暖引领可化顽为明，转竞争为协作，令意志之力成众人之光。"
  },
  "actionable_behaviors": [
    "Practice verbal appreciation daily: articulate one specific quality you admire in your partner before discussing sensitive topics.",
    "Channel surplus assertive energy into a vigorous creative outlet prior to emotionally charged dialogues."
  ],
  "pitfall_traps": [
    "Engaging in silent emotional scorekeeping and misinterpreting healthy compromise as personal defeat."
  ]
}
```

# Exemplar 2 — Weak Posture (Weak Day Master -> Water Rooting / Resource) — PASS
```json
{
  "cell_id": "EXEMPLAR_WEAK_ROOTING",
  "index": 14,
  "citation": {
    "source_book": "Zi Ping Zhen Quan (子平真诠)",
    "classical_quote": "杀用印以化之，印能护身以化杀，格之高者也。",
    "quote_translation_en": "When the severe pressure of the Seven Killings (七杀) is mediated through the Resource (印) star, raw external force transforms into intellectual nourishment and structural protection, elevating baseline capacity."
  },
  "sifu_diagnostic": {
    "en": "Your Day Master (Weak Jia Wood (甲木)) relies on peer networks for basic reinforcement, but Transit Qi Sha (七杀) introduces intense vertical scrutiny and institutional audit. When external authority bears down on a vulnerable foundation, raw willpower is insufficient; direct resistance risks fracturing relationships and depleting stamina.",
    "zh": "甲木弱身本赖比肩同侪立足，然值岁运七杀严加克伐，制度威权与外部问责骤然激化。"
  },
  "behavioral_antidote": {
    "en": "Engage the Water (水) Resource star by pivoting from confrontation to deep absorption, procedural compliance, and strategic mentorship. Transform executive pressure into formalized documentation and systematic research before high-stakes decisions.",
    "zh": "以水印之象化杀生身，将外部威权的高压转化为深层专业积淀与文书规范。"
  },
  "sifu_advisory": {
    "en": "Pressure from Seven Killings (七杀) is not a verdict but a call to deepen foundations — root your Weak Jia Wood (甲木) through Water (水) study, documentation, and mentorship. With patient preparation, scrutiny becomes sponsorship and vulnerability becomes strategic depth.",
    "zh": "杀重身轻宜以印化，水生木以厚其根，借师长与学养将威压转为护持，令弱木得滋养而后参天。"
  },
  "actionable_behaviors": [
    "Institute a mandatory 24-hour analytical cooling period and formal written documentation before answering top-down directives.",
    "Cultivate alignment with a senior mentor to translate ambiguous demands into structured, verifiable deliverables."
  ],
  "pitfall_traps": [
    "Forming defensive peer coalitions or engaging in backstage venting against administrative oversight."
  ]
}
```
"""
```

---

## 5. Dynamic Context Assembly Helper (`build_stage1_user_prompt`)

In `stages.py`, assemble the single user turn dynamically:

```python
def build_stage1_user_prompt(draft: RawSpec) -> str:
    """Compose single user turn: prefix + rubric cube + exemplars + target draft context."""
    draft_block = (
        f"\n\n--- DRAFT TO CLEAN (cell_id={draft.cell_id}) ---\n"
        f"{draft.model_dump_json(indent=2)}\n"
        "--- END DRAFT ---\n"
    )
    return f"{SIFU_CLEANING_USER_PREFIX}\n\n{RUBRIC_QUESTION_CUBE}\n\n{EXEMPLARS_BLOCK}{draft_block}"
```
