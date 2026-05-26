# Public Plugin Step Registration

Public plugin steps are not discovered via `.titan/steps/**`.

They must be exposed through the plugin package's registration mechanism, typically:

1. `plugin.py -> get_steps()`
2. one or more `step_registry/*.py` files

Any new step must be implemented and then registered explicitly.
