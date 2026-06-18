from django.apps import AppConfig
from django.urls import path, include


class TomSurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tom_surveys"

    def nav_items(self):
        return [{'partial': f'{self.name}/partials/navbar_surveys.html', 'position': 'left'}]

    def include_url_paths(self):
        return [path('surveys/', include(f'{self.name}.urls', namespace='surveys'))]
