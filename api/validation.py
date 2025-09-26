# api/validation.py
"""
Script validation utilities.

Provides:
- high-level validate_script(...) for the Flask API
- smaller helpers for AST checks (presence of main, banned/usual risky patterns)
"""

import ast
from typing import Tuple, List, Optional

# Tunable limits
MAX_SCRIPT_SIZE = 200 * 1024  # 200 KB
MAX_FUNCTION_DEFS = 100  # arbitrary sanity limit

# Names / attributes we flag as suspicious (static analysis; not foolproof)
DISALLOWED_GLOBAL_NAMES = {
    "eval",
    "exec",       # builtin exec (also handled via AST)
    "compile",
    "importlib",
    "ctypes",
    "ctypes.util",
    # network / process control
    "subprocess",
    "socket",
    "multiprocessing",
    "threading",
    "os.system",
    # dynamic attribute access that may be used for escapes
    "sys.modules",
    "__import__",
}

# Attributes of modules (module.attr) to flag (e.g. os.system)
DISALLOWED_ATTRS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "execv"),
    ("os", "execl"),
    ("sys", "exec_prefix"),  # example suspicious attr usage
}


def _parse_ast(script: str) -> Optional[ast.AST]:
    try:
        return ast.parse(script)
    except Exception:
        return None


def has_main_function(script: str) -> bool:
    """
    Return True iff a top-level function named 'main' is defined.
    """
    tree = _parse_ast(script)
    if tree is None:
        return False

    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for fn in defs:
        if fn.name == "main":
            return True
    return False


def _find_disallowed_usage(script: str) -> List[str]:
    """
    Walk AST and look for usage of disallowed names/attributes/callables.
    Returns a list of human-readable issues (possibly empty).
    """
    issues: List[str] = []
    tree = _parse_ast(script)
    if tree is None:
        issues.append("Script is syntactically invalid Python.")
        return issues

    # Count function defs for sanity
    fn_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    if fn_count > MAX_FUNCTION_DEFS:
        issues.append(f"Too many function definitions ({fn_count} > {MAX_FUNCTION_DEFS}).")

    # Walk
    for node in ast.walk(tree):
        # direct calls to builtins like eval/exec/compile/open
        if isinstance(node, ast.Call):
            # handle simple Name() calls like eval(...)
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in DISALLOWED_GLOBAL_NAMES:
                    issues.append(f"Use of '{name}()' is disallowed for security reasons.")
            # handle attribute calls like os.system(...)
            elif isinstance(node.func, ast.Attribute):
                # e.g. node.func.value.id == "os" and node.func.attr == "system"
                value = node.func.value
                attr = node.func.attr
                if isinstance(value, ast.Name):
                    if (value.id, attr) in DISALLOWED_ATTRS:
                        issues.append(f"Use of '{value.id}.{attr}()' is disallowed for security reasons.")
        # direct import of disallowed modules
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # import x, y as z
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if any(name == d or name.startswith(d + ".") for d in DISALLOWED_GLOBAL_NAMES):
                        issues.append(f"Import of '{name}' is disallowed or flagged as suspicious.")
            else:  # ImportFrom
                module = node.module or ""
                if any(module == d or module.startswith(d + ".") for d in DISALLOWED_GLOBAL_NAMES):
                    issues.append(f"Import-from '{module}' is disallowed or flagged as suspicious.")
        # look for Exec (python2) or Exec nodes are not in py3 AST; skip

        # look for Name nodes referencing suspicious globals even if not called
        if isinstance(node, ast.Name):
            if node.id in {"eval", "exec", "__import__"}:
                issues.append(f"Reference to '{node.id}' is disallowed.")
        # look for attribute access e.g. os.system (without call)
        if isinstance(node, ast.Attribute):
            value = node.value
            if isinstance(value, ast.Name):
                if (value.id, node.attr) in DISALLOWED_ATTRS:
                    issues.append(f"Use of attribute '{value.id}.{node.attr}' is disallowed.")

    # Deduplicate
    uniq = []
    for i in issues:
        if i not in uniq:
            uniq.append(i)
    return uniq


def validate_script(script: str) -> Tuple[bool, Optional[str]]:
    """
    High-level validator used by the API controller.

    Returns (True, None) if valid, otherwise (False, "<error message>").
    """
    if script is None:
        return False, "Missing 'script' field."
    if not isinstance(script, str):
        return False, "'script' must be a string."
    if len(script.strip()) == 0:
        return False, "'script' must be a non-empty string."
    if len(script) > MAX_SCRIPT_SIZE:
        return False, f"Script too large (>{MAX_SCRIPT_SIZE} bytes)."

    if not has_main_function(script):
        return False, "Script must define a top-level function named 'main()'."

    issues = _find_disallowed_usage(script)
    if issues:
        # Return first few issues for clarity
        summary = "; ".join(issues[:5])
        return False, f"Script contains disallowed or suspicious constructs: {summary}"

    return True, None
