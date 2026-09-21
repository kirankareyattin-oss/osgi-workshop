#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PRODUCTS = ["catalog", "customer", "security", "thirdparty", "orders", "payment", "shipping", "notification", "reporting"]
PRODUCT_INDEX = {name: i for i, name in enumerate(PRODUCTS)}

def stable_key(name: str):
    return (PRODUCT_INDEX.get(name, 999), name)

def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    text = path.read_text(encoding="utf-8")
    logical_lines = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and logical_lines:
            logical_lines[-1] += line.strip()
        else:
            logical_lines.append(line.strip())
    headers = {}
    for line in logical_lines:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    symbolic = headers.get("Bundle-SymbolicName", "").split(";", 1)[0].strip() or None
    def clause_names(value: str) -> list[str]:
        result = []
        for clause in value.split(","):
            name = clause.split(";", 1)[0].strip()
            if name:
                result.append(name)
        return result
    return symbolic, clause_names(headers.get("Export-Package", "")), clause_names(headers.get("Import-Package", "")), clause_names(headers.get("Require-Bundle", ""))

def parse_feature(path: Path) -> tuple[str | None, list[str], list[str]]:
    root = ET.parse(path).getroot()
    feature_id = root.attrib.get("id")
    plugins = []
    required_features = []
    for child in root:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "plugin":
            plugin_id = child.attrib.get("id")
            if plugin_id:
                plugins.append(plugin_id)
        elif tag == "requires":
            for item in child:
                if item.tag.rsplit("}", 1)[-1] == "import":
                    feature = item.attrib.get("feature")
                    if feature:
                        required_features.append(feature)
    return feature_id, plugins, required_features

def discover_products() -> dict[str, dict]:
    products = {}
    for product_dir in sorted(ROOT.iterdir()):
        if not product_dir.is_dir() or not (product_dir / "pom.xml").exists():
            continue
        product = product_dir.name
        if product not in PRODUCTS:
            continue
        bundles = {}
        features = {}
        for manifest in product_dir.glob("plugins/*/META-INF/MANIFEST.MF"):
            symbolic, exports, imports, required = parse_manifest(manifest)
            if symbolic:
                bundles[symbolic] = {"path": manifest.parent.parent, "manifest": manifest, "exports": exports, "imports": imports, "requires": required}
        for feature_xml in product_dir.glob("features/*/feature.xml"):
            feature_id, plugins, required_features = parse_feature(feature_xml)
            if feature_id:
                features[feature_id] = {"path": feature_xml.parent, "feature_xml": feature_xml, "plugins": plugins, "requires": required_features}
        products[product] = {"path": product_dir, "bundles": bundles, "features": features}
    return products

def build_product_graph(products: dict[str, dict]) -> dict[str, set[str]]:
    graph = {p: set() for p in products}
    bundle_to_product = {}
    package_to_products = defaultdict(set)
    feature_to_product = {}
    for product, info in products.items():
        for bundle, bundle_info in info["bundles"].items():
            bundle_to_product[bundle] = product
            for package in bundle_info["exports"]:
                package_to_products[package].add(product)
        for feature in info["features"]:
            feature_to_product[feature] = product
    for product, info in products.items():
        for bundle_info in info["bundles"].values():
            for required_bundle in bundle_info["requires"]:
                dependency = bundle_to_product.get(required_bundle)
                if dependency and dependency != product:
                    graph[product].add(dependency)
            for imported_package in bundle_info["imports"]:
                for dependency in package_to_products.get(imported_package, set()):
                    if dependency != product:
                        graph[product].add(dependency)
        for feature_info in info["features"].values():
            for required_feature in feature_info["requires"]:
                dependency = feature_to_product.get(required_feature)
                if dependency and dependency != product:
                    graph[product].add(dependency)
    return graph

def reverse_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse = {p: set() for p in graph}
    for product, dependencies in graph.items():
        for dependency in dependencies:
            reverse.setdefault(dependency, set()).add(product)
    return reverse

