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
    InferenceEngine,
    Model,
    PropertyInstance,
    Query,
    Rule,
    SubGroupInstance,
)

def parse_value(value_str: str):
    """Parse a value string to its native type (int, float, bool, or str)."""
    value_str = value_str.strip()
    
    # Check for boolean
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    
    # Check for integer
    try:
        if "." not in value_str and "e" not in value_str.lower():
            return int(value_str)
    except ValueError:
        pass
    
    # Check for float
    try:
        return float(value_str)
    except ValueError:
        pass
    
    # Return as string
    return value_str

def evaluate_calculation(expression: str, model: Model, line_no: int):
    """Evaluate a mathematical calculation expression."""
    import math
    
    # Handle EQUIV (modular equivalence)
    if "EQUIV" in expression:
        match = re.match(r"(\w+)\s+EQUIV\s+(\d+)\s+MOD\s+(\w+)", expression)
        if match:
            var1, target, var2 = match.groups()
            
            # Resolve values
            val1 = None
            val2 = None
            
            # Try to find var1 and var2 in instances
            for inst in model.instances:
                if inst.name == var1:
                    # Look for 'value' property by checking register
                    for prop_id in inst.properties:
                        prop = model.register.get(prop_id)
                        if prop and isinstance(prop, PropertyInstance) and prop.key == "value":
                            val1 = int(prop.value) if isinstance(prop.value, (int, str)) else prop.value
                            break
                if inst.name == var2:
                    for prop_id in inst.properties:
                        prop = model.register.get(prop_id)
                        if prop and isinstance(prop, PropertyInstance) and prop.key == "value":
                            val2 = int(prop.value) if isinstance(prop.value, (int, str)) else prop.value
                            break
            
            if val1 is not None and val2 is not None:
                # Check if k % val2 == target (divides check)
                result = (val2 % val1) == int(target)
                return result
            else:
                raise ValueError(f"Line {line_no}: Cannot resolve variables in CALCULATE: {expression} (val1={val1}, val2={val2})")
    
    # Handle arithmetic expressions
    # Replace instance names with their values
    eval_expr = expression
    
    # Replace SQRT function
    eval_expr = eval_expr.replace("SQRT", "math.sqrt")
    
    # Find all variable names and replace with their values
    var_pattern = r'\b([a-zA-Z_]\w*)\b'
    variables = re.findall(var_pattern, eval_expr)
    
    # Build a namespace with variable values
    namespace = {"math": math}
    
    for var_name in variables:
        # Skip if it's already a known function
        if var_name in ["math", "sqrt", "SQRT"]:
            continue
            
        # Try to find variable in instances
        for inst in model.instances:
            if inst.name == var_name:
                # Look for 'value' property
                for prop_id in inst.properties:
                    prop = model.register.get(prop_id)
                    if prop and isinstance(prop, PropertyInstance) and prop.key == "value":
                        namespace[var_name] = prop.value
                        break
                break
    
    try:
        # Evaluate the expression safely
        result = eval(eval_expr, {"__builtins__": {}}, namespace)
        
        # Convert to appropriate type
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result
    except Exception as e:
        raise ValueError(f"Line {line_no}: Cannot evaluate CALCULATE expression '{expression}': {e}")

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
                value_str = " ".join(tokens[eq_idx + 1 : value_end])
                value = parse_value(value_str)  # Parse to native type
                inst = resolve_instance(inst_name, line_no)
                prop = PropertyInstance(key=key, value=value, instance=inst)
                if subgroup_name:
                    subgroup = subgroups.get((inst.id, subgroup_name))
                    if subgroup is None:
                        raise ValueError(f"Line {line_no}: Unknown subgroup '{subgroup_name}' for '{inst_name}'")
                    subgroup.link(prop)
                continue

            if keyword == "CALCULATE":
                # CALCULATE instance_name key = EXPRESSION
                if "=" not in tokens:
                    raise ValueError(f"Line {line_no}: CALCULATE requires '='")
                eq_idx = tokens.index("=")
                inst_name = tokens[1]
                key = " ".join(tokens[2:eq_idx])
                expression = " ".join(tokens[eq_idx + 1:])
                
                inst = resolve_instance(inst_name, line_no)
                calculated_value = evaluate_calculation(expression, model, line_no)
                prop = PropertyInstance(key=key, value=calculated_value, instance=inst, calculated=True)
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

            if keyword == "RULE":
                if len(tokens) < 2:
                    raise ValueError(f"Line {line_no}: RULE requires a name")
                rule_name = tokens[1]
                condition_str = ""
                consequence_str = ""
                axiom = True
                if "IF" in tokens and "THEN" in tokens:
                    if_idx = tokens.index("IF")
                    then_idx = tokens.index("THEN")
                    condition_str = " ".join(tokens[if_idx + 1 : then_idx])
                    then_end = len(tokens)
                    if "AXIOM" in tokens:
                        axiom_idx = tokens.index("AXIOM")
                        then_end = axiom_idx
                        axiom = tokens[axiom_idx + 1].lower() == "true"
                    consequence_str = " ".join(tokens[then_idx + 1 : then_end])

                def make_condition(cond_str: str):
                    def condition_func(obj):
                        if isinstance(obj, InstanceObject):
                            if "IN" in cond_str and "Domain" in cond_str:
                                parts = cond_str.split(" IN Domain ")
                                domain_name = parts[1].strip()
                                return any(
                                    d.name == domain_name for d in obj.env.domains if obj in d.instances
                                )
                        return False

                    return condition_func

                def make_consequence(cons_str: str):
                    def consequence_func(obj):
                        pass

                    return consequence_func

                rule = Rule(
                    name=rule_name,
                    condition=make_condition(condition_str),
                    consequence=make_consequence(consequence_str),
                    axiom=axiom,
                )
                model.rules.append(rule)
                model.inference_engine.add_rule(rule)
                continue

            if keyword == "QUERY":
                if len(tokens) < 2:
                    raise ValueError(f"Line {line_no}: QUERY requires a name")
                query_name = tokens[1]
                query_desc = " ".join(tokens[2:])
                query = Query(query_desc)

                if "Domain" in query_desc:
                    parts = query_desc.split(" IN Domain ")
                    if len(parts) == 2:
                        domain_name = parts[1].strip()
                        for dom in model.domains:
                            if dom.name == domain_name:
                                query.results.extend(dom.instances)
                elif "ENV" in query_desc:
                    parts = query_desc.split(" IN ENV ")
                    if len(parts) == 2:
                        env_name = parts[1].strip()
                        for env in model.environments:
                            if env.name == env_name:
                                query.results.extend(
                                    model.register.get(iid) for iid in env.instances
                                )

                model.queries.append(query)
                continue

            if keyword == "PROVE":
                if ":" not in line:
                    raise ValueError(f"Line {line_no}: PROVE requires 'name: statement' format")
                colon_idx = line.index(":")
                proof_name = line[len("PROVE"):colon_idx].strip()
                statement = line[colon_idx + 1:].strip()
                
                # Store proof request in model
                if not hasattr(model, "proofs"):
                    model.proofs = []
                model.proofs.append({"name": proof_name, "statement": statement})
                continue

            if keyword == "ASSERT":
                if ":" not in line:
                    raise ValueError(f"Line {line_no}: ASSERT requires 'name: statement' format")
                colon_idx = line.index(":")
                assertion_name = line[len("ASSERT"):colon_idx].strip()
                statement = line[colon_idx + 1:].strip()
                
                # Store assertion in model
                if not hasattr(model, "assertions"):
                    model.assertions = []
                model.assertions.append({"name": assertion_name, "statement": statement})
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


