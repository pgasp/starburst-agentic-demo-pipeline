#!/usr/bin/env python3
"""
starburst-demo-lineage-gen.py
Generates a data lineage HTML diagram from a demo spec.json + dp.yaml.

Usage:
  python starburst-demo-lineage-gen.py \
    --spec  dataproduct/<Client>/<Entity>/<dp-name>-spec.json \
    --yaml  dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml \
    --output account/<Client>/<dp-name>-lineage.html
"""
import argparse, json, re, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr); sys.exit(1)

# ── CLI ───────────────────────────────────────────────────────────────────────
p = argparse.ArgumentParser()
p.add_argument("--spec",   required=True)
p.add_argument("--yaml",   required=True)
p.add_argument("--output", required=True)
args = p.parse_args()

spec = json.loads(Path(args.spec).read_text())
dp   = yaml.safe_load(Path(args.yaml).read_text())

# ── Extract data ──────────────────────────────────────────────────────────────
dp_name    = spec.get("dp_name", "demo")
client     = spec.get("client", "")
domain     = spec.get("domain", "")
rls_col    = spec.get("rls_column")
sensitive  = spec.get("sensitive_columns", [])

raw_tables = [t["name"] for t in spec.get("tables", [])]
views      = [v["name"] for v in dp.get("views", [])]

catalog = dp.get("metadata", {}).get("catalogName", "data_products")
schema  = dp.get("metadata", {}).get("schemaName", dp_name.replace("-", "_"))

# BIAC prefix
segs   = dp_name.replace("-", "_").split("_")[:3]
prefix = "_".join(segs)

# Determine view→table connections (heuristic: shared substrings)
def tables_for_view(view_name, tables):
    hits = [t for t in tables if any(w in view_name for w in t.split("_") if len(w) > 3)]
    return hits if hits else tables[:1]

connections = {v: tables_for_view(v, raw_tables) for v in views}

