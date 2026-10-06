"""Project catalogue filtering helpers."""

from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.models.view import UIFirebaseProject
from titan_plugin_firebase.operations.project_operations import (
    enrich_projects_with_config,
    filter_projects,
    parse_project_filter,
)


def _project(
    project_id: str,
    display_name: str,
    number: str,
) -> UIFirebaseProject:
    return UIFirebaseProject(
        project_id=project_id,
        display_name=display_name,
        name=f"projects/{project_id}",
        project_number=number,
    )


def test_parse_project_filter_accepts_commas_spaces_and_lists():
    assert parse_project_filter("Prepago, National") == ["prepago", "national"]
    assert parse_project_filter(["Prepago", "National; Prepago"]) == [
        "prepago",
        "national",
    ]
    assert parse_project_filter("") == []


def test_filter_projects_matches_display_name_and_preserves_order():
    projects = [
        _project("mm-firebase-lebara", "- Prepago - Lebara", "111"),
        _project("mm-firebase-yoigo", "- National Telco - Yoigo", "222"),
        _project("mm-firebase-energy", "- Energia - MasOrange", "333"),
    ]

    filtered = filter_projects(projects, "Prepago, National")

    assert [project.project_id for project in filtered] == [
        "mm-firebase-lebara",
        "mm-firebase-yoigo",
    ]


def test_enrich_projects_with_config_recovers_project_set_metadata():
    config = FirebasePluginConfig(
        project_sets={
            "ragnarok_ios": {
                "default_environment": "PRO",
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo",
                        "label": "Yoigo",
                        "brand": "Yoigo",
                        "groups": ["national"],
                    }
                ],
            }
        }
    )

    enriched = enrich_projects_with_config(
        [_project("mm-firebase-yoigo", "Firebase Yoigo", "111")],
        config,
    )

    assert enriched[0].configured_label == "Yoigo"
    assert enriched[0].label == "Yoigo"
    assert enriched[0].brand == "Yoigo"
    assert enriched[0].environment == "pro"
    assert enriched[0].groups == ("national",)


def test_filter_projects_can_match_enriched_metadata():
    config = FirebasePluginConfig(
        project_sets={
            "ragnarok_ios": {
                "default_environment": "live",
                "projects": [
                    {
                        "project_id": "mm-firebase-yoigo",
                        "brand": "Yoigo",
                        "groups": ["national"],
                    }
                ],
            }
        }
    )
    projects = enrich_projects_with_config(
        [
            _project("mm-firebase-yoigo", "Firebase Yoigo", "111"),
            _project("mm-firebase-energy", "Energia", "333"),
        ],
        config,
    )

    assert [project.project_id for project in filter_projects(projects, "live")] == [
        "mm-firebase-yoigo"
    ]
    assert [project.project_id for project in filter_projects(projects, "national")] == [
        "mm-firebase-yoigo"
    ]
