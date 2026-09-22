#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import re
import subprocess
from collections import defaultdict,deque
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
PRODUCTS=["catalog","customer","security","thirdparty","orders","payment","shipping","notification","reporting"]
PRODUCT_INDEX={name:i for i,name in enumerate(PRODUCTS)}

def parse_manifest(path:Path)->dict:
    text=path.read_text(encoding="utf-8")
    logical=[]
    for line in text.splitlines():
        if line.startswith((" ","\t")) and logical:
            logical[-1]+=line[1:]
        else:
            logical.append(line)
    headers={}
    for line in logical:
        if ":" in line:
            key,value=line.split(":",1)
            headers[key.strip()]=value.strip()
    def clause_names(value:str)->list[str]:
        result=[]
        current=[]
        quoted=False
        escaped=False
        for char in value:
            if escaped:
                current.append(char)
                escaped=False
                continue
            if char=="\\":
                current.append(char)
                escaped=True
                continue
            if char=='"':
                quoted=not quoted
                current.append(char)
                continue
            if char=="," and not quoted:
                name="".join(current).split(";",1)[0].strip()
                if name:
                    result.append(name)
                current=[]
            else:
                current.append(char)
        name="".join(current).split(";",1)[0].strip()
        if name:
            result.append(name)
        return result
    symbolic=headers.get("Bundle-SymbolicName","").split(";",1)[0].strip()
    return {"symbolic":symbolic or None,"exports":clause_names(headers.get("Export-Package","")),"imports":clause_names(headers.get("Import-Package","")),"requires":clause_names(headers.get("Require-Bundle",""))}

def parse_feature(path:Path)->dict:
    root=ET.parse(path).getroot()
    feature_id=root.attrib.get("id")
    plugins=[]
    required_features=[]
    for child in root:
        tag=child.tag.rsplit("}",1)[-1]
        if tag=="plugin":
            plugin_id=child.attrib.get("id")
            if plugin_id:
                plugins.append(plugin_id)
        elif tag=="requires":
            for item in child:
                if item.tag.rsplit("}",1)[-1]=="import":
                    feature=item.attrib.get("feature")
                    if feature:
                        required_features.append(feature)
    return {"feature_id":feature_id,"plugins":plugins,"requires":required_features}

def discover_osgi_modules()->dict[str,dict]:
    modules={}
    for product in PRODUCTS:
        product_dir=ROOT/product
        if not product_dir.is_dir():
            continue
        for manifest in sorted(product_dir.glob("plugins/*/META-INF/MANIFEST.MF")):
            data=parse_manifest(manifest)
            symbolic=data["symbolic"]
            if not symbolic:
                continue
            if symbolic in modules:
                raise RuntimeError(f"Duplicate OSGi bundle symbolic name: {symbolic}")
            modules[symbolic]={"id":symbolic,"kind":"bundle","product":product,"path":manifest.parent.parent,"manifest":manifest,"exports":data["exports"],"imports":data["imports"],"requires":data["requires"],"plugins":[],"feature_requires":[]}
        for feature_xml in sorted(product_dir.glob("features/*/feature.xml")):
            data=parse_feature(feature_xml)
            feature_id=data["feature_id"]
            if not feature_id:
                continue
            if feature_id in modules:
                raise RuntimeError(f"Duplicate OSGi module id: {feature_id}")
            modules[feature_id]={"id":feature_id,"kind":"feature","product":product,"path":feature_xml.parent,"feature_xml":feature_xml,"exports":[],"imports":[],"requires":[],"plugins":data["plugins"],"feature_requires":data["requires"]}
    return modules

def module_key(node,modules):
    info=modules[node]
    return (PRODUCT_INDEX.get(info["product"],999),0 if info["kind"]=="bundle" else 1,node)

def module_label(node,modules):
    return f"{modules[node]['product']}/{node}"

def build_osgi_graph(modules):
    graph={node:set() for node in modules}
    bundles={node:node for node,info in modules.items() if info["kind"]=="bundle"}
    features={node:node for node,info in modules.items() if info["kind"]=="feature"}
    exporters=defaultdict(set)
    for node,info in modules.items():
        if info["kind"]=="bundle":
            for package in info["exports"]:
                exporters[package].add(node)
    for node,info in modules.items():
        if info["kind"]=="bundle":
            for required in info["requires"]:
                dependency=bundles.get(required)
                if dependency and dependency!=node:
                    graph[node].add(dependency)
            for imported in info["imports"]:
                for dependency in sorted(exporters.get(imported,set())):
                    if dependency!=node:
                        graph[node].add(dependency)
        else:
            for plugin in info["plugins"]:
                dependency=bundles.get(plugin)
                if dependency and dependency!=node:
                    graph[node].add(dependency)
            for required in info["feature_requires"]:
                dependency=features.get(required)
                if dependency and dependency!=node:
                    graph[node].add(dependency)
    return graph

