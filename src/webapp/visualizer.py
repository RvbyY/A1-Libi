"""
Module webapp/visualizer.py
Fournit PipelineTracker et PipelineVisualizer pour générer en temps réel
un graphique SVG interactif de l'état des nœuds (Commandes, Guardrail, RAG,
PromptBuilder, Chat LLM, ToolExecutor, HallucinationGrader, Persistance).
"""
from dataclasses import dataclass, field
from datetime import datetime
import html
from typing import Optional


@dataclass
class NodeStatus:
    node_id: str
    title: str
    subtitle: str
    x: int
    y: int
    state: str = "idle"  # idle | active | success | warning | error
    detail: str = "En attente"
    visits: int = 0


@dataclass
class TraceEvent:
    timestamp: str
    node_id: str
    title: str
    state: str
    message: str


class PipelineVisualizer:
    """
    Gère l'état temps réel du graphe d'exécution de SensAI et génère un rendu
    visuel SVG + journal d'événements détaillé pour l'application Web.
    """

    DEFAULT_NODES = (
        ("input", "1. Entrée", "User / CLI / Web", 40, 140),
        ("command", "CommandRegistry", "/schedule, /recall...", 210, 40),
        ("guardrail", "2. IntentGuardrail", "Classify & Ambiguity", 210, 140),
        ("retrieve", "3. RAGManager", "DeepContext Search", 390, 140),
        ("prompt", "4. PromptBuilder", "Profile + RAG + Tools", 570, 140),
        ("generate", "5. Chat (LLM)", "Stream / Génération", 750, 140),
        ("tools", "6. ToolExecutor", "Calendar, Tasks, Mail", 750, 255),
        ("grade", "7. HallucinationGrader", "Self-RAG Vérification", 930, 140),
        ("persist", "8. SessionManager", "SQLite Persistence", 1110, 140),
    )

    EDGES = (
        ("input", "command", "/cmd"),
        ("input", "guardrail", "texte"),
        ("guardrail", "retrieve", "LEGAL"),
        ("retrieve", "prompt", "mémoires"),
        ("prompt", "generate", "Prompt"),
        ("generate", "tools", "tool_calls"),
        ("tools", "grade", "résultats"),
        ("generate", "grade", "candidat"),
        ("grade", "prompt", "hallucination (retry)"),
        ("grade", "persist", "grounded"),
        ("command", "persist", "état"),
    )

    STATE_COLORS = {
        "idle": ("#1e293b", "#475569", "#94a3b8"),
        "active": ("#1e3a8a", "#3b82f6", "#ffffff"),
        "success": ("#064e3b", "#10b981", "#ecfdf5"),
        "warning": ("#78350f", "#f59e0b", "#fffbeb"),
        "error": ("#7f1d1d", "#ef4444", "#fef2f2"),
    }

    def __init__(self):
        self.nodes: dict[str, NodeStatus] = {}
        self.events: list[TraceEvent] = []
        self.active_edge: Optional[tuple[str, str]] = None
        self.last_node: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self.nodes = {
            nid: NodeStatus(node_id=nid, title=title, subtitle=sub, x=x, y=y)
            for nid, title, sub, x, y in self.DEFAULT_NODES
        }
        self.events = []
        self.active_edge = None
        self.last_node = None

    def mark(self, node_id: str, state: str, detail: str = "") -> None:
        """Met à jour l'état d'un nœud et enregistre l'événement dans la trace temps réel."""
        if node_id not in self.nodes:
            return

        if self.last_node and self.last_node != node_id:
            self.active_edge = (self.last_node, node_id)
        self.last_node = node_id

        node = self.nodes[node_id]
        node.state = state
        if detail:
            node.detail = detail
        if state == "active":
            node.visits += 1

        now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.events.append(
            TraceEvent(
                timestamp=now_str,
                node_id=node_id,
                title=node.title,
                state=state,
                message=detail or state,
            )
        )

    def render_html(self) -> str:
        """Génère le graphique SVG temps réel ainsi que la timeline des étapes."""
        svg_edges = []
        for src_id, dst_id, label in self.EDGES:
            src = self.nodes[src_id]
            dst = self.nodes[dst_id]
            x1, y1 = src.x + 70, src.y + 32
            x2, y2 = dst.x + 70, dst.y + 32

            is_active = self.active_edge == (src_id, dst_id)
            stroke = "#3b82f6" if is_active else "#475569"
            width = "3" if is_active else "1.8"
            dash = 'stroke-dasharray="6,4"' if label == "hallucination (retry)" else ""

            if src_id == "grade" and dst_id == "prompt":
                # Courbe de rebouclage anti-hallucination par le haut
                path_d = f"M {x1} {src.y} C {x1} {src.y - 75}, {x2} {dst.y - 75}, {x2} {dst.y}"
                lx, ly = (x1 + x2) // 2, src.y - 60
            else:
                path_d = f"M {x1} {y1} L {x2} {y2}"
                lx, ly = (x1 + x2) // 2, (y1 + y2) // 2 - 8

            svg_edges.append(
                f'<path d="{path_d}" fill="none" stroke="{stroke}" stroke-width="{width}" {dash} marker-end="url(#arrow)"/>'
                f'<text x="{lx}" y="{ly}" fill="#94a3b8" font-size="10" text-anchor="middle">{html.escape(label)}</text>'
            )

        svg_nodes = []
        for node in self.nodes.values():
            bg, border, fg = self.STATE_COLORS.get(node.state, self.STATE_COLORS["idle"])
            pulse = (
                f'<rect x="{node.x - 4}" y="{node.y - 4}" width="148" height="72" rx="12" '
                f'fill="none" stroke="{border}" stroke-width="2" opacity="0.6"/>'
                if node.state == "active"
                else ""
            )
            badge = (
                f'<circle cx="{node.x + 132}" cy="{node.y + 10}" r="9" fill="{border}"/>'
                f'<text x="{node.x + 132}" y="{node.y + 14}" fill="#fff" font-size="10" font-weight="bold" text-anchor="middle">{node.visits}</text>'
                if node.visits > 0
                else ""
            )
            short_detail = node.detail[:22] + "..." if len(node.detail) > 25 else node.detail
            svg_nodes.append(
                f"<g>"
                f"{pulse}"
                f'<rect x="{node.x}" y="{node.y}" width="140" height="64" rx="10" fill="{bg}" stroke="{border}" stroke-width="2.2"/>'
                f'{badge}'
                f'<text x="{node.x + 10}" y="{node.y + 22}" fill="{fg}" font-size="11.5" font-weight="bold">{html.escape(node.title)}</text>'
                f'<text x="{node.x + 10}" y="{node.y + 38}" fill="#cbd5e1" font-size="10">{html.escape(node.subtitle)}</text>'
                f'<text x="{node.x + 10}" y="{node.y + 54}" fill="{border}" font-size="10" font-weight="600">{html.escape(short_detail)}</text>'
                f"</g>"
            )

        trace_rows = []
        for ev in reversed(self.events[-12:]):
            _, border, _ = self.STATE_COLORS.get(ev.state, self.STATE_COLORS["idle"])
            trace_rows.append(
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 10px;'
                f'border-left:3px solid {border};background:#0f172a;margin-bottom:4px;border-radius:4px;font-size:12px;">'
                f'<span style="color:#64748b;font-family:monospace;">{html.escape(ev.timestamp)}</span>'
                f'<strong style="color:#e2e8f0;min-width:160px;">{html.escape(ev.title)}</strong>'
                f'<span style="color:#cbd5e1;">{html.escape(ev.message)}</span>'
                f"</div>"
            )

        trace_html = (
            "".join(trace_rows)
            if trace_rows
            else '<div style="color:#64748b;font-size:12px;padding:8px;">Aucun événement exécuté pour le moment. Envoyez un message ou une commande (/help, /schedule...) pour voir le graphe s\'animer en temps réel.</div>'
        )

        return f"""
        <div style="background:#020617;border:1px solid #1e293b;border-radius:12px;padding:14px;color:#f8fafc;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-weight:700;font-size:14px;color:#38bdf8;">⚡ Graphe d'Exécution Temps Réel (StateGraph & Pipeline LLM)</span>
            <div style="display:flex;gap:12px;font-size:11px;color:#94a3b8;">
              <span>🔵 En cours</span>
              <span>🟢 Validé</span>
              <span>🟠 Rebouclage / Alerte</span>
              <span>🔴 Bloqué / Erreur</span>
            </div>
          </div>
          <div style="overflow-x:auto;">
            <svg viewBox="0 0 1280 340" width="100%" height="290" style="background:#090d16;border-radius:8px;">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/>
                </marker>
              </defs>
              {''.join(svg_edges)}
              {''.join(svg_nodes)}
            </svg>
          </div>
          <div style="margin-top:10px;">
            <div style="font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:6px;">Journal des transitions de nœuds :</div>
            <div style="max-height:170px;overflow-y:auto;">
              {trace_html}
            </div>
          </div>
        </div>
        """