def show_inference(result):
    """Run inference engine if model has rules."""
    if isinstance(result, Model) and result.rules:
        print("\n=== INFERENCE ENGINE ===")
        inference_results = result.inference_engine.infer()
        
        total = len(inference_results['triggered_rules'])
        iterations = inference_results.get('iterations', 0)
        
        print(f"Completed in {iterations} iteration(s)")
        print(f"Total rules triggered: {total}")
        
        if "warning" in inference_results:
            print(f"⚠ {inference_results['warning']}")
        
        # Show unique rule applications
        if total > 0:
            rule_summary = {}
            for triggered in inference_results["triggered_rules"]:
                rule_name = triggered['rule']
                rule_summary[rule_name] = rule_summary.get(rule_name, 0) + 1
            
            print("\nRule summary:")
            for rule_name, count in rule_summary.items():
                print(f"  '{rule_name}' applied {count} time(s)")
        else:
            print("  (no rules triggered)")


def show_queries(result):
    """Show query results."""
    if isinstance(result, Model) and result.queries:
        print("\n=== QUERY RESULTS ===")
        for query in result.queries:
            print(f"Query: {query.description}")
            if query.results:
                for obj in query.results:
                    print(f"  - {obj.name}")
            else:
                print("  (no results)")


def show_proofs(result):
    """Execute and show proof results using Z3."""
    if isinstance(result, Model) and hasattr(result, "proofs"):
        from z3_integration import Z3ModelBuilder
        
        print("\n=== MATHEMATICAL PROOFS (Z3) ===")
        z3_builder = Z3ModelBuilder(result)
        z3_builder.build()
        
        for proof in result.proofs:
            name = proof["name"]
            statement = proof["statement"]
            print(f"\nProof: {name}")
            print(f"Statement: {statement}")
            
            if "INHERITS" in statement:
                parts = statement.split(" INHERITS ")
                if len(parts) == 2:
                    child = parts[0].strip()
                    ancestor = parts[1].strip()
                    result_proof = z3_builder.prove_transitive_inheritance(child, ancestor)
                    if result_proof["valid"]:
                        print(f"✓ PROVEN: {result_proof['proof']}")
                    else:
                        print(f"✗ FAILED: {result_proof['reason']}")
            
            elif "ARE_DISJOINT" in statement:
                parts = statement.split(" AND ")
                if len(parts) == 2:
                    dom1 = parts[0].strip()
                    dom2 = parts[1].split(" ARE_DISJOINT")[0].strip()
                    result_proof = z3_builder.prove_disjoint_domains(dom1, dom2)
                    if result_proof["valid"]:
                        print(f"✓ PROVEN: {result_proof['proof']}")
                        print(f"  |{dom1}| = {result_proof['dom1_size']}, |{dom2}| = {result_proof['dom2_size']}")
                    else:
                        print(f"✗ FAILED: {result_proof['reason']}")
            
            elif "HAS_PROPERTY" in statement:
                parts = statement.split(" HAS_PROPERTY ")
                if len(parts) == 2:
                    inst_name = parts[0].strip()
                    prop_part = parts[1].strip()
                    if " = " in prop_part:
                        key, value = prop_part.split(" = ")
                        result_proof = z3_builder.prove_property_propagation(inst_name, key.strip(), value.strip())
                        if result_proof["valid"]:
                            print(f"✓ PROVEN: {result_proof['proof']}")
                            if "chain" in result_proof:
                                print(f"  Inheritance chain: {' → '.join(result_proof['chain'])}")
                        else:
                            print(f"✗ FAILED: {result_proof['reason']}")


