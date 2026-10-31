"""Persist node layout and cast choices; reconstruct only supported topology."""
import math
import re

from core.json_store import JsonStore, require
from core.node_registry import build_default_graph, SPECS


def snapshot(graph):
    return {'nodes': [{'id': node.id, 'x': node.x, 'y': node.y,
                       'enabled': node.enabled, 'values': dict(node.values)}
                      for node in graph.nodes.values()]}


def restore(data):
    require(isinstance(data, dict) and isinstance(data.get('nodes'), list), 'Invalid graph state')
    graph = build_default_graph()
    seen = set()
    for item in data['nodes']:
        require(isinstance(item, dict), 'Invalid node state')
        node_id = item.get('id')
        require(isinstance(node_id, str) and node_id not in seen, 'Duplicate or invalid node ID')
        seen.add(node_id)
        if node_id not in graph.nodes:
            require(bool(re.fullmatch(r'tts_rvc_[2-9]\d*|tts_rvc_1\d+', node_id)), 'Unsupported node ID')
            graph.add_node(node_id, SPECS['tts_rvc'], removable=True)
            for edge in list(graph.edges):
                if edge.source_id == 'tts_rvc':
                    graph.connect(node_id, edge.target_id)
                if edge.target_id == 'tts_rvc':
                    graph.connect(edge.source_id, node_id)
        node = graph.nodes[node_id]
        for key in ('x', 'y'):
            value = item.get(key)
            require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 100000,
                    'Invalid node coordinate')
            setattr(node, key, value)
        enabled = item.get('enabled')
        require(type(enabled) is bool and (node.spec.mutable or enabled), 'Invalid required-node state')
        node.enabled = enabled
        values = item.get('values')
        require(isinstance(values, dict), 'Invalid node parameters')
        require(set(values) == set(node.values), 'Unknown or missing node parameter')
        for parameter in node.spec.params:
            value = values[parameter.key]
            if parameter.kind == 'readonly':
                require(value == parameter.default, 'Read-only node parameter changed')
            elif parameter.kind == 'combo':
                require(isinstance(value, str) and bool(value.strip()), 'Invalid voice selection')
        node.values = dict(values)
    require(set(build_default_graph().nodes).issubset(seen), 'Required graph nodes are missing')
    return graph


class GraphState:
    _serializable = False

    def __init__(self, path, warning=None):
        def validate(data):
            restore(data)
            return data
        self.store = JsonStore(path, snapshot(build_default_graph()), validate, warning)

    def load(self):
        return restore(self.store.read())

    def save(self, graph):
        self.store.replace(snapshot(graph))
