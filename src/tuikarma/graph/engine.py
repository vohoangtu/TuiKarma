"""Code Knowledge Graph Engine powered by Graphify and Tree-Sitter.
Constructs deterministic architectural graphs, analyzes couplings, detects God Nodes,
and performs impact blast-radius analysis across long-running software projects.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import networkx as nx

logger = logging.getLogger("tuikarma.graph")

try:
    from graphify.extract import collect_files, extract
    from graphify.build import build
    from graphify.analyze import god_nodes, find_import_cycles, surprising_connections
    from graphify.cluster import cluster
    from graphify.export import to_html
    GRAPHIFY_AVAILABLE = True
except ImportError:
    GRAPHIFY_AVAILABLE = False
    logger.warning("graphify package is not installed. Code Knowledge Graph will operate in fallback mode.")


class CodeKnowledgeGraphEngine:
    """Manages Code Knowledge Graph generation, queries, and architectural analytics."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.graph: Optional[nx.Graph] = None
        self.communities: Dict[int, List[str]] = {}
        self._raw_extractions: Optional[Dict[str, Any]] = None

    def is_available(self) -> bool:
        return GRAPHIFY_AVAILABLE

    def build(self, force_rebuild: bool = False) -> nx.Graph:
        """Constructs or retrieves the cached Code Knowledge Graph."""
        if self.graph is not None and not force_rebuild:
            return self.graph

        if not GRAPHIFY_AVAILABLE:
            self.graph = nx.Graph()
            return self.graph

        if not self.root_dir.exists():
            self.graph = nx.Graph()
            return self.graph

        try:
            files = collect_files(self.root_dir)
            if not files:
                self.graph = nx.Graph()
                return self.graph

            raw = extract(files, parallel=False)
            self._raw_extractions = raw
            G = build([raw])
            self.graph = G

            try:
                self.communities = cluster(G)
            except Exception as e:
                logger.debug(f"Clustering warning: {e}")
                self.communities = {}

            logger.info(f"Built Code Knowledge Graph for {self.root_dir}: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return self.graph
        except Exception as e:
            logger.error(f"Failed to build Code Knowledge Graph: {e}", exc_info=True)
            self.graph = nx.Graph()
            return self.graph

    def get_summary(self) -> Dict[str, Any]:
        """Returns executive architectural summary, god nodes, and potential cycles."""
        G = self.build()
        if len(G.nodes) == 0:
            return {
                "available": GRAPHIFY_AVAILABLE,
                "total_nodes": 0,
                "total_edges": 0,
                "god_nodes": [],
                "import_cycles": [],
                "communities_count": 0,
            }

        gods: List[Dict[str, Any]] = []
        cycles: List[List[str]] = []
        try:
            raw_gods = god_nodes(G)
            gods = raw_gods[:8]
        except Exception:
            pass

        try:
            cycles = find_import_cycles(G)
        except Exception:
            pass

        return {
            "available": True,
            "root_path": str(self.root_dir),
            "total_nodes": len(G.nodes),
            "total_edges": len(G.edges),
            "god_nodes": gods,
            "import_cycles": cycles[:10],
            "communities_count": len(self.communities),
        }

    def _resolve_node_id(self, symbol: str) -> Optional[str]:
        """Fuzzy matches a user symbol/name to a node ID in the graph."""
        if not self.graph or len(self.graph.nodes) == 0:
            return None

        # Exact match
        if symbol in self.graph.nodes:
            return symbol

        target_lower = symbol.lower().strip()
        # Exact match on label
        for n, data in self.graph.nodes(data=True):
            if data.get("label", "").lower() == target_lower:
                return n

        # Suffix / Contains match
        for n, data in self.graph.nodes(data=True):
            if n.lower().endswith(f"_{target_lower}") or n.lower() == target_lower:
                return n

        # Partial substring match
        for n, data in self.graph.nodes(data=True):
            if target_lower in data.get("label", "").lower() or target_lower in n.lower():
                return n

        return None

    def query_symbol(self, symbol: str) -> Dict[str, Any]:
        """Queries relationships, callers, callees, and metadata of a symbol."""
        G = self.build()
        node_id = self._resolve_node_id(symbol)
        if not node_id or node_id not in G:
            return {
                "found": False,
                "symbol": symbol,
                "message": f"Symbol '{symbol}' not found in code knowledge graph."
            }

        node_data = dict(G.nodes[node_id])
        neighbors = []
        for nbr in G.neighbors(node_id):
            edge_data = G.get_edge_data(node_id, nbr) or {}
            nbr_info = dict(G.nodes[nbr])
            neighbors.append({
                "id": nbr,
                "label": nbr_info.get("label", nbr),
                "file": nbr_info.get("source_file", ""),
                "relation": edge_data.get("relation", "related"),
                "confidence": edge_data.get("confidence", "EXTRACTED"),
            })

        return {
            "found": True,
            "id": node_id,
            "label": node_data.get("label", node_id),
            "file": node_data.get("source_file", ""),
            "location": node_data.get("source_location", ""),
            "degree": G.degree(node_id),
            "connections_count": len(neighbors),
            "connections": neighbors[:40],
        }

    def find_path(self, source_symbol: str, target_symbol: str) -> Dict[str, Any]:
        """Finds shortest architectural dependency path between two components."""
        G = self.build()
        src_id = self._resolve_node_id(source_symbol)
        tgt_id = self._resolve_node_id(target_symbol)

        if not src_id or not tgt_id:
            return {
                "found": False,
                "message": f"One or both symbols could not be resolved: '{source_symbol}' -> '{target_symbol}'"
            }

        try:
            path = nx.shortest_path(G, source=src_id, target=tgt_id)
            path_details = []
            for idx, nid in enumerate(path):
                n_info = dict(G.nodes[nid])
                edge_relation = ""
                if idx < len(path) - 1:
                    edge_data = G.get_edge_data(nid, path[idx + 1]) or {}
                    edge_relation = edge_data.get("relation", "related")

                path_details.append({
                    "id": nid,
                    "label": n_info.get("label", nid),
                    "file": n_info.get("source_file", ""),
                    "next_relation": edge_relation
                })

            return {
                "found": True,
                "length": len(path) - 1,
                "path": path_details,
            }
        except nx.NetworkXNoPath:
            return {
                "found": False,
                "message": f"No architectural path found between '{source_symbol}' and '{target_symbol}'."
            }

    def impact_analysis(self, symbol: str, max_depth: int = 2) -> Dict[str, Any]:
        """Analyzes downstream blast radius: which components might break if symbol is modified?"""
        G = self.build()
        node_id = self._resolve_node_id(symbol)
        if not node_id:
            return {"found": False, "message": f"Symbol '{symbol}' not found."}

        visited: Set[str] = {node_id}
        current_layer: Set[str] = {node_id}
        layers: List[List[Dict[str, Any]]] = []

        for d in range(1, max_depth + 1):
            next_layer: Set[str] = set()
            layer_items: List[Dict[str, Any]] = []

            for cur in current_layer:
                for nbr in G.neighbors(cur):
                    if nbr not in visited:
                        visited.add(nbr)
                        next_layer.add(nbr)
                        nbr_data = dict(G.nodes[nbr])
                        e_data = G.get_edge_data(cur, nbr) or {}
                        layer_items.append({
                            "id": nbr,
                            "label": nbr_data.get("label", nbr),
                            "file": nbr_data.get("source_file", ""),
                            "depends_via": cur,
                            "relation": e_data.get("relation", "related"),
                        })

            if layer_items:
                layers.append(layer_items)
            current_layer = next_layer
            if not current_layer:
                break

        total_affected = sum(len(l) for l in layers)
        risk_level = "HIGH" if total_affected > 15 else "MEDIUM" if total_affected > 5 else "LOW"

        return {
            "found": True,
            "target_symbol": symbol,
            "target_node": node_id,
            "risk_level": risk_level,
            "total_affected_components": total_affected,
            "depth_layers": layers,
        }

    def export_interactive_html(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Generates an interactive force-directed HTML graph for browser visualization."""
        if not GRAPHIFY_AVAILABLE:
            return None

        G = self.build()
        if len(G.nodes) == 0:
            return None

        if output_path is None:
            out_file = self.root_dir / ".tuikarma" / "code_graph.html"
        else:
            out_file = Path(output_path)

        out_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            success = to_html(G, self.communities, str(out_file))
            if success and out_file.exists():
                return out_file
        except Exception as e:
            logger.error(f"Failed to export interactive HTML graph: {e}")

        return None
