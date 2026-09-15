"""Stable topological order and cycle paths for a graph snapshot."""

import heapq
from typing import Mapping

from .model import GraphError, Node, NodeId


def ordered(
    nodes: Mapping[NodeId, Node],
    parents: Mapping[NodeId, Mapping[NodeId, None]],
    children: Mapping[NodeId, Mapping[NodeId, None]],
) -> tuple[NodeId, ...]:
    rank = {key: i for i, key in enumerate(nodes)}
    remaining = {key: len(parents[key]) for key in nodes}
    ready = [(rank[key], key) for key in nodes if remaining[key] == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        _, key = heapq.heappop(ready)
        result.append(key)
        for child in children[key]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, (rank[child], child))
    if len(result) != len(nodes):
        cycle = cycle_path(nodes, children)
        raise GraphError("dependency cycle: " + " -> ".join(map(str, cycle)))
    return tuple(result)


def cycle_path(
    nodes: Mapping[NodeId, Node],
    children: Mapping[NodeId, Mapping[NodeId, None]],
) -> list[NodeId]:
    """Iterative DFS also handles consumer repositories with long action chains."""
    finished = set()
    for start in nodes:
        if start in finished:
            continue
        path, active = [start], {start: 0}
        stack = [iter(children[start])]
        while stack:
            child = next(stack[-1], None)
            if child is None:
                completed = path.pop()
                finished.add(completed)
                active.pop(completed)
                stack.pop()
            elif child in active:
                return path[active[child] :] + [child]
            elif child not in finished:
                active[child] = len(path)
                path.append(child)
                stack.append(iter(children[child]))
    return []
