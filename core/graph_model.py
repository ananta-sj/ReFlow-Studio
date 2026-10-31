"""Plain-data pipeline graph model - no Qt dependency, independently testable.

The backbone topology is fixed (a dubbing pipeline has hard data
dependencies - translate needs STT text, TTS needs translated text, etc.)
so this isn't a free-form graph executor. What IS real: each optional node
can be muted/bypassed, and each node's parameters are edited on the node
itself. See node_registry.py for the actual stage definitions.
"""


class NodeParam:
    def __init__(self, key, kind, label, default=None, options=None):
        self.key = key
        self.kind = kind          # "combo" | "checkbox" | "readonly"
        self.label = label
        self.default = default
        self.options = options or []


class NodeSpec:
    """Static definition of a stage kind, shared by every node of that kind."""

    def __init__(self, id, title, icon, mutable, params=None, header_color=None, duplicable=False):
        self.id = id
        self.title = title
        self.icon = icon
        self.mutable = mutable  # can be muted/bypassed by the user
        self.params = params or []
        self.header_color = header_color  # per-category color, Blender-style
        # Can the user add a second instance of this stage? Only meaningful
        # for stages the pipeline actually knows how to run more than one
        # of - today that's just tts_rvc (multi-cast dubbing), since
        # ReflowPipeline already cycles cast_list per segment. Duplicating
        # any other stage would just be a second visual box the pipeline
        # never executes.
        self.duplicable = duplicable


class Node:
    """A live instance of a NodeSpec placed on the canvas."""

    def __init__(self, node_id, spec, x=0, y=0, removable=False):
        self.id = node_id
        self.spec = spec
        self.x = x
        self.y = y
        self.enabled = True
        self.values = {p.key: p.default for p in spec.params}
        # Fixed backbone nodes (built by node_registry.build_default_graph)
        # are never removable - only extra instances added at runtime via
        # duplicable specs are.
        self.removable = removable


class Edge:
    def __init__(self, source_id, target_id):
        self.source_id = source_id
        self.target_id = target_id


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, spec, x=0, y=0, removable=False):
        node = Node(node_id, spec, x, y, removable=removable)
        self.nodes[node_id] = node
        return node

    def remove_node(self, node_id):
        node = self.nodes.get(node_id)
        if not node or not node.removable:
            return False
        del self.nodes[node_id]
        self.edges = [e for e in self.edges if e.source_id != node_id and e.target_id != node_id]
        return True

    def connect(self, source_id, target_id):
        self.edges.append(Edge(source_id, target_id))

    def edges_from(self, node_id):
        return [e for e in self.edges if e.source_id == node_id]

    def edges_to(self, node_id):
        return [e for e in self.edges if e.target_id == node_id]
