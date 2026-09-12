#!/usr/bin/env python3
"""
Commands to run:
  python buildapp.py --mode all
  python buildapp.py --mode all --build
  python buildapp.py --mode changed
  python buildapp.py --mode changed --build
  python buildapp.py --mode changed --base main
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

# Product order is only a stable display tie-breaker. Actual ordering is
# calculated from the dependency graph.
PRODUCTS = [
    "catalog",
    "customer",
    "security",
    "thirdparty",
    "orders",
    "payment",
    "shipping",
    "notification",
    "reporting",
]

PRODUCT_INDEX = {name: i for i, name in enumerate(PRODUCTS)}


def stable_key(name: str):
    return (PRODUCT_INDEX.get(name, 999), name)


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout


def git_available() -> bool:
    try:
        run_git(["rev-parse", "--show-toplevel"])
        return True
    except RuntimeError:
        return False


def parse_manifest(path: Path) -> tuple[str | None, list[str], list[str], list[str]]:
    """Return symbolic name, exports, imports, required bundles."""
    text = path.read_text(encoding="utf-8")

    # OSGi manifest continuation lines begin with whitespace.
    logical_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and logical_lines:
            logical_lines[-1] += line.strip()
        else:
            logical_lines.append(line.strip())

    headers: dict[str, str] = {}
    for line in logical_lines:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

    symbolic = headers.get("Bundle-SymbolicName", "").split(";", 1)[0].strip() or None

    def parse_clause_names(value: str) -> list[str]:
        names: list[str] = []
        for clause in value.split(","):
            clause = clause.strip()
            if not clause:
                continue
            name = clause.split(";", 1)[0].strip()
            if name:
                names.append(name)
        return names

    exports = parse_clause_names(headers.get("Export-Package", ""))
    imports = parse_clause_names(headers.get("Import-Package", ""))
    required = parse_clause_names(headers.get("Require-Bundle", ""))
    return symbolic, exports, imports, required


def parse_feature(path: Path) -> tuple[str | None, list[str], list[str]]:
    """Return feature id, plugin IDs, required feature IDs."""
    root = ET.parse(path).getroot()
    feature_id = root.attrib.get("id")
    plugins: list[str] = []
    required_features: list[str] = []

    for child in root:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "plugin":
            plugin_id = child.attrib.get("id")
            if plugin_id:
                plugins.append(plugin_id)
        elif tag == "requires":
            for item in child:
                item_tag = item.tag.rsplit("}", 1)[-1]
                if item_tag == "import":
                    feature = item.attrib.get("feature")
                    if feature:
                        required_features.append(feature)

    return feature_id, plugins, required_features


def discover_products() -> dict[str, dict]:
    """Discover the repository's product components and OSGi metadata."""
    products: dict[str, dict] = {}

    for product_dir in sorted(
        p for p in ROOT.iterdir() if p.is_dir() and (p / "pom.xml").exists()
    ):
        product = product_dir.name
        if product not in PRODUCTS:
            continue

        bundles: dict[str, dict] = {}
        features: dict[str, dict] = {}

        for manifest in product_dir.glob("plugins/*/META-INF/MANIFEST.MF"):
            symbolic, exports, imports, required = parse_manifest(manifest)
            if symbolic:
                bundles[symbolic] = {
                    "path": manifest.parent.parent,
                    "manifest": manifest,
                    "exports": exports,
                    "imports": imports,
                    "requires": required,
                }

        for feature_xml in product_dir.glob("features/*/feature.xml"):
            feature_id, plugins, required_features = parse_feature(feature_xml)
            if feature_id:
                features[feature_id] = {
                    "path": feature_xml.parent,
                    "feature_xml": feature_xml,
                    "plugins": plugins,
                    "requires": required_features,
                }

        products[product] = {
            "path": product_dir,
            "bundles": bundles,
            "features": features,
        }

    return products


def build_product_graph(products: dict[str, dict]) -> dict[str, set[str]]:
    """Build product -> dependency-products graph.

    graph[A] contains products that A depends on.
    """
    graph: dict[str, set[str]] = {p: set() for p in products}

    bundle_to_product: dict[str, str] = {}
    package_to_products: dict[str, set[str]] = defaultdict(set)
    feature_to_product: dict[str, str] = {}

    for product, info in products.items():
        for bundle, bundle_info in info["bundles"].items():
            bundle_to_product[bundle] = product
            for package in bundle_info["exports"]:
                package_to_products[package].add(product)

        for feature in info["features"]:
            feature_to_product[feature] = product

    # Bundle-level dependencies.
    for product, info in products.items():
        for bundle_info in info["bundles"].values():
            for required_bundle in bundle_info["requires"]:
                dependency_product = bundle_to_product.get(required_bundle)
                if dependency_product and dependency_product != product:
                    graph[product].add(dependency_product)

            for imported_package in bundle_info["imports"]:
                for dependency_product in package_to_products.get(imported_package, set()):
                    if dependency_product != product:
                        graph[product].add(dependency_product)

    # Feature-level dependencies.
    for product, info in products.items():
        for feature_info in info["features"].values():
            for required_feature in feature_info["requires"]:
                dependency_product = feature_to_product.get(required_feature)
                if dependency_product and dependency_product != product:
                    graph[product].add(dependency_product)

    return graph


