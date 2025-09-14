#!/usr/bin/env python3
"""
Code Graph KuzuDB to Graphviz Converter

This script converts the KuzuDB code graph database to Graphviz DOT format
for visualization of code structure, relationships, and dependencies.

Usage:
    python code_graph_kuzu_to_graphviz.py [options]

Examples:
    # Generate full graph (warning: may be very large!)
    python code_graph_kuzu_to_graphviz.py --db-path ./code_graph.kuzu --output ./full_graph.dot

    # Generate filtered graph for specific files
    python code_graph_kuzu_to_graphviz.py --filter-files "src/graph_sitter/extensions/kuzu_map/*" --output ./kuzu_map.dot

    # Generate high-level overview (files and classes only)
    python code_graph_kuzu_to_graphviz.py --entities files,classes --output ./overview.dot

    # Generate function call graph with complexity filtering
    python code_graph_kuzu_to_graphviz.py --entities functions --show-calls --min-complexity 5 --output ./complex_functions.dot
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import fnmatch

try:
    import kuzu
except ImportError:
    print("Error: kuzu package not found. Install with: pip install kuzu")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CodeGraphVisualizer:
    """Converts KuzuDB code graph to Graphviz format."""

    def __init__(self, db_path: str):
        """Initialize with KuzuDB database path."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)

        # Visual styling for different node types
        self.node_styles = {
            'file': {
                'shape': 'box',
                'style': 'filled',
                'fillcolor': 'lightblue',
                'fontname': 'Arial',
                'fontsize': '10'
            },
            'function': {
                'shape': 'ellipse',
                'style': 'filled',
                'fillcolor': 'lightgreen',
                'fontname': 'Arial',
                'fontsize': '9'
            },
            'class': {
                'shape': 'box',
                'style': 'filled,rounded',
                'fillcolor': 'lightyellow',
                'fontname': 'Arial Bold',
                'fontsize': '10'
            },
            'import': {
                'shape': 'diamond',
                'style': 'filled',
                'fillcolor': 'plum',
                'fontname': 'Arial',
                'fontsize': '8'
            },
            'symbol': {
                'shape': 'circle',
                'style': 'filled',
                'fillcolor': 'orange',
                'fontname': 'Arial',
                'fontsize': '8'
            },
            'parameter': {
                'shape': 'box',
                'style': 'filled',
                'fillcolor': 'cyan',
                'fontname': 'Arial',
                'fontsize': '7'
            },
            'codeblock': {
                'shape': 'hexagon',
                'style': 'filled',
                'fillcolor': 'lightcoral',
                'fontname': 'Arial',
                'fontsize': '8'
            }
        }

        # Edge styling for different relationship types
        self.edge_styles = {
            'contains': {'style': 'solid', 'color': 'black', 'penwidth': '1'},
            'calls': {'style': 'dashed', 'color': 'red', 'penwidth': '1', 'arrowhead': 'normal'},
            'inherits': {'style': 'solid', 'color': 'blue', 'penwidth': '2', 'arrowhead': 'empty'},
            'implements': {'style': 'dotted', 'color': 'green', 'penwidth': '1', 'arrowhead': 'normal'},
            'has_param': {'style': 'solid', 'color': 'gray', 'penwidth': '0.5'},
            'declares': {'style': 'solid', 'color': 'purple', 'penwidth': '0.5'},
            'assigns': {'style': 'solid', 'color': 'orange', 'penwidth': '0.5'}
        }

    def close(self):
        """Close database connections."""
        if hasattr(self, 'conn'):
            self.conn.close()
        if hasattr(self, 'db'):
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_database_stats(self) -> Dict[str, int]:
        """Get basic statistics about the database content."""
        stats = {}
        queries = {
            'files': 'MATCH (f:File) RETURN count(f) as count',
            'functions': 'MATCH (f:Function) RETURN count(f) as count',
            'classes': 'MATCH (c:Class) RETURN count(c) as count',
            'imports': 'MATCH (i:Import) RETURN count(i) as count',
            'symbols': 'MATCH (s:Symbol) RETURN count(s) as count',
            'assignments': 'MATCH (a:Assignment) RETURN count(a) as count',
            'parameters': 'MATCH (p:Parameter) RETURN count(p) as count',
            'code_blocks': 'MATCH (b:CodeBlock) RETURN count(b) as count'
        }

        for name, query in queries.items():
            try:
                result = self.conn.execute(query)
                stats[name] = result.get_next()[0] if result.has_next() else 0
            except Exception as e:
                logger.warning(f"Could not get {name} count: {e}")
                stats[name] = 0

        return stats

    def filter_files_by_pattern(self, pattern: str) -> Set[str]:
        """Get file paths matching the given pattern."""
        result = self.conn.execute("MATCH (f:File) RETURN f.path")

        all_paths = []
        while result.has_next():
            all_paths.append(result.get_next()[0])

        # Use fnmatch for pattern matching
        matching_paths = set()
        for path in all_paths:
            if fnmatch.fnmatch(path, pattern):
                matching_paths.add(path)

        logger.info(f"Pattern '{pattern}' matched {len(matching_paths)} files")
        return matching_paths

    def get_nodes(self, entities: List[str], file_filter: Optional[Set[str]] = None,
                  min_complexity: int = 0, max_nodes: Optional[int] = None) -> List[Dict]:
        """Extract nodes based on entity types and filters."""
        nodes = []

        # Build file filter clause for files
        file_clause = ""
        if file_filter:
            file_list = "', '".join(file_filter)
            file_clause = f"WHERE n.path IN ['{file_list}']"

        # Files
        if 'files' in entities:
            query = f"MATCH (n:File) {file_clause} RETURN n.path as id, n.name as name, n.extension as ext, n.size as size"
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                file_path, name, ext, size = row
                label = f"{name}\\n({size} bytes)" if size else name
                nodes.append({
                    'id': self._safe_node_id(file_path),
                    'label': self._escape_label(label),
                    'type': 'file',
                    'title': file_path
                })

        # Functions
        if 'functions' in entities:
            complexity_clause = f"AND n.complexity >= {min_complexity}" if min_complexity > 0 else ""
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND n.file_path IN ['{file_list}']"

            query = f"""
                MATCH (n:Function)
                WHERE TRUE {file_filter_clause} {complexity_clause}
                RETURN n.id as id, n.name as name, n.file_path as file_path, n.complexity as complexity,
                       n.is_method as is_method, n.params_count as params_count
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                func_id, name, file_path, complexity, is_method, params_count = row
                method_indicator = "⚡" if is_method else "🔧"
                label = f"{method_indicator} {name}\\n(C:{complexity}, P:{params_count})"
                nodes.append({
                    'id': self._safe_node_id(func_id),
                    'label': self._escape_label(label),
                    'type': 'function',
                    'title': f"{name} in {file_path}"
                })

        # Classes
        if 'classes' in entities:
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND n.file_path IN ['{file_list}']"

            query = f"""
                MATCH (n:Class)
                WHERE TRUE {file_filter_clause}
                RETURN n.id as id, n.name as name, n.file_path as file_path, n.methods_count as methods_count
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                cls_id, name, file_path, methods_count = row
                label = f"📦 {name}\\n({methods_count} methods)"
                nodes.append({
                    'id': self._safe_node_id(cls_id),
                    'label': self._escape_label(label),
                    'type': 'class',
                    'title': f"{name} in {file_path}"
                })

        # Imports
        if 'imports' in entities:
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND n.file_path IN ['{file_list}']"

            query = f"""
                MATCH (n:Import)
                WHERE TRUE {file_filter_clause}
                RETURN n.id as id, n.module_name as module_name, n.imported_name as imported_name,
                       n.alias as alias, n.file_path as file_path
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                imp_id, module_name, imported_name, alias, file_path = row
                display_name = alias if alias else imported_name if imported_name else module_name
                label = f"📥 {display_name}\\nfrom {module_name}"
                nodes.append({
                    'id': self._safe_node_id(imp_id),
                    'label': self._escape_label(label),
                    'type': 'import',
                    'title': f"Import in {file_path}"
                })

        # Symbols
        if 'symbols' in entities:
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND n.file_path IN ['{file_list}']"

            query = f"""
                MATCH (n:Symbol)
                WHERE TRUE {file_filter_clause}
                RETURN n.id as id, n.name as name, n.kind as kind, n.scope as scope, n.type_annotation as type_ann
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                sym_id, name, kind, scope, type_ann = row
                type_info = f": {type_ann}" if type_ann else ""
                label = f"🏷️ {name}{type_info}\\n({kind}, {scope})"
                nodes.append({
                    'id': self._safe_node_id(sym_id),
                    'label': self._escape_label(label),
                    'type': 'symbol',
                    'title': f"{kind} symbol: {name}"
                })

        # Parameters
        if 'parameters' in entities:
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND EXISTS {{MATCH (f:Function {{id: n.function_id}}) WHERE f.file_path IN ['{file_list}']}}"

            query = f"""
                MATCH (n:Parameter)
                WHERE TRUE {file_filter_clause}
                RETURN n.id as id, n.name as name, n.type_annotation as type_ann,
                       n.default_value as default_val, n.is_optional as is_optional
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                param_id, name, type_ann, default_val, is_optional = row
                type_info = f": {type_ann}" if type_ann else ""
                optional_marker = "?" if is_optional else ""
                default_info = f" = {default_val}" if default_val else ""
                label = f"🎯 {name}{type_info}{optional_marker}{default_info}"
                nodes.append({
                    'id': self._safe_node_id(param_id),
                    'label': self._escape_label(label),
                    'type': 'parameter',
                    'title': f"Parameter: {name}"
                })

        # Code Blocks
        if 'codeblocks' in entities:
            file_filter_clause = ""
            if file_filter:
                file_list = "', '".join(file_filter)
                file_filter_clause = f"AND n.file_path IN ['{file_list}']"

            query = f"""
                MATCH (n:CodeBlock)
                WHERE TRUE {file_filter_clause}
                RETURN n.id as id, n.block_type as block_type, n.complexity_contribution as complexity
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                block_id, block_type, complexity = row
                label = f"🔀 {block_type}\\n(C:{complexity})"
                nodes.append({
                    'id': self._safe_node_id(block_id),
                    'label': self._escape_label(label),
                    'type': 'codeblock',
                    'title': f"{block_type} block"
                })

        # Limit nodes if specified
        if max_nodes and len(nodes) > max_nodes:
            logger.warning(f"Limiting output to {max_nodes} nodes (found {len(nodes)})")
            nodes = nodes[:max_nodes]

        logger.info(f"Extracted {len(nodes)} nodes")
        return nodes

    def get_edges(self, entities: List[str], file_filter: Optional[Set[str]] = None,
                  show_calls: bool = False, show_inheritance: bool = False,
                  show_parameters: bool = False, show_symbols: bool = False) -> List[Dict]:
        """Extract edges based on relationship types and filters."""
        edges = []

        # File containment relationships
        if any(e in entities for e in ['files', 'functions', 'classes', 'imports']):
            # File contains functions
            if 'files' in entities and 'functions' in entities:
                query = """
                    MATCH (f:File)-[:CONTAINS_FUNCTION]->(func:Function)
                    RETURN f.path as from_id, func.id as to_id
                """
                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    from_id, to_id = row
                    if not file_filter or from_id in file_filter:
                        edges.append({
                            'from': self._safe_node_id(from_id),
                            'to': self._safe_node_id(to_id),
                            'type': 'contains',
                            'label': 'contains'
                        })

            # File contains classes
            if 'files' in entities and 'classes' in entities:
                query = """
                    MATCH (f:File)-[:CONTAINS_CLASS]->(cls:Class)
                    RETURN f.path as from_id, cls.id as to_id
                """
                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    from_id, to_id = row
                    if not file_filter or from_id in file_filter:
                        edges.append({
                            'from': self._safe_node_id(from_id),
                            'to': self._safe_node_id(to_id),
                            'type': 'contains',
                            'label': 'contains'
                        })

            # File contains imports
            if 'files' in entities and 'imports' in entities:
                query = """
                    MATCH (f:File)-[:CONTAINS_IMPORT]->(imp:Import)
                    RETURN f.path as from_id, imp.id as to_id
                """
                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    from_id, to_id = row
                    if not file_filter or from_id in file_filter:
                        edges.append({
                            'from': self._safe_node_id(from_id),
                            'to': self._safe_node_id(to_id),
                            'type': 'contains',
                            'label': 'imports'
                        })

        # Class-method relationships
        if 'classes' in entities and 'functions' in entities:
            query = """
                MATCH (cls:Class)-[:CLASS_METHOD]->(method:Function)
                RETURN cls.id as from_id, method.id as to_id
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                from_id, to_id = row
                edges.append({
                    'from': self._safe_node_id(from_id),
                    'to': self._safe_node_id(to_id),
                    'type': 'contains',
                    'label': 'method'
                })

        # Function calls
        if show_calls and 'functions' in entities:
            query = """
                MATCH (caller:Function)-[:FUNCTION_CALLS]->(callee:Function)
                RETURN caller.id as from_id, callee.id as to_id
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                from_id, to_id = row
                edges.append({
                    'from': self._safe_node_id(from_id),
                    'to': self._safe_node_id(to_id),
                    'type': 'calls',
                    'label': 'calls'
                })

        # Inheritance relationships
        if show_inheritance and 'classes' in entities:
            query = """
                MATCH (child:Class)-[:INHERITS]->(parent:Class)
                RETURN child.id as from_id, parent.id as to_id
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                from_id, to_id = row
                edges.append({
                    'from': self._safe_node_id(from_id),
                    'to': self._safe_node_id(to_id),
                    'type': 'inherits',
                    'label': 'inherits'
                })

        # Parameter relationships
        if show_parameters and 'functions' in entities and 'parameters' in entities:
            query = """
                MATCH (func:Function)-[:HAS_PARAMETER]->(param:Parameter)
                RETURN func.id as from_id, param.id as to_id
            """
            result = self.conn.execute(query)
            while result.has_next():
                row = result.get_next()
                from_id, to_id = row
                edges.append({
                    'from': self._safe_node_id(from_id),
                    'to': self._safe_node_id(to_id),
                    'type': 'has_param',
                    'label': 'param'
                })

        # Symbol relationships
        if show_symbols and 'symbols' in entities:
            # Function declares symbols
            if 'functions' in entities:
                query = """
                    MATCH (func:Function)-[:DECLARES_SYMBOL]->(sym:Symbol)
                    RETURN func.id as from_id, sym.id as to_id
                """
                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    from_id, to_id = row
                    edges.append({
                        'from': self._safe_node_id(from_id),
                        'to': self._safe_node_id(to_id),
                        'type': 'declares',
                        'label': 'declares'
                    })

            # Assignment relationships
            if 'assignments' in entities:
                query = """
                    MATCH (assign:Assignment)-[:ASSIGNS_TO]->(sym:Symbol)
                    RETURN assign.id as from_id, sym.id as to_id
                """
                result = self.conn.execute(query)
                while result.has_next():
                    row = result.get_next()
                    from_id, to_id = row
                    edges.append({
                        'from': self._safe_node_id(from_id),
                        'to': self._safe_node_id(to_id),
                        'type': 'assigns',
                        'label': 'assigns'
                    })

        logger.info(f"Extracted {len(edges)} edges")
        return edges

    def _safe_node_id(self, node_id: str) -> str:
        """Convert node ID to a safe identifier for Graphviz."""
        # Replace problematic characters
        safe_id = str(node_id).replace(':', '_').replace('/', '_').replace('-', '_')
        safe_id = safe_id.replace('.', '_').replace(' ', '_').replace('\\', '_')
        # Ensure it starts with a letter or underscore
        if safe_id[0].isdigit():
            safe_id = f"n_{safe_id}"
        return safe_id

    def _escape_label(self, label: str) -> str:
        """Escape special characters in labels for Graphviz."""
        # Replace problematic characters for labels
        escaped = str(label).replace('"', '\\"').replace('\n', '\\n')
        return escaped

    def generate_graphviz(self, entities: List[str], output_file: str,
                         file_pattern: Optional[str] = None,
                         min_complexity: int = 0,
                         max_nodes: Optional[int] = None,
                         show_calls: bool = False,
                         show_inheritance: bool = False,
                         show_parameters: bool = False,
                         show_symbols: bool = False,
                         graph_title: str = "Code Graph") -> None:
        """Generate complete Graphviz DOT file."""

        # Filter files if pattern provided
        file_filter = None
        if file_pattern:
            file_filter = self.filter_files_by_pattern(file_pattern)
            if not file_filter:
                logger.warning(f"No files matched pattern: {file_pattern}")
                return

        # Get nodes and edges
        logger.info("Extracting nodes...")
        nodes = self.get_nodes(entities, file_filter, min_complexity, max_nodes)

        logger.info("Extracting edges...")
        edges = self.get_edges(entities, file_filter, show_calls, show_inheritance,
                             show_parameters, show_symbols)

        if not nodes:
            logger.warning("No nodes found matching criteria")
            return

        # Generate DOT content
        logger.info(f"Generating Graphviz DOT file: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f'digraph "{graph_title}" {{\n')
            f.write('  // Graph attributes\n')
            f.write('  rankdir=TB;\n')
            f.write('  concentrate=true;\n')
            f.write('  compound=true;\n')
            f.write('  overlap=false;\n')
            f.write('  splines=true;\n')
            f.write('  fontname="Arial";\n')
            f.write('  fontsize=14;\n')
            f.write(f'  label="{self._escape_label(graph_title)}\\n{len(nodes)} nodes, {len(edges)} edges";\n')
            f.write('  labelloc=top;\n')
            f.write('  labeljust=center;\n')
            f.write('\\n')

            # Write node styles
            for node_type, style in self.node_styles.items():
                if any(node['type'] == node_type for node in nodes):
                    f.write(f'  // {node_type.title()} node style\n')
                    style_parts = [f'{k}="{v}"' for k, v in style.items()]
                    f.write(f'  node [{", ".join(style_parts)}];\n')

                    # Write nodes of this type
                    for node in nodes:
                        if node['type'] == node_type:
                            f.write(f'  {node["id"]} [label="{node["label"]}"];\n')
                    f.write('\\n')

            # Write edges
            if edges:
                f.write('  // Relationships\n')
                for edge_type, style in self.edge_styles.items():
                    type_edges = [e for e in edges if e['type'] == edge_type]
                    if type_edges:
                        f.write(f'  // {edge_type.title()} relationships\n')
                        style_parts = [f'{k}="{v}"' for k, v in style.items()]
                        f.write(f'  edge [{", ".join(style_parts)}];\n')

                        for edge in type_edges:
                            label_attr = f' [label="{edge["label"]}"]' if edge.get('label') else ''
                            f.write(f'  {edge["from"]} -> {edge["to"]}{label_attr};\n')
                        f.write('\\n')

            f.write('}\\n')

        logger.info(f"Generated {output_file} with {len(nodes)} nodes and {len(edges)} edges")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert KuzuDB code graph to Graphviz DOT format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required arguments
    parser.add_argument('--db-path', '-d', default='./code_graph.kuzu',
                       help='Path to KuzuDB database (default: ./code_graph.kuzu)')
    parser.add_argument('--output', '-o',
                       help='Output DOT file path (required unless --stats is used)')

    # Filtering options
    parser.add_argument('--entities', '-e',
                       default='files,functions,classes',
                       help='Comma-separated list of entities to include: '
                            'files,functions,classes,imports,symbols,parameters,codeblocks '
                            '(default: files,functions,classes)')
    parser.add_argument('--filter-files', '-f',
                       help='File pattern to filter (e.g., "src/graph_sitter/*")')
    parser.add_argument('--min-complexity', '-c', type=int, default=0,
                       help='Minimum complexity for functions (default: 0)')
    parser.add_argument('--max-nodes', '-n', type=int,
                       help='Maximum number of nodes to include')

    # Relationship options
    parser.add_argument('--show-calls', action='store_true',
                       help='Show function call relationships')
    parser.add_argument('--show-inheritance', action='store_true',
                       help='Show class inheritance relationships')
    parser.add_argument('--show-parameters', action='store_true',
                       help='Show function parameter relationships')
    parser.add_argument('--show-symbols', action='store_true',
                       help='Show symbol declaration/assignment relationships')

    # Output options
    parser.add_argument('--title', '-t', default='Code Graph',
                       help='Graph title (default: Code Graph)')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics and exit')

    args = parser.parse_args()

    # Validate arguments
    if not args.stats and not args.output:
        parser.error("--output/-o is required unless --stats is specified")

    try:
        with CodeGraphVisualizer(args.db_path) as visualizer:
            if args.stats:
                stats = visualizer.get_database_stats()
                print("Database Statistics:")
                for entity, count in stats.items():
                    print(f"  {entity}: {count:,}")
                return

            # Parse entities
            entities = [e.strip() for e in args.entities.split(',')]
            valid_entities = {'files', 'functions', 'classes', 'imports',
                            'symbols', 'parameters', 'codeblocks', 'assignments'}
            entities = [e for e in entities if e in valid_entities]

            if not entities:
                logger.error("No valid entities specified")
                return

            logger.info(f"Generating graph for entities: {', '.join(entities)}")

            visualizer.generate_graphviz(
                entities=entities,
                output_file=args.output,
                file_pattern=args.filter_files,
                min_complexity=args.min_complexity,
                max_nodes=args.max_nodes,
                show_calls=args.show_calls,
                show_inheritance=args.show_inheritance,
                show_parameters=args.show_parameters,
                show_symbols=args.show_symbols,
                graph_title=args.title
            )

            print(f"\\nGraphviz DOT file generated: {args.output}")
            print("\\nTo render as image, use:")
            print(f"  dot -Tpng {args.output} -o {args.output.replace('.dot', '.png')}")
            print(f"  dot -Tsvg {args.output} -o {args.output.replace('.dot', '.svg')}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()