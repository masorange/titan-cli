"""Default review profile definitions for GitHub code review."""

from ..models.review_enums import AttentionTier, ChecklistCategory
from ..models.review_profile_models import (
    CandidateExclusions,
    CandidateScoringRule,
    ReviewAxisRule,
    ReviewProfile,
)


DEFAULT_REVIEW_PROFILE = ReviewProfile(
    version=1,
    change_patterns={
        "central_behavior": [
            "**/core/**",
            "**/services/**",
            "**/domain/**",
            "**/operations/**",
            "**/usecases/**",
            "**/utils/**",
            "**/middleware/**",
            "**/configuration/**",
        ],
        "entrypoint": [
            "**/main.py",
            "**/main.ts",
            "**/main.js",
            "**/*mainactivity*",
            "**/*cli.py",
            "**/routes/**",
            "**/controllers/**",
            "**/router*",
            "**/listener*",
            "**/dispatcher*",
        ],
        "repeated_callsite": [
            "**/components/**",
            "**/views/**",
            "**/screens/**",
            "**/dialogs/**",
            "**/*screen*",
            "**/*view*",
        ],
    },
    file_roles={
        # Anchored on directories and separators, never on a bare "test" substring:
        # path_matches_any lowercases both sides, so "**/*test*" also claims latest.py,
        # attestation.py and contest/. CamelCase conventions (FooTest.kt) are covered by
        # the case-sensitive regexes in manifest_operations instead.
        "tests": [
            "**/test/**",
            "**/tests/**",
            "**/spec/**",
            "**/specs/**",
            "**/androidTest/**",
            "**/integrationTest/**",
            "**/sharedTest/**",
            "**/functionalTest/**",
            "**/test_*.py",
            "**/*_test.py",
            "**/*_spec.py",
            "**/*_test.go",
            "**/*.test.js",
            "**/*.test.ts",
            "**/*.test.jsx",
            "**/*.test.tsx",
            "**/*.spec.js",
            "**/*.spec.ts",
            "**/*.spec.jsx",
            "**/*.spec.tsx",
        ],
        "config_or_contracts": [
            "**/*config*",
            "**/*schema*",
            "**/*contract*",
            "**/*constants*",
            "**/*settings*",
            "**/*.yaml",
            "**/*.yml",
            "**/*.toml",
            "**/*.json",
        ],
        "workflow_orchestration": [
            "**/workflows/**",
            "**/steps/**",
            "**/step_registry/**",
            "**/*step_registry*",
            "**/*workflow*",
            "**/*step*",
            "**/*executor*",
            "**/*pipeline*",
            "**/*command*",
        ],
        "integration_or_adapter": [
            "**/clients/**",
            "**/adapters/**",
            "**/network/**",
            "**/api/**",
            "**/serializers/**",
            "**/parsers/**",
            "**/mappers/**",
            "**/*adapter*",
            "**/*client*",
            "**/*network*",
            "**/*api*",
            "**/*gateway*",
            "**/*serializer*",
            "**/*parser*",
            "**/*mapper*",
            "**/*converter*",
        ],
        "entrypoints_or_ui": [
            "**/screens/**",
            "**/views/**",
            "**/controllers/**",
            "**/routers/**",
            "**/*screen*",
            "**/*view*",
            "**/*activity*",
            "**/*controller*",
            "**/*cli*",
            "**/main.py",
            "**/main.ts",
            "**/main.js",
            "**/*mainactivity*",
            "**/*router*",
        ],
        "business_logic": [
            "**/services/**",
            "**/usecases/**",
            "**/operations/**",
            "**/core/**",
            "**/*service*",
            "**/*usecase*",
            "**/*operation*",
            "**/*manager*",
            "**/*logic*",
            "**/*core*",
            "**/*model*",
        ],
    },
    # Attention per role. Three roles get a full read because that is where a defect
    # can hide behind code the diff does not show: behaviour, the adapters that talk to
    # the outside, and the orchestration that decides what runs. The rest are covered by
    # the cheap tier - seen, not opened - and only generated output and docs are skipped
    # outright. Nothing here is a guess about importance: it is a guess about whether
    # the DIFF ALONE is enough to judge the change, which is the question the tiers ask.
    attention={
        "business_logic": AttentionTier.DEEP,
        "integration_or_adapter": AttentionTier.DEEP,
        "workflow_orchestration": AttentionTier.DEEP,
        "config_or_contracts": AttentionTier.GLANCE,
        "entrypoints_or_ui": AttentionTier.GLANCE,
        "tests": AttentionTier.GLANCE,
        "other": AttentionTier.GLANCE,
        "docs_or_generated": AttentionTier.SKIP,
    },
    # Empty by default: Titan cannot know which paths a given project treats as a
    # boundary worth reading whole on a two-line change. A project declares its own.
    always_deep=[],
    # Conventional names only, and every one is checked for existence in the working tree
    # before it reaches the prompt -- a repo that has none of them sends none, so this is
    # safe on a project Titan has never seen. These are the files a human reviewer opens
    # before their first review of an unfamiliar repo: the instructions the project gives
    # its contributors (and its agents), and the harness that records what the work is
    # for. A project names its own architecture notes in `.titan/review/profile.yaml`,
    # because only it knows which document is load-bearing.
    # Deliberately short: these are consulted, not read end to end, and every extra
    # document is time the one deep call spends on prose instead of code. An agent
    # harness is NOT here on purpose -- it records what the work is for, not how this
    # code must be written -- but a project that wants it can name it, along with its own
    # architecture notes, in `.titan/review/profile.yaml`.
    context_docs=[
        "CLAUDE.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
    ],
    candidate_scoring=[
        CandidateScoringRule(
            name="domain_critical_path",
            patterns=[
                "**/*controller*",
                "**/*service*",
                "**/*store*",
                "**/*client*",
                "**/*handler*",
                "**/*validator*",
                "**/*middleware*",
                "**/*repository*",
                "**/*viewmodel*",
                "**/*presenter*",
                "**/*coordinator*",
                "**/*manager*",
                "**/*api*",
                "**/*router*",
                "**/*mapper*",
                "**/*serializer*",
                "**/*formatter*",
                "**/*adapter*",
                "**/*converter*",
                "**/*event*",
                "**/*classification*",
                "**/*normalizer*",
                "**/*parser*",
                "**/*model*",
            ],
            score_delta=4,
            reason="domain-critical path",
        ),
        CandidateScoringRule(
            name="semantic_mapping",
            patterns=[
                "**/*mapper*",
                "**/*serializer*",
                "**/*formatter*",
                "**/*adapter*",
                "**/*converter*",
                "**/*event*",
                "**/*classification*",
                "**/*normalizer*",
                "**/*parser*",
                "**/*model*",
            ],
            score_delta=3,
            reason="semantic mapping surface",
        ),
        CandidateScoringRule(
            name="security_sensitive",
            patterns=["**/*auth*", "**/*permission*", "**/*security*", "**/*payment*", "**/*billing*"],
            score_delta=5,
            reason="security or access-sensitive area",
        ),
        CandidateScoringRule(
            name="shared_helper",
            patterns=["**/*util*", "**/*interceptor*", "**/*configuration*", "**/*intent*"],
            score_delta=5,
            reason="shared helper or policy surface",
        ),
    ],
    candidate_exclusions=CandidateExclusions(
        low_signal_test_max_changes=20,
        low_signal_config_max_changes=10,
    ),
    review_axes={
        ChecklistCategory.FUNCTIONAL_CORRECTNESS: ReviewAxisRule(always_include=True),
        ChecklistCategory.ERROR_HANDLING: ReviewAxisRule(always_include=True),
        ChecklistCategory.SEMANTIC_CORRECTNESS: ReviewAxisRule(
            patterns=[
                "**/*mapper*",
                "**/*serializer*",
                "**/*formatter*",
                "**/*adapter*",
                "**/*converter*",
                "**/*event*",
                "**/*classification*",
                "**/*normalizer*",
                "**/*parser*",
                "**/*model*",
            ]
        ),
        ChecklistCategory.STATE_CONSISTENCY: ReviewAxisRule(
            patterns=[
                "**/*state*",
                "**/*result*",
                "**/*status*",
                "**/*callback*",
                "**/*listener*",
                "**/*event*",
                "**/*store*",
            ]
        ),
        ChecklistCategory.TEST_COVERAGE: ReviewAxisRule(patterns=["**/*test*", "**/*spec*"]),
        ChecklistCategory.API_CONTRACT: ReviewAxisRule(
            patterns=["**/*api*", "**/*schema*", "**/*model*", "**/*contract*"]
        ),
        ChecklistCategory.DATA_VALIDATION: ReviewAxisRule(
            patterns=["**/*validator*", "**/*request*", "**/*form*", "**/*serializer*"]
        ),
        ChecklistCategory.SECURITY: ReviewAxisRule(
            patterns=["**/*auth*", "**/*permission*", "**/*security*", "**/*payment*", "**/*billing*"]
        ),
    },
)