def topo_sort(graph: dict[str, set[str]], selected: set[str] | None = None) -> list[str]:
    nodes = set(selected if selected is not None else graph.keys())
    indegree = {n: sum(1 for d in graph.get(n, set()) if d in nodes) for n in nodes}
    dependents = {n: set() for n in nodes}
    for node in nodes:
        for dep in graph.get(node, set()):
            if dep in nodes:
                dependents[dep].add(node)
    queue = deque(sorted((n for n in nodes if indegree[n] == 0), key=stable_key))
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for dependent in sorted(dependents[node], key=stable_key):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    if len(order) != len(nodes):
        cycle_nodes = sorted(nodes - set(order), key=stable_key)
        raise RuntimeError("Dependency cycle detected: " + ", ".join(cycle_nodes))
    return order

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

def print_product_graph(graph: dict[str, set[str]], selected: set[str] | None = None, title: str = "DEPENDENCY GRAPH"):
    nodes = set(selected if selected is not None else graph.keys())
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print("Direction: DEPENDENCY -> DEPENDENT")
    print("Example: core -> inventory means inventory depends on core.\n")
    for product in sorted(nodes, key=stable_key):
        deps = sorted(graph.get(product, set()) & nodes, key=stable_key)
        if deps:
            for dep in deps:
                print(f"  {dep:<14} -> {product}")
        else:
            print(f"  {product:<14} -> (none)")

def get_dependency_paths(changed: set[str], graph: dict[str, set[str]]) -> dict[str, list[list[str]]]:
    reverse = reverse_graph(graph)
    result = {}
    for start in sorted(changed, key=stable_key):
        paths = []
        def walk(node: str, path: list[str]):
            dependents = sorted(reverse.get(node, set()), key=stable_key)
            if not dependents:
                if len(path) > 1:
                    paths.append(path)
                return
            for dependent in dependents:
                if dependent not in path:
                    walk(dependent, path + [dependent])
        walk(start, [start])
        result[start] = paths
    return result

def print_dependency_paths(changed: set[str], graph: dict[str, set[str]]):
    print("\n" + "=" * 72)
    print("DEPENDENCY PATHS FROM CHANGED PRODUCTS")
    print("=" * 72)
    print("Direction: CHANGED PRODUCT -> PRODUCT THAT MUST BE REBUILT")
    paths_by_product = get_dependency_paths(changed, graph)
    for start in sorted(changed, key=stable_key):
        print(f"\n[{start}]")
        paths = paths_by_product.get(start, [])
        if paths:
            for path in paths:
                print("  " + " -> ".join(path))
        else:
            print("  No dependent products")

def git_changed_files(base: str | None = None) -> list[str]:
    paths = set()
    if base:
        output = run_git(["diff", "--name-only", f"{base}..HEAD"])
        paths.update(x.strip() for x in output.splitlines() if x.strip())
    else:
        paths.update(x.strip() for x in run_git(["diff", "--name-only"]).splitlines() if x.strip())
        paths.update(x.strip() for x in run_git(["diff", "--cached", "--name-only"]).splitlines() if x.strip())
        for line in run_git(["status", "--porcelain"]).splitlines():
            if line.startswith("??"):
                paths.add(line[3:].strip())
        if not paths:
            try:
                paths.update(x.strip() for x in run_git(["diff", "--name-only", "HEAD~1", "HEAD"]).splitlines() if x.strip())
            except RuntimeError:
                pass
    return sorted(paths)

def changed_products(changed_files: list[str], products: dict[str, dict]) -> tuple[set[str], bool]:
    changed = set()
    full_build = False
    product_dirs = {p: info["path"].relative_to(ROOT).as_posix() for p, info in products.items()}
    for raw in changed_files:
        normalized = raw.replace("\\", "/").lstrip("./")
        if normalized == "pom.xml":
            full_build = True
            continue
        if normalized in {"README.md", "buildapp.py"}:
            continue
        matched = False
        for product, rel_dir in product_dirs.items():
            if normalized == rel_dir or normalized.startswith(rel_dir + "/"):
                changed.add(product)
                matched = True
                break
        if not matched and normalized:
            full_build = True
    return changed, full_build

def print_changed_files(files: list[str]):
    print("\n" + "=" * 72)
    print("DETECTED CHANGED FILES")
    print("=" * 72)
    if not files:
        print("  No changed files detected.")
    else:
        for path in files:
            print(f"  - {path}")

