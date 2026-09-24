"""Default review profile definitions for GitHub code review."""

from ..models.review_enums import AttentionTier, ChecklistCategory
from ..models.review_profile_models import ReviewAxisRule, ReviewProfile


DEFAULT_REVIEW_PROFILE = ReviewProfile(
    version=1,
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
    # Attention per role. Four roles get a full read because that is where a defect
    # can hide behind code the diff does not show: behaviour, the adapters that talk to
    # the outside, the orchestration that decides what runs, and the UI. The rest are
    # covered by the triage - seen, not opened - and only generated output and docs are
    # skipped outright. Nothing here is a guess about importance: it is a guess about
    # whether the DIFF ALONE is enough to judge the change, which is the question the
    # tiers ask.
    #
    # UI is deep because in the frameworks Titan meets (Compose, SwiftUI, React) a screen
    # or view model holds state and effects, and the diff alone cannot show what they
    # interact with. On ragnarok PR #3692 the UI tier held LoginViewModel, LoginScreen
    # and PasskeyInfoViewModel -- the post-login flow -- in glance, triaged from diffs.
    attention={
        "business_logic": AttentionTier.DEEP,
        "integration_or_adapter": AttentionTier.DEEP,
        "workflow_orchestration": AttentionTier.DEEP,
        "entrypoints_or_ui": AttentionTier.DEEP,
        "config_or_contracts": AttentionTier.GLANCE,
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
        # Named deliberately rather than left ruleless. An axis with no rule now applies
        # to everything, so these three had to become a decision instead of an accident:
        # concurrency is about a recognisable vocabulary, while "is this change slow" and
        # "does this need documenting" are fair questions about any code and cost one
        # prompt line each.
        ChecklistCategory.CONCURRENCY: ReviewAxisRule(
            patterns=[
                "**/*async*",
                "**/*await*",
                "**/*coroutine*",
                "**/*suspend*",
                "**/*thread*",
                "**/*concurrent*",
                "**/*lock*",
                "**/*mutex*",
                "**/*semaphore*",
                "**/*atomic*",
                "**/*queue*",
                "**/*worker*",
                "**/*executor*",
                "**/*scheduler*",
                "**/*channel*",
                "**/*flow*",
                "**/*observable*",
                "**/*stream*",
            ]
        ),
        ChecklistCategory.PERFORMANCE: ReviewAxisRule(always_include=True),
        ChecklistCategory.DOCUMENTATION: ReviewAxisRule(always_include=True),
        ChecklistCategory.API_CONTRACT: ReviewAxisRule(
            patterns=["**/*api*", "**/*schema*", "**/*model*", "**/*contract*", "**/*.yaml", "**/*.json"]
        ),
        ChecklistCategory.DATA_VALIDATION: ReviewAxisRule(
            patterns=["**/*validator*", "**/*request*", "**/*form*", "**/*serializer*"]
        ),
        # The vocabulary of authentication code, not just the word "auth". Measured on
        # ragnarok run `70777691`: a 38-file PR about credentials, sessions, OTP and
        # magic links matched NONE of `auth`/`permission`/`security`/`payment`/`billing`,
        # so the security axis was never asked about on the one PR that most needed it.
        # These are generic names, not one project's: a repo that does not touch
        # credentials matches none of them and loses nothing.
        ChecklistCategory.SECURITY: ReviewAxisRule(
            patterns=[
                "**/*auth*",
                "**/*credential*",
                "**/*token*",
                "**/*session*",
                "**/*login*",
                "**/*oauth*",
                "**/*passkey*",
                "**/*password*",
                "**/*secret*",
                "**/*crypt*",
                "**/*permission*",
                "**/*security*",
                "**/*payment*",
                "**/*billing*",
            ]
        ),
    },
)
