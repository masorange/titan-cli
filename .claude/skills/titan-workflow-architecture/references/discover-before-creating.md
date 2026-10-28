# Discover Before Creating

Inspect before inventing. Prefer local evidence over generic assumptions.

## Project (`.titan/`)

1. `.titan/workflows/*.yaml` — workflows to extend or call
2. `.titan/steps/**/*.py` — reusable step names
3. `.titan/operations/`, `.titan/clients/`, `.titan/services/` — domains and integrations
   already present

## Plugin package

1. `plugin.py` and its `get_steps()` / step registry modules
2. workflow files under the package
3. steps, operations, clients, services, models
4. `docs/plugins/<plugin>/` (official plugins): `client-api.md` lists the public client API

## Built-in capabilities

1. official plugin workflows and steps: `docs/plugins/<plugin>/`, generated step references
   in `docs/plugins/generated/`
2. the `ctx.textual` UI API: `ctx-textual-capabilities.md`

## Report

1. workflows worth extending or calling
2. steps worth reusing
3. domains or integrations worth building on
4. registration patterns worth preserving
5. the pieces that really need new code
