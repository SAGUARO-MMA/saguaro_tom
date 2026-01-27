from django.apps import AppConfig


class CustomCodeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'custom_code'

    def target_detail_buttons(self):
        return [
            {'partial': 'custom_code/partials/tns_button.html'},
            {'partial': 'custom_code/partials/mpc_button.html'},
            {'partial': 'custom_code/partials/vet_button.html'},
        ]
