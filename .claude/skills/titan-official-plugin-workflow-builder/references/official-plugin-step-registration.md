# Official Plugin Step Registration

Official plugin steps are made available through `get_steps()` in `plugin.py`.

When adding a new step:

1. place the implementation in the plugin package
2. import it in `plugin.py` or the plugin's existing step aggregation structure
3. expose a stable step name in `get_steps()`
4. use that exposed step name in workflow YAML