# ── Logo (Starburst SVG, base64 inline — embedded, no external dependency) ────
LOGO = "data:image/svg+xml;base64,PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5NjkuNTcgMTU3LjEiPjxkZWZzPjxzdHlsZT4uY2xzLTF7ZmlsbDojZmZmO30uY2xzLTJ7ZmlsbDojMDBhN2I1O308L3N0eWxlPjwvZGVmcz48dGl0bGU+U3RhcmJ1cnN0X0xvZ29fSG9yaXpvbnRhbF9XaGl0ZVRlYWxfUkdCPC90aXRsZT48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0yMjEuNTgsODAuMzFhMjUuODMsMjUuODMsMCwwLDAtNi40OS0zLjUyYy0yLjQtLjktNC43OS0xLjczLTcuMTYtMi41MS0xLjkyLS42NC0zLjc3LTEuMjgtNS41My0xLjkyYTE5LjM5LDE5LjM5LDAsMCwxLTQuNzEtMi40NiwxMS45MywxMS45MywwLDAsMS0zLjMxLTMuNjIsMTAuNDIsMTAuNDIsMCwwLDEtMS4yMi01LjM5LDExLjcxLDExLjcxLDAsMCwxLDEuMy01LjY5LDEyLjA4LDEyLjA4LDAsMCwxLDMuNDItNCwxNC45NCwxNC45NCwwLDAsMSw0LjcyLTIuMzYsMTcuNzQsMTcuNzQsMCwwLDEsNS4xMS0uNzgsMTcuNDUsMTcuNDUsMCwwLDEsOC4zOSwxLjg4LDE2Ljc3LDE2Ljc3LDAsMCwxLDUuNjksNWw1LjQ5LTQuNDNhMjAuMjUsMjAuMjUsMCwwLDAtNy40Mi01Ljg0QTI2LjI1LDI2LjI1LDAsMCwwLDIwOCw0Mi4yMWEyOC44MiwyOC44MiwwLDAsMC03LjYxLDEuMDYsMjEuNTIsMjEuNTIsMCwwLDAtNywzLjM4LDE3Ljg0LDE3Ljg0LDAsMCwwLTUuMjMsNS45LDE3LjI3LDE3LjI3LDAsMCwwLTIsOC40OCwxNy4zNywxNy4zNywwLDAsMCwxLjU5LDcuODEsMTYuNTUsMTYuNTUsMCwwLDAsNC4xOSw1LjM1LDIyLjI0LDIyLjI0LDAsMCwwLDUuODgsMy41MmMyLjE5LjksNC40LDEuNyw2LjY1LDIuNDFzNC4yOCwxLjQxLDYuMjcsMi4xMmEyMi44NSwyMi44NSwwLDAsMSw1LjMsMi42NSwxMi41LDEyLjUsMCwwLDEsMy43MSw0LDEyLjg0LDEyLjg0LDAsMCwxLDAsMTEuNjcsMTMuNjQsMTMuNjQsMCwwLDEtMy41Nyw0LjE0LDE0Ljg5LDE0Ljg5LDAsMCwxLTQuODYsMi41MSwxOC4zMiwxOC4zMiwwLDAsMS01LjMuODIsMTcuNTUsMTcuNTUsMCwwLDEtOS40LTIuNDYsMTguMywxOC4zLDAsMCwxLTYuMjItNi4xMmwtNiw0LjQzYTIzLjQ3LDIzLjQ3LDAsMCwwLDQuMjQsNC40NCwyNC44MSwyNC44MSwwLDAsMCw1LjIxLDMuMTgsMjguMzcsMjguMzcsMCwwLDAsNS44OCwxLjg4LDMxLjE5LDMxLjE5LDAsMCwwLDYuMTcuNjIsMjguOSwyOC45LDAsMCwwLDgtMS4xNSwyMS4wNiwyMS4wNiwwLDAsMCw3LjExLTMuNTcsMTguMTEsMTguMTEsMCwwLDAsNy0xNC45NCwxNi4xOCwxNi4xOCwwLDAsMC02LjU0LTEzLjkzIi8+PHBhdGggY2xhc3M9ImNscy0xIiBkPSJNMjQ5LjA5LDU0LjMzaC02LjU1VjY3LjA2aC05LjM4djUuNDloOS4zNVYxMDAuN2ExMy45MSwxMy45MSwwLDAsMCwxLjExLDYuMDcsOS44OCw5Ljg4LDAsMCwwLDIuODQsMy42Niw5LjcyLDkuNzIsMCwwLDAsMy43NiwxLjg0LDE2LjcyLDE2LjcyLDAsMCwwLDMuODYuNDgsMjMuMzYsMjMuMzYsMCwwLDAsNC4wOS0uMzQsMTkuNjEsMTkuNjEsMCwwLDAsMy42Mi0xbC0uMjktNS42OWExMy43NiwxMy43NiwwLDAsMS0yLjg1LDEuMDYsMTEuMzcsMTEuMzcsMCwwLDEtMi44NC4zOSwxMC4yNSwxMC4yNSwwLDAsMS0yLjctLjM0LDQuNjcsNC42NywwLDAsMS0yLjE3LTEuMjUsNiw2LDAsMCwxLTEuNC0yLjU2LDE1LjE4LDE1LjE4LDAsMCwxLS40OC00LjE0VjcyLjU1aDEyLjczVjY3LjA2aC0xMi43WiIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTMwMi40LDkzYTE2LjY1LDE2LjY1LDAsMCwxLTEsNS42OCwxNC4zMywxNC4zMywwLDAsMS0yLjc5LDQuNzcsMTIuOTMsMTIuOTMsMCwwLDEtNC41MywzLjI4LDE0Ljg3LDE0Ljg3LDAsMCwxLTYuMTcsMS4yMSwxNi44NywxNi44NywwLDAsMS0zLjgxLS40NCwxMC4zNCwxMC4zNCwwLDAsMS0zLjQyLTEuNDQsNy41Myw3LjUzLDAsMCwxLTIuNDYtMi42NSw4LjE3LDguMTcsMCwwLDEtLjkyLTQsNi41Niw2LjU2LDAsMCwxLDIuMTMtNS4xMSwxNCwxNCwwLDAsMSw1LjQ0LTIuOTRBMzYsMzYsMCwwLDEsMjkyLjI5LDkwYzIuNzQtLjIyLDUuNDUtLjM0LDguMTUtLjM0aDEuOTNabTYuMTcsOS4wNlY4Mi4yOWExNy43NCwxNy43NCwwLDAsMC0xLjM1LTcuMjNBMTMuODcsMTMuODcsMCwwLDAsMzAzLjQ2LDcwYTE2LjIsMTYuMiwwLDAsMC01LjU5LTNBMjIuNDEsMjIuNDEsMCwwLDAsMjkxLDY2YTI3LjU1LDI3LjU1LDAsMCwwLTEwLjM2LDEuODMsMjEuNDQsMjEuNDQsMCwwLDAtNy4zNyw0LjYzTDI3Nyw3Ni43NWExOCwxOCwwLDAsMSw1Ljg4LTMuODYsMTkuNCwxOS40LDAsMCwxLDcuNTItMS40NXE1Ljg4LDAsOSwyLjg3YzIuMDgsMS45MSwzLjExLDQuODIsMy4wOSw4LjcxdjEuNDRjLTQuMTEsMC04LjA5LjE0LTExLjkxLjQzYTQxLjM5LDQxLjM5LDAsMCwwLTEwLjE2LDEuOTQsMTUuOTEsMTUuOTEsMCwwLDAtNy4wOSw0LjU0cS0yLjY1LDMtMi42NSw4LjI3YTEyLjgsMTIuOCwwLDAsMCwxLjQ5LDYuMzksMTMuMzMsMTMuMzMsMCwwLDAsMy43Niw0LjI1LDE0Ljc2LDE0Ljc2LDAsMCwwLDUsMi4zNywyMSwyMSwwLDAsMCw1LjM1LjczLDIwLjQ5LDIwLjQ5LDAsMCwwLDkuNC0yLDE5LDE5LDAsMCwwLDctNi41MWguMTlhMzYuMjgsMzYuMjgsMCwwLDAsLjIsMy43NmMuMTIsMS4yOS4yOSwyLjQ4LjQ4LDMuNTdoNS44OGEzNy40OCwzNy40OCwwLDAsMS0uNTgtNC43M2MtLjEzLTEuODYtLjE5LTMuNjYtLjE5LTUuMzkiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0zNDIuMTYsNjUuOWExNS44NywxNS44NywwLDAsMC04LjY4LDIuNDUsMTUuNTgsMTUuNTgsMCwwLDAtNS43OCw2LjQyaC0uMTljMC0xLDAtMi4xOS0uMS0zLjY3cy0uMTYtMi44Mi0uMjktNGgtNi4yNmMuMTMsMS41NC4yMiwzLjI3LjI5LDUuMnMuMDksMy41LjA5LDQuNzJ2MzUuMTloNi41NlY4OS4wOWEyMy45LDIzLjksMCwwLDEsMS4xMS03Ljc0LDE1Ljc5LDE1Ljc5LDAsMCwxLDIuODktNS4yOSwxMC42MiwxMC42MiwwLDAsMSw0LjE5LTMsMTMuMzksMTMuMzksMCwwLDEsNS0xLDE4Ljc1LDE4Ljc1LDAsMCwxLDIuNy4xOSwxNCwxNCwwLDAsMSwxLjkzLjM4bC44Ny02LjI2YTEyLjMsMTIuMywwLDAsMC0yLjA4LS4zOWMtLjY3LS4wNi0xLjQzLS4wOS0yLjI2LS4wOSIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTM5NS43Niw5Ni43YTE2Ljg3LDE2Ljg3LDAsMCwxLTMuMzIsNS43OCwxNS4yOSwxNS4yOSwwLDAsMS01LjM1LDMuODYsMTgsMTgsMCwwLDEtNy4yMywxLjQsMTYuODksMTYuODksMCwwLDEtMTYuMDUtMTAuOTMsMjAuNTEsMjAuNTEsMCwwLDEsMC0xNC4zNiwxNy42OCwxNy42OCwwLDAsMSwzLjYyLTUuNzgsMTYuNjIsMTYuNjIsMCwwLDEsNS40OS0zLjg2LDE4LjMzLDE4LjMzLDAsMCwxLDE0LjE3LDAsMTUuNTIsMTUuNTIsMCwwLDEsNS4zNSwzLjksMTYuOTEsMTYuOTEsMCwwLDEsMy4zMiw1Ljc5LDIyLjE3LDIyLjE3LDAsMCwxLDAsMTQuMTdtMS42OS0yNGEyMS44MywyMS44MywwLDAsMC03LjMzLTVBMjQuMDcsMjQuMDcsMCwwLDAsMzgwLjEyLDY1LjksMjEuMzYsMjEuMzYsMCwwLDAsMzcxLDY4LjE2YTE4LjY4LDE4LjY4LDAsMCwwLTcuNTIsNi42OWgtLjE5VjM5LjI5aC02LjU1djcyLjg4aDYuNTV2LTcuNjJoLjE5YTE4LjU3LDE4LjU3LDAsMCwwLDcuNTIsNi41NiwyMS44OSwyMS44OSwwLDAsMCw5LjU0LDIuMjIsMjQuMjUsMjQuMjUsMCwwLDAsOS42My0xLjc4LDIxLjkzLDIxLjkzLDAsMCwwLDcuMzMtNUEyMi4zMSwyMi4zMSwwLDAsMCw0MDIuMTYsOTlhMjYuNzUsMjYuNzUsMCwwLDAsMC0xOC43LDIyLjQ1LDIyLjQ1LDAsMCwwLTQuNzItNy41MiIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTQ1MC44MiwxMDIuMjRWNjcuMDZoLTYuNTZWOTAuMTlhMjMuNTYsMjMuNTYsMCwwLDEtMS4xNiw3Ljg2LDE2LjE5LDE2LjE5LDAsMCwxLTMuMDgsNS40OSwxMi41LDEyLjUsMCwwLDEtOS40NSw0LjI5LDEzLjQzLDEzLjQzLDAsMCwxLTUuOTMtMS4xNiw5LjQ1LDkuNDUsMCwwLDEtMy43Ni0zLjIyLDEzLjc2LDEzLjc2LDAsMCwxLTItNUEzMi41NSwzMi41NSwwLDAsMSw0MTguMyw5MlY2N2gtNi41NVY5NC43MnEwLDguMzksNC4yOSwxMy41YzIuODUsMy40LDcuMTUsNS4xMSwxMi44Niw1LjExYTE4LjI4LDE4LjI4LDAsMCwwLDkuMTYtMi40NiwxNC44NywxNC44NywwLDAsMCw2LjI3LTYuNDFoLjE5YzAsMSwwLDIuMTguMSwzLjY2cy4xNiwyLjgzLjI5LDRoNi4yNWMtLjEzLTEuNTQtLjIyLTMuMjgtLjI5LTUuMjFzLS4wOS0zLjUtLjA5LTQuNzIiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik00ODMuMzIsNjUuOWExNS45MywxNS45MywwLDAsMC0xNC40Niw4Ljg3aC0uMTljMC0xLDAtMi4xOS0uMS0zLjY3cy0uMTYtMi44Mi0uMjgtNEg0NjJjLjEzLDEuNTQuMjIsMy4yNy4yOSw1LjJzLjA5LDMuNS4wOSw0LjcydjM1LjE5SDQ2OVY4OS4wOWEyMy45LDIzLjksMCwwLDEsMS4xMS03Ljc0QTE2LDE2LDAsMCwxLDQ3Myw3Ni4wNmExMC42MiwxMC42MiwwLDAsMSw0LjE5LTMsMTMuMzksMTMuMzksMCwwLDEsNS0xLDE4LjYyLDE4LjYyLDAsMCwxLDIuNjkuMTksMTQsMTQsMCwwLDEsMS45My4zOGwuODctNi4yNmExMi4xOCwxMi4xOCwwLDAsMC0yLjA3LS4zOWMtLjY4LS4wNi0xLjQ0LS4wOS0yLjI3LS4wOSIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTUxMC4zMiw4Ni4xNGEyNS4xNSwyNS4xNSwwLDAsMS04LjItMi44NCw1LjQ3LDUuNDcsMCwwLDEtMi42LTQuODcsNiw2LDAsMCwxLC44Mi0zLjE4QTYuNjcsNi42NywwLDAsMSw1MDIuNTEsNzNhOS42MSw5LjYxLDAsMCwxLDMuMDgtMS4yNSwxNS41OCwxNS41OCwwLDAsMSwzLjQ3LS4zOSwxMi42MiwxMi42MiwwLDAsMSw2LjcsMS43OSwxMS41NCwxMS41NCwwLDAsMSw0LjQsNC41OGw1LTMuNzZhMTQuNzYsMTQuNzYsMCwwLDAtNi42NS02LDIxLjA3LDIxLjA3LDAsMCwwLTkuMTYtMi4xMiwyMi45MiwyMi45MiwwLDAsMC02LC43N0ExNi4zMywxNi4zMywwLDAsMCw0OTguMTksNjlhMTEuODYsMTEuODYsMCwwLDAtMy42Miw0LDEyLjIsMTIuMiwwLDAsMC0xLjM0LDUuOTMsMTAuMiwxMC4yLDAsMCwwLDEuMjUsNS4zLDExLjUxLDExLjUxLDAsMCwwLDMuMTgsMy41MiwxNC42NCwxNC42NCwwLDAsMCw0LjE5LDIuMTJjMS41MS40OCwyLjk0Ljg4LDQuMjksMS4yMUE0NC4yLDQ0LjIsMCwwLDEsNTE2LDk0LjQxYTUuNzEsNS43MSwwLDAsMSwzLjQyLDUuMzUsNi45NCw2Ljk0LDAsMCwxLTMuMTgsNi4xNyw5LjUxLDkuNTEsMCwwLDEtMy4zNywxLjM1LDIwLjM2LDIwLjM2LDAsMCwxLTQuMDUuMzgsMTQuNzIsMTQuNzIsMCwwLDEtMTIuNTMtN2wtNS4xNSwzLjg5YTE4LjM4LDE4LjM4LDAsMCwwLDcuOTEsNi42NiwyNC40NywyNC40NywwLDAsMCw5LjkzLDIuMTIsMjYuMjcsMjYuMjcsMCwwLDAsNi4xMi0uNzMsMTUuNTYsMTUuNTYsMCwwLDAsNS40NC0yLjQxQTEyLjQyLDEyLjQyLDAsMCwwLDUyNiw5OS4zNWExMC4zOCwxMC4zOCwwLDAsMC0zLjgtOC40NHEtMy44MS0zLjEyLTExLjgxLTQuNzciLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik01NjAuODgsNzIuNTVWNjcuMDZINTQ4LjE2VjU0LjMzSDU0MS42VjY3LjA2aC05LjM1djUuNDloOS4zNVYxMDAuN2ExNC4yMSwxNC4yMSwwLDAsMCwxLjExLDYuMDcsMTAsMTAsMCwwLDAsMi44NSwzLjY3LDkuODcsOS44NywwLDAsMCwzLjc1LDEuODMsMTYuNzIsMTYuNzIsMCwwLDAsMy44Ni40OCwyMy40NywyMy40NywwLDAsMCw0LjEtLjM0LDE5LjcyLDE5LjcyLDAsMCwwLDMuNjEtMWwtLjI4LTUuNjlhMTQuNTksMTQuNTksMCwwLDEtMi44NSwxLjA2LDExLjM3LDExLjM3LDAsMCwxLTIuODQuMzksMTAuMjUsMTAuMjUsMCwwLDEtMi43LS4zNCw0Ljg0LDQuODQsMCwwLDEtMi4xNy0xLjI1LDYsNiwwLDAsMC0xLjQtMi41NiwxNS4xOCwxNS4xOCwwLDAsMC0uNDgtNC4xNFY3Mi41NVoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik0xMDMuMTYsNzIuNDIsODAuNjgsOEg4MC42YTcxLjQyLDcxLjQyLDAsMCwwLTEwLjEyLjgxbDMxLjA2LDY0LjI1Yy41MS0uMjQsMS0uNDUsMS41Ny0uNjQiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik05OC4xNiw3NS4zNCw0Ni4xNiwxN0E3Miw3MiwwLDAsMCwzNywyMy4xNWw1OS45Miw1My40YTE0LDE0LDAsMCwxLDEuMjMtMS4yMSIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTk0LjY1LDgwLDE5LjM5LDQzLjU1YTY5LjMsNjkuMywwLDAsMC00LjgxLDEwLjI5TDk0LDgxLjU1Yy4xOS0uNTMuNC0xLjA2LjY0LTEuNTciLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik05My4xNiw4Ni4zOWMwLS4yOS4wNy0uNTYuMDgtLjg1TDEwLjE2LDgwLjc2QTcwLjI1LDcwLjI1LDAsMCwwLDExLjM2LDkybDgxLjg1LTQuNzJjMC0uMjktLjA4LS41Ni0uMDgtLjg1Ii8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNOTQsOTEuMjYsMjEuMjUsMTE2LjZhNzAuMTQsNzAuMTQsMCwwLDAsNi40OSw4LjU3TDk0LjY1LDkyLjgzYy0uMjQtLjUxLS40NS0xLS42NC0xLjU3Ii8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNOTYuOTMsOTYuMjMsNDcuMDksMTQwLjY1YTcwLjIzLDcwLjIzLDAsMCwwLDksNEw5OC4xNiw5Ny40NEExMy44MiwxMy44MiwwLDAsMSw5Nyw5Ni4yMyIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTEwMS41NCw5OS43Miw3Ny43NCwxNDljMSwwLDEuODkuMTQsMi44Ni4xNCwxLjksMCwzLjc3LS4xNCw1LjY0LS4yOGwxNi45Mi00OC40NmExNC4zNCwxNC4zNCwwLDAsMS0xLjU3LS42NCIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTEwOCwxMDEuMjRjLS4yOSwwLS41Ni0uMDctLjg1LS4wOGwtMi41Miw0My42NmE3MC44LDcwLjgsMCwwLDAsNi41OC0yLjc3bC0yLjM2LTQwLjg5Yy0uMjksMC0uNTYuMDgtLjg1LjA4Ii8+PHBhdGggY2xhc3M9ImNscy0xIiBkPSJNMTE3LjgyLDk3LjQ0bDE5LjkzLDIyLjM2cTEuNTEtMi4xLDIuODgtNC4zMkwxMTksOTYuMjNhMTMuODIsMTMuODIsMCwwLDEtMS4yMSwxLjIxIi8+PHBhdGggY2xhc3M9ImNscy0xIiBkPSJNMTIyLjc1LDg1LjU1YzAsLjI5LjA4LjU2LjA4Ljg1cy0uMDcuNTctLjA4Ljg1bDI3LjU3LDEuNTljLjIzLTEuNjIuNDMtMy4yNi41Ni00LjkxWiIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTExOSw3Ni41NWwyNy4wNi0yNC4xMmMtLjc5LTItMS42OC0zLjk0LTIuNjUtNS44M0wxMTcuODIsNzUuMzRBMTMuODIsMTMuODIsMCwwLDEsMTE5LDc2LjU1Ii8+PHBhdGggY2xhc3M9ImNscy0xIiBkPSJNMTA3LjE2LDcxLjYyYy4yOSwwLC41Ni0uMDguODUtLjA4cy41Ni4wNy44NS4wOGwzLjI0LTU2LjE1YTY4LjQ1LDY4LjQ1LDAsMCwwLTguMzgtMy41M1oiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMTIuODUsMTAwLjM2bDExLjYyLDMzLjM4YzEuNTYtMS4yNCwzLTIuNTYsNC41LTMuOTNMMTE0LjQyLDk5LjcyYTE0LjM0LDE0LjM0LDAsMCwxLTEuNTcuNjQiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMjEuMzEsOTIuODNsMjQuNzQsMTJjLjYtMS41LDEuMTctMywxLjY3LTQuNTZsLTI1Ljc3LTlhMTQuMzQsMTQuMzQsMCwwLDEtLjY0LDEuNTciLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMjIsODEuNTVsMjguODQtMTBjLS4xOC0xLjgzLS40OS0zLjYxLS44MS01LjM5TDEyMS4zMSw4MGExMi43NCwxMi43NCwwLDAsMSwuNjQsMS41OCIvPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0iTTEzNCwzMi41NUE3MS41OSw3MS41OSwwLDAsMCwxMjguNjYsMjdsLTE1LjgxLDQ1LjRjLjUzLjE5LDEuMDYuNCwxLjU3LjY0WiIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTU4Nyw5OS43aC0yLjcxbDEwLjUxLTI0LjNoMi40bDEwLjQ0LDI0LjNoLTIuNzVsLTIuNjgtNi4zOEg1ODkuNjlabTMuNTgtOC42NWgxMC43MUw1OTYsNzguMTRaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNjI4LjQ4LDk2LjFoLjA3Vjc1LjRINjMxVjk5LjdoLTMuMDlMNjEzLjc5LDc4LjhoLS4wN1Y5OS43aC0yLjQ3Vjc1LjRoMy4wOVoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik02MzcuMyw5OS43aC0yLjcxbDEwLjUtMjQuM2gyLjQxbDEwLjQzLDI0LjNoLTIuNzdsLTIuNjgtNi4zOEg2MzkuOTRabTMuNTctOC42NWgxMC43MWwtNS4zNS0xMi45MVoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik02NjQsOTcuNTVINjc1LjN2Mi4ySDY2MS41Vjc1LjRINjY0WiIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTY4Mi4yNSw5OS43aC0yLjQ3Vjg5LjIzbC05LjEtMTMuODNoMy4wOWw3LjMyLDExLjc3LDcuMzgtMTEuNzdoMi44OGwtOS4xLDEzLjgzWiIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTcwNC4zOCw5OS43aC0yLjQ3Vjc3LjU1aC04LjE0Vjc1LjRoMTguNzR2Mi4xNWgtOC4xM1oiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik03MTguNjIsOTkuN2gtMi40NlY3NS40aDIuNDdaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNzQ1LjU0LDk1Ljc1YTEwLjM0LDEwLjM0LDAsMCwxLTEuNDksMS44LDkuODIsOS44MiwwLDAsMS0yLDEuNDUsMTEuMSwxMS4xLDAsMCwxLTIuNTQsMSwxMS42OSwxMS42OSwwLDAsMS0zLC4zNywxMy40MSwxMy40MSwwLDAsMS01LjA4LTEsMTEuOCwxMS44LDAsMCwxLTYuNjQtNi43LDEzLjM2LDEzLjM2LDAsMCwxLS45NS01LjExLDEzLjIsMTMuMiwwLDAsMSwxLTUuMTIsMTIsMTIsMCwwLDEsMi42Ni00LDEyLjEzLDEyLjEzLDAsMCwxLDQtMi42NiwxMywxMywwLDAsMSw1LTEsMTIuMjQsMTIuMjQsMCwwLDEsMi42My4yOCwxMi44OSwxMi44OSwwLDAsMSwyLjQyLjc4LDExLDExLDAsMCwxLDIuMDYsMS4yMiw2Ljg4LDYuODgsMCwwLDEsMS41NCwxLjZsLTIuMDYsMS41MWE2LjE5LDYuMTksMCwwLDAtMS0xLjE3LDYuODIsNi44MiwwLDAsMC0xLjQ5LTEsOSw5LDAsMCwwLTEuODctLjcyLDguODYsOC44NiwwLDAsMC0yLjE4LS4yNywxMCwxMCwwLDAsMC00LjI0Ljg1LDkuNTcsOS41NywwLDAsMC0zLjE4LDIuMzEsMTAuMTEsMTAuMTEsMCwwLDAtMiwzLjM3LDExLjg1LDExLjg1LDAsMCwwLS42OSw0LDExLjYzLDExLjYzLDAsMCwwLC43MSw0LDEwLjM5LDEwLjM5LDAsMCwwLDIsMy4zNyw5LjQzLDkuNDMsMCwwLDAsMy4xNywyLjMxLDEwLjE2LDEwLjE2LDAsMCwwLDQuMjEuODUsOS41Miw5LjUyLDAsMCwwLDQtLjg1LDcuNjgsNy42OCwwLDAsMCwzLjA5LTIuNjdaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNzYxLjU3LDc5LjMxYTYuMDYsNi4wNiwwLDAsMC0yLTEuNzcsNi4yNSw2LjI1LDAsMCwwLTMtLjY3LDYuNTgsNi41OCwwLDAsMC0xLjgyLjI4LDUsNSwwLDAsMC0xLjY4Ljg0LDQuMjgsNC4yOCwwLDAsMC0xLjIyLDEuNDIsNC4yMSw0LjIxLDAsMCwwLS40NywyLDMuNjgsMy42OCwwLDAsMCwuNDUsMS45MkE0LjE2LDQuMTYsMCwwLDAsNzUzLDg0LjYyYTYuNyw2LjcsMCwwLDAsMS42OC44N2MuNjMuMjMsMS4yOC40NiwyLC42OXMxLjY5LjU3LDIuNTUuODlhOS4yNiw5LjI2LDAsMCwxLDIuMzEsMS4yNiw2LDYsMCwwLDEsMS42NywyLDYuMTIsNi4xMiwwLDAsMSwuNjUsMyw2LjcsNi43LDAsMCwxLS42OSwzLjE0LDYuNTQsNi41NCwwLDAsMS0xLjgsMi4xOCw3LjYzLDcuNjMsMCwwLDEtMi41MywxLjI3LDEwLjMyLDEwLjMyLDAsMCwxLTIuODcuNDEsMTAuOCwxMC44LDAsMCwxLTIuMi0uMjIsMTAuMTksMTAuMTksMCwwLDEtMi4wOS0uNjcsOC40NCw4LjQ0LDAsMCwxLTEuODYtMS4xNCw4LDgsMCwwLDEtMS41MS0xLjU3bDIuMTMtMS41OGE2LjcsNi43LDAsMCwwLDIuMjIsMi4xOCw2LjIzLDYuMjMsMCwwLDAsMy4zNC44Nyw2LjM3LDYuMzcsMCwwLDAsMS44OS0uMjksNS4xOCw1LjE4LDAsMCwwLDEuNzMtLjg5LDUsNSwwLDAsMCwxLjI0LTEuNDcsNC42Niw0LjY2LDAsMCwwLDAtNC4xNUE0LjU5LDQuNTksMCwwLDAsNzU5LjU0LDkwYTcuNjksNy42OSwwLDAsMC0xLjg4LS45NGMtLjcxLS4yNi0xLjQ2LS41MS0yLjI0LS43NnMtMS41OS0uNTQtMi4zNi0uODZhOC4xMSw4LjExLDAsMCwxLTIuMS0xLjI1LDYsNiwwLDAsMS0xLjQ5LTEuOTEsNi44OCw2Ljg4LDAsMCwxLC4xNC01LjgsNi4zMyw2LjMzLDAsMCwxLDEuODMtMi4wOSw3LjY1LDcuNjUsMCwwLDEsMi41MS0xLjIsOS45MSw5LjkxLDAsMCwxLDIuNzEtLjM4LDkuMzEsOS4zMSwwLDAsMSw0LjIyLjg4LDcuMjQsNy4yNCwwLDAsMSwyLjY1LDIuMDdaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNzc3LDk5LjdoLTIuNzFsMTAuNS0yNC4zaDIuNDJsMTAuNDMsMjQuM2gtMi43NWwtMi42OC02LjM4SDc3OS41OVptMy41Ny04LjY1aDEwLjcxbC01LjM1LTEyLjkxWiIvPjxwYXRoIGNsYXNzPSJjbHMtMiIgZD0iTTgxOC4zOCw5Ni4xaC4wN1Y3NS40SDgyMVY5OS43aC0zLjA5TDgwMy42OSw3OC44aC0uMDdWOTkuN2gtMi40NlY3NS40aDMuMDlaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNODM0LjM4LDk5LjdIODMxLjlWODkuMjNMODIyLjgxLDc1LjRoMy4wOWw3LjMxLDExLjc3LDcuMzgtMTEuNzdoMi44OGwtOS4wOSwxMy44M1oiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik04NTMuOTEsOTYuM0g4NTRsNi4wOC0yMC45aDNsNi4wOCwyMC45aDBsNS45NC0yMC45aDIuNjFsLTcuMTcsMjQuM2gtMi44OWwtNi4xMS0yMC44N2gtLjA2TDg1NS4zNiw5OS43aC0yLjg4bC03LjE3LTI0LjNoMi42MVoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik04ODEuNDEsNzUuNGgyLjQ3Vjg1Ljk0aDEzLjI4Vjc1LjRoMi40N1Y5OS43aC0yLjQ3Vjg4LjJIODgzLjg4Vjk5LjdoLTIuNDdaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNOTA2LjUyLDk3LjU1aDEzdjIuMkg5MDQuMDVWNzUuNGgxNS4xMXYyLjE1aC0xMi42Vjg1LjloMTEuNzd2Mi4xOUg5MDYuNTJaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNOTI2Ljg0LDk5LjdoLTIuNDdWNzUuNGg3LjE0YTE0Ljc3LDE0Ljc3LDAsMCwxLDMuMzEuMzQsNy40OSw3LjQ5LDAsMCwxLDIuNjUsMS4xMiw1LjMsNS4zLDAsMCwxLDEuNzMsMiw2LjksNi45LDAsMCwxLC42MiwzQTYsNiwwLDAsMSw5MzgsODYuMmE2LjQyLDYuNDIsMCwwLDEtMiwxLjI5LDguNSw4LjUsMCwwLDEtMi40OC42MWw3LjExLDExLjU3aC0zbC03LjExLTExLjM2aC00LjEyWm0wLTEzLjQ5aDQuMzJhOC4yMSw4LjIxLDAsMCwwLDQuNi0xLjA4LDMuNjIsMy42MiwwLDAsMCwxLjYyLTMuMjQsNC4yMiw0LjIyLDAsMCwwLS40NS0yLDMuNjMsMy42MywwLDAsMC0xLjI3LTEuMzQsNS41Nyw1LjU3LDAsMCwwLTEuOTItLjc1LDExLjY0LDExLjY0LDAsMCwwLTIuNS0uMjRoLTQuNFoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Ik05NDYuNCw5Ny41NWgxM3YyLjJIOTQzLjkzVjc1LjRIOTU5djIuMTVIOTQ2LjRWODUuOWgxMS43NnYyLjE5SDk0Ni40WiIvPjwvc3ZnPg=="