def reverse_graph(graph):
    reverse={node:set() for node in graph}
    for node,deps in graph.items():
        for dependency in deps:
            reverse.setdefault(dependency,set()).add(node)
    return reverse

def topo_sort(graph,modules,selected=None):
    nodes=set(selected if selected is not None else graph.keys())
    indegree={node:sum(1 for dep in graph.get(node,set()) if dep in nodes) for node in nodes}
    dependents={node:set() for node in nodes}
    for node in nodes:
        for dependency in graph.get(node,set()):
            if dependency in nodes:
                dependents[dependency].add(node)
    queue=deque(sorted((n for n in nodes if indegree[n]==0),key=lambda n:module_key(n,modules)))
    order=[]
    while queue:
        node=queue.popleft()
        order.append(node)
        for dependent in sorted(dependents[node],key=lambda n:module_key(n,modules)):
            indegree[dependent]-=1
            if indegree[dependent]==0:
                queue.append(dependent)
    if len(order)!=len(nodes):
        raise RuntimeError("OSGi dependency cycle detected: "+", ".join(sorted(nodes-set(order))))
    return order

def run_git(args):
    result=subprocess.run(["git",*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode!=0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout

def git_available():
    try:
        run_git(["rev-parse","--show-toplevel"])
        return True
    except RuntimeError:
        return False

def git_changed_files(base=None):
    paths=set()
    if base:
        paths.update(x.strip() for x in run_git(["diff","--name-only",f"{base}..HEAD"]).splitlines() if x.strip())
    else:
        paths.update(x.strip() for x in run_git(["diff","--name-only"]).splitlines() if x.strip())
        paths.update(x.strip() for x in run_git(["diff","--cached","--name-only"]).splitlines() if x.strip())
        for line in run_git(["status","--porcelain"]).splitlines():
            if line.startswith("??"):
                paths.add(line[3:].strip())
        if not paths:
            try:
                paths.update(x.strip() for x in run_git(["diff","--name-only","HEAD~1","HEAD"]).splitlines() if x.strip())
            except RuntimeError:
                pass
    return sorted(paths)

def print_module_inventory(modules):
    print("\n"+"="*80)
    print("DISCOVERED OSGi MODULES")
    print("="*80)
    for node in sorted(modules,key=lambda n:module_key(n,modules)):
        info=modules[node]
        print(f"\n[{info['kind'].upper()}] {module_label(node,modules)}")
        print("  path: "+info["path"].relative_to(ROOT).as_posix())
        if info["kind"]=="bundle":
            print("  exports: "+(", ".join(info["exports"]) or "(none)"))
            print("  imports: "+(", ".join(info["imports"]) or "(none)"))
            print("  require-bundle: "+(", ".join(info["requires"]) or "(none)"))
        else:
            print("  plugins: "+(", ".join(info["plugins"]) or "(none)"))
            print("  required features: "+(", ".join(info["feature_requires"]) or "(none)"))

def print_osgi_graph(graph,modules,selected=None,title="OSGi DEPENDENCY GRAPH"):
    nodes=set(selected if selected is not None else graph.keys())
    print("\n"+"="*80)
    print(title)
    print("="*80)
    print("Direction: DEPENDENCY -> DEPENDENT")
    for node in sorted(nodes,key=lambda n:module_key(n,modules)):
        deps=sorted(graph.get(node,set())&nodes,key=lambda n:module_key(n,modules))
        if deps:
            for dependency in deps:
                print(f"  {module_label(dependency,modules)} -> {module_label(node,modules)}")
        else:
            print(f"  {module_label(node,modules)} -> (none)")

def get_dependency_paths(changed,graph,modules):
    reverse=reverse_graph(graph)
    result={}
    for start in sorted(changed,key=lambda n:module_key(n,modules)):
        paths=[]
        def walk(node,path):
            dependents=sorted(reverse.get(node,set()),key=lambda n:module_key(n,modules))
            if not dependents:
                if len(path)>1:
                    paths.append(path)
                return
            for dependent in dependents:
                if dependent not in path:
                    walk(dependent,path+[dependent])
        walk(start,[start])
        result[start]=paths
    return result

def print_dependency_paths(changed,graph,modules):
    print("\n"+"="*80)
    print("OSGi DEPENDENCY PATHS FROM CHANGED MODULES")
    print("="*80)
    for start in sorted(changed,key=lambda n:module_key(n,modules)):
        print(f"\n[{module_label(start,modules)}]")
        paths=get_dependency_paths(changed,graph,modules).get(start,[])
        if paths:
            for path in paths:
                print("  "+" -> ".join(module_label(x,modules) for x in path))
        else:
            print("  No dependent OSGi modules")

def print_changed_files(files):
    print("\n"+"="*80)
    print("DETECTED CHANGED FILES")
    print("="*80)
    if files:
        for path in files:
            print(f"  - {path}")
    else:
        print("  No changed files detected.")

def find_module_for_path(path,modules):
    normalized=path.replace("\\","/").lstrip("./")
    candidates=[]
    for node,info in modules.items():
        relative=info["path"].relative_to(ROOT).as_posix()
        if normalized==relative or normalized.startswith(relative+"/"):
            candidates.append((len(relative),node))
    return max(candidates)[1] if candidates else None

def changed_modules(changed_files,modules):
    changed=set()
    full_build=False
    for raw in changed_files:
        normalized=raw.replace("\\","/").lstrip("./")
        if normalized=="pom.xml":
            full_build=True
            continue
        if normalized in {"README.md","buildapp.py"} or normalized.startswith(".github/"):
            continue
        node=find_module_for_path(normalized,modules)
        if node:
            changed.add(node)
            continue
        matched=False
        for product in PRODUCTS:
            product_path=f"{product}/"
            if normalized.startswith(product_path):
                matched=True
                for module,info in modules.items():
                    if info["product"]==product:
                        changed.add(module)
                break
        if not matched and normalized:
            full_build=True
    return changed,full_build

def select_dependents(changed,graph,modules):
    reverse=reverse_graph(graph)
    selected=set(changed)
    queue=deque(sorted(changed,key=lambda n:module_key(n,modules)))
    while queue:
        current=queue.popleft()
        for dependent in sorted(reverse.get(current,set()),key=lambda n:module_key(n,modules)):
            if dependent not in selected:
                selected.add(dependent)
                queue.append(dependent)
    return selected

def print_build_order(order,modules):
    print("\n"+"="*80)
    print("OSGi BUILD ORDER")
    print("="*80)
    for index,node in enumerate(order,1):
        info=modules[node]
        print(f"  {index:02d}. [{info['kind'].upper():7}] {module_label(node,modules)}")
    print(f"\nTotal OSGi modules selected: {len(order)}")

def build_modules(order,modules):
    print("\n"+"="*80)
    print("EXECUTING OSGi BUILD")
    print("="*80)
    if subprocess.run(["mvn","-version"],cwd=ROOT).returncode!=0:
        print("ERROR: Maven is not available on PATH.")
        return False
    for index,node in enumerate(order,1):
        info=modules[node]
        relative=info["path"].relative_to(ROOT).as_posix()
        pom=info["path"]/"pom.xml"
        print("\n"+"-"*80)
        print(f"BUILD [{index}/{len(order)}]: {module_label(node,modules)}")
        print("-"*80)
        if not pom.exists():
            print(f"ERROR: POM not found: {pom}")
            return False
        command=["mvn","-B","-f",f"{relative}/pom.xml","clean","install","-DskipTests"]
        print("$ "+" ".join(command))
        result=subprocess.run(command,cwd=ROOT,text=True)
        print(f"Maven exit code: {result.returncode}")
        if result.returncode!=0:
            print(f"ERROR: OSGi module build failed: {node}")
            return False
        targets=list(info["path"].rglob("target"))
        if targets:
            for target in targets:
                print("Target: "+target.relative_to(ROOT).as_posix())
        else:
            print("WARNING: Maven succeeded but no target directory was found.")
    print("\nOSGi BUILD COMPLETED SUCCESSFULLY")
    return True

def collect_build_artifacts():
    artifacts=[]
    extensions={".jar",".zip",".war",".ear"}
    for artifact in ROOT.rglob("*"):
        if not artifact.is_file() or artifact.suffix.lower() not in extensions:
            continue
        relative=artifact.relative_to(ROOT).as_posix()
        if relative.startswith(".git/") or "target" not in artifact.parts:
            continue
        artifacts.append((relative,artifact.stat().st_size))
    return sorted(set(artifacts))

def safe_mermaid_id(node):
    return re.sub(r"[^A-Za-z0-9_]","_",node)

def write_mermaid_graph(file,graph,modules,changed,selected):
    file.write("```mermaid\nflowchart TD\n")
    for node in sorted(graph,key=lambda n:module_key(n,modules)):
        info=modules[node]
        if node in changed:
            label=f"{node}<br/>{info['kind'].upper()}<br/>CHANGED"
        elif node in selected:
            label=f"{node}<br/>{info['kind'].upper()}<br/>REBUILD"
        else:
            label=f"{node}<br/>{info['kind'].upper()}"
        file.write(f'    {safe_mermaid_id(node)}["{label}"]\n')
    for node in sorted(graph,key=lambda n:module_key(n,modules)):
        for dependency in sorted(graph.get(node,set()),key=lambda n:module_key(n,modules)):
            file.write(f"    {safe_mermaid_id(dependency)} --> {safe_mermaid_id(node)}\n")
    file.write("```\n\n")

def write_github_summary(mode,changed,selected,order,graph,modules,status):
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with open(summary,"a",encoding="utf-8") as f:
        f.write("# Northwind OMS Smart OSGi Build\n\n")
        f.write(f"**Status:** {status}\n\n")
        f.write(f"**Build Mode:** `{mode}`\n\n")
        f.write("**Dependency source:** OSGi `MANIFEST.MF` and `feature.xml`\n\n")
        f.write("## Discovered OSGi Modules\n\n")
        f.write("| Product | Type | OSGi Module | Path |\n|---|---|---|---|\n")
        for node in sorted(modules,key=lambda n:module_key(n,modules)):
            info=modules[node]
            path=info["path"].relative_to(ROOT).as_posix()
            f.write(f"| `{info['product']}` | `{info['kind']}` | `{node}` | `{path}` |\n")
        f.write("\n## OSGi Dependency Graph\n\n")
        f.write("`A --> B` means B depends on A.\n\n")
        write_mermaid_graph(f,graph,modules,changed,selected)
        if changed:
            f.write("## Changed OSGi Modules\n\n")
            for node in sorted(changed,key=lambda n:module_key(n,modules)):
                f.write(f"- `{module_label(node,modules)}`\n")
            f.write("\n## Dependency Paths\n\n")
            paths=get_dependency_paths(changed,graph,modules)
            for start in sorted(changed,key=lambda n:module_key(n,modules)):
                f.write(f"### `{module_label(start,modules)}`\n\n")
                if paths.get(start):
                    for path in paths[start]:
                        f.write("- "+" -> ".join(f"`{module_label(x,modules)}`" for x in path)+"\n")
                else:
                    f.write("- No dependent OSGi modules\n")
                f.write("\n")
        f.write("## Modules Selected for Rebuild\n\n")
        for node in sorted(selected,key=lambda n:module_key(n,modules)):
            marker="CHANGED" if node in changed else "DEPENDENT"
            f.write(f"- `{module_label(node,modules)}` ({marker})\n")
        f.write("\n## Build Order\n\n")
        for index,node in enumerate(order,1):
            f.write(f"{index}. `{module_label(node,modules)}`\n")
        f.write(f"\n**Total OSGi modules:** {len(order)}\n\n")
        f.write("## Build Artifacts\n\n")
        artifacts=collect_build_artifacts()
        if artifacts:
            f.write("| Artifact | Size |\n|---|---:|\n")
            for artifact,size in artifacts:
                display=f"{size/(1024*1024):.2f} MB" if size>=1024*1024 else f"{size/1024:.1f} KB" if size>=1024 else f"{size} B"
                f.write(f"| `{artifact}` | {display} |\n")
        else:
            f.write("No build artifacts found.\n")

def execute(mode,build,base):
    print("="*80)
    print("NORTHWIND OMS SMART OSGi BUILD PIPELINE")
    print("="*80)
    modules=discover_osgi_modules()
    graph=build_osgi_graph(modules)
    print_module_inventory(modules)
    if mode=="all":
        changed=set()
        selected=set(modules)
        order=topo_sort(graph,modules,selected)
        print_osgi_graph(graph,modules,title="FULL OSGi DEPENDENCY GRAPH")
        print_build_order(order,modules)
        status="DRY RUN"
        if build:
            status="SUCCESS" if build_modules(order,modules) else "FAILED"
        write_github_summary(mode,changed,selected,order,graph,modules,status)
        return 0 if status!="FAILED" else 1
    if not git_available():
        print("ERROR: changed mode requires a Git repository.")
        return 2
    changed_files=git_changed_files(base)
    print_changed_files(changed_files)
    changed,full_build=changed_modules(changed_files,modules)
    if full_build:
        selected=set(modules)
        order=topo_sort(graph,modules,selected)
    elif not changed:
        print("\nNo OSGi module changes detected.")
        write_github_summary(mode,set(),set(),[],graph,modules,"NO CHANGES")
        return 0
    else:
        selected=select_dependents(changed,graph,modules)
        print_dependency_paths(changed,graph,modules)
        order=topo_sort(graph,modules,selected)
    print_osgi_graph(graph,modules,title="COMPLETE OSGi DEPENDENCY GRAPH")
    print_build_order(order,modules)
    status="DRY RUN"
    if build:
        status="SUCCESS" if build_modules(order,modules) else "FAILED"
    write_github_summary(mode,changed,selected,order,graph,modules,status)
    return 0 if status!="FAILED" else 1

def main():
    parser=argparse.ArgumentParser(description="Northwind OMS smart OSGi build pipeline")
    parser.add_argument("--mode",choices=["all","changed"],default="changed")
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--base")
    args=parser.parse_args()
    try:
        return execute(args.mode,args.build,args.base)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1

if __name__=="__main__":
    raise SystemExit(main())