def print_build_order(order: list[str]):
    print("\n" + "=" * 72)
    print("BUILD ORDER")
    print("=" * 72)
    for index, product in enumerate(order, 1):
        print(f"  {index:02d}. {product}")
    print(f"\nTotal products selected: {len(order)}")

def build_products(order: list[str]) -> bool:
    print("\n" + "=" * 72)
    print("EXECUTING TYCHO BUILD")
    print("=" * 72)
    mvn_check = subprocess.run(["mvn", "-version"], cwd=ROOT, text=True)
    if mvn_check.returncode != 0:
        print("\nERROR: Maven is not available on PATH.")
        return False
    for index, product in enumerate(order, 1):
        print("\n" + "-" * 72)
        print(f"BUILD [{index}/{len(order)}] : {product}")
        print("-" * 72)
        pom_path = ROOT / product / "pom.xml"
        if not pom_path.exists():
            print(f"ERROR: POM not found for product '{product}': {pom_path}")
            return False
        command = ["mvn", "-B", "-f", f"{product}/pom.xml", "clean", "install", "-DskipTests"]
        print("Working directory:", ROOT)
        print("POM:", pom_path)
        print("$ " + " ".join(command))
        result = subprocess.run(command, cwd=ROOT, text=True)
        print(f"Maven exit code for {product}: {result.returncode}")
        if result.returncode != 0:
            print(f"\nERROR: Build failed for product '{product}'.")
            return False
        print(f"BUILD SUCCESS: {product}")
        targets = list((ROOT / product).rglob("target"))
        if targets:
            print("Target directories created:")
            for target in targets:
                print("  " + target.relative_to(ROOT).as_posix())
        else:
            print(f"WARNING: Maven succeeded but no target directory was found under {product}")
    print("\n" + "=" * 72)
    print("BUILD COMPLETED SUCCESSFULLY")
    print("=" * 72)
    return True

def collect_build_artifacts(selected: set[str] | None = None) -> list[tuple[str, int]]:
    artifacts = []
    extensions = {".jar", ".zip", ".war", ".ear"}
    selected_prefixes = {f"{product}/" for product in selected} if selected else set()
    for artifact in ROOT.rglob("*"):
        if not artifact.is_file() or artifact.suffix.lower() not in extensions:
            continue
        relative = artifact.relative_to(ROOT).as_posix()
        if ".git/" in relative or "target" not in artifact.parts:
            continue
        if selected_prefixes and not any(relative.startswith(prefix) for prefix in selected_prefixes):
            continue
        artifacts.append((relative, artifact.stat().st_size))
    return sorted(set(artifacts))