# ── Helpers ───────────────────────────────────────────────────────────────────
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def node_html(name, cls="node-table"):
    return f'<div class="{cls}" data-name="{esc(name)}">{esc(name)}</div>'

# Arrow color per view index (cycles)
COLORS = ["#1ED9C0", "#8B8FF7", "#F87B3C", "#4FA8E8", "#F5A623", "#34D399"]

# ── BIAC role cards ────────────────────────────────────────────────────────────
def role_card(title, accent_var, icon, grants_html):
    return f"""
    <div class="role-card" style="border-color: var({accent_var})">
      <div class="role-header" style="color: var({accent_var})">{icon} {esc(title)}</div>
      <div class="role-body">{grants_html}</div>
    </div>"""

sup_grants = f"""
  <div class="grant">SELECT → toutes vues ({len(views)})</div>
  <div class="grant">Aucun filtre (vision globale)</div>
  <div class="grant text-dim">Assigné : starburst_service</div>"""

usr_grants = f"""
  <div class="grant">SELECT → toutes vues ({len(views)})</div>
  {'<div class="grant rls-tag">RLS : ' + esc(rls_col) + ' = current_user</div>' if rls_col else ''}
  {'<div class="grant cls-tag">CLS : ' + str(len(sensitive)) + ' colonne(s) masquée(s)</div>' if sensitive else ''}
  <div class="grant text-dim">Assigné : {esc(spec.get("client","demo").lower().replace(" ","."))}@...</div>"""

