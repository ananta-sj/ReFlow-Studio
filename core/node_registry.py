"""Declarative table of pipeline stage nodes + the fixed backbone graph
that mirrors ReflowPipeline.process_video_gen()'s real execution order."""

from core.graph_model import Graph, NodeSpec, NodeParam

# Per-category node header colors, Blender-style (each stage kind gets a
# distinct color so the graph reads at a glance instead of every box looking
# identical).
CATEGORY_COLORS = {
    "io": "#5A5F6B",         # Input/Output
    "audio": "#3EA3A3",      # Separate BG
    "data": "#4A7FC9",       # Transcribe, Subtitles
    "neural": "#8A5FC2",     # Translate
    "voice": "#C04FA0",      # TTS + RVC
    "visual": "#C0405A",     # Lip Sync
    "shader": "#E0954C",     # Face Enhance
    "safety": "#4A9B6E",     # Content Filter
}

SPECS = {
    "input": NodeSpec("input", "INPUT VIDEO", "🎬", mutable=False, header_color=CATEGORY_COLORS["io"], params=[
        NodeParam("video_name", "readonly", "File"),
    ]),
    "separate": NodeSpec("separate", "SEPARATE BG", "🎵", mutable=True, header_color=CATEGORY_COLORS["audio"], params=[]),
    "stt": NodeSpec("stt", "TRANSCRIBE", "📝", mutable=False, header_color=CATEGORY_COLORS["data"], params=[
        NodeParam("engine", "readonly", "Engine", default="Whisper (CPU)"),
    ]),
    # lang is a read-only mirror of the Control Panel's Pipeline tab (the
    # single source of truth for a render's language) - shown on the node
    # for context, not independently editable here.
    "translate": NodeSpec("translate", "TRANSLATE", "🌐", mutable=False, header_color=CATEGORY_COLORS["neural"], params=[
        NodeParam("lang", "readonly", "Target Language", default="English (en)"),
    ]),
    # Voice IS independently editable per node (not a Control Panel
    # mirror), since that's the whole point of duplicating this node for
    # multi-cast: each instance picks its own voice. bridge/api.py injects
    # the live installed-voice list into this param's options at request
    # time (this table has no knowledge of the model registry).
    "tts_rvc": NodeSpec(
        "tts_rvc", "VOICE (TTS + RVC)", "🎙️", mutable=False, duplicable=True,
        header_color=CATEGORY_COLORS["voice"],
        params=[NodeParam("voice", "combo", "Voice Model", default="CLONED_USER", options=[])],
    ),
    "lipsync": NodeSpec("lipsync", "LIP SYNC", "👄", mutable=True, header_color=CATEGORY_COLORS["visual"], params=[]),
    "enhance": NodeSpec("enhance", "FACE ENHANCE", "✨", mutable=True, header_color=CATEGORY_COLORS["shader"], params=[]),
    "content_filter": NodeSpec("content_filter", "CONTENT FILTER", "🛡️", mutable=True, header_color=CATEGORY_COLORS["safety"], params=[]),
    "subtitles": NodeSpec("subtitles", "SUBTITLES", "💬", mutable=True, header_color=CATEGORY_COLORS["data"], params=[]),
    "output": NodeSpec("output", "OUTPUT", "📤", mutable=False, header_color=CATEGORY_COLORS["io"], params=[]),
}

# (node_id, spec_id, x, y, default_enabled)
LAYOUT = [
    ("input", "input", 20, 260, True),
    ("separate", "separate", 260, 100, True),
    ("stt", "stt", 500, 260, True),
    ("translate", "translate", 740, 260, True),
    ("tts_rvc", "tts_rvc", 980, 260, True),
    ("lipsync", "lipsync", 1220, 260, False),
    ("enhance", "enhance", 1460, 260, False),
    ("content_filter", "content_filter", 1700, 260, False),
    ("subtitles", "subtitles", 980, 460, True),
    ("output", "output", 1940, 260, True),
]

# Mirrors the real sequential order in ReflowPipeline.process_video_gen():
# video_to_merge flows through lipsync -> enhance -> content_filter in that
# order, each stage optionally a no-op passthrough when its node is muted.
BACKBONE_EDGES = [
    ("input", "separate"), ("separate", "stt"),
    ("stt", "translate"), ("translate", "tts_rvc"),
    ("tts_rvc", "lipsync"), ("lipsync", "enhance"),
    ("enhance", "content_filter"), ("content_filter", "output"),
    ("subtitles", "output"),
]


def build_default_graph():
    graph = Graph()
    for node_id, spec_id, x, y, enabled in LAYOUT:
        node = graph.add_node(node_id, SPECS[spec_id], x, y)
        node.enabled = enabled
    for source_id, target_id in BACKBONE_EDGES:
        graph.connect(source_id, target_id)
    return graph
