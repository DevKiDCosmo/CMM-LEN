import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Optional

from main import (
    Domain,
    EnvironmentObject,
    InstanceObject,
    Model,
    PropertyInstance,
    SubGroupInstance,
)

def parse_len(filepath):
    """Parse a .len file and build the model."""
    model = Model()
    environments: dict[str, EnvironmentObject] = {}
    instances_by_env_name: dict[str, dict[str, list[InstanceObject]]] = {}
    subgroups: dict[tuple[str, str], SubGroupInstance] = {}
    domains_by_env_name: dict[str, dict[str, Domain]] = {}

    def split_name_index(name: str) -> tuple[str, Optional[int]]:
        match = re.match(r"^(.*)\[(\d+)\]$", name)
        if match:
            return match.group(1), int(match.group(2))
        return name, None

    def resolve_instance(name_ref: str, line_no: int, env_name: Optional[str] = None) -> InstanceObject:
        base_name, idx = split_name_index(name_ref)
        candidates: list[InstanceObject] = []
        if env_name is not None:
            candidates = instances_by_env_name.get(env_name, {}).get(base_name, [])
        else:
            for env_map in instances_by_env_name.values():
                candidates.extend(env_map.get(base_name, []))
        if not candidates:
            suffix = f" in env '{env_name}'" if env_name else ""
            raise ValueError(f"Line {line_no}: Unknown instance '{base_name}'{suffix}")
        if idx is None:
            return candidates[0]
        if idx < 0 or idx >= len(candidates):
            raise ValueError(f"Line {line_no}: Instance index out of range for '{base_name}[{idx}]'")
        return candidates[idx]

    with open(filepath, "r") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            tokens = shlex.split(line)
            if not tokens:
                continue

            keyword = tokens[0].upper()

            if keyword == "MODEL":
                continue

            if keyword == "ENV":
                if len(tokens) < 2:
                    raise ValueError(f"Line {line_no}: ENV requires a name")
                name = " ".join(tokens[1:])
                environments[name] = EnvironmentObject(name=name)
                continue

            if keyword == "DOMAIN":
                if "IN" not in tokens:
                    raise ValueError(f"Line {line_no}: DOMAIN must specify IN <env>")
                in_idx = tokens.index("IN")
                name = " ".join(tokens[1:in_idx])
                env_name = " ".join(tokens[in_idx + 1 :])
                env = environments.get(env_name)
                if env is None:
                    raise ValueError(f"Line {line_no}: Unknown environment '{env_name}'")
                env_domains = domains_by_env_name.setdefault(env_name, {})
                if name in env_domains:
                    raise ValueError(f"Line {line_no}: Duplicate domain '{name}' in env '{env_name}'")
                env_domains[name] = Domain(name=name, env=env)
                continue

            if keyword == "INSTANCE":
                if "IN" not in tokens:
                    raise ValueError(f"Line {line_no}: INSTANCE must specify IN <env>")
                in_idx = tokens.index("IN")
                name = " ".join(tokens[1:in_idx])
                base_name, idx = split_name_index(name)
                if idx is not None:
                    raise ValueError(f"Line {line_no}: INSTANCE name cannot include index")
                env_name = " ".join(tokens[in_idx + 1 :])
                parent = None
                if "PARENT" in tokens:
                    parent_idx = tokens.index("PARENT")
                    env_name = " ".join(tokens[in_idx + 1 : parent_idx])
                    parent_name = " ".join(tokens[parent_idx + 1 :])
                    parent = resolve_instance(parent_name, line_no)
                env = environments.get(env_name)
                if env is None:
                    raise ValueError(f"Line {line_no}: Unknown environment '{env_name}'")
                inst = InstanceObject(name=base_name, env=env, parent=parent)
                env_map = instances_by_env_name.setdefault(env.name, {})
                env_map.setdefault(base_name, []).append(inst)
                continue

            if keyword == "SUBGROUP":
                if len(tokens) < 3:
                    raise ValueError(f"Line {line_no}: SUBGROUP requires instance and name")
                inst_name = tokens[1]
                subgroup_name = " ".join(tokens[2:])
                inst = resolve_instance(inst_name, line_no)
                subgroups[(inst.id, subgroup_name)] = SubGroupInstance(name=subgroup_name)
                continue

            if keyword == "PROPERTY":
                if "=" not in tokens:
                    raise ValueError(f"Line {line_no}: PROPERTY requires '='")
                eq_idx = tokens.index("=")
                inst_name = tokens[1]
                key = " ".join(tokens[2:eq_idx])
                value_end = len(tokens)
                subgroup_name = None
                if "IN" in tokens:
                    in_idx = tokens.index("IN")
                    value_end = in_idx
                    if tokens[in_idx + 1].upper() != "SUBGROUP":
                        raise ValueError(f"Line {line_no}: PROPERTY IN must be SUBGROUP")
                    subgroup_name = " ".join(tokens[in_idx + 2 :])
                value = " ".join(tokens[eq_idx + 1 : value_end])
                inst = resolve_instance(inst_name, line_no)
                prop = PropertyInstance(key=key, value=value, instance=inst)
                if subgroup_name:
                    subgroup = subgroups.get((inst.id, subgroup_name))
                    if subgroup is None:
                        raise ValueError(f"Line {line_no}: Unknown subgroup '{subgroup_name}' for '{inst_name}'")
                    subgroup.link(prop)
                continue

            if keyword == "RELATE":
                if len(tokens) < 3:
                    raise ValueError(f"Line {line_no}: RELATE requires two instances")
                env_name = None
                if "IN" in tokens:
                    in_idx = tokens.index("IN")
                    env_name = " ".join(tokens[in_idx + 1 :])
                if env_name is not None:
                    env = environments.get(env_name)
                    if env is None:
                        raise ValueError(f"Line {line_no}: Unknown environment '{env_name}'")

                    def resolve_domain(name_ref: str) -> Domain:
                        env_domains = domains_by_env_name.setdefault(env_name, {})
                        dom = env_domains.get(name_ref)
                        if dom is None:
                            dom = Domain(name=name_ref, env=env)
                            env_domains[name_ref] = dom
                        return dom

                    def resolve_target(name_ref: str):
                        try:
                            return resolve_instance(name_ref, line_no, env_name)
                        except ValueError:
                            base_name, idx = split_name_index(name_ref)
                            if idx is not None:
                                raise ValueError(
                                    f"Line {line_no}: Cannot resolve indexed domain '{name_ref}'"
                                )
                            return resolve_domain(base_name)

                    left = resolve_target(tokens[1])
                    right = resolve_target(tokens[2])
                else:
                    left = resolve_instance(tokens[1], line_no, env_name)
                    right = resolve_instance(tokens[2], line_no, env_name)

                if isinstance(left, Domain) and isinstance(right, Domain):
                    raise ValueError(f"Line {line_no}: Domain-to-domain relation is not supported")
                if isinstance(left, Domain) and isinstance(right, InstanceObject):
                    left.link(right)
                elif isinstance(right, Domain) and isinstance(left, InstanceObject):
                    right.link(left)
                else:
                    left.relationship_to(right)
                continue

            if keyword == "MODELRELATE":
                if len(tokens) < 3:
                    raise ValueError(f"Line {line_no}: MODELRELATE requires two instances")
                if "IN" in tokens:
                    in_indices = [i for i, t in enumerate(tokens) if t == "IN"]
                    if len(in_indices) != 2 or len(tokens) < 6:
                        raise ValueError(
                            f"Line {line_no}: MODELRELATE expects '<inst> IN <env> <inst> IN <env>'"
                        )
                    left_name = " ".join(tokens[1:in_indices[0]])
                    left_env = " ".join(tokens[in_indices[0] + 1 : in_indices[1] - 1])
                    right_name = tokens[in_indices[1] - 1]
                    right_env = " ".join(tokens[in_indices[1] + 1 :])
                    left = resolve_instance(left_name, line_no, left_env)
                    right = resolve_instance(right_name, line_no, right_env)
                else:
                    left = resolve_instance(tokens[1], line_no)
                    right = resolve_instance(tokens[2], line_no)
                model.relate_model(left, right)
                continue

            raise ValueError(f"Line {line_no}: Unknown command '{keyword}'")

    return model


def parse_file(filepath):
    """Parse a file and return tree structure or model."""
    try:
        path = Path(filepath)
        if path.suffix.lower() == ".len":
            return parse_len(filepath)

        with open(filepath, "r") as f:
            content = f.read()

        tree = {
            "name": path.name,
            "path": filepath,
            "size": len(content),
            "lines": len(content.splitlines()),
        }
        return tree
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found")
        return None


def show_tree(result):
    if isinstance(result, Model):
        result.tree()
    else:
        print(json.dumps(result, indent=2))


def show_relationships(result):
    if isinstance(result, Model):
        result.relation()


def main():
    parser = argparse.ArgumentParser(description="Parse and analyze files")
    parser.add_argument("filepath", help="Path to file to parse")
    
    args = parser.parse_args()
    
    result = parse_file(args.filepath)
    if result:
        show_tree(result)
        show_relationships(result)


if __name__ == "__main__":
    main()