ing_grants = f"""
  <div class="grant">SELECT → toutes vues DP ({len(views)})</div>
  <div class="grant">SELECT → iceberg (raw, allEntities)</div>
  <div class="grant">SELECT → data_products (allEntities)</div>
  <div class="grant text-dim">Assigné : demo user</div>"""

role_cards_html = (
    role_card(f"{prefix}_superuser", "--teal", "●", sup_grants) +
    role_card(f"{prefix}_user", "--amber", "◐", usr_grants) +
    role_card(f"{prefix}_data_ing", "--blue", "◈", ing_grants)
)

# ── Raw table nodes HTML ───────────────────────────────────────────────────────
raw_nodes_html = "\n".join(node_html(t, "node-table") for t in raw_tables)
view_nodes_html = "\n".join(node_html(v, "node-view") for v in views)

# ── Arrow JS ──────────────────────────────────────────────────────────────────
# Build list of (raw_table_name, view_name, color)
arrow_defs = []
for i, v in enumerate(views):
    color = COLORS[i % len(COLORS)]
    tables_used = connections[v]
    for t in tables_used:
        arrow_defs.append({"from": t, "to": v, "color": color})

arrows_json = json.dumps(arrow_defs)

# ── HTML ───────────────────────────────────────────────────────────────────────
html = f"""<title>{esc(dp_name)} · Data Lineage</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:        #070B17; --surface:   #0D1424; --surface-2: #131D33;
  --border:    #1B2840; --border-dim:#111928;
  --text-hi:   #D9E4F5; --text-mid:  #667EA8; --text-lo:   #2E4165;
  --teal:      #1ED9C0; --teal-dim:  #071A1A; --teal-border:#0F3030;
  --amber:     #F5A623; --amber-dim: #170F02; --amber-border:#382408;
  --purple:    #8B8FF7; --blue:      #4FA8E8; --green:     #34D399; --orange:#F87B3C;
  --mono: 'Menlo','Consolas','Courier New',monospace;
  --sans: system-ui,-apple-system,'Segoe UI',Helvetica,sans-serif;
  --r: 5px;
}}
body {{ background:var(--bg); color:var(--text-hi); font-family:var(--sans);
        font-size:13px; line-height:1.55; padding:36px 40px 48px; min-height:100vh; }}
.page-layout {{ display:flex; gap:40px; align-items:flex-start; max-width:1080px; margin:0 auto; }}
.col-left {{ flex:1; min-width:0; }}
.col-right {{ width:300px; flex-shrink:0; }}

/* eyebrow + title */
.eyebrow {{ font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--text-mid); margin-bottom:4px; }}
.dp-title {{ font-size:22px; font-weight:700; color:var(--text-hi); margin-bottom:4px; }}
.dp-sub   {{ font-size:12px; color:var(--text-mid); margin-bottom:24px; }}

/* layers */
.layer-label {{ font-size:10px; letter-spacing:.1em; text-transform:uppercase;
                color:var(--text-lo); margin-bottom:8px; padding-left:4px; }}

/* diagram wrap */
.diagram-wrap {{ position:relative; }}
.nodes-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:4px; }}
.connector-row {{ height:60px; position:relative; margin-bottom:4px; }}
.connector-row svg {{ position:absolute; inset:0; overflow:visible; width:100%; height:100%; }}

/* nodes */
.node-table, .node-view {{
  font-family:var(--mono); font-size:11px; padding:6px 10px; border-radius:var(--r);
  border:1px solid; white-space:nowrap; cursor:default;
}}
.node-table {{ background:var(--surface); border-color:var(--border); color:var(--text-mid); }}
.node-view  {{ background:var(--teal-dim); border-color:var(--teal-border); color:var(--teal); }}

/* legend */
.legend {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:16px; }}
.legend-item {{ display:flex; align-items:center; gap:6px; font-size:11px; color:var(--text-mid); }}
.legend-dot {{ width:8px; height:8px; border-radius:50%; }}

/* right panel */
.panel-title {{ font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--text-mid);
                margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
.role-card {{ border:1px solid; border-radius:var(--r); padding:12px; margin-bottom:10px;
              background:var(--surface); }}
.role-header {{ font-family:var(--mono); font-size:11px; font-weight:700; margin-bottom:8px; }}
.role-body {{ font-size:11px; }}
.grant {{ padding:2px 0; color:var(--text-mid); }}
.rls-tag {{ color:#7DDFB6; }}
.cls-tag {{ color:var(--amber); }}
.text-dim {{ color:var(--text-lo); }}

/* stats bar */
.stats-bar {{ display:flex; gap:12px; margin-top:16px; flex-wrap:wrap; }}
.stat {{ text-align:center; }}
.stat-val {{ font-size:18px; font-weight:700; color:var(--teal); font-family:var(--mono); }}
.stat-lbl {{ font-size:10px; color:var(--text-lo); text-transform:uppercase; letter-spacing:.08em; }}

/* logo */
.logo-wrap {{ margin-top:24px; opacity:.5; }}
.logo-wrap img {{ height:18px; }}
</style>

<div class="page-layout">
  <!-- LEFT — lineage diagram -->
  <div class="col-left">
    <div class="eyebrow">{esc(client)} · {esc(domain)}</div>
    <div class="dp-title">{esc(dp_name)}</div>
    <div class="dp-sub">{esc(catalog)}.{esc(schema)}</div>

    <div class="diagram-wrap" id="diag">
      <div class="layer-label">Sources Iceberg (raw)</div>
      <div class="nodes-row" id="raw-row">
        {raw_nodes_html}
      </div>
      <div class="connector-row" id="conn-row">
        <svg id="arrows"></svg>
      </div>
      <div class="layer-label">Vues Data Product</div>
      <div class="nodes-row" id="view-row">
        {view_nodes_html}
      </div>
    </div>

    <div class="legend" id="legend"></div>
  </div>

  <!-- RIGHT — BIAC roles -->
  <div class="col-right">
    <div class="panel-title">Habilitations BIAC</div>
    {role_cards_html}

    <div class="stats-bar">
      <div class="stat">
        <div class="stat-val">{len(raw_tables)}</div>
        <div class="stat-lbl">tables raw</div>
      </div>
      <div class="stat">
        <div class="stat-val">{len(views)}</div>
        <div class="stat-lbl">vues DP</div>
      </div>
      <div class="stat">
        <div class="stat-val">3</div>
        <div class="stat-lbl">rôles BIAC</div>
      </div>
    </div>

    <div class="logo-wrap">
      <img src="{LOGO}" alt="Starburst">
    </div>
  </div>
</div>

<script>
const ARROWS = {arrows_json};
const COLORS = {json.dumps(COLORS)};

function drawArrows() {{
  const svg    = document.getElementById('arrows');
  const diag   = document.getElementById('diag');
  const rawRow = document.getElementById('raw-row');
  const conRow = document.getElementById('conn-row');
  const viewRow= document.getElementById('view-row');
  const diagR  = diag.getBoundingClientRect();

  svg.innerHTML = '';
  svg.setAttribute('viewBox', `0 0 ${{conRow.offsetWidth}} ${{conRow.offsetHeight}}`);

  ARROWS.forEach((a, i) => {{
    const fromEl = rawRow.querySelector(`[data-name="${{a.from}}"]`);
    const toEl   = viewRow.querySelector(`[data-name="${{a.to}}"]`);
    if (!fromEl || !toEl) return;

    const fr = fromEl.getBoundingClientRect();
    const tr = toEl.getBoundingClientRect();
    const cr = conRow.getBoundingClientRect();

    const x1 = fr.left + fr.width / 2 - cr.left;
    const y1 = 0;
    const x2 = tr.left + tr.width / 2 - cr.left;
    const y2 = conRow.offsetHeight;
    const cy = conRow.offsetHeight / 2;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${{x1}},${{y1}} C${{x1}},${{cy}} ${{x2}},${{cy}} ${{x2}},${{y2}}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', a.color);
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('opacity', '0.7');
    svg.appendChild(path);

    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', x2); dot.setAttribute('cy', y2);
    dot.setAttribute('r', 3); dot.setAttribute('fill', a.color);
    svg.appendChild(dot);
  }});
}}

// Build legend from unique view colors
function buildLegend() {{
  const leg = document.getElementById('legend');
  const seen = {{}};
  ARROWS.forEach((a,i) => {{
    if (!seen[a.to]) {{
      seen[a.to] = a.color;
      const item = document.createElement('div');
      item.className = 'legend-item';
      item.innerHTML = `<span class="legend-dot" style="background:${{a.color}}"></span> ${{a.to}}`;
      leg.appendChild(item);
    }}
  }});
}}

window.addEventListener('load', () => {{ drawArrows(); buildLegend(); }});
window.addEventListener('resize', drawArrows);
setTimeout(drawArrows, 80);
</script>
"""

# ── Write output ──────────────────────────────────────────────────────────────
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"✅ Lineage generated: {args.output}")