def show_assertions(result):
    """Execute and show assertion results."""
    if isinstance(result, Model) and hasattr(result, "assertions"):
        from z3_integration import Z3ModelBuilder
        
        print("\n=== ASSERTIONS (Z3) ===")
        z3_builder = Z3ModelBuilder(result)
        z3_builder.build()
        
        for assertion in result.assertions:
            name = assertion["name"]
            statement = assertion["statement"]
            print(f"\nAssertion: {name}")
            print(f"Statement: {statement}")
            
            if "NO_CYCLES" in statement:
                result_assert = z3_builder.assert_no_cycles()
                if result_assert["valid"]:
                    print(f"✓ VALID: {result_assert['proof']}")
                else:
                    print(f"✗ INVALID: {result_assert['reason']}")


def show_calculations(result):
    """Display all calculated values in a table."""
    if not isinstance(result, Model):
        return
    
    # Collect all calculated properties
    calculated_props = []
    for prop in result.properties:
        if isinstance(prop, PropertyInstance) and prop.calculated:
            calculated_props.append(prop)
    
    if not calculated_props:
        return
    
    print("\n=== CALCULATED VALUES ===")
    
    # Find max widths for table columns
    max_instance = max(len(prop.instance.name) for prop in calculated_props)
    max_key = max(len(prop.key) for prop in calculated_props)
    max_value = max(len(str(prop.value)) for prop in calculated_props)
    max_type = max(len(type(prop.value).__name__) for prop in calculated_props)
    
    # Ensure minimum widths
    max_instance = max(max_instance, len("Instance"))
    max_key = max(max_key, len("Property"))
    max_value = max(max_value, len("Value"))
    max_type = max(max_type, len("Type"))
    
    # Print header
    header = f"{'Instance':<{max_instance}} | {'Property':<{max_key}} | {'Value':<{max_value}} | {'Type':<{max_type}}"
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)
    
    # Print rows
    for prop in calculated_props:
        instance_name = prop.instance.name
        key = prop.key
        value = str(prop.value)
        value_type = type(prop.value).__name__
        print(f"{instance_name:<{max_instance}} | {key:<{max_key}} | {value:<{max_value}} | {value_type:<{max_type}}")
    
    print(separator)
    print(f"Total calculated values: {len(calculated_props)}")


def main():
    parser = argparse.ArgumentParser(description="Parse and analyze files")
    parser.add_argument("filepath", help="Path to file to parse")
    
    args = parser.parse_args()
    
    result = parse_file(args.filepath)
    if result:
        show_tree(result)
        show_relationships(result)
        show_queries(result)
        show_inference(result)
        show_calculations(result)
        show_proofs(result)
        show_assertions(result)


if __name__ == "__main__":
    main()