def reverse_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse = {p: set() for p in graph}
    for product, dependencies in graph.items():
        for dependency in dependencies:
            reverse.setdefault(dependency, set()).add(product)
    return reverse


def topo_sort(graph: dict[str, set[str]], selected: set[str] | None = None) -> list[str]:
    """Topologically sort products. graph[node] = dependencies of node."""
    nodes = set(selected if selected is not None else graph.keys())
    indegree = {
        node: sum(1 for dep in graph.get(node, set()) if dep in nodes)
        for node in nodes
    }

    dependents = {node: set() for node in nodes}
    for node in nodes:
        for dep in graph.get(node, set()):
            if dep in nodes:
                dependents[dep].add(node)

    queue = deque(sorted((n for n in nodes if indegree[n] == 0), key=stable_key))
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for dependent in sorted(dependents[node], key=stable_key):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(nodes):
        cycle_nodes = sorted(nodes - set(order), key=stable_key)
        raise RuntimeError(
            "Dependency cycle detected involving: " + ", ".join(cycle_nodes)
        )

    return order


def print_product_graph(graph: dict[str, set[str]], selected: set[str] | None = None, title: str = "DEPENDENCY GRAPH"):
    nodes = set(selected if selected is not None else graph.keys())
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print("Direction: DEPENDENT  --->  DEPENDENCY")
    print()

    for product in sorted(nodes, key=stable_key):
        deps = sorted(graph.get(product, set()) & nodes, key=stable_key)
        if deps:
            for dep in deps:
                print(f"  {product:<14} ---> {dep}")
        else:
            print(f"  {product:<14} ---> (none)")


def print_dependency_paths(changed: set[str], graph: dict[str, set[str]]):
    """Print paths from each changed product through all dependents."""
    reverse = reverse_graph(graph)

    print("\n" + "=" * 72)
    print("DEPENDENCY PATHS FROM CHANGED PRODUCTS")
    print("=" * 72)
    print("Direction: CHANGED PRODUCT  --->  PRODUCT THAT MUST BE REBUILT")

    for start in sorted(changed, key=stable_key):
        print(f"\n[{start}]")
        seen: set[str] = set()

        def walk(node: str, path: list[str]):
            for dependent in sorted(reverse.get(node, set()), key=stable_key):
                if dependent in seen:
                    continue
                seen.add(dependent)
                new_path = path + [dependent]
                print("  " + " -> ".join(new_path))
                walk(dependent, new_path)

        walk(start, [start])
        if not seen:
            print("  No dependent products")


def git_changed_files(base: str | None = None) -> list[str]:
    """Return changed paths.

    Without --base:
      - includes staged + unstaged working-tree changes
      - if working tree is clean, compares HEAD~1..HEAD

    With --base:
      - compares <base>..HEAD plus working-tree changes
    """
    paths: set[str] = set()

    if base:
        output = run_git(["diff", "--name-only", f"{base}..HEAD"])
        paths.update(x.strip() for x in output.splitlines() if x.strip())
    else:
        # Unstaged changes.
        output = run_git(["diff", "--name-only"])
        paths.update(x.strip() for x in output.splitlines() if x.strip())

        # Staged changes.
        output = run_git(["diff", "--cached", "--name-only"])
        paths.update(x.strip() for x in output.splitlines() if x.strip())

        # Untracked files.
        output = run_git(["status", "--porcelain"])
        for line in output.splitlines():
            if len(line) >= 3 and line[:2] == "??":
                paths.add(line[3:].strip())

        if not paths:
            try:
                output = run_git(["diff", "--name-only", "HEAD~1", "HEAD"])
                paths.update(x.strip() for x in output.splitlines() if x.strip())
            except RuntimeError:
                # Repository may contain only one commit.
                pass

    return sorted(paths)


def changed_products(
    changed_files: list[str],
    products: dict[str, dict],
) -> tuple[set[str], bool]:
    """Map changed paths to products. Return (products, full_build_required)."""
    changed: set[str] = set()
    full_build = False

    product_dirs = {p: info["path"].relative_to(ROOT).as_posix() for p, info in products.items()}

    for raw in changed_files:
        normalized = raw.replace("\\", "/").lstrip("./")

        # Root build metadata affects the whole reactor.
        if normalized in {"pom.xml", "buildapp.py"}:
            if normalized == "pom.xml":
                full_build = True
            continue

        # A root README change is documentation only.
        if normalized in {"README.md"}:
            continue

        # Anything under a product belongs to that product.
        matched = False
        for product, rel_dir in product_dirs.items():
            if normalized == rel_dir or normalized.startswith(rel_dir + "/"):
                changed.add(product)
                matched = True
                break

        if not matched and normalized:
            # Unknown repository-level build/config files are conservatively
            # treated as full-build triggers.
            full_build = True

    return changed, full_build


