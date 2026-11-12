from django.apps import AppConfig


class CustomCodeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'custom_code'

    def ready(self):
        # tom_targets hardcodes '/targets/...' in TargetList.get_absolute_url, which drops
        # FORCE_SCRIPT_NAME (e.g. /saguaro_tom) on the target grouping page links.
        from django.urls import reverse
        from tom_targets.models import TargetList

        def get_absolute_url(self):
            return reverse('targets:list') + f'?targetlist__name={self.id}'

        TargetList.get_absolute_url = get_absolute_url

    def target_detail_buttons(self):
        return [
            {'partial': 'custom_code/partials/tns_button.html'},
            {'partial': 'custom_code/partials/mpc_button.html'},
            {'partial': 'custom_code/partials/vet_button.html'},
        ]
