# Project vs Plugin Workflow

Project workflow:

1. lives in `.titan/workflows/`
2. uses `plugin: project` for local steps
3. is local to the project

Plugin workflow:

1. lives in the plugin package
2. uses the plugin's registered step names
3. is part of the plugin capability surface
4. must respect plugin registration and package structure
