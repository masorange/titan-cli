# titan-plugin-firebase

Firebase Remote Config for Titan CLI: read a project's template and publish
parameter changes across brands.

## Authentication

Application Default Credentials. Run once:

```bash
gcloud auth application-default login
```

Titan stores no credential of its own — `google.auth` reads the ADC session and
refreshes the token. That also means Firebase attributes every publish to your
own Google account, which is what the Remote Config version history shows.

## Configuration

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
brands = ["yoigo", "masmovil", "lebara"]
project_id_pattern = "mm-firebase-{brand}"

[plugins.firebase.config.brand_project_overrides]
guuk = "mm-guuk-firebase-prod"
```
