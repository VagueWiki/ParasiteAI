"""ParasiteAI Mind Subsystem - Local Brain Management, Cognitive Pipeline & Browser Offloader."""

from parasite_ai.mind.affordance import (
    ActionAffordance,
    AffordanceAssessment,
    AffordanceEvaluator,
    CLIExecutionResult,
    CLIExecutionSandbox,
)
from parasite_ai.mind.brain_manager import (
    BrainMode,
    BrainState,
    BrainStatus,
    BrowserOffloadBackend,
    DownloadProgress,
    InferenceBackend,
    LlamaCppBackend,
    LocalBrainManager,
    MockBackend,
    ModelMetadata,
    OpenAIEndpointBackend,
    validate_gguf_header,
)
from parasite_ai.mind.dual_mind import (
    ActionDispatcher,
    ActionResult,
    DualMindPipeline,
    PersonaEngine,
    PersonaOutput,
)
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    DiffResult,
    EpisodicMemory,
    INTERACTIVE_ACTION_TYPES,
    StepRecord,
    compute_dhash,
    compute_pixel_diff,
    hamming_distance,
)
from parasite_ai.mind.offloader import (
    BrowserNotFoundError,
    BrowserOffloader,
    ChromeOffloader,
    IBrowserWindowBackend,
    IClipboardBackend,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
    SentinelClipboardVerifier,
    Win32BrowserWindowBackend,
    Win32ClipboardBackend,
)
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepIntent,
    StepStatus,
    check_and_insert_contingencies,
    extract_strategic_blueprint_json,
    format_gemini_consultation_prompt,
    parse_gemini_consultation_response,
    verify_step_completion,
)
from parasite_ai.mind.resolver import (
    PrecisionAppMatcher,
    UniversalAppResolver,
)

__all__ = [
    # Brain Manager
    "BrainMode",
    "BrainState",
    "BrainStatus",
    "BrowserOffloadBackend",
    "DownloadProgress",
    "InferenceBackend",
    "LlamaCppBackend",
    "LocalBrainManager",
    "MockBackend",
    "ModelMetadata",
    "OpenAIEndpointBackend",
    "validate_gguf_header",
    # Memory
    "ActionPlan",
    "ActionType",
    "DiffResult",
    "EpisodicMemory",
    "INTERACTIVE_ACTION_TYPES",
    "StepRecord",
    "compute_dhash",
    "compute_pixel_diff",
    "hamming_distance",
    # Dual Mind
    "ActionDispatcher",
    "ActionResult",
    "DualMindPipeline",
    "PersonaEngine",
    "PersonaOutput",
    # Browser Offloader
    "BrowserNotFoundError",
    "BrowserOffloader",
    "ChromeOffloader",
    "IBrowserWindowBackend",
    "IClipboardBackend",
    "MockBrowserWindowBackend",
    "MockClipboardBackend",
    "OffloadHarvestError",
    "OffloaderState",
    "SentinelClipboardVerifier",
    "Win32BrowserWindowBackend",
    "Win32ClipboardBackend",
    # Dynamic Living Plan & Strategic Consultation Protocol
    "LivingPlan",
    "PlanStep",
    "StepIntent",
    "StepStatus",
    "check_and_insert_contingencies",
    "extract_strategic_blueprint_json",
    "format_gemini_consultation_prompt",
    "parse_gemini_consultation_response",
    "verify_step_completion",
    # Universal App Resolver & Precision Matching
    "PrecisionAppMatcher",
    "UniversalAppResolver",
    # Affordance & CLI Execution Sandbox
    "ActionAffordance",
    "AffordanceAssessment",
    "AffordanceEvaluator",
    "CLIExecutionResult",
    "CLIExecutionSandbox",
]

