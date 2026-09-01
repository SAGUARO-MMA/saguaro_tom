from django.apps import AppConfig
from django.urls import path, include


class TomTreasuremapConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tom_treasuremap"

    def nav_items(self):
        return []

    def include_url_paths(self):
        return [path('treasuremap/', include(f'{self.name}.urls', namespace='treasuremap'))]