def print_changed_files(files: list[str]):
    print("\n" + "=" * 72)
    print("DETECTED CHANGED FILES")
    print("=" * 72)
    if not files:
        print("  No changed files detected.")
    else:
        for f in files:
            print(f"  - {f}")


def print_product_inventory(products: dict[str, dict]):
    print("\n" + "=" * 72)
    print("DISCOVERED NORTHWIND PRODUCTS")
    print("=" * 72)
    for product in sorted(products, key=stable_key):
        bundles = sorted(products[product]["bundles"])
        features = sorted(products[product]["features"])
        print(f"\n  {product}")
        print(f"    bundles : {', '.join(bundles) if bundles else '(none)'}")
        print(f"    features: {', '.join(features) if features else '(none)'}")


def print_build_order(order: list[str]):
    print("\n" + "=" * 72)
    print("BUILD ORDER")
    print("=" * 72)
    for i, product in enumerate(order, 1):
        print(f"  {i:02d}. {product}")
    print(f"\nTotal products selected: {len(order)}")


def build_products(order: list[str]):
    print("\n" + "=" * 72)
    print("EXECUTING TYCHO BUILD")
    print("=" * 72)
    print("Each selected product is built as a Maven reactor (-pl <product> -am).")

    for i, product in enumerate(order, 1):
        print("\n" + "-" * 72)
        print(f"BUILD [{i}/{len(order)}] : {product}")
        print("-" * 72)

        command = [
            "mvn",
            "-B",
            "-pl",
            product,
            "-am",
            "clean",
            "install",
            "-DskipTests",
        ]
        print("$ " + " ".join(command))
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            print(f"\nERROR: Build failed for product '{product}'.")
            sys.exit(result.returncode)

    print("\n" + "=" * 72)
    print("BUILD COMPLETED SUCCESSFULLY")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Northwind OMS smart OSGi/Tycho build")
    parser.add_argument(
        "--mode",
        choices=["all", "changed"],
        default="changed",
        help="Build all products or only changed/affected products (default: changed)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Actually run Maven. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--base",
        help="Git base revision for changed mode, e.g. main or origin/main",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("NORTHWIND OMS - SMART OSGi BUILD PIPELINE")
    print("=" * 72)
    print(f"Repository : {ROOT}")
    print(f"Mode       : {args.mode}")
    print(f"Execution  : {'BUILD' if args.build else 'DRY RUN'}")

    if not git_available() and args.mode == "changed":
        print("\nERROR: changed mode requires a Git repository.")
        print("Run this script from a cloned Git repository.")
        return 2

    products = discover_products()
    missing = [p for p in PRODUCTS if p not in products]
    if missing:
        print("\nWARNING: Expected products not found: " + ", ".join(missing))

    print_product_inventory(products)

    graph = build_product_graph(products)
    print_product_graph(graph, title="FULL PRODUCT DEPENDENCY GRAPH")

    if args.mode == "all":
        selected = set(products)
        order = topo_sort(graph, selected)
        print_build_order(order)

        if args.build:
            build_products(order)
        else:
            print("\nDRY RUN: Maven was not executed. Add --build to execute it.")
        return 0

    changed_files = git_changed_files(args.base)
    print_changed_files(changed_files)

    changed, full_build = changed_products(changed_files, products)

    if full_build:
        print("\nROOT-LEVEL BUILD CONFIGURATION CHANGED")
        print("A full build is required because reactor/build metadata changed.")
        selected = set(products)
        order = topo_sort(graph, selected)
        print_product_graph(graph, selected, "FULL BUILD GRAPH (REQUIRED)")
        print_build_order(order)
        if args.build:
            build_products(order)
        else:
            print("\nDRY RUN: Maven was not executed. Add --build to execute it.")
        return 0

    if not changed:
        print("\nNo product source/feature/plugin changes detected.")
        print("Nothing needs to be rebuilt.")
        return 0

    print("\n" + "=" * 72)
    print("CHANGED PRODUCTS")
    print("=" * 72)
    for product in sorted(changed, key=stable_key):
        print(f"  [CHANGED] {product}")

    reverse = reverse_graph(graph)
    selected = set(changed)
    queue = deque(sorted(changed, key=stable_key))

    while queue:
        current = queue.popleft()
        for dependent in sorted(reverse.get(current, set()), key=stable_key):
            if dependent not in selected:
                selected.add(dependent)
                queue.append(dependent)

    print("\n" + "=" * 72)
    print("PRODUCTS SELECTED FOR REBUILD")
    print("=" * 72)
    for product in sorted(selected, key=stable_key):
        marker = "CHANGED" if product in changed else "DEPENDENT"
        print(f"  [{marker:<9}] {product}")

    print_dependency_paths(changed, graph)
    print_product_graph(graph, selected, "CHANGED-MODULES PRODUCT DEPENDENCY GRAPH")

    order = topo_sort(graph, selected)
    print_build_order(order)

    if args.build:
        build_products(order)
    else:
        print("\nDRY RUN: Maven was not executed. Add --build to execute it.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(1)