def safe_mermaid_id(product: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", product)

def write_mermaid_graph(file, graph: dict[str, set[str]], changed: set[str], selected: set[str]):
    file.write("```mermaid\n")
    file.write("flowchart TD\n")
    for product in sorted(graph, key=stable_key):
        node_id = safe_mermaid_id(product)
        if product in changed:
            label = f"{product}<br/>CHANGED"
        elif product in selected:
            label = f"{product}<br/>REBUILD"
        else:
            label = product
        file.write(f'    {node_id}["{label}"]\n')
    for product in sorted(graph, key=stable_key):
        for dependency in sorted(graph.get(product, set()), key=stable_key):
            file.write(f"    {safe_mermaid_id(dependency)} --> {safe_mermaid_id(product)}\n")
    file.write("```\n\n")

def write_github_summary(mode: str, changed: set[str], selected: set[str], order: list[str], graph: dict[str, set[str]], status: str):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write("# Northwind OMS Smart Build\n\n")
        f.write("## Build Status\n\n")
        f.write(f"**Status:** {status}\n\n")
        f.write(f"**Build Mode:** `{mode}`\n\n")
        if mode == "changed":
            f.write("## Changed Products\n\n")
            if changed:
                for product in sorted(changed, key=stable_key):
                    f.write(f"- `{product}`\n")
            else:
                f.write("- None\n")
            f.write("\n")
        f.write("## OSGi Product Dependency Graph\n\n")
        f.write("**Graph direction:** `A --> B` means **B depends on A**.\n\n")
        write_mermaid_graph(f, graph, changed, selected)
        if mode == "changed" and changed:
            f.write("## Dependency Paths for Changed Products\n\n")
            paths_by_product = get_dependency_paths(changed, graph)
            for start in sorted(changed, key=stable_key):
                f.write(f"### `{start}`\n\n")
                paths = paths_by_product.get(start, [])
                if paths:
                    for path in paths:
                        f.write("- " + " -> ".join(f"`{item}`" for item in path) + "\n")
                else:
                    f.write("- No dependent products\n")
                f.write("\n")
        if mode == "changed":
            f.write("## Products Selected for Rebuild\n\n")
            if selected:
                for product in sorted(selected, key=stable_key):
                    marker = "CHANGED" if product in changed else "DEPENDENT"
                    f.write(f"- `{product}` ({marker})\n")
            else:
                f.write("- None\n")
            f.write("\n")
        f.write("## Artifacts\n\n")
        artifacts = collect_build_artifacts()
        if artifacts:
            f.write("| Artifact | Size |\n|---|---:|\n")
            for artifact, size in artifacts:
                if size >= 1024 * 1024:
                    display_size = f"{size / (1024 * 1024):.2f} MB"
                elif size >= 1024:
                    display_size = f"{size / 1024:.1f} KB"
                else:
                    display_size = f"{size} B"
                f.write(f"| `{artifact}` | {display_size} |\n")
        else:
            f.write("No build artifacts found.\n")
        f.write("\n## Build Order\n\n")
        if order:
            for index, product in enumerate(order, 1):
                f.write(f"{index}. `{product}`\n")
        else:
            f.write("No products selected.\n")
        f.write("\n")
        f.write(f"**Total products:** {len(order)}\n")

def main() -> int:
    parser = argparse.ArgumentParser(description="Northwind OMS smart OSGi/Tycho build")
    parser.add_argument("--mode", choices=["all", "changed"], default="changed")
    parser.add_argument("--build", action="store_true", help="Run Maven instead of dry run")
    parser.add_argument("--base", help="Git base revision for changed mode")
    args = parser.parse_args()
    print("=" * 72)
    print("NORTHWIND OMS - SMART OSGi BUILD PIPELINE")
    print("=" * 72)
    print(f"Repository : {ROOT}")
    print(f"Mode       : {args.mode}")
    print(f"Execution  : {'BUILD' if args.build else 'DRY RUN'}")
    if args.mode == "changed" and not git_available():
        print("\nERROR: changed mode requires a Git repository.")
        return 2
    products = discover_products()
    missing = [p for p in PRODUCTS if p not in products]
    if missing:
        print("\nWARNING: Expected products not found: " + ", ".join(missing))
    print_product_inventory(products)
    graph = build_product_graph(products)
    if args.mode == "all":
        selected = set(products)
        order = topo_sort(graph, selected)
        print_product_graph(graph, selected, "FULL PRODUCT DEPENDENCY GRAPH")
        print_build_order(order)
        status = "DRY RUN"
        if args.build:
            status = "SUCCESS" if build_products(order) else "FAILED"
        else:
            print("\nDRY RUN: Maven was not executed. Add --build to execute it.")
        write_github_summary(args.mode, set(), selected, order, graph, status)
        return 0 if status != "FAILED" else 1
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
        status = "DRY RUN"
        if args.build:
            status = "SUCCESS" if build_products(order) else "FAILED"
        else:
            print("\nDRY RUN: Maven was not executed. Add --build to execute it.")
        write_github_summary(args.mode, changed, selected, order, graph, status)
        return 0 if status != "FAILED" else 1
    if not changed:
        print("\nNo product source, feature, or plugin changes detected.")
        print("Nothing needs to be rebuilt.")
        write_github_summary(args.mode, set(), set(), [], graph, "NO CHANGES")
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
    print_product_graph(graph, None, "COMPLETE PRODUCT DEPENDENCY GRAPH")
    order = topo_sort(graph, selected)
    print_build_order(order)
    status = "DRY RUN"
    if args.build:
        status = "SUCCESS" if build_products(order) else "FAILED"
    else:
        print("\nDRY RUN: Maven was not executed. Add --build to execute it.")
    write_github_summary(args.mode, changed, selected, order, graph, status)
    return 0 if status != "FAILED" else 1

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(1)