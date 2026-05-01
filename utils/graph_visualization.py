from __future__ import annotations

try:
    from pyvis.network import Network
except Exception:  # pragma: no cover - handled by UI fallback
    Network = None


def _base_network(height: str = "720px") -> Network | None:
    if Network is None:
        return None
    net = Network(
        height=height,
        width="100%",
        bgcolor="#081526",
        font_color="#e5eefb",
        directed=False,
    )
    net.barnes_hut(gravity=-22000, central_gravity=0.22, spring_length=160, spring_strength=0.035, damping=0.88)
    net.set_options(
        """
        const options = {
          "nodes": {
            "font": { "size": 14, "face": "Manrope", "color": "#e5eefb" },
            "borderWidth": 2,
            "shadow": { "enabled": true, "color": "rgba(15, 23, 42, 0.55)", "size": 16, "x": 0, "y": 8 }
          },
          "edges": {
            "smooth": false,
            "color": { "inherit": false },
            "selectionWidth": 2.6,
            "hoverWidth": 2.2
          },
          "layout": { "improvedLayout": true },
          "configure": { "enabled": false },
          "interaction": {
            "hover": true,
            "tooltipDelay": 120,
            "navigationButtons": true,
            "keyboard": true
          },
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -22000,
              "centralGravity": 0.22,
              "springLength": 160,
              "springConstant": 0.035,
              "damping": 0.88
            },
            "minVelocity": 0.75
          }
        }
        """
    )
    return net


def build_bipartite_graph_html(edges: list[dict], focus_teacher_id: str = "") -> str | None:
    net = _base_network()
    if net is None or not edges:
        return None

    teacher_nodes: set[str] = set()
    publication_nodes: set[str] = set()
    normalized_focus_teacher_id = focus_teacher_id.strip()

    for edge in edges:
        teacher_node = f"teacher::{edge['teacher_id']}"
        publication_node = f"publication::{edge['publication_id']}"

        if teacher_node not in teacher_nodes:
            teacher_nodes.add(teacher_node)
            is_focus_teacher = normalized_focus_teacher_id and str(edge.get("teacher_id") or "").strip() == normalized_focus_teacher_id
            net.add_node(
                teacher_node,
                label=edge["teacher_name"],
                title=f"Викладач: {edge['teacher_name']}<br>Кафедра: {edge['department_name']}",
                group="teacher",
                color="#f59e0b" if is_focus_teacher else "#2dd4bf",
                shape="dot",
                size=26 if is_focus_teacher else 20,
            )

        if publication_node not in publication_nodes:
            publication_nodes.add(publication_node)
            year_value = edge["year"] if edge["year"] is not None else "н/д"
            net.add_node(
                publication_node,
                label=edge["publication_title"][:48],
                title=f"Публікація: {edge['publication_title']}<br>Рік: {year_value}",
                group="publication",
                color="#38bdf8",
                shape="square",
                size=17,
            )

        net.add_edge(teacher_node, publication_node, color="#5b728f", width=1.2)

    return net.generate_html()


def build_coauthor_graph_html(edges: list[dict]) -> str | None:
    net = _base_network()
    if net is None or not edges:
        return None

    seen_nodes: set[str] = set()
    for edge in edges:
        source_id = f"teacher::{edge['source_id']}"
        target_id = f"teacher::{edge['target_id']}"
        if source_id not in seen_nodes:
            seen_nodes.add(source_id)
            net.add_node(
                source_id,
                label=edge["source_name"],
                title=f"Викладач: {edge['source_name']}<br>Кафедра: {edge['source_department']}",
                color="#2dd4bf",
                shape="dot",
                size=18 + min(int(edge.get("weight", 1)), 8),
            )
        if target_id not in seen_nodes:
            seen_nodes.add(target_id)
            net.add_node(
                target_id,
                label=edge["target_name"],
                title=f"Викладач: {edge['target_name']}<br>Кафедра: {edge['target_department']}",
                color="#7dd3fc",
                shape="dot",
                size=18 + min(int(edge.get("weight", 1)), 8),
            )

        titles = "<br>".join(str(item) for item in edge.get("sample_titles", []) if item)
        net.add_edge(
            source_id,
            target_id,
            color="#f59e0b",
            width=max(1.6, min(float(edge.get("weight", 1)) * 1.4, 8.0)),
            title=f"Спільні публікації: {edge.get('weight', 1)}<br>{titles}",
        )

    return net.generate_html()


def build_department_graph_html(edges: list[dict]) -> str | None:
    net = _base_network()
    if net is None or not edges:
        return None

    seen_nodes: set[str] = set()
    for edge in edges:
        source_id = f"department::{edge['source_id']}"
        target_id = f"department::{edge['target_id']}"
        if source_id not in seen_nodes:
            seen_nodes.add(source_id)
            net.add_node(
                source_id,
                label=edge["source_name"],
                title=f"Кафедра: {edge['source_name']}<br>Факультет: {edge['source_faculty']}",
                color="#2dd4bf",
                shape="box",
                size=24,
            )
        if target_id not in seen_nodes:
            seen_nodes.add(target_id)
            net.add_node(
                target_id,
                label=edge["target_name"],
                title=f"Кафедра: {edge['target_name']}<br>Факультет: {edge['target_faculty']}",
                color="#38bdf8",
                shape="box",
                size=24,
            )

        titles = "<br>".join(str(item) for item in edge.get("sample_titles", []) if item)
        net.add_edge(
            source_id,
            target_id,
            color="#f59e0b",
            width=max(2.0, min(float(edge.get("weight", 1)) * 1.5, 9.0)),
            title=f"Спільні публікації: {edge.get('weight', 1)}<br>{titles}",
        )

    return net.generate_